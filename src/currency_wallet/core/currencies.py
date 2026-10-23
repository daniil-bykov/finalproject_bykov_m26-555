from abc import ABC, abstractmethod


class Currency(ABC):
    """Абстрактный базовый класс для всех валют."""

    def __init__(self, name: str, code: str):
        if not name or not isinstance(name, str):
            raise ValueError("Имя валюты не может быть пустым")
        
        code = code.upper()
        if not (2 <= len(code) <= 5) or not code.isalpha():
            raise ValueError("Код валюты должен быть от 2 до 5 букв")
        
        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строку для UI/логов."""
        pass


class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        return (
                f"[CRYPTO] {self.code} — {self.name} "
                f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
)


_REGISTRY = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 3.7e11),
}


def get_currency(code: str) -> Currency:
    """Фабричный метод для получения валюты по коду."""
    code = code.upper()
    if code not in _REGISTRY:
        from .exceptions import CurrencyNotFoundError
        raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")
    return _REGISTRY[code]