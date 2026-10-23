import hashlib
import os
from datetime import datetime


class User:
    def __init__(self, user_id: int, username: str, hashed_password: str,
             salt: str, registration_date: datetime):
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    # Геттеры
    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def get_user_info(self):
        """Выводит информацию о пользователе (без пароля)."""
        print(f"ID: {self._user_id}")
        print(f"Имя: {self._username}")
        print(f"Дата регистрации: {self._registration_date}")

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли введенный пароль с хешем."""
        check_hash = hashlib.sha256((password + self._salt).encode()).hexdigest()
        return check_hash == self._hashed_password

    def change_password(self, new_password: str):
        """Меняет пароль на новый (с хешированием)."""
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        # Генерируем новую соль при смене пароля
        self._salt = os.urandom(4).hex()
        self._hashed_password = hashlib.sha256(
        (new_password + self._salt).encode()
        ).hexdigest()


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code.upper()
        self._balance = 0.0
        self.balance = balance  # Используем сеттер для проверки

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float):
        """Пополнение баланса."""
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительным числом")
        self.balance += amount

    def withdraw(self, amount: float):
        """Снятие средств (если баланс позволяет)."""
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Сумма снятия должна быть положительным числом")
        if amount > self._balance:
            raise ValueError(
            f"Недостаточно средств: доступно {self._balance}, "
            f"требуется {amount}"
            )
        self.balance -= amount

    def get_balance_info(self):
        """Вывод информации о текущем балансе."""
        print(f"Валюта: {self.currency_code}, Баланс: {self._balance:.4f}")


class Portfolio:
    # Фиктивные курсы для конвертации (пока нет API)
    EXCHANGE_RATES = {
        "USD": 1.0,
        "EUR": 1.08,
        "BTC": 59300.0,
        "ETH": 3720.0,
        "RUB": 0.01016
    }

    def __init__(self, user_id: int, wallets: dict = None):
        self._user_id = user_id
        self._wallets = wallets if wallets else {}

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> dict:
        # Возвращаем копию словаря, чтобы нельзя было изменить его напрямую
        return self._wallets.copy()

    def add_currency(self, currency_code: str):
        """Добавляет новый кошелёк в портфель."""
        currency_code = currency_code.upper()
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк {currency_code} уже существует")
        self._wallets[currency_code] = Wallet(currency_code)

    def get_wallet(self, currency_code: str) -> Wallet:
        """Возвращает объект Wallet по коду валюты."""
        currency_code = currency_code.upper()
        if currency_code not in self._wallets:
            raise KeyError(f"Кошелёк {currency_code} не найден")
        return self._wallets[currency_code]

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Считает общую стоимость всех валют в указанной базовой валюте."""
        base_currency = base_currency.upper()
        if base_currency not in self.EXCHANGE_RATES:
            raise ValueError(f"Неизвестная базовая валюта: {base_currency}")
        
        total = 0.0
        for code, wallet in self._wallets.items():
            if code in self.EXCHANGE_RATES:
                # Переводим в USD, а потом в базовую
                value_in_usd = wallet.balance * self.EXCHANGE_RATES[code]
                total += value_in_usd / self.EXCHANGE_RATES[base_currency]
        return total