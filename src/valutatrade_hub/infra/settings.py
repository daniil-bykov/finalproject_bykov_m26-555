class SettingsLoader:
    """Singleton для загрузки настроек."""
    _instance = None

    # Используем __new__ для реализации Singleton, потому что это самый простой
    # и читаемый способ в Python. Метаклассы дают больше гибкости, но здесь
    # они избыточны. __new__ гарантирует, что при любом импорте и вызове
    # SettingsLoader() будет возвращаться один и тот же объект.
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_defaults()
        return cls._instance

    def _load_defaults(self):
        self._settings = {
            "data_dir": "data",
            "rates_ttl_seconds": 300,
            "base_currency": "USD",
            "log_file": "logs/actions.log",
        }

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def reload(self):
        self._load_defaults()