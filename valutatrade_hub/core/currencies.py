from abc import ABC, abstractmethod

from .exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактный базовый класс для всех валют."""

    def __init__(self, name: str, code: str):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Имя валюты не может быть пустым")

        if not isinstance(code, str):
            raise ValueError("Код валюты должен быть строкой из 2–5 букв")
        code = code.upper()
        if not (2 <= len(code) <= 5) or not code.isascii() or not code.isalpha():
            raise ValueError("Код валюты должен быть от 2 до 5 букв")

        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строку для UI/логов."""
        pass


class FiatCurrency(Currency):
    """Фиатная валюта с указанием страны или региона эмиссии."""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self.issuing_country = issuing_country  # Доп. атрибут

    def get_display_info(self) -> str:
        # Формат: "[FIAT] USD — US Dollar (Issuing: United States)"
        """Возвращает код, название и страну эмиссии для отображения."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и необязательной капитализацией."""

    def __init__(
        self, name: str, code: str, algorithm: str, market_cap: float | None = None
    ):
        super().__init__(name, code)
        self.algorithm = algorithm  # Доп. атрибут
        self.market_cap = market_cap  # None, если капитализация не загружена

    def get_display_info(self) -> str:
        # Формат: "[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)"
        """Возвращает описание криптовалюты для отображения."""
        market_cap = f"{self.market_cap:.2e}" if self.market_cap is not None else "n/a"
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {market_cap})"
        )


_REGISTRY = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 3.7e11),
    "SOL": CryptoCurrency("Solana", "SOL", "PoS"),
}


def get_currency(code: str) -> Currency:
    """Фабричный метод для получения валюты по коду."""
    if not isinstance(code, str):
        raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")
    code = code.upper()
    if code not in _REGISTRY:
        raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")
    return _REGISTRY[code]


def get_currency_codes() -> tuple[str, ...]:
    """Возвращает поддерживаемые коды в алфавитном порядке."""
    return tuple(sorted(_REGISTRY))
