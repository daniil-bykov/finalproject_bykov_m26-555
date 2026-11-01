import logging
from threading import Lock

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import utc_timestamp

from .api_clients import CoinGeckoClient, ExchangeRateApiClient
from .storage import RatesStorage


class RatesUpdater:
    """Последовательно собирает курсы источников и сохраняет общие данные."""

    _update_lock = Lock()

    def __init__(self, crypto_client=None, fiat_client=None, storage=None):
        """Подготавливает объекты для загрузки и сохранения курсов."""
        self.crypto_client = (
            CoinGeckoClient() if crypto_client is None else crypto_client
        )
        self.fiat_client = (
            ExchangeRateApiClient() if fiat_client is None else fiat_client
        )
        self.storage = RatesStorage() if storage is None else storage
        self.errors = {}
        self.last_refresh = None
        self.fetched_count = 0

    def _fetch_rates(self, client):
        source = client.source
        try:
            logging.info(f"Fetching from {source}...")
            rates = client.fetch_rates()
        except ApiRequestError as error:
            self.errors[source] = error.reason
            logging.error(f"Failed to fetch from {source}: {error}")
            return None
        received_at = client.received_at or utc_timestamp()
        logging.info(f"{source} OK ({len(rates)} rates)")
        return {
            "rates": rates,
            "sources": {pair: source for pair in rates},
            "timestamps": {pair: received_at for pair in rates},
            "metadata": client.metadata,
        }

    def _collect_rates(self, source):
        clients = {"coingecko": self.crypto_client, "exchangerate": self.fiat_client}
        if source != "all" and source not in clients:
            raise ValueError("Источник должен быть all, coingecko или exchangerate")
        batch = {"rates": {}, "sources": {}, "timestamps": {}, "metadata": {}}
        selected = clients.values() if source == "all" else [clients[source]]
        for client in selected:
            result = self._fetch_rates(client)
            if result is not None:
                for key in batch:
                    batch[key].update(result[key])
        return batch

    def _save_rates(self, batch):
        rates = batch["rates"]
        logging.info(f"Appending {len(rates)} rates to history...")
        self.storage.append_history(
            rates,
            source=batch["sources"],
            timestamps=batch["timestamps"],
            metadata=batch["metadata"],
        )
        logging.info(f"Writing {len(rates)} rates to cache...")
        return self.storage.save_rates(
            rates, source=batch["sources"], timestamps=batch["timestamps"]
        )

    def run_update(self, source="all"):
        """Загружает и сохраняет курсы из выбранных источников.

        Возвращает словарь курсов, обновлённых в rates.json.
        """
        with self._update_lock:
            self.errors = {}
            self.last_refresh = None
            self.fetched_count = 0
            logging.info("Starting rates update...")
            try:
                batch = self._collect_rates(source)
                self.fetched_count = len(batch["rates"])
                if not batch["rates"]:
                    logging.warning("Rates update finished without fresh rates.")
                    return {}
                saved = self._save_rates(batch)
                self.last_refresh = saved["last_refresh"]
                updated = saved["rates"]
            except Exception as error:
                logging.error(f"Rates update failed: {type(error).__name__}: {error}")
                raise
            if self.errors:
                logging.warning(
                    f"Update completed with errors. Total rates updated: {len(updated)}"
                )
            else:
                logging.info(f"Update successful. Total rates updated: {len(updated)}")
            return updated
