from openai import OpenAI
import asyncio
from functools import partial
import os
import json
from typing import NewType, Callable, Optional
from .utils import AssistantConfig, _validate, cfg, _parent
from .logger import Logger

Assistant = NewType("Assistant", object)
Thread = NewType("Thread", object)
VectorStore = NewType("Vector Store", object)

class TeachingAgent:
    def __init__(self, client: OpenAI, config: Optional[AssistantConfig] = None, verbosity: dict[str, bool | str] = {"verbose": True, "threshold": "debug"}) -> None:
        assert _validate(config), "Invalid Assistant config."
        assert isinstance(verbosity, dict), "Invalid verbosity set."
        
        self.logger = Logger(_parent / "sessions.log", verbose=verbosity.get("verbose", True), threshold=verbosity.get("threshold", "debug"))
        self.client = client
        self.in_session = False
        self.thread = self.client.beta.threads.create()
        self.vector_store = client.beta.vector_stores.create(
            chunking_strategy={
                "type": "static",
                "static": {
                    "max_chunk_size_tokens": 2048,
                    "chunk_overlap_tokens": 512,
                }
            },
            name="textbook",
        )
        
        if config is not None: # setup config/prompt for assistant
            assert type(config) is AssistantConfig, "Invalid config."
            
            with open(cfg["prompts"]["main"], "r") as f:
                self.prompt = f.read()
                
            self.config = config
        else:
            self.config = AssistantConfig()
            self.prompt = self.config.prompt
        
        self.assistant = self.client.beta.assistants.create( # initialise assistant
            name="Teaching Assistant",
            instructions=self.prompt,
            tools=self.config.tools,
            model=self.config.model,
            tool_resources={
                "file_search": {
                    "vector_store_ids": [self.vector_store.id]
                }
            }
        )
        
        self.ra = RevisionTool(self.assistant, self.client, self.vector_store, self.logger)
        self.logger.log("Initialised assistant and vector storage.", "debug")
    
    def add_files(self, *filepaths: str | list[str], binaries: bool = False) -> None: # single or batch file upload to vector storage
        if isinstance(filepaths[0], list):
            filepaths = filepaths[0]
        
        if not binaries:
            fps = []
            for fp in filepaths:
                if not os.path.exists(fp):
                    self.logger.log(f"'{fp}' does not exist. Skipped upload.", "warning")
                    continue
                
                fps.append(fp)
                
            self.logger.log(f"Uploading {', '.join(fps)}...")
                
        else:
            fps = filepaths[:]
            self.logger.log(f"Uploading file binaries...")
        
        batch = self.client.beta.vector_stores.file_batches.upload_and_poll( # streaming done on their end
            vector_store_id=self.vector_store.id,
            files=[open(fp, "rb") if not binaries else fp for fp in fps],
        )
        self.logger.log(f"Batch upload: {batch.status}")
        
    async def _session(self, num_faq_questions: Optional[int] = 5) -> None:
        summary = asyncio.create_task(self.ra.prep_overview(num_faq_questions)) # concurrently generate revision help - see RevisionTool()
        summary.add_done_callback(lambda fut: print(f"Revision Overview Result: {fut.result()}"))
        thread = self.client.beta.threads.create() # main thread for session
        
        while True: 
            next_msg = input(r"Next chat (ENTER to return): ")
            
            if not next_msg.strip():
                summary.cancel()
                break
            
            status, resp = TeachingAgent._handle_run_step(
                client=self.client, 
                thread=thread, 
                assistant=self.assistant, 
                prompt=next_msg, 
                logger=self.logger,
            )
            
            if not status: # run call failed
                continue
            
            self.logger.log(f"Run response: {resp}")
            print(f"TeachingAgent: {resp}\n")
            
    async def _session_streamlit(self, callback: Callable, num_faq_questions: Optional[int] = 5) -> None:
        self.st_summary = asyncio.create_task(self.ra.prep_overview(num_faq_questions)) # concurrently generate revision help - see RevisionTool()
        self.st_summary.add_done_callback(callback)
        
    def session(self, num_faq_questions: Optional[int] = 5) -> None: # synchronous wrapper
        if self.in_session: # extra protection
            self.logger.log("Attempted call of another session, returning.", "warning")
            return 
        
        self.in_session = True
        asyncio.run(self._session(num_faq_questions))
        self.in_session = False
        
    def session_streamlit(self, callback: Callable) -> None:
        if self.in_session:
            self.logger.log("Attempted call of another session, returning.", "warning")
            return 
        
        self.st_thread = self.client.beta.threads.create() # main thread for session
        
        self.in_session = True
        asyncio.run(self._session_streamlit(callback))
        
    def converse_streamlit(self, prompt: str) -> str:
        assert self.in_session
        
        status, resp = TeachingAgent._handle_run_step(
            client=self.client, 
            thread=self.st_thread, 
            assistant=self.assistant, 
            prompt=prompt, 
            logger=self.logger,
        )
        
        if not status: # run call failed
            return "Failed to generate response."
        
        self.logger.log(f"Run response: {resp}")
        return resp        
        
    @staticmethod
    def _handle_run_step(*, client: OpenAI, thread: Thread, assistant: Assistant, prompt: str, logger: Optional[Logger] = None) -> list[bool, str]:
        if logger is None:
            logger = Logger(_parent / "sessions.log")
        
        run = client.beta.threads.runs.create_and_poll( # send message
            thread_id=thread.id,
            assistant_id=assistant.id,
            instructions=prompt,
        )
        
        if run.status == "completed":
            logger.log(f"Run prompt=[{prompt if len(prompt) < 20 else prompt[:20]+'...'}] completed.", "debug")
            return True, client.beta.threads.messages.list(
                thread_id=thread.id,
            ).data[0].content[0].text.value # return assistant response & run status
        
        else:
            logger.log(f"Run prompt=[{prompt if len(prompt) < 20 else prompt[:20]+'...'}] failed with status: {run.status}.", "warning")
            return False, str()        

    def close(self) -> None: # "end" instance
        self.in_session = False
        
        self.client.beta.assistants.delete(self.assistant.id)
        self.ra.close()
        self.logger.log("Deleted assistants.")
        self.client.beta.threads.delete(self.thread.id)
        self.client.beta.vector_stores.delete(self.vector_store.id)
        
        self.logger.log("Ended session. Create a new instance of TeachingAgent() for a new session.")
        
