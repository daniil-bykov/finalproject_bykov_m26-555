# ValutaTrade Hub

Консольное приложение для симуляции торговли валютами с реальными курсами из интернета.

## Возможности

- Регистрация и вход пользователей (пароли хешируются).
- Управление портфелем: покупка и продажа валют.
- Получение актуальных курсов из CoinGecko (крипта) и ExchangeRate-API (фиат).
- Кэширование курсов в `data/rates.json`.
- Логирование операций в `logs/actions.log`.

## Установка и запуск

1. Склонируйте репозиторий.
2. Создайте файл `.env` в корне проекта и добавьте туда ключ от ExchangeRate-API:

EXCHANGERATE_API_KEY=ваш_ключ

3. Установите зависимости и запустите:
uv sync
uv run wallet

## Основные команды

- `register --username <имя> --password <пароль>` — зарегистрироваться.
- `login --username <имя> --password <пароль>` — войти.
- `update-rates` — обновить курсы из внешних API.
- `show-rates [--currency <код>] [--top <N>]` — показать актуальные курсы из кэша.
- `get-rate --from <код> --to <код>` — узнать курс.
- `buy --currency <код> --amount <число>` — купить валюту.
- `sell --currency <код> --amount <число>` — продать валюту.
- `show-portfolio` — показать портфель.
- `exit` — выйти.

## Структура проекта

- src/valutatrade_hub/core/ — бизнес-логика (модели, usecases, валюты).
- src/valutatrade_hub/infra/ — инфраструктура (настройки, база данных).
- src/valutatrade_hub/parser_service/ — сервис парсинга курсов из внешних API.
- src/valutatrade_hub/cli/ — интерфейс командной строки.

## Кэширование курсов (TTL)

Курсы валют сохраняются в data/rates.json. У каждой пары есть поле updated_at. Если с момента обновления прошло больше RATES_TTL_SECONDS (по умолчанию 300 секунд), курс считается устаревшим, и программа предложит выполнить update-rates.

## Как включить Parser Service

Для обновления курсов из интернета выполните команду: update-rates.

Она обратится к CoinGecko и ExchangeRate-API, сохранит данные в data/rates.json и добавит запись в историю data/exchange_rates.json.

## Демонстрация работы

[![asciicast](https://asciinema.org/a/AuMA24D6761r0qXY.svg)](https://asciinema.org/a/AuMA24D6761r0qXY)