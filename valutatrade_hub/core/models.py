from datetime import datetime
from math import isfinite

from .currencies import get_currency
from .exceptions import InsufficientFundsError
from .utils import create_password_hash, hash_password, load_user, value_portfolio


class User:
    """Хранит имя, дату регистрации и данные для проверки пароля пользователя."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ):
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    # Геттеры
    @property
    def user_id(self) -> int:
        """Возвращает неизменяемый идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Возвращает имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str):
        """Проверяет и устанавливает непустое имя пользователя."""
        self.validate_username(value)
        self._username = value

    @staticmethod
    def validate_username(value):
        """Отклоняет пустое имя и значения, не являющиеся строками."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")

    @classmethod
    def from_dict(cls, data):
        """Восстанавливает пользователя из JSON-записи с ISO-датой."""
        return cls(
            data["user_id"],
            data["username"],
            data["hashed_password"],
            data["salt"],
            datetime.fromisoformat(data["registration_date"]),
        )

    @property
    def hashed_password(self) -> str:
        """Возвращает хеш пароля для сериализации."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Возвращает соль, использованную при хешировании пароля."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Возвращает дату регистрации пользователя."""
        return self._registration_date

    def get_user_info(self):
        """Выводит информацию о пользователе (без пароля)."""
        print(f"ID: {self._user_id}")
        print(f"Имя: {self._username}")
        print(f"Дата регистрации: {self._registration_date}")

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли введенный пароль с хешем."""
        return (
            isinstance(password, str)
            and hash_password(password, self._salt) == self._hashed_password
        )

    def change_password(self, new_password: str):
        """Меняет пароль на новый (с хешированием)."""
        self._hashed_password, self._salt = create_password_hash(new_password)


class Wallet:
    """Хранит баланс одной валюты и проверяет его допустимость."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = get_currency(currency_code).code
        self._balance = 0.0
        self.balance = balance  # Используем сеттер для проверки

    @property
    def balance(self) -> float:
        """Возвращает текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value: float):
        """Проверяет новое значение баланса и сохраняет его, если оно допустимо."""
        if type(value) not in (int, float):
            raise TypeError("Баланс должен быть числом")
        try:
            value = float(value)
        except OverflowError as error:
            raise ValueError("Баланс слишком велик") from error
        if not isfinite(value) or value < 0:
            raise ValueError("Баланс должен быть конечным неотрицательным числом")
        self._balance = value

    @staticmethod
    def validate_amount(amount):
        """Проверяет положительную конечную сумму и возвращает float."""
        if type(amount) not in (int, float):
            raise ValueError("Сумма должна быть положительным конечным числом")
        try:
            amount = float(amount)
        except OverflowError as error:
            raise ValueError("Сумма слишком велика") from error
        if not isfinite(amount) or amount <= 0:
            raise ValueError("Сумма должна быть положительным конечным числом")
        return amount

    def deposit(self, amount: float):
        """Пополнение баланса."""
        amount = self.validate_amount(amount)
        updated = self.balance + amount
        if updated == self.balance:
            raise ValueError("Сумма слишком мала для изменения текущего баланса")
        self.balance = updated

    def withdraw(self, amount: float):
        """Списывает сумму; при нехватке выбрасывает InsufficientFundsError."""
        amount = self.validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(self._balance, self.currency_code, amount)
        updated = self.balance - amount
        if updated == self.balance:
            raise ValueError("Сумма слишком мала для изменения текущего баланса")
        self.balance = updated

    def get_balance_info(self):
        """Вывод информации о текущем балансе."""
        print(f"Валюта: {self.currency_code}, Баланс: {self._balance:.4f}")


class Portfolio:
    """Набор кошельков одного пользователя с оценкой в выбранной валюте."""

    def __init__(self, user_id: int, wallets: dict = None):
        self._user_id = user_id
        self._wallets = wallets if wallets else {}

    @property
    def user_id(self) -> int:
        """Возвращает идентификатор владельца портфеля."""
        return self._user_id

    @property
    def user(self) -> User:
        """Загружает владельца из хранилища; свойство доступно только для чтения."""
        return User.from_dict(load_user(self._user_id))

    @property
    def wallets(self) -> dict:
        # Возвращаем копию словаря, чтобы нельзя было изменить его напрямую
        """Возвращает копию словаря с существующими объектами кошельков."""
        return self._wallets.copy()

    def add_currency(self, currency_code: str):
        """Добавляет новый кошелёк в портфель."""
        currency_code = get_currency(currency_code).code
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк {currency_code} уже существует")
        self._wallets[currency_code] = Wallet(currency_code)

    def get_wallet(self, currency_code: str) -> Wallet:
        """Возвращает объект Wallet по коду валюты."""
        currency_code = currency_code.upper()
        if currency_code not in self._wallets:
            raise KeyError(f"Кошелёк {currency_code} не найден")
        return self._wallets[currency_code]

    def get_total_value(
        self, base=None, *, rate_provider=None, base_currency=None
    ) -> float:
        """Рассчитывает общую стоимость всех кошельков в выбранной валюте.

        Если валюта не указана, использует валюту из настроек.
        Валюту можно задать через base или base_currency.
        rate_provider позволяет указать функцию для получения курсов.
        """
        if base_currency is not None:
            if base is not None:
                raise ValueError("Укажите только один аргумент: base или base_currency")
            base = base_currency
        if rate_provider is None:
            # Отложенный импорт: usecases использует модели при загрузке модуля.
            from .usecases import get_rate

            rate_provider = get_rate
        return value_portfolio(self.wallets, base, rate_provider)["total"]
