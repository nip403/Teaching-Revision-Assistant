from openai import OpenAI
import asyncio
import os
import json
from typing import NewType
from .utils import AssistantConfig, _validate, cfg
from .logger import Logger

Assistant = NewType("Assistant", object)
Thread = NewType("Thread", object)

class TeachingAgent:
    def __init__(self, client: OpenAI, config: AssistantConfig | None = None, verbose: bool = True) -> None:
        assert _validate(config), "Invalid Assistant config."
        
        self.logger = Logger(r"..\sessions.log", verbose=verbose)
        self.client = client
        self.ra = RevisionAgent(self.client, self.logger)
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
        
        if config is not None:
            assert type(config) is AssistantConfig, "Invalid config."
            
            with open(cfg["prompts"]["main"], "r") as f:
                self.prompt = f.read()
                
            self.config = config
        else:
            self.config = AssistantConfig()
            self.prompt = self.config.prompt
        
        self.assistant = self.client.beta.assistants.create(
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
        
        self.logger.log("Initialised assistant and vector storage.", "debug")
    
    def add_files(self, *filepaths: str | list[str]) -> None:
        if isinstance(filepaths[0], list):
            filepaths = filepaths[0]
        
        fps = []
        for fp in filepaths:
            if not os.path.exists(fp):
                self.logger.log(f"'{fp}' does not exist. Skipped upload.", "warning")
                continue
            
            fps.append(fp)
        
        self.logger.log(f"Uploading {', '.join(fps)}...")
        batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=self.vector_store.id,
            files=[open(fp, "rb") for fp in fps],
        )
        self.logger.log(f"Batch upload: {batch.status}")
        
    async def session(self) -> None:
        if self.in_session:
            self.logger.log("Attempted call of another session, returning.", "warning")
            return 
        
        self.in_session = True
        
        summary = asyncio.create_task(self.ra.prep_overview()) # attach end condition TODO TODO TODO
        thread = self.client.beta.threads.create()
        
        while True: 
            next_msg = input(r"Next chat (ENTER to return): ")
            
            if not next_msg:
                break
            
            status, resp = TeachingAgent._handle_run_step(self.client, thread, self.assistant, next_msg, self.logger)
            
            if not status:
                continue
            
            self.logger.log(f"Run response: {resp}")
            print(f"TeachingAgent: {resp}\n")
           
        self.in_session = False    
        
    @staticmethod
    def _handle_run_step(client: OpenAI, thread: Thread, assistant: Assistant, prompt: str, logger: Logger | None = None) -> list[bool, str]:
        if logger is None:
            logger = Logger(r"..\sessions.log")
        
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant.id,
            instructions=prompt,
        )
        
        if run.status == "completed":
            logger.log(f"Run prompt=[{prompt if len(prompt) < 10 else prompt[:10]}] completed.")
            return True, client.beta.threads.messages.list(
                thread_id=thread.id,
            ).data[0].content[0].text.value # response
        
        else:
            logger.log(f"Run prompt=[{prompt if len(prompt) < 10 else prompt[:10]}] failed with status: {run.status}.", "warning")
            return False, str()        

    def close(self) -> None:
        self.client.beta.assistants.delete(self.assistant.id)
        self.logger.log("Deleted assistant.")
        self.client.beta.threads.delete(self.thread.id)
        self.logger.log("Ended session. Create a new instance of TeachingAgent() for a new session.")
        
class RevisionAgent:
    def __init__(self, base_assistant: Assistant, client: OpenAI, logger: Logger) -> None:
        self.assistant = base_assistant
        self.client = client
        self.logger = logger
        
    async def _revision_guide(self, topics: dict[str, list[str]]) -> str:
        """
        Generate a revision sheet for the provided content.        
        """
        
        thread = self.client.beta.threads.create()
        
        
        self.client.beta.threads.delete(thread.id)
        
        """
        assistant main (list all topics and subtopics)
        assistant main (generate a concise summary without losing any important info about each topic and subtopic)
        optional: pass through another agent to format response to html or whatever
        """
        
    async def _questions(self, topics: dict[str, list[str]], n: int = 5) -> str:
        """
        Generate a list of n questions which learners may ask about the revision material.      
        """
        
        thread = self.client.beta.threads.create()
        
        
        self.client.beta.threads.delete(thread.id)
        
    
        """
        assistant main 
        """
        
    async def prep_overview(self, n: int = 5) -> list[dict[str, list[str]], str, list[str]]:
        """
        Runs 2 pipelines concurrently:
        
        Builds topic list
        1) Find 3 questions per topic > compile top n questions
        2) Extract bullet points from each subtopic > compile into a revision sheet
        """
        
        log = lambda m, l="info": self.logger.log(f"[GEN_SUMMARY]: {m}", l)
        overview_thread = self.client.beta.threads.create()

        # Step 1: generate list of topics and subtopics in json format 
        # potential TODO: add a quality assurance agent for formatting and faithfulness to content
        
        with open(cfg["prompts"]["topics"], "r") as f:
            topic_prompt = f.read()
        
        status, resp = TeachingAgent._handle_run_step(
            self.client, 
            overview_thread,
            self.assistant, 
            topic_prompt, 
            type(
                "LoggerOverview", 
                (object, ), 
                {"log": log},
            ), # a cool yet horrible use case for metaclasses
        )
        
        self.client.beta.threads.delete(thread_id=overview_thread.id)
        
        try:
            if not resp:
                raise
            
            topics = json.loads(resp)
        except:
            log("Failed to generate topics from dataset.", "warning")
            return dict()
            
        log("Created topic list.")
        
        async with asyncio.TaskGroup() as tg:
            revision = asyncio.create_task(self._revision_guide(topics)) #summary.add_done_callback(func) - for app 
            questions = asyncio.create_task(self._questions(topics, n))
        
        return topics, revision.result(), questions.result()