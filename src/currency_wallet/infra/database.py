import json
import os

from .settings import SettingsLoader


class DatabaseManager:
    """Singleton для работы с JSON-файлами."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.settings = SettingsLoader()
        return cls._instance

    def _get_path(self, filename):
        data_dir = self.settings.get("data_dir", "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, filename)

    def load(self, filename):
        """Загружает данные из JSON."""
        path = self._get_path(filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return [] if "rates" not in filename else {}

    def save(self, filename, data):
        """Сохраняет данные в JSON."""
        path = self._get_path(filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)