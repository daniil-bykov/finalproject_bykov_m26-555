import json
import os
import tempfile
from datetime import datetime

from .config import ParserConfig


class RatesStorage:
    def __init__(self):
        self.config = ParserConfig()
        os.makedirs("data", exist_ok=True)

    def _atomic_write(self, filepath: str, data: dict):
        """Атомарно записывает данные в JSON-файл (tmp -> rename)."""
        # Создаем временный файл в той же директории
        dir_name = os.path.dirname(filepath) or "."
        with tempfile.NamedTemporaryFile(
            "w", dir=dir_name, delete=False, encoding="utf-8"
        ) as tmp_file:
            json.dump(data, tmp_file, indent=4, ensure_ascii=False)
            temp_path = tmp_file.name
        
        # Переименовываем (атомарная операция)
        os.replace(temp_path, filepath)

    def save_rates(self, rates: dict, source: str):
        """Сохраняет текущие курсы в rates.json (снимок)."""
        data = {
            "pairs": {},
            "last_refresh": datetime.now().isoformat()
        }
        for pair, rate in rates.items():
            data["pairs"][pair] = {
                "rate": rate,
                "updated_at": datetime.now().isoformat(),
                "source": source
            }
        
        self._atomic_write(self.config.RATES_FILE_PATH, data)

    def append_history(self, rates: dict, source: str):
        """Добавляет запись в исторический журнал exchange_rates.json."""
        history = []
        if os.path.exists(self.config.HISTORY_FILE_PATH):
            with open(self.config.HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
                try:
                    history = json.load(f)
                except json.JSONDecodeError:
                    history = []

        now = datetime.now().isoformat()
        for pair, rate in rates.items():
            from_code, to_code = pair.split("_")
            record = {
                "id": f"{pair}_{now}",
                "from_currency": from_code,
                "to_currency": to_code,
                "rate": rate,
                "timestamp": now,
                "source": source,
                "meta": {}
            }
            history.append(record)

        self._atomic_write(self.config.HISTORY_FILE_PATH, history)