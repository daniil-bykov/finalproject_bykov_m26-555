import logging
import os


def setup_logging():
    """Настраивает логирование в файл и консоль."""
    os.makedirs("logs", exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("logs/actions.log", encoding="utf-8"),
            logging.StreamHandler(),
        ]
    )