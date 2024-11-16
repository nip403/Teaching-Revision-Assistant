from openai import OpenAI
import asyncio
import tomllib
import os
from .utils import AssistantConfig, _validate

class TeachingAgent:
    def __init__(self, client: OpenAI, config: AssistantConfig | None = None) -> None:
        assert _validate(config), "Invalid Assistant config."
        
        self.client = client
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
            
            with open("config.toml", "rb+") as f:
                prompt_file = tomllib.load(f)["assistant"]["default_prompt"]
                
            with open(prompt_file, "r") as f:
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
        
    async def _add_file(self, fp: str, _verbose: bool = True) -> str:
        batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=self.vector_store.id,
            files=[open(fp, "rb")],
        )
        
        while not batch.status == "completed":
            if _verbose:
                print(f"Batch upload status: {batch.status}.")
            
            if batch.status == "failed":
                return "Failed."
            
            await asyncio.sleep(0.5)
        
        return "Success."
    
    def add_file(self, fp: str, _verbose: bool = True) -> None:
        if not os.path.exists(fp):
            raise FileNotFoundError()
        
        if _verbose:
            print(f"Uploading {fp}...")
            
        out = asyncio.run(self._add_file(fp, _verbose))
        
        if _verbose:
            print(out)
            
            
        """TODO
        3) initialise with creation of notes, present to user
        
        4) initialise conversation with user about topics        
        """
            
    def session(self) -> None:
        self.conversation = []
        thread = self.client.beta.threads.create()
        
        next_msg = input("Next chat: ")
        message = self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=next_msg,
        )
        
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=self.assistant.id,
            instructions=next_msg,
        )
        
        if run.status == "completed":
            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id,
            )
            
            print(messages.value)
            
        else:
            print(run.status)
            
    def _handle_run_step(self) -> str:
        pass

    def close(self) -> None:
        self.client.beta.assistants.delete(self.assistant.id)