import json
import os
import tempfile
from datetime import datetime, tzinfo
from pathlib import Path
from threading import Lock

from valutatrade_hub.core.utils import utc_timestamp, validate_pair, validate_rate
from valutatrade_hub.infra.database import DatabaseManager

from .config import ParserConfig


class RatesStorage:
    """Проверяет и сохраняет текущие курсы валют и историю их обновлений."""

    _write_lock = Lock()

    def __init__(self):
        self.config = ParserConfig()
        for path in (self.config.RATES_FILE_PATH, self.config.HISTORY_FILE_PATH):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def _atomic_write(self, filepath: str, data):
        """Записывает данные во временный файл, затем заменяет им основной."""
        dir_name = os.path.dirname(filepath) or "."
        os.makedirs(dir_name, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=dir_name, delete=False, encoding="utf-8"
            ) as tmp_file:
                temp_path = tmp_file.name
                json.dump(data, tmp_file, indent=4, ensure_ascii=False, allow_nan=False)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(temp_path, filepath)
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass

    @staticmethod
    def _validate_metadata(metadata):
        if not isinstance(metadata, dict):
            raise ValueError("Метаданные замера должны быть объектом")
        for key in ("raw_id", "etag"):
            if key in metadata and not isinstance(metadata[key], str):
                raise ValueError(f"Метаданные {key} должны быть строкой")
        if "request_ms" in metadata:
            value = metadata["request_ms"]
            if type(value) is not int or value < 0:
                raise ValueError("request_ms должен быть неотрицательным целым числом")
        if "status_code" in metadata:
            value = metadata["status_code"]
            if type(value) is not int or not 200 <= value < 300:
                raise ValueError("В историю можно записать только успешный HTTP-ответ")
        json.dumps(metadata, allow_nan=False)

    def _prepare_records(self, rates, source, timestamps=None, metadata=None):
        if not isinstance(rates, dict):
            raise ValueError("Курсы должны быть словарём валютных пар")
        default_time = utc_timestamp() if timestamps is None else None
        records = []
        for pair, value in rates.items():
            from_code, to_code = validate_pair(pair)
            rate = validate_rate(value, pair)
            pair_source = source.get(pair) if isinstance(source, dict) else source
            if not isinstance(pair_source, str) or not pair_source.strip():
                raise ValueError(f"Не указан источник для {pair}")
            timestamp = timestamps.get(pair) if timestamps is not None else default_time
            if not isinstance(timestamp, str):
                raise ValueError(f"Не указано время получения курса {pair}")
            timestamp = utc_timestamp(timestamp)
            meta = metadata.get(pair, {}) if metadata is not None else {}
            self._validate_metadata(meta)
            records.append(
                {
                    "id": f"{pair}_{timestamp}",
                    "from_currency": from_code,
                    "to_currency": to_code,
                    "rate": rate,
                    "timestamp": timestamp,
                    "source": pair_source,
                    "meta": meta.copy(),
                }
            )
        return records

    def _load_snapshot(self):
        try:
            content = Path(self.config.RATES_FILE_PATH).read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"pairs": {}}
        if not content.strip():
            return {"pairs": {}}
        try:
            data = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("Файл кэша повреждён; данные не изменены") from error
        if data == {}:
            return {"pairs": {}}
        if not isinstance(data, dict) or not isinstance(data.get("pairs"), dict):
            raise ValueError("Некорректная структура кэша курсов")
        return data

    @staticmethod
    def _is_newer(record, previous):
        if not isinstance(previous, dict):
            return True
        timestamp = previous.get("updated_at")
        if not isinstance(timestamp, str):
            return True
        try:
            validate_rate(previous.get("rate"), record["id"])
            previous_time = datetime.fromisoformat(utc_timestamp(timestamp))
        except ValueError:
            return True
        return datetime.fromisoformat(record["timestamp"]) > previous_time

    def save_rates(self, rates, source, *, timestamps=None):
        """Сохраняет новые и более свежие курсы и возвращает сведения об обновлении."""
        records = self._prepare_records(rates, source, timestamps)
        with (
            self._write_lock,
            DatabaseManager.file_lock(Path(self.config.RATES_FILE_PATH).parent),
        ):
            data = self._load_snapshot()
            updated = {}
            for record in records:
                pair = f"{record['from_currency']}_{record['to_currency']}"
                if not self._is_newer(record, data["pairs"].get(pair)):
                    continue
                data["pairs"][pair] = {
                    "rate": record["rate"],
                    "updated_at": record["timestamp"],
                    "source": record["source"],
                }
                updated[pair] = record["rate"]
            if updated:
                data["last_refresh"] = utc_timestamp()
                self._atomic_write(self.config.RATES_FILE_PATH, data)
            return {"rates": updated, "last_refresh": data.get("last_refresh")}

    def _load_history(self):
        try:
            with open(self.config.HISTORY_FILE_PATH, "r", encoding="utf-8") as file:
                history = json.load(file)
        except FileNotFoundError:
            return []
        except (ValueError, UnicodeError) as error:
            raise ValueError("Файл истории повреждён; история не изменена") from error
        try:
            if not isinstance(history, list):
                raise ValueError("Ожидался список измерений")
            ids = set()
            for record in history:
                pair = f"{record['from_currency']}_{record['to_currency']}"
                validate_pair(pair)
                validate_rate(record["rate"], pair)
                # Старые записи могут содержать локальное время без часового пояса.
                datetime.fromisoformat(record["timestamp"])
                if (
                    record["id"] != f"{pair}_{record['timestamp']}"
                    or record["id"] in ids
                ):
                    raise ValueError("Некорректный или повторяющийся ID")
                if (
                    not isinstance(record["source"], str)
                    or not record["source"].strip()
                ):
                    raise ValueError("Не указан источник")
                self._validate_metadata(record["meta"])
                ids.add(record["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Файл истории повреждён; история не изменена") from error
        return history

    def append_history(self, rates, source, *, timestamps=None, metadata=None):
        """Добавляет новые записи о курсах в историю, пропуская повторные.

        Возвращает количество добавленных записей.
        """
        records = self._prepare_records(rates, source, timestamps, metadata)
        if not records:
            return 0
        with (
            self._write_lock,
            DatabaseManager.file_lock(Path(self.config.HISTORY_FILE_PATH).parent),
        ):
            history = self._load_history()
            existing = {record["id"]: record for record in history}
            added = 0
            for record in records:
                previous = existing.get(record["id"])
                if previous is not None:
                    if (
                        previous["rate"] != record["rate"]
                        or previous["source"] != record["source"]
                    ):
                        raise ValueError(
                            f"Конфликт замера {record['id']}; история не изменена"
                        )
                    continue
                history.append(record)
                existing[record["id"]] = record
                added += 1
            if added:
                self._atomic_write(self.config.HISTORY_FILE_PATH, history)
            return added

    def migrate_history(self, source_timezone):
        """Переводит старое локальное время в UTC, сохраняя точную резервную копию."""
        if not isinstance(source_timezone, tzinfo):
            raise ValueError("Укажите подтверждённый часовой пояс старых записей")
        with (
            self._write_lock,
            DatabaseManager.file_lock(Path(self.config.HISTORY_FILE_PATH).parent),
        ):
            history = self._load_history()
            migrated = []
            ids = set()
            changed = 0
            for original in history:
                record = original.copy()
                timestamp = datetime.fromisoformat(record["timestamp"])
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=source_timezone)
                    record["timestamp"] = utc_timestamp(timestamp.isoformat())
                    pair = f"{record['from_currency']}_{record['to_currency']}"
                    record["id"] = f"{pair}_{record['timestamp']}"
                    changed += 1
                if record["id"] in ids:
                    raise ValueError(
                        "Миграция создаёт повторяющиеся ID; история не изменена"
                    )
                ids.add(record["id"])
                migrated.append(record)
            if not changed:
                return {"migrated": 0, "backup_path": None}
            path = Path(self.config.HISTORY_FILE_PATH)
            suffix = utc_timestamp().replace(":", "-")
            backup = path.with_name(f"{path.stem}.backup-{suffix}{path.suffix}")
            self._backup_history(path, backup)
            self._atomic_write(str(path), migrated)
            return {"migrated": changed, "backup_path": str(backup)}

    @staticmethod
    def _backup_history(path, backup):
        created = False
        try:
            with backup.open("xb") as file:
                created = True
                file.write(path.read_bytes())
                file.flush()
                os.fsync(file.fileno())
        except Exception:
            if created:
                backup.unlink(missing_ok=True)
            raise
