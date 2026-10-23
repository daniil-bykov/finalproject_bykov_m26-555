import json
import os
from datetime import datetime

from .config import ParserConfig


class RatesStorage:
    def __init__(self):
        self.config = ParserConfig()
        os.makedirs("data", exist_ok=True)

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
        
        with open(self.config.RATES_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

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

        with open(self.config.HISTORY_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)