import logging
import os
import sys
import io

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
except:
    pass

class Logger:
    def __init__(self, file: str, verbose: bool = True, threshold: str = "debug") -> None:
        self.logger = logging.getLogger("BaseLogger")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []
        
        if not os.path.exists(file):
            open(file, "w+").close()
            
        file_handler = logging.FileHandler(file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("[%(levelname)s] (%(asctime)s): %(message)s")
        )
        self.logger.addHandler(file_handler)
        
        if verbose: # outputs to stdout, threshold determines lowest level that is output
            sout_handler = logging.StreamHandler()
            sout_handler.setLevel(getattr(logging, threshold.upper(), logging.DEBUG))
            sout_handler.setFormatter(
                logging.Formatter("[%(levelname)s]: %(message)s")
            )
            self.logger.addHandler(sout_handler)
        
    def log(self, message: str, level: str = "INFO") -> None:
        getattr(self.logger, level.lower(), self.logger.info)(message.encode("utf-8", errors="replace").decode("utf-8")) # overwrites root logger