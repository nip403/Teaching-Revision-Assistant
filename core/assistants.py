from openai import OpenAI
import asyncio
import tomllib
import os

class TeachingAgent:
    def __init__(self, client: OpenAI, prompt: str) -> None:
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
        
        if not len(prompt):
            with open("config.toml", "rb+") as f:
                prompt_file = tomllib.load(f)["assistant"]["prompt"]
                
            with open("prompt_file")
        
        self.assistant = self.client.beta.assistants.create(
            name="Teaching Assistant",
            instructions=prompt,
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
            
            
        """
        
        Flow: 
        1a) manually setup assistant with prompts
        1b) pull assistant from api
        
        2) setup thread with assistant(s)
        
        3) initialise with creation of notes, present to user
        
        4) initialise conversation with user about topics        
        
        """
            
    def build(self) -> None:
        pass

    def close(self) -> None:
        pass