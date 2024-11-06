from assistants import TeachingAgent
from openai import OpenAI
import tomllib
from pathlib import Path
import sys
import os

def main(client, config) -> None:
    ta = TeachingAgent(client)
    
    ta.add_file(config["local"]["small1"])
    ta.add_file(config["local"]["small2"])
    
    


if __name__ == "__main__":
    with open("config.toml", "rb+") as f:
        config = tomllib.load(f)
        
    secret = config["openai"]["secret"]
    assistant = config["openai"]["assistant_id_1"]
    client = OpenAI(api_key=secret)
    
    main(client, config)