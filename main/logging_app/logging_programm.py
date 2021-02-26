import logging
from logging.handlers import TimedRotatingFileHandler
import os
import datetime


class logging_app:
    """
    Логирование для программы.
    """
    def __init__(self, LOG_FILE, FORMATTER=logging.Formatter("%(asctime)s — %(pathname)s— %(name)s — %(levelname)s — %(message)s")):
        self.FORMATTER=FORMATTER
        self.name_user = os.environ.get("USERNAME")
        self.now = datetime.datetime.now()
        self.LOG_FILE = f"{self.name_user}_{self.now.day}-{self.now.month}-{self.now.year}_{self.now.hour}_logo.txt"


    def get_file_handler(self):
        file_handler = TimedRotatingFileHandler(self.LOG_FILE, when='midnight')
        file_handler.setFormatter(self.FORMATTER)
        return file_handler
    
    def get_stream_handler(self):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(self.FORMATTER)
        return stream_handler

    def get_logger(self,logger_name):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self.get_stream_handler())
        logger.addHandler(self.get_file_handler())
        logger.propagate = True
        return logger
