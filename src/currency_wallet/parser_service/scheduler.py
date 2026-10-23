import logging
import time

from .updater import RatesUpdater


def run_scheduler(interval_seconds=3600):
    """Запускает обновление курсов по таймеру."""
    logging.info(f"Scheduler started. Interval: {interval_seconds} sec.")
    while True:
        try:
            updater = RatesUpdater()
            updater.run_update()
            logging.info("Scheduled update completed.")
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
        time.sleep(interval_seconds)