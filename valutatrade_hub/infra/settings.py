import tomllib
from pathlib import Path
from threading import RLock

# По заданию снимки курсов и оценка сделок используют USD.
RATES_BASE_CURRENCY = "USD"
RATES_FILENAME = "rates.json"
HISTORY_FILENAME = "exchange_rates.json"
RATES_UPDATER_THREAD_NAME = "rates-updater"

MIN_PASSWORD_LENGTH = 4
PASSWORD_SALT_BYTES = 4
SETTINGS_FILE = Path("pyproject.toml")

DEFAULT_SETTINGS = {
    "data_dir": "data",
    "rates_ttl_seconds": 3900,
    "rates_update_interval_seconds": 3600,
    # Валюта отображения портфеля; не меняет базу снимков курсов.
    "base_currency": RATES_BASE_CURRENCY,
    "log_file": "logs/actions.log",
    "log_level": "INFO",
    "log_max_bytes": 1024 * 1024,
    "log_backup_count": 3,
}


class SettingsLoader:
    """Загружает и хранит общие настройки приложения в единственном экземпляре."""

    _instance = None
    _lock = RLock()

    def __new__(cls):
        # __new__ сохраняет обычный вызов SettingsLoader() и проще метакласса.
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance.reload()
                cls._instance = instance
            return cls._instance

    @staticmethod
    def _read_config():
        try:
            with SETTINGS_FILE.open("rb") as file:
                document = tomllib.load(file)
        except FileNotFoundError:
            return {}
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"Некорректный TOML в {SETTINGS_FILE}") from error
        tool = document.get("tool", {})
        if not isinstance(tool, dict):
            raise ValueError("Раздел tool должен быть таблицей TOML")
        config = tool.get("valutatrade", {})
        if not isinstance(config, dict):
            raise ValueError("Раздел tool.valutatrade должен быть таблицей TOML")
        return config

    @staticmethod
    def _validate(settings):
        for key in ("data_dir", "log_file", "base_currency"):
            value = settings[key]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Настройка {key} должна быть непустой строкой")
        for key in (
            "rates_ttl_seconds",
            "rates_update_interval_seconds",
            "log_max_bytes",
            "log_backup_count",
        ):
            value = settings[key]
            if type(value) is not int or value <= 0:
                raise ValueError(
                    f"Настройка {key} должна быть положительным целым числом"
                )
        if settings["rates_update_interval_seconds"] >= settings["rates_ttl_seconds"]:
            raise ValueError("Интервал обновления должен быть меньше TTL курсов")
        if settings["log_level"] not in (
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ):
            raise ValueError(
                "Укажите log_level: DEBUG, INFO, WARNING, ERROR или CRITICAL"
            )

    def get(self, key: str, default=None):
        """Возвращает настройку или переданное значение по умолчанию."""
        return self._settings.get(key, default)

    def get_data_path(self, filename: str) -> Path:
        """Строит путь к файлу внутри настроенной папки данных."""
        return Path(self.get("data_dir")) / filename

    def reload(self):
        """Перечитывает конфигурацию; ошибка не меняет действующие настройки."""
        with self._lock:
            settings = {**DEFAULT_SETTINGS, **self._read_config()}
            self._validate(settings)
            self._settings = settings
