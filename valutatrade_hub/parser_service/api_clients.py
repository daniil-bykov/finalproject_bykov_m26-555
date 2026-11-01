from abc import ABC, abstractmethod
from time import perf_counter

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import utc_timestamp, validate_pair, validate_rate

from .config import ParserConfig


class BaseApiClient(ABC):
    """API-клиент с временем получения и метаданными последнего ответа."""

    source = "API"

    def __init__(self):
        self.config = ParserConfig()
        self.received_at = None
        self.metadata = {}

    @abstractmethod
    def fetch_rates(self) -> dict:
        """Возвращает словарь пар и курсов; при сбое бросает ApiRequestError."""
        pass

    @staticmethod
    def _http_error_reason(status):
        messages = {
            400: "Некорректный запрос. Проверьте параметры.",
            401: "Ошибка авторизации. Проверьте API-ключ.",
            403: "Доступ запрещён. Проверьте API-ключ и права доступа.",
            408: "Истекло время ожидания запроса. Повторите попытку позже.",
            429: "Превышен лимит запросов. Повторите попытку позже.",
        }
        if 500 <= status < 600:
            return "Сервис временно недоступен. Повторите попытку позже."
        return messages.get(status, "Неожиданный статус ответа сервиса.")

    def _request_json(self, url, *, params=None):
        self.received_at = None
        self.metadata = {}
        started = perf_counter()
        try:
            response = requests.get(
                url, params=params, timeout=self.config.REQUEST_TIMEOUT
            )
        except requests.Timeout as error:
            raise ApiRequestError(
                f"{self.source}: истекло время ожидания ответа. "
                "Повторите попытку позже."
            ) from error
        except requests.ConnectionError as error:
            raise ApiRequestError(
                f"{self.source}: не удалось подключиться. Проверьте соединение с сетью."
            ) from error
        except requests.RequestException as error:
            # URL ExchangeRate-API содержит ключ: не включаем его в сообщение.
            raise ApiRequestError(
                f"{self.source}: ошибка сетевого запроса. Повторите попытку позже."
            ) from error
        received_at = utc_timestamp()
        request_ms = round((perf_counter() - started) * 1000)
        if not 200 <= response.status_code < 300:
            reason = self._http_error_reason(response.status_code)
            raise ApiRequestError(
                f"{self.source}: HTTP {response.status_code}: {reason}"
            )
        try:
            data = response.json()
        except (requests.exceptions.JSONDecodeError, ValueError) as error:
            raise ApiRequestError(f"{self.source} вернул некорректный JSON") from error
        if not isinstance(data, dict):
            raise ApiRequestError(f"{self.source}: ожидался JSON-объект")
        metadata = {"request_ms": request_ms, "status_code": response.status_code}
        etag = response.headers.get("ETag")
        if etag is not None:
            metadata["etag"] = etag
        return data, received_at, metadata

    @staticmethod
    def _validate_rate(value, pair: str) -> float:
        try:
            validate_pair(pair)
            return validate_rate(value, pair)
        except ValueError as error:
            raise ApiRequestError(str(error)) from error


class CoinGeckoClient(BaseApiClient):
    """Загружает цены выбранных криптовалют через CoinGecko."""

    source = "CoinGecko"

    def fetch_rates(self) -> dict:
        """Возвращает курсы криптовалют к базе и сохраняет метаданные ответа."""
        crypto_ids = self.config.get_crypto_ids()
        if not crypto_ids:
            self.received_at = None
            self.metadata = {}
            return {}
        params = {
            "ids": ",".join(crypto_ids.values()),
            "vs_currencies": self.config.BASE_CURRENCY.lower(),
        }
        data, received_at, request_meta = self._request_json(
            self.config.COINGECKO_URL, params=params
        )
        result = {}
        metadata = {}
        quote = self.config.BASE_CURRENCY.lower()
        for code, raw_id in crypto_ids.items():
            if raw_id not in data:
                continue
            entry = data[raw_id]
            if not isinstance(entry, dict):
                raise ApiRequestError(f"CoinGecko: неверная структура курса {raw_id}")
            if quote not in entry:
                continue
            pair = f"{code}_{self.config.BASE_CURRENCY}"
            result[pair] = self._validate_rate(entry[quote], pair)
            metadata[pair] = {"raw_id": raw_id, **request_meta}
        if not result:
            raise ApiRequestError("CoinGecko не вернул запрошенные курсы")
        self.received_at = received_at
        self.metadata = metadata
        return result


class ExchangeRateApiClient(BaseApiClient):
    """Загружает фиатные курсы через ExchangeRate-API с ключом из env."""

    source = "ExchangeRate-API"

    @staticmethod
    def _api_error_reason(error_type):
        messages = {
            "invalid-key": "Неверный API-ключ. Проверьте EXCHANGERATE_API_KEY.",
            "quota-reached": "Превышен лимит запросов. Повторите попытку позже.",
            "inactive-account": "Учётная запись не активирована. Подтвердите почту.",
            "unsupported-code": "Сервис не поддерживает указанную базовую валюту.",
            "malformed-request": "Некорректный запрос. Проверьте базовую валюту и URL.",
        }
        if not isinstance(error_type, str):
            return "Сервис сообщил об ошибке запроса. Повторите попытку позже."
        return messages.get(
            error_type, "Сервис сообщил об ошибке запроса. Повторите попытку позже."
        )

    def fetch_rates(self) -> dict:
        """Возвращает курсы фиатных валют к базе, обращая котировки API."""
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                "API-ключ для ExchangeRate-API не найден в переменных окружения"
            )
        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_CURRENCY}"
        )
        data, received_at, request_meta = self._request_json(url)
        if data.get("result") != "success":
            reason = self._api_error_reason(data.get("error-type"))
            raise ApiRequestError(f"{self.source}: {reason}")
        if data.get("base_code") != self.config.BASE_CURRENCY:
            raise ApiRequestError("ExchangeRate-API вернул другую базовую валюту")
        rates = data.get("conversion_rates")
        if not isinstance(rates, dict):
            raise ApiRequestError(
                "ExchangeRate-API: неверная структура conversion_rates"
            )

        result = {}
        metadata = {}
        for code in self.config.FIAT_CURRENCIES:
            if code not in rates:
                continue
            pair = f"{code}_{self.config.BASE_CURRENCY}"
            base_to_currency = self._validate_rate(rates[code], pair)
            result[pair] = self._validate_rate(1.0 / base_to_currency, pair)
            metadata[pair] = {"raw_id": code, **request_meta}
        if not result:
            raise ApiRequestError("ExchangeRate-API не вернул запрошенные курсы")
        self.received_at = received_at
        self.metadata = metadata
        return result
