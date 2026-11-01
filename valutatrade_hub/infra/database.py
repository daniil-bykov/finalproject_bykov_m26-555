import json
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from math import isfinite
from pathlib import Path
from threading import RLock, local

from .settings import RATES_FILENAME, SettingsLoader


class DatabaseManager:
    """JSON-хранилище с атомарной записью и блокировкой потоков и процессов."""

    _instance = None
    _lock = RLock()
    _local = local()

    def __new__(cls):
        # __new__ даёт один менеджер при привычном вызове DatabaseManager().
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.settings = SettingsLoader()
            return cls._instance

    def _get_path(self, filename):
        path = self.settings.get_data_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    @contextmanager
    def file_lock(cls, directory, timeout=5.0):
        """Блокирует каталог данных между процессами; повторный вход допустим."""
        directory = Path(directory).resolve()
        with cls._lock:
            held = getattr(cls._local, "directories", set())
            if directory in held:
                yield
                return
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / ".storage.lock").open("a+b") as handle:
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                deadline = time.monotonic() + timeout
                while True:
                    try:
                        handle.seek(0)
                        if os.name == "nt":
                            import msvcrt

                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl

                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError as error:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(
                                "Хранилище занято. Повторите операцию позже."
                            ) from error
                        time.sleep(0.05)
                cls._local.directories = held | {directory}
                try:
                    yield
                finally:
                    cls._local.directories = held
                    handle.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _validate_records(filename, records):
        if filename not in ("users.json", "portfolios.json"):
            return
        ids, names = set(), set()
        try:
            for record in records:
                user_id = record["user_id"]
                if type(user_id) is not int or user_id <= 0 or user_id in ids:
                    raise ValueError("Некорректный или повторяющийся ID")
                ids.add(user_id)
                if filename == "users.json":
                    for field in ("username", "hashed_password", "salt"):
                        value = record[field]
                        if not isinstance(value, str) or not value.strip():
                            raise ValueError("Некорректные данные пользователя")
                    if record["username"] in names:
                        raise ValueError("Повторяющееся имя пользователя")
                    names.add(record["username"])
                    datetime.fromisoformat(record["registration_date"])
                else:
                    if not isinstance(record["wallets"], dict):
                        raise ValueError("Кошельки должны быть объектом")
                    for code, wallet in record["wallets"].items():
                        if (
                            not isinstance(code, str)
                            or not code.isascii()
                            or not code.isalpha()
                            or not code.isupper()
                            or not 2 <= len(code) <= 5
                        ):
                            raise ValueError("Некорректный код кошелька")
                        balance = wallet["balance"]
                        if (
                            type(balance) not in (int, float)
                            or not isfinite(balance)
                            or balance < 0
                        ):
                            raise ValueError("Некорректный баланс")
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ValueError(
                f"Некорректная запись в {filename}; данные не изменены"
            ) from error

    @staticmethod
    def _decode(filename, content):
        expected = dict if filename == RATES_FILENAME else list
        if content is None or (filename == RATES_FILENAME and not content.strip()):
            return expected()
        try:
            data = json.loads(content)
        except (ValueError, UnicodeError) as error:
            raise ValueError(
                f"Файл {filename} повреждён; данные не изменены"
            ) from error
        if not isinstance(data, expected):
            raise ValueError(f"Некорректная структура {filename}; данные не изменены")
        DatabaseManager._validate_records(filename, data)
        return data

    @staticmethod
    def _read(path):
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    @staticmethod
    def _stage(path, content):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
            ) as file:
                temporary = Path(file.name)
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            return temporary
        except Exception:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise

    def load(self, filename):
        """Читает данные из указанного JSON-файла и проверяет их структуру."""
        path = self._get_path(filename)
        with self.file_lock(path.parent):
            return self._decode(filename, self._read(path))

    def save(self, filename, data):
        """Сохраняет JSON через блокировку и атомарную замену файла."""
        with self.transaction(filename) as documents:
            documents[filename] = data

    def _encode_changes(self, documents, originals):
        encoded = {}
        for name, data in documents.items():
            content = json.dumps(
                data, indent=4, ensure_ascii=False, allow_nan=False
            ).encode("utf-8")
            self._decode(name, content)
            if content != originals[name]:
                encoded[name] = content
        return encoded

    def _rollback(self, paths, originals, written):
        for name in reversed(written):
            if originals[name] is None:
                paths[name].unlink(missing_ok=True)
                continue
            rollback = self._stage(paths[name], originals[name])
            try:
                os.replace(rollback, paths[name])
            finally:
                rollback.unlink(missing_ok=True)

    def _commit(self, paths, originals, encoded):
        staged = {}
        written = []
        try:
            for name, content in encoded.items():
                staged[name] = self._stage(paths[name], content)
            for name, temporary in staged.items():
                os.replace(temporary, paths[name])
                written.append(name)
        except Exception:
            self._rollback(paths, originals, written)
            raise
        finally:
            for temporary in staged.values():
                temporary.unlink(missing_ok=True)

    @contextmanager
    def transaction(self, *filenames):
        """Позволяет прочитать, изменить и сохранить один или несколько JSON-файлов.

        Блокирует одновременное изменение данных другими операциями программы.
        При ошибке сохранения пытается восстановить исходное содержимое файлов.
        Восстановление после аварийного выключения компьютера не гарантируется.
        """
        with self.file_lock(self.settings.get("data_dir")):
            paths = {name: self._get_path(name) for name in filenames}
            originals = {name: self._read(path) for name, path in paths.items()}
            documents = {
                name: self._decode(name, content) for name, content in originals.items()
            }
            yield documents
            self._commit(paths, originals, self._encode_changes(documents, originals))
