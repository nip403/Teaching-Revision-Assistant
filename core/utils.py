from openai import OpenAI
from dataclasses import dataclass, field
import tomllib
from pathlib import Path

_parent = Path(__file__).resolve().parent.parent

with (_parent / "config.toml").open("rb+") as f:
    cfg = tomllib.load(f)
    default_model = cfg["openai"]["model"]

    with (_parent / cfg["prompts"]["main"]).open("r") as g:
        default_prompt = g.read()

@dataclass(kw_only=True)
class AssistantConfig: 
    prompt: str = default_prompt
    temperature: float = 1.0
    top_p: float = 0.05
    model: str = default_model
    tools: list[dict[str, str]] = field(
        default_factory=lambda: [{"type": "file_search"}]
    )
    
def _validate(config: AssistantConfig | None) -> bool:
    return config is None or ( # thank you chat gpt
        isinstance(config.prompt, str) and config.prompt.strip() and
        isinstance(config.temperature, (int, float)) and 0.0 <= config.temperature <= 2.0 and
        isinstance(config.top_p, (int, float)) and 0.0 <= config.top_p <= 1.0 and
        isinstance(config.model, str) and config.model.strip() and
        isinstance(config.tools, list) and all(
            isinstance(tool, dict) and "type" in tool and isinstance(tool["type"], str)
            for tool in config.tools
        )
    )
    
def quick_delete( # danger! deletes everything in storage
        client: OpenAI, 
        files: bool = True,
        vector_stores: bool = True,
        assistants: bool = True,
        blacklist_file_ids: list[str] = [], 
        blacklist_vector_store_ids: list[str] = [],
        blacklist_assistant_ids: list[str] = [],
    ) -> None: 
    
    if files:
        files = client.files.list()
        file_count = 0
        file_ids = []
        
        for file in files: # some weird stuff going on if deleting when iterating
            if not file.id in blacklist_file_ids:
                file_ids.append(file.id)
                
        for f in file_ids:
            try:
                client.files.delete(f)
                print(f"Deleted file with ID: {f}")
                file_count += 1
            except Exception as e:
                print(f"Failed to delete file [{f}]. Error: {e}.")
            
        print(f"Deleted {file_count} file{'s' if not file_count == 1 else ''}.\n")
        
    if vector_stores:
        stores = client.beta.vector_stores.list()
        store_count = 0
        store_ids = []
        
        for store in stores:
            if not store.id in blacklist_vector_store_ids:
                store_ids.append(store.id)
                
        for s in store_ids:
            try:    
                client.beta.vector_stores.delete(s)
                print(f"Deleted vector store with ID: {s}")
                store_count += 1
            except Exception as e:
                print(f"Failed to delete vector store [{s}]. Error: {e}.")

        print(f"Deleted {store_count} vector store{'s' if not store_count == 1 else ''}.\n")
        
    if assistants:
        assistants = client.beta.assistants.list()
        assistant_count = 0
        assistant_ids = []
        
        for assistant in assistants:
            if not assistant.id in blacklist_assistant_ids:
                assistant_ids.append(assistant.id)
                
        for a in assistant_ids:
            try:    
                client.beta.assistants.delete(a)
                print(f"Deleted assistant with ID: {a}")
                assistant_count += 1
            except Exception as e:
                print(f"Failed to delete assistant [{a}]. Error: {e}.")

        print(f"Deleted {assistant_count} assistant{'s' if not assistant_count == 1 else ''}.\n")
    
if __name__ == "__main__":
    with open("config.toml", "rb+") as f:
        config = tomllib.load(f)
        
    client = OpenAI(api_key=config["openai"]["secret"])
    quick_delete(client)
    
