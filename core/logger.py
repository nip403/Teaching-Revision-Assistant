import logging
import os

class Logger:
    def __init__(self, file: str, verbose: bool = True) -> None:
        self.logger = logging.getLogger("BaseLogger")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []
        
        if not os.path.exists(file):
            open(file, "w+").close()
            
        file_handler = logging.FileHandler(file)
        file_handler.setFormatter(
            logging.Formatter("[%(levelname)s] (%(asctime)s): %(message)s")
        )
        self.logger.addHandler(file_handler)
        
        if verbose: # outputs to stdout
            sout_handler = logging.StreamHandler()
            sout_handler.setFormatter(
                logging.Formatter("[%(levelname)s]: %(message)s")
            )
            self.logger.addHandler(sout_handler)
        
    def log(self, message: str, level: str = "INFO") -> None:
        getattr(self.logger, level.lower(), self.logger.info)(message) # overwrites root logger