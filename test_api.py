from currency_wallet.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)

print("--- Проверка CoinGecko ---")
try:
    cg = CoinGeckoClient()
    print(cg.fetch_rates())
except Exception as e:
    print("Ошибка CoinGecko:", e)

print("\n--- Проверка ExchangeRate-API ---")
try:
    er = ExchangeRateApiClient()
    print(er.fetch_rates())
except Exception as e:
    print("Ошибка ExchangeRate:", e)