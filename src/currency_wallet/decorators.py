import functools
import logging
from datetime import datetime


def log_action(action_name):
    """Декоратор для логирования операций."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logging.info(f"{datetime.now().isoformat()} {action_name} START")
            try:
                result = func(*args, **kwargs)
                logging.info(f"{datetime.now().isoformat()} {action_name} OK")
                return result
            except Exception as e:
                logging.error(f"{datetime.now().isoformat()} {action_name} ERROR: {e}")
                raise
        return wrapper
    return decorator