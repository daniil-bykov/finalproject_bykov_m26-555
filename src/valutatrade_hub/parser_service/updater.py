import logging

from valutatrade_hub.core.exceptions import ApiRequestError

from .api_clients import CoinGeckoClient, ExchangeRateApiClient
from .storage import RatesStorage


class RatesUpdater:
    def __init__(self):
        self.crypto_client = CoinGeckoClient()
        self.fiat_client = ExchangeRateApiClient()
        self.storage = RatesStorage()

    def run_update(self, source: str = "all"):
        """Запускает обновление курсов."""
        logging.info("Starting rates update...")
        all_rates = {}

        # 1. Получаем крипту
        if source in ("all", "coingecko"):
            try:
                logging.info("Fetching from CoinGecko...")
                crypto_rates = self.crypto_client.fetch_rates()
                all_rates.update(crypto_rates)
                logging.info(f"CoinGecko OK ({len(crypto_rates)} rates)")
            except ApiRequestError as e:
                logging.error(f"Failed to fetch from CoinGecko: {e}")

        # 2. Получаем фиат
        if source in ("all", "exchangerate"):
            try:
                logging.info("Fetching from ExchangeRate-API...")
                fiat_rates = self.fiat_client.fetch_rates()
                all_rates.update(fiat_rates)
                logging.info(f"ExchangeRate-API OK ({len(fiat_rates)} rates)")
            except ApiRequestError as e:
                logging.error(f"Failed to fetch from ExchangeRate-API: {e}")

        # 3. Сохраняем
        if all_rates:
            logging.info(f"Writing {len(all_rates)} rates to data/rates.json...")
            self.storage.save_rates(all_rates, source="ParserService")
            self.storage.append_history(all_rates, source="ParserService")
            logging.info(f"Update successful. Total rates updated: {len(all_rates)}")
        else:
            logging.warning("No rates were fetched.")