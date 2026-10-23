import json
import os

DATA_DIR = "data"
USERS_FILE = f"{DATA_DIR}/users.json"
PORTFOLIOS_FILE = f"{DATA_DIR}/portfolios.json"
RATES_FILE = f"{DATA_DIR}/rates.json"


def _ensure_data_dir():
    """Создает папку data, если ее нет."""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_data(filepath):
    """Загружает данные из JSON. Если файла нет — возвращает пустой список/словарь."""
    _ensure_data_dir()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Для users/portfolios возвращаем список, для rates — словарь
        return {} if "rates" in filepath else []


def save_data(filepath, data):
    """Сохраняет данные в JSON."""
    _ensure_data_dir()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_users():
    return load_data(USERS_FILE)


def save_users(users):
    save_data(USERS_FILE, users)


def load_portfolios():
    return load_data(PORTFOLIOS_FILE)


def save_portfolios(portfolios):
    save_data(PORTFOLIOS_FILE, portfolios)


def load_rates():
    return load_data(RATES_FILE)


def save_rates(rates):
    save_data(RATES_FILE, rates)