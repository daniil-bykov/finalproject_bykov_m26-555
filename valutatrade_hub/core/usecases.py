import logging
from datetime import datetime, timedelta, timezone
from math import isfinite
from threading import RLock

from valutatrade_hub.core.currencies import (
    CryptoCurrency,
    get_currency,
    get_currency_codes,
)
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.utils import (
    create_password_hash,
    load_portfolios,
    load_rates,
    load_user,
    load_users,
    value_portfolio,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import RATES_BASE_CURRENCY, SettingsLoader
from valutatrade_hub.parser_service.scheduler import RatesScheduler
from valutatrade_hub.parser_service.updater import RatesUpdater

from .models import Portfolio, User, Wallet


class UserManager:
    """Регистрация и проверка учётных данных через JSON-хранилище."""

    def __init__(self):
        self.database = DatabaseManager()

    @property
    def users(self):
        """Читает актуальный список пользователей из хранилища."""
        return load_users()

    @property
    def portfolios(self):
        """Читает актуальный список сохранённых портфелей."""
        return load_portfolios()

    @staticmethod
    def _make_user(data):
        return User.from_dict(data)

    @log_action("REGISTER")
    def register(self, username, password):
        """Создаёт пользователя и пустой портфель в одной безопасной операции."""
        User.validate_username(username)
        hashed_password, salt = create_password_hash(password)

        with self.database.transaction("users.json", "portfolios.json") as documents:
            users = documents["users.json"]
            if any(user["username"] == username for user in users):
                raise ValueError(f"Имя пользователя '{username}' уже занято")
            user_id = max((user["user_id"] for user in users), default=0) + 1
            users.append(
                {
                    "user_id": user_id,
                    "username": username,
                    "hashed_password": hashed_password,
                    "salt": salt,
                    "registration_date": datetime.now().isoformat(),
                }
            )
            documents["portfolios.json"].append({"user_id": user_id, "wallets": {}})
        return user_id

    @log_action("LOGIN")
    def login(self, username, password):
        """Проверяет учётные данные и возвращает пользователя."""
        user_data = next(
            (user for user in self.users if user["username"] == username), None
        )
        if user_data is None:
            raise ValueError(f"Пользователь '{username}' не найден")
        user = self._make_user(user_data)
        if not isinstance(password, str) or not user.verify_password(password):
            raise ValueError("Неверный пароль")
        return user

    def get_user(self, user_id):
        """Возвращает пользователя по ID или сообщает об его отсутствии."""
        return self._make_user(load_user(user_id))


class PortfolioManager:
    """Покупка, продажа и оценка портфеля выбранного пользователя."""

    def __init__(self, user: User, rate_manager=None):
        self.user = user
        self.database = DatabaseManager()
        self.rate_manager = rate_manager if rate_manager is not None else RateManager()

    @property
    def portfolio_data(self):
        """Возвращает актуальную JSON-запись портфеля либо пустой портфель."""
        return next(
            (row for row in load_portfolios() if row["user_id"] == self.user.user_id),
            {"user_id": self.user.user_id, "wallets": {}},
        )

    @staticmethod
    def _make_portfolio(data):
        wallets = {
            code: Wallet(code, entry["balance"])
            for code, entry in data["wallets"].items()
        }
        return Portfolio(data["user_id"], wallets)

    def get_portfolio(self) -> Portfolio:
        """Восстанавливает модель портфеля с проверенными балансами."""
        return self._make_portfolio(self.portfolio_data)

    @log_action("BUY", verbose=True)
    def buy_currency(self, currency_code, amount):
        """Пополняет кошелёк и возвращает сохранённые балансы и стоимость."""
        return self._trade(currency_code, amount, selling=False)

    @log_action("SELL", verbose=True)
    def sell_currency(self, currency_code, amount):
        """Списывает валюту и возвращает балансы и оценочную выручку."""
        return self._trade(currency_code, amount, selling=True)

    def _prepare_trade(self, currency_code, amount):
        code = get_currency(currency_code).code
        amount = Wallet.validate_amount(amount)
        wallet = self.get_portfolio().wallets.get(code)
        balance = wallet.balance if wallet else 0.0
        return {
            "base": RATES_BASE_CURRENCY,
            "currency_code": code,
            "amount": amount,
            "balance_before": balance,
            "balance_after": balance,
        }

    @staticmethod
    def _check_funds(available, code, amount):
        if available < amount:
            raise InsufficientFundsError(available, code, amount)

    def _apply_trade(self, portfolios, details, selling):
        code, amount = details["currency_code"], details["amount"]
        data = next(
            (row for row in portfolios if row["user_id"] == self.user.user_id), None
        )
        if data is None:
            data = {"user_id": self.user.user_id, "wallets": {}}
            portfolios.append(data)
        portfolio = self._make_portfolio(data)
        wallet = portfolio.wallets.get(code)
        before = wallet.balance if wallet else 0.0
        details.update(balance_before=before, balance_after=before)
        if selling:
            self._check_funds(before, code, amount)
            wallet.withdraw(amount)
        else:
            if wallet is None:
                portfolio.add_currency(code)
                wallet = portfolio.get_wallet(code)
            wallet.deposit(amount)
        data["wallets"] = {
            currency: {"balance": item.balance}
            for currency, item in portfolio.wallets.items()
        }
        return wallet.balance

    def _save_trade(self, details, selling):
        with self.database.transaction("portfolios.json") as documents:
            after = self._apply_trade(documents["portfolios.json"], details, selling)
        # Баланс "после" меняется только после успешной записи.
        details["balance_after"] = after

    def _trade(self, currency_code, amount, *, selling):
        details = {"base": RATES_BASE_CURRENCY}
        try:
            details.update(self._prepare_trade(currency_code, amount))
            if selling:
                self._check_funds(
                    details["balance_before"],
                    details["currency_code"],
                    details["amount"],
                )
            # Сеть вызывается до блокировки изменения портфеля.
            quote = self.rate_manager.get_rate(
                details["currency_code"], details["base"]
            )
            details.update(rate=quote["rate"], updated_at=quote["updated_at"])
            estimated_value = details["amount"] * quote["rate"]
            if not isfinite(estimated_value):
                raise ValueError("Оценочная стоимость операции слишком велика")
            self._save_trade(details, selling)
            details["estimated_value"] = estimated_value
            return details
        except Exception as error:
            error.action_details = details
            raise

    def get_summary(self, base=None):
        """Оценивает портфель, отмечая кошельки с недоступными курсами."""
        return value_portfolio(
            self.get_portfolio().wallets,
            base,
            self.rate_manager.get_rate,
            allow_partial=True,
        )


class RateManager:
    """Чтение курсов с проверкой TTL, обновление и управление таймером."""

    _refresh_lock = RLock()

    def __init__(self):
        self.settings = SettingsLoader()
        self.scheduler = None

    @staticmethod
    def _timestamp(value):
        return datetime.fromisoformat(value).astimezone(timezone.utc)

    def _is_fresh(self, updated_at_str):
        try:
            updated_at = self._timestamp(updated_at_str)
            ttl = self.settings.get("rates_ttl_seconds")
            age = datetime.now(timezone.utc) - updated_at
            return timedelta(0) <= age < timedelta(seconds=ttl)
        except (ValueError, TypeError, OverflowError):
            return False

    def _entry_quote(self, entry, *, inverse=False, allow_stale=False):
        if not isinstance(entry, dict):
            return None
        rate = entry.get("rate")
        try:
            if type(rate) not in (int, float) or not isfinite(rate) or rate <= 0:
                return None
            rate = 1.0 / rate if inverse else float(rate)
            if not isfinite(rate):
                return None
            timestamp = self._timestamp(entry.get("updated_at"))
        except (ValueError, TypeError, OverflowError, ZeroDivisionError):
            return None
        if not allow_stale and not self._is_fresh(entry.get("updated_at")):
            return None
        return {
            "rate": rate,
            "updated_at": timestamp.isoformat().replace("+00:00", "Z"),
        }

    def _pair_quote(self, pairs, from_code, to_code, *, allow_stale=False):
        return self._entry_quote(
            pairs.get(f"{from_code}_{to_code}"), allow_stale=allow_stale
        ) or self._entry_quote(
            pairs.get(f"{to_code}_{from_code}"), inverse=True, allow_stale=allow_stale
        )

    def _quote_from_pairs(self, pairs, from_code, to_code, *, allow_stale=False):
        if not isinstance(pairs, dict):
            raise ValueError("Некорректная структура кэша курсов")
        quote = self._pair_quote(pairs, from_code, to_code, allow_stale=allow_stale)
        if quote is not None:
            return quote
        if from_code != RATES_BASE_CURRENCY and to_code != RATES_BASE_CURRENCY:
            first = self._pair_quote(
                pairs, from_code, RATES_BASE_CURRENCY, allow_stale=allow_stale
            )
            second = self._pair_quote(
                pairs, to_code, RATES_BASE_CURRENCY, allow_stale=allow_stale
            )
            if first and second:
                rate = first["rate"] / second["rate"]
                if isfinite(rate) and rate > 0:
                    timestamp = min(
                        first["updated_at"], second["updated_at"], key=self._timestamp
                    )
                    return {"rate": rate, "updated_at": timestamp}
        return None

    def _cached_quote(self, from_code, to_code):
        return self._quote_from_pairs(load_rates().get("pairs", {}), from_code, to_code)

    def get_rate(self, from_code, to_code):
        """Возвращает rate и updated_at; устаревший/отсутствующий курс обновляет."""
        from_code = get_currency(from_code).code
        to_code = get_currency(to_code).code
        if from_code == to_code:
            return {
                "rate": 1.0,
                "updated_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        quote = self._cached_quote(from_code, to_code)
        if quote is not None:
            return quote
        refresh_error = None
        with self._refresh_lock:
            # Другой запрос мог уже обновить кэш, пока мы ждали блокировку.
            quote = self._cached_quote(from_code, to_code)
            if quote is not None:
                return quote
            try:
                self.update_rates()
            except ApiRequestError as error:
                refresh_error = error
            quote = self._cached_quote(from_code, to_code)
            if quote is not None:
                return quote
        pairs = load_rates().get("pairs", {})
        has_pair = (
            f"{from_code}_{to_code}" in pairs or f"{to_code}_{from_code}" in pairs
        )
        has_cross = (
            f"{from_code}_{RATES_BASE_CURRENCY}" in pairs
            or f"{RATES_BASE_CURRENCY}_{from_code}" in pairs
        ) and (
            f"{to_code}_{RATES_BASE_CURRENCY}" in pairs
            or f"{RATES_BASE_CURRENCY}_{to_code}" in pairs
        )
        reason = (
            "устарел или некорректен" if has_pair or has_cross else "отсутствует в кэше"
        )
        raise ApiRequestError(
            f"Курс {from_code}→{to_code} {reason}. "
            "Обновление не дало свежего курса. Повторите update-rates позже."
        ) from refresh_error

    def get_rate_details(self, from_code, to_code):
        """Возвращает курсы в обоих направлениях, коды валют и время обновления."""
        quote = self.get_rate(from_code, to_code)
        reverse_rate = 1.0 / quote["rate"]
        if not isfinite(reverse_rate):
            raise ApiRequestError("Обратный курс слишком велик для расчёта")
        return {
            **quote,
            "from_currency": from_code.upper(),
            "to_currency": to_code.upper(),
            "reverse_rate": reverse_rate,
        }

    def update_rates(self, source="all"):
        """Обновляет выбранные источники и возвращает изменённые пары."""
        return self.update_rates_details(source)["rates"]

    def update_rates_details(self, source="all"):
        """Обновляет курсы и возвращает отчёт, включая частичные сбои источников."""
        if source not in ("all", "coingecko", "exchangerate"):
            raise ValueError("Источник должен быть all, coingecko или exchangerate")
        with self._refresh_lock:
            try:
                updater = RatesUpdater()
                rates = updater.run_update(source=source)
            except ApiRequestError:
                raise
            except (OSError, ValueError) as error:
                raise ApiRequestError(
                    "Не удалось сохранить обновлённые курсы"
                ) from error
            if not rates and updater.fetched_count == 0:
                reasons = "; ".join(updater.errors.values()) or "Попробуйте позже."
                raise ApiRequestError(f"Не удалось получить свежие курсы. {reasons}")
            return {
                "rates": rates,
                "errors": updater.errors.copy(),
                "last_refresh": updater.last_refresh,
                "log_file": self.settings.get("log_file"),
            }

    def refresh_after_login(self):
        """Обновляет курсы после входа и запускает таймер."""
        try:
            return self.update_rates()
        except ApiRequestError as error:
            logging.error(f"Не удалось обновить курсы после входа: {error}")
            raise
        finally:
            if self.scheduler is None:
                self.scheduler = RatesScheduler()
            self.scheduler.start()

    def close(self):
        """Останавливает таймер и дожидается начатого обновления."""
        if self.scheduler is not None:
            self.scheduler.stop()

    def _rate_list_items(self, pairs, codes, base, *, crypto_only=False):
        items = []
        for code in sorted(codes - {base}):
            try:
                currency = get_currency(code)
            except CurrencyNotFoundError:
                continue
            if crypto_only and not isinstance(currency, CryptoCurrency):
                continue
            quote = self._quote_from_pairs(pairs, code, base)
            if quote is None and not crypto_only:
                quote = self._quote_from_pairs(pairs, code, base, allow_stale=True)
            if quote is not None:
                items.append(
                    (
                        f"{code}_{base}",
                        {
                            **quote,
                            "is_stale": not self._is_fresh(quote["updated_at"]),
                        },
                    )
                )
        return items

    def show_rates(self, currency=None, top=None, base=None):
        """Показывает локальные котировки; просмотр не запускает запросы API."""
        if currency is not None:
            currency = currency.upper()
            try:
                get_currency(currency)
            except CurrencyNotFoundError as error:
                raise ValueError(f"Курс для '{currency}' не найден в кеше.") from error
        if top is not None and (type(top) is not int or top <= 0):
            raise ValueError("Количество курсов должно быть положительным целым числом")
        base = get_currency(RATES_BASE_CURRENCY if base is None else base).code
        snapshot = load_rates()
        pairs = snapshot.get("pairs", {})
        if not isinstance(pairs, dict):
            raise ValueError("Некорректная структура кэша курсов")
        if not pairs:
            raise ValueError(
                "Локальный кеш курсов пуст. "
                "Выполните 'update-rates', чтобы загрузить данные."
            )
        codes = (
            {currency}
            if currency
            else {code for pair in pairs for code in pair.split("_")}
        )
        items = self._rate_list_items(pairs, codes, base, crypto_only=top is not None)
        if not items:
            if top is not None:
                raise ValueError(
                    "В кеше нет актуальных курсов криптовалют для выбранных фильтров."
                )
            if currency is not None:
                raise ValueError(f"Курс для '{currency}' не найден в кеше.")
            raise ValueError(f"Курсы относительно '{base}' не найдены в кеше.")
        if top is not None:
            items.sort(key=lambda item: item[1]["rate"], reverse=True)
            items = items[:top]
        return {
            "items": items,
            "last_refresh": snapshot.get("last_refresh", "неизвестно"),
        }


def buy(user_id, currency_code, amount):
    """Покупает валюту для пользователя и возвращает сведения об операции."""
    return PortfolioManager(UserManager().get_user(user_id)).buy_currency(
        currency_code, amount
    )


def sell(user_id, currency_code, amount):
    """Продаёт валюту пользователя и возвращает сведения об операции."""
    return PortfolioManager(UserManager().get_user(user_id)).sell_currency(
        currency_code, amount
    )


def get_rate(from_code, to_code):
    """Возвращает свежий курс и updated_at либо пробрасывает ошибку."""
    return RateManager().get_rate(from_code, to_code)


def get_supported_currency_codes():
    """Возвращает доступные коды валют для CLI."""
    return get_currency_codes()
