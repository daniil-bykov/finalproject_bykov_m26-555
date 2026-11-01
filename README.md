# ValutaTrade Hub

Консольное приложение для симуляции торговли валютами с реальными курсами из интернета.

## Возможности

- Регистрация и вход пользователей (пароли хешируются).
- Управление портфелем: покупка и продажа валют.
- Получение актуальных курсов из CoinGecko (крипта) и ExchangeRate-API (фиат).
- Кэширование курсов в `data/rates.json`.
- Логирование операций в `logs/actions.log`.

## Установка и запуск

Требуются Python 3.12 или новее и uv.

1. Склонируйте репозиторий и перейдите в его папку:

   ```bash
   git clone https://github.com/daniil-bykov/finalproject_bykov_m26-555.git
   cd finalproject_bykov_m26-555
   ```
2. Создайте файл `.env` в корне проекта и добавьте туда ключ от ExchangeRate-API:

   ```dotenv
   EXCHANGERATE_API_KEY=ваш_ключ
   ```

3. Установите зависимости и запустите:

   ```bash
   uv sync --locked
   uv run wallet
   ```

## Основные команды

- `register --username <имя> --password <пароль>` — зарегистрироваться.
- `login --username <имя> --password <пароль>` — войти и обновить курсы.
- `update-rates [--source coingecko|exchangerate]` — обновить курсы из всех источников или выбранного.
- `show-rates [--currency <код>] [--top <N>] [--base <код>]` — показать курсы из кэша; `--top` выбирает свежие курсы криптовалют.
- `get-rate --from <код> --to <код>` — узнать курс.
- `buy --currency <код> --amount <число>` — купить валюту.
- `sell --currency <код> --amount <число>` — продать валюту.
- `show-portfolio [--base <код>]` — показать портфель в выбранной базовой валюте.
- `exit` — выйти.

## Пример работы

После запуска `wallet` вводите команды по очереди:

```text
register --username alice --password demo1234
login --username alice --password demo1234
buy --currency BTC --amount 0.05
sell --currency BTC --amount 0.02
show-portfolio
get-rate --from BTC --to USD
update-rates
show-rates --top 2
sell --currency BTC --amount 1
get-rate --from XYZ --to USD
exit
```

## Демонстрация работы

Запись полного цикла программы: [смотреть на asciinema.org](https://asciinema.org/a/6m44gaTkBVuy660U) — 3 минуты 29 секунд.
Локальный файл записи: [demo.cast](demo.cast).

## Структура проекта

```text
finalproject_bykov_m26-555/
├── data/
│   ├── users.json
│   ├── portfolios.json
│   ├── rates.json
│   └── exchange_rates.json
├── valutatrade_hub/
│   ├── __init__.py
│   ├── logging_config.py
│   ├── decorators.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── currencies.py
│   │   ├── exceptions.py
│   │   ├── models.py
│   │   ├── utils.py
│   │   └── usecases.py
│   ├── parser_service/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── api_clients.py
│   │   ├── updater.py
│   │   ├── storage.py
│   │   └── scheduler.py
│   ├── infra/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── database.py
│   └── cli/
│       ├── __init__.py
│       └── interface.py
├── main.py
├── uv.lock
├── pyproject.toml
├── demo.cast
├── README.md
└── .gitignore
```

В `core/utils.py` находятся общие функции чтения данных, проверки паролей,
валютных пар и курсов, преобразования времени и расчёта стоимости портфеля.

При установке и работе появляются локальные служебные файлы: `.venv/`,
`__pycache__/`, `logs/`, `.env` и `data/.storage.lock`. Они исключены через `.gitignore`
и не входят в состав файлов проекта в Git.

`.storage.lock` координирует запись данных, если одновременно запущены несколько
экземпляров программы. После закрытия программы блокировка освобождается автоматически.

## Обновление курсов

Папка данных, TTL, часовой интервал обновления, базовая валюта портфеля и параметры логов задаются в `[tool.valutatrade]` файла `pyproject.toml`. API-ключ остаётся в `.env`.

Курсы обновляются после успешного входа и затем раз в час, пока приложение открыто. Если запрошенный курс устарел или отсутствует в кэше, приложение пробует обновить его автоматически. Для ручного обновления используйте `update-rates`.

TTL — срок годности отдельного курса: по умолчанию 3900 секунд (65 минут). Если получить свежий курс не удалось, операция завершается понятной ошибкой; устаревший курс не используется.

## Как включить Parser Service

Parser Service включается автоматически после успешного `login`. Для дополнительного обновления вручную выполните команду `update-rates`.

Сервис получает курсы из CoinGecko и ExchangeRate-API, сохраняет их в `data/rates.json` и добавляет записи в историю `data/exchange_rates.json`.
