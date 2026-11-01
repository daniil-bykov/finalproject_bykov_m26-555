"""Общие функции хранения данных, проверки значений и оценки портфеля."""

import hashlib
import os
import re
from datetime import datetime, timezone
from math import isfinite

from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import (
    MIN_PASSWORD_LENGTH,
    PASSWORD_SALT_BYTES,
    RATES_FILENAME,
    SettingsLoader,
)

from .currencies import get_currency
from .exceptions import ApiRequestError


def load_users():
    """Читает список пользователей из users.json."""
    return DatabaseManager().load("users.json")


def load_user(user_id):
    """Ищет запись пользователя по ID; при отсутствии выбрасывает ValueError."""
    data = next((row for row in load_users() if row["user_id"] == user_id), None)
    if data is None:
        raise ValueError(f"Пользователь с id={user_id} не найден")
    return data


def save_users(users):
    """Атомарно сохраняет список пользователей в users.json."""
    DatabaseManager().save("users.json", users)


def load_portfolios():
    """Читает список портфелей из portfolios.json."""
    return DatabaseManager().load("portfolios.json")


def save_portfolios(portfolios):
    """Атомарно сохраняет список портфелей в portfolios.json."""
    DatabaseManager().save("portfolios.json", portfolios)


def load_rates():
    """Читает локальный снимок курсов из rates.json."""
    return DatabaseManager().load(RATES_FILENAME)


def save_rates(rates):
    """Атомарно сохраняет локальный снимок курсов."""
    DatabaseManager().save(RATES_FILENAME, rates)


def validate_password(password):
    """Проверяет непустой пароль и его минимальную длину."""
    if not isinstance(password, str) or not password.strip():
        raise ValueError("Пароль не может быть пустым")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")


def hash_password(password, salt):
    """Возвращает SHA-256 от пароля с добавленной солью."""
    return hashlib.sha256((password + salt).encode()).hexdigest()


def create_password_hash(password):
    """Проверяет пароль и возвращает его хеш и новую случайную соль."""
    validate_password(password)
    salt = os.urandom(PASSWORD_SALT_BYTES).hex()
    return hash_password(password, salt), salt


def validate_pair(pair: str) -> tuple[str, str]:
    """Проверяет формат FROM_TO с кодами из 2–5 заглавных латинских букв."""
    if not isinstance(pair, str) or not re.fullmatch(r"[A-Z]{2,5}_[A-Z]{2,5}", pair):
        raise ValueError("Коды валют должны содержать от 2 до 5 заглавных букв")
    return tuple(pair.split("_"))


def validate_rate(value, pair: str) -> float:
    """Возвращает положительный конечный курс или выбрасывает ValueError."""
    try:
        valid = type(value) in (int, float) and isfinite(value) and value > 0
        if valid:
            return float(value)
    except OverflowError:
        pass
    raise ValueError(f"Некорректный курс для {pair}")


def utc_timestamp(value: str | None = None) -> str:
    """Единый формат времени замера для ID, снимка и истории."""
    if value is None:
        timestamp = datetime.now(timezone.utc)
    else:
        try:
            timestamp = datetime.fromisoformat(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Некорректное время получения курса") from error
        if timestamp.tzinfo is None:
            raise ValueError("Время получения курса должно содержать часовой пояс")
        timestamp = timestamp.astimezone(timezone.utc)
    return timestamp.isoformat().replace("+00:00", "Z")


def _value_wallet(wallet, base, rate_provider):
    if wallet.currency_code == base:
        return {"value": wallet.balance, "updated_at": None}
    if rate_provider is None:
        raise ValueError("Для оценки в другой валюте передайте поставщик курсов")
    quote = rate_provider(wallet.currency_code, base)
    value = wallet.balance * quote["rate"]
    if not isfinite(value):
        raise ValueError("Стоимость кошелька слишком велика")
    return {"value": value, "updated_at": quote["updated_at"]}


def value_portfolio(wallets, base, rate_provider, *, allow_partial=False):
    """Общая оценка портфеля; получение и TTL курсов выполняет rate_provider."""
    if base is None:
        base = SettingsLoader().get("base_currency")
    base = get_currency(base).code
    items = []
    total = 0.0
    complete = True
    for code, wallet in wallets.items():
        item = {"currency_code": code, "balance": wallet.balance}
        try:
            item.update(_value_wallet(wallet, base, rate_provider))
            total += item["value"]
            if not isfinite(total):
                raise ValueError("Стоимость портфеля слишком велика")
        except ApiRequestError as error:
            if not allow_partial:
                raise
            item.update(value=None, error=str(error))
            complete = False
        items.append(item)
    return {"base": base, "items": items, "total": total, "complete": complete}
