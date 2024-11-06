from openai import OpenAI
import asyncio
from typing import TypeAlias
import os

class TeachingAgent:
    def __init__(self, client: OpenAI) -> None:
        self.client = client
        self.vector_store = client.beta.vector_stores.create(name="textbook")
        print(self.vector_store.id)
        
    async def _add_file(self, fp: str, _verbose: bool = True):
        batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=self.vector_store.id,
            files=[open(fp, "rb")],
        )
        
        while not batch.status == "completed":
            if _verbose:
                print(f"Batch upload status: {batch.status}.")
            
            if batch.status == "failed":
                return batch
            
            await asyncio.sleep(1)
        
        return batch
    
    def add_file(self, fp: str, _verbose: bool = True) -> None:
        if not os.path.exists(fp):
            raise FileNotFoundError()
        
        if _verbose:
            print(f"Uploading {fp}...")
            
        batch = asyncio.run(self._add_file(fp, _verbose))
        
        print(self.vector_store.id)
        print(self.vector_store.usage_bytes)
        print(self.vector_store.status)
        print(self.vector_store.file_counts)
        #print(self.vector_store.file_ids)
        print(self.vector_store.metadata)
        
        
        """    def add_file(self, fp: str, _verbose: bool = True) -> None:
        if not os.path.exists(fp):
            raise FileNotFoundError()
        
        file = self.client.files.create(
            file=open(fp, "rb"),
            purpose="batch",
        )
        
        self.files[file.id] = file
            
    def push(self) -> None:
        self.vector_store = self.client.beta.vector_stores.create(
            name="textbook",
            file_ids=list(self.files.keys()),
        )
        
        print(self.vector_store.__dict__)
        """