class RevisionTool:
    def __init__(self, base_assistant: Assistant, client: OpenAI, vector_store: VectorStore, logger: Logger) -> None:
        self.assistant = base_assistant
        self.client = client
        self.vector_store = vector_store

        self.base_logger = logger
        self.log = lambda m, l="info": self.base_logger.log(f"[GEN_SUMMARY]: {m}", l)
        self.logger = type(
            "Logger[Overview]", 
            (object, ), 
            {"log": partial(self.log)}
        )() # a cool yet horrible use case for metaclasses`
        
    async def _revision_guide(self, topics: dict[str, list[str]], log: Callable[[str, str], None]) -> dict[str, dict[str, str]]: # topic: {subtopic: content} 
        """
        Generate a revision sheet for the provided content.        
        """
        
        thread = self.client.beta.threads.create()
        revision_sheet = {}
        
        with open(cfg["prompts"]["summary_gen"], "r") as f:
            p = f.read()
            
        for topic, subtopics in topics.items():
            status, resp = TeachingAgent._handle_run_step(
                client=self.client,
                thread=thread,
                assistant=self.assistant,
                prompt=f"{p}\n\nBelow are the topic and list of subtopics you are to create a revision sheet for:\nTopic: {topic}\n\t{'\n\t- '.join(subtopics)}",
                logger=self.logger,
            )
            
            if not status:
                log(f"Failed to generate revision notes for topic '{topic}'.")
                continue
        
            try:
                revision_sheet[topic] = json.loads(resp)[topic] # {subtopic: content}
                
            except:
                log(f"Topic [{topic}] was returned in an incorrect format: {resp}", "debug")
            
            log(f"Generated revision notes for topic '{topic}'.")
        
        self.client.beta.threads.delete(thread.id)
        
        return revision_sheet
        
    async def _questions(self, topics: dict[str, list[str]], log: Callable[[str, str], None], n: int = 5) -> list[str]:
        """
        Generate a list of n questions which learners may ask about the revision material.      
        """
        
        with open(cfg["prompts"]["gen_questions"], "r") as f:
            self.faq_assistant = self.client.beta.assistants.create(
                name="FAQ Generator",
                instructions=f.read(),
                tools=[{"type": "file_search"}],
                model=cfg["openai"]["model"],
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [self.vector_store.id]
                    }
                }
            )
        
        with open(cfg["prompts"]["pick_questions"], "r") as f:
            self.selector_assistant = self.client.beta.assistants.create( 
                name="FAQ Selector",
                instructions=f.read().replace("[NUM_OF_QUESTIONS]", str(n)),
                tools=[{"type": "file_search"}],
                model=cfg["openai"]["model"],
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [self.vector_store.id]
                    }
                }
            )
            
        log("Initialised question creation assistants.")
        
        thread = self.client.beta.threads.create()
        
        # 1: Generate questions
        status, all_qs = TeachingAgent._handle_run_step(
            client=self.client,
            thread=thread,
            assistant=self.faq_assistant,
            prompt=f"Generate {n} questions each for the following topics: {', '.join(topics.keys())}.",
            logger=self.logger,
        )

        if not status:
            return list()
        
        log("Generated initial questions.")
        
        # 2: Evaluate
        
        with open(cfg["prompts"]["eval_questions"], "r") as f:
            status, feedback = TeachingAgent._handle_run_step(
                client=self.client,
                thread=thread,
                assistant=self.assistant,
                prompt=f"{f.read()}. The questions provided are {all_qs}",
                logger=self.logger,
            )
        
        if not status:
            return list()
        
        log("Evaluated initial questions.")
        
        # 3: Finalise
        
        with open(cfg["prompts"]["pick_questions"], "r") as f:
            status, qs = TeachingAgent._handle_run_step(
                client=self.client,
                thread=thread,
                assistant=self.selector_assistant,
                prompt=f"{f.read()}\n\nQuestions: {all_qs}\n\nFeedback: {feedback}",
                logger=self.logger,
            )
        
        self.client.beta.threads.delete(thread.id)

        try:
            if not status:
                raise
            
            questions = json.loads(qs)["Questions"] # ensure correct format
            log("Successfully generated FAQs.")
            
            return questions # returns a list of questions
            
        except:
            return list()
        
    async def prep_overview(self, num_faq_questions: Optional[int] = 5) -> list[dict[str, list[str]], str, list[str]]:
        """
        Runs 2 pipelines concurrently:
        
        Builds topic list
        1) Find 3 questions per topic > compile top n questions
        2) Extract bullet points from each subtopic > compile into a revision sheet
        """
        
        overview_thread = self.client.beta.threads.create()

        # Step 1: generate list of topics and subtopics in json format 
        # potential TODO: add a quality assurance agent for formatting
        
        with open(cfg["prompts"]["topics"], "r") as f:
            topic_prompt = f.read()
        
        status, resp = TeachingAgent._handle_run_step( # generate list of topics from dataset
            client=self.client, 
            thread=overview_thread,
            assistant=self.assistant, 
            prompt=topic_prompt, 
            logger=self.logger,
        )
        
        self.client.beta.threads.delete(thread_id=overview_thread.id)
        
        try:
            if not status:
                raise
            
            topics = json.loads(resp)
        except:
            self.log("Failed to generate topics from dataset.", "warning")
            return dict(), str(), list()
            
        self.log("Created topic list.")
        
        # Step 2: pass topics into pipelines
        
        revision, questions = await asyncio.gather(
            self._revision_guide(topics, self.log),
            self._questions(topics, self.log, num_faq_questions)
        )

        return topics, revision, questions
    
    def close(self) -> None:
        try:
            self.client.beta.assistants.delete(self.faq_assistant.id)
            self.client.beta.assistants.delete(self.selector_assistant.id)
            
        except:
            self.logger.log("Failed to delete helper assistants (likely from failed or interrupted execution of summary generation).")