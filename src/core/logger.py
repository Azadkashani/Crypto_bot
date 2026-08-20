import sys
from loguru import logger

def setup_logger():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add("logs/whale_engine_{time:YYYYMMDD}.log", rotation="1 day", retention="7 days", level="DEBUG")
    return logger

logger = setup_logger()
