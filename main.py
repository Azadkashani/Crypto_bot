from src.core.config import settings
from src.core.logger import logger
from src.storage.database import init_db

def main():
    logger.info(f"Starting Whale Engine in {settings.mode} mode")
    if settings.mode == "live" and not settings.live_trading_enabled:
        logger.warning("Live trading is disabled. Running in research mode only.")
        settings.mode = "research"
    init_db()
    logger.info("Phase 2 skeleton ready. Exiting.")

if __name__ == "__main__":
    main()
