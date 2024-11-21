import logging
import os

class Logger:
    def __init__(self, file: str, verbose: bool = True) -> None:
        self.verbose = verbose
        
        if not os.path.exists(file):
            with open(file, "w+") as f:
                pass
            
        logging.basicConfig(
            filename=file,
            format="[%(levelname)s] (%(asctime)s): %(message)s",
            force=True,
        )
        
    def log(self, message: str, level: str = "INFO") -> None:
        if self.verbose:
            print(f"[{level.upper()}]: {message}")
            
        """{
            "debug": logging.debug,
            "info": logging.info, 
            "warning": logging.warning,
            "error": logging.error,
            "critical": logging.critical,
            "exception": logging.exception,
        }.get(
            level.lower(), logging.info
        )(message)"""
        
        getattr(logging, level.lower(), logging.info)(message)