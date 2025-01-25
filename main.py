from TeachingAgent import TeachingAgent, quick_delete
from openai import OpenAI
import tomllib

def main(client, config) -> None:
    ta = TeachingAgent(client)
    
    ta.add_files(config["local"]["pdf1"])
    ta.add_files(config["local"]["pdf2"])
    
    ta.session()
    ta.close()

if __name__ == "__main__":
    with open("config.toml", "rb+") as f:
        config = tomllib.load(f)
        
    secret = config["openai"]["secret"]
    client = OpenAI(api_key=secret)
    
    main(client, config)

    quick_delete(client)