"""Строковый формат: LEVEL ISO-UTC ACTION key=value.

По умолчанию INFO, ротация по 1 МиБ с тремя архивами.
Для отладки: LOG_LEVEL=DEBUG. Поля операций формирует log_action.
"""

import logging
import os
import time
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import RATES_UPDATER_THREAD_NAME, SettingsLoader

LOG_FORMAT = "{levelname} {asctime} {message}"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def setup_logging(level=None):
    """Настраивает запись сообщений о работе программы в файл и вывод в терминал.

    При повторном вызове заменяет предыдущие настройки вывода сообщений."""
    settings = SettingsLoader()
    if level is None:
        level = os.getenv("LOG_LEVEL", settings.get("log_level"))
    if isinstance(level, str):
        level = getattr(logging, level.upper(), None)
    if type(level) is not int or level not in (
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ):
        raise ValueError("Укажите LOG_LEVEL: DEBUG, INFO, WARNING, ERROR или CRITICAL")

    log_file = settings.get("log_file")
    max_bytes = settings.get("log_max_bytes")
    backup_count = settings.get("log_backup_count")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("Размер файла логов должен быть положительным целым числом")
    if type(backup_count) is not int or backup_count <= 0:
        raise ValueError("Количество архивов логов должно быть положительным")

    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT, style="{")
    formatter.converter = time.gmtime
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    console_handler = logging.StreamHandler()
    # В терминале показываем только предупреждения и ошибки.
    console_handler.setLevel(logging.WARNING)
    # Сообщения таймера остаются в файле и не прерывают ввод команды.
    console_handler.addFilter(
        lambda record: record.threadName != RATES_UPDATER_THREAD_NAME
    )
    for handler in (file_handler, console_handler):
        handler.setFormatter(formatter)
    logging.basicConfig(
        level=level,
        handlers=[file_handler, console_handler],
        force=True,
    )
    # Отладочные сообщения HTTP-библиотеки могут содержать API-ключ в URL.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
