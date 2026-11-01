class InsufficientFundsError(Exception):
    """Недостаточно средств на кошельке."""

    def __init__(self, available: float, code: str, required: float):
        self.available = available
        self.code = code
        self.required = required
        message = (
            f"Недостаточно средств: доступно {available:.12g} {code}, "
            f"требуется {required:.12g} {code}"
        )
        super().__init__(message)


class CurrencyNotFoundError(Exception):
    """Валюта не найдена в реестре."""

    pass


class ApiRequestError(Exception):
    """Ошибка при обращении к внешнему API."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
