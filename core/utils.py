from openai import OpenAI
from dataclasses import dataclass, field
import tomllib

with open("config.toml", "rb+") as f:
    cfg = tomllib.load(f)
    default_model = cfg["assistant"]["model"]
    
    with open(cfg["assistant"]["default_prompt_main"], "r") as g:
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
    
    # assistant functions
    
def _validate(config: AssistantConfig | None) -> bool:
    if config is None:
        return True
    
    return True # TODO: validation
    
def quick_delete(client: OpenAI, blacklist_file_ids: list[str] = [], blacklist_vector_store_ids: list[str] = []) -> None: # danger! deletes all files in storage
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
        
    print(f"Deleted {file_count} file{'s' if file_count > 1 else ''}.\n")
        
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

    print(f"Deleted {store_count} vector store{'s' if store_count > 1 else ''}.\n")
