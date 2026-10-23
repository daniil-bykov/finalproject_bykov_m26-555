from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError

from .config import ParserConfig


class BaseApiClient(ABC):
    """Базовый класс для всех API-клиентов."""
    @abstractmethod
    def fetch_rates(self) -> dict:
        pass


class CoinGeckoClient(BaseApiClient):
    def __init__(self):
        self.config = ParserConfig()

    def fetch_rates(self) -> dict:
        ids = ",".join(self.config.CRYPTO_ID_MAP.values())
        params = {
            "ids": ids,
            "vs_currencies": self.config.BASE_CURRENCY.lower()
        }
        try:
            response = requests.get(
                self.config.COINGECKO_URL, 
                params=params, 
                timeout=self.config.REQUEST_TIMEOUT
            )
            response.raise_for_status() # Вызовет ошибку, если статус не 200
            data = response.json()
            
            # Приводим к формату {"BTC_USD": 59337.21}
            result = {}
            for code, cg_id in self.config.CRYPTO_ID_MAP.items():
                if cg_id in data and self.config.BASE_CURRENCY.lower() in data[cg_id]:
                    rate = data[cg_id][self.config.BASE_CURRENCY.lower()]
                    result[f"{code}_{self.config.BASE_CURRENCY}"] = rate
            return result
        except requests.RequestException as e:
            raise ApiRequestError(f"Ошибка при запросе к CoinGecko: {e}")


class ExchangeRateApiClient(BaseApiClient):
    def __init__(self):
        self.config = ParserConfig()

    def fetch_rates(self) -> dict:
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
            "API-ключ для ExchangeRate-API не найден в переменных окружения"
            )
            
        url = (
               f"{self.config.EXCHANGERATE_API_URL}/"
               f"{self.config.EXCHANGERATE_API_KEY}/latest/"
               f"{self.config.BASE_CURRENCY}"
              )
        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            if data.get("result") != "success":
                raise ApiRequestError(
                f"ExchangeRate-API вернул ошибку: {data.get('error-type')}"
               )

            rates = data["conversion_rates"]
            result = {}
            for code in self.config.FIAT_CURRENCIES:
                if code in rates:
                    # Пересчитываем так, чтобы было 1 EUR = X USD
                    result[f"{code}_{self.config.BASE_CURRENCY}"] = rates[code]
            return result
        except requests.RequestException as e:
            raise ApiRequestError(f"Ошибка при запросе к ExchangeRate-API: {e}")