import logging
from threading import Event, Thread

from valutatrade_hub.infra.settings import RATES_UPDATER_THREAD_NAME, SettingsLoader

from .updater import RatesUpdater


def _get_interval(interval_seconds=None):
    if interval_seconds is None:
        interval_seconds = SettingsLoader().get("rates_update_interval_seconds")
    if type(interval_seconds) is not int or interval_seconds <= 0:
        raise ValueError("Интервал обновления должен быть положительным целым числом")
    return interval_seconds


def run_scheduler(interval_seconds=None, stop_event=None, *, update_immediately=True):
    """Регулярно обновляет курсы валют, пока программа не запросит остановку."""
    interval_seconds = _get_interval(interval_seconds)
    if stop_event is None:
        stop_event = Event()
    logging.info(f"Scheduler started. Interval: {interval_seconds} sec.")
    if not update_immediately and stop_event.wait(interval_seconds):
        return
    while not stop_event.is_set():
        try:
            updater = RatesUpdater()
            updater.run_update()
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
        if stop_event.wait(interval_seconds):
            break


class RatesScheduler:
    """Управляет автоматическим обновлением курсов после входа пользователя."""

    def __init__(self):
        settings = SettingsLoader()
        self.interval_seconds = _get_interval()
        ttl = settings.get("rates_ttl_seconds")
        if not 0 < self.interval_seconds < ttl:
            raise ValueError("Интервал обновления должен быть больше нуля и меньше TTL")
        self._stop_event = Event()
        self._thread = None

    def start(self):
        """Запускает регулярное обновление курсов, если оно ещё не запущено."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=run_scheduler,
            args=(self.interval_seconds, self._stop_event),
            kwargs={"update_immediately": False},
            name=RATES_UPDATER_THREAD_NAME,
        )
        self._thread.start()

    def stop(self):
        """Останавливает автоматическое обновление курсов и ждёт завершения начатого."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
