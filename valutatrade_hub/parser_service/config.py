import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from valutatrade_hub.infra.settings import (
    HISTORY_FILENAME,
    RATES_BASE_CURRENCY,
    RATES_FILENAME,
    SettingsLoader,
)

load_dotenv()


@dataclass
class ParserConfig:
    """URL, список валют, ключ API, таймаут и пути Parser Service."""

    EXCHANGERATE_API_KEY: str = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", ""),
        repr=False,
    )
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )
    REQUEST_TIMEOUT: int = 10

    @property
    def BASE_CURRENCY(self):
        """Возвращает базовую валюту для курсов и расчёта стоимости операций."""
        return RATES_BASE_CURRENCY

    @property
    def RATES_FILE_PATH(self):
        """Возвращает путь к кэшу из текущих настроек приложения."""
        return str(SettingsLoader().get_data_path(RATES_FILENAME))

    @property
    def HISTORY_FILE_PATH(self):
        """Возвращает путь к файлу с историей курсов валют."""
        return str(SettingsLoader().get_data_path(HISTORY_FILENAME))

    def get_crypto_ids(self):
        """Возвращает ID CoinGecko для криптовалют, выбранных в настройках."""
        selected = {}
        for code in self.CRYPTO_CURRENCIES:
            if code not in self.CRYPTO_ID_MAP:
                raise ValueError(f"Для криптовалюты {code} не задан ID CoinGecko")
            selected[code] = self.CRYPTO_ID_MAP[code]
        return selected
