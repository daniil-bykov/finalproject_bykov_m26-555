import hashlib
import os
from datetime import datetime, timedelta

from valutatrade_hub.core.exceptions import CurrencyNotFoundError
from valutatrade_hub.core.utils import load_rates
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader

from .models import Portfolio, User, Wallet
from .utils import load_portfolios, load_users, save_portfolios, save_users


class UserManager:
    def __init__(self):
        self.users = load_users()
        self.portfolios = load_portfolios()

    def _get_next_user_id(self):
        if not self.users:
            return 1
        return max(u["user_id"] for u in self.users) + 1

    def register(self, username, password):
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        
        if any(u["username"] == username for u in self.users):
            raise ValueError(f"Имя пользователя '{username}' уже занято")

        user_id = self._get_next_user_id()
        salt = os.urandom(4).hex()
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        
        new_user = {
            "user_id": user_id,
            "username": username,
            "hashed_password": hashed,
            "salt": salt,
            "registration_date": datetime.now().isoformat()
        }
        self.users.append(new_user)
        save_users(self.users)

        # Создаем пустой портфель
        new_portfolio = {
            "user_id": user_id,
            "wallets": {}
        }
        self.portfolios.append(new_portfolio)
        save_portfolios(self.portfolios)

        return user_id

    def login(self, username, password):
        user_data = next((u for u in self.users if u["username"] == username), None)
        if not user_data:
            raise ValueError(f"Пользователь '{username}' не найден")

        salt = user_data["salt"]
        check_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        if check_hash != user_data["hashed_password"]:
            raise ValueError("Неверный пароль")

        # Возвращаем объект User
        return User(
            user_id=user_data["user_id"],
            username=user_data["username"],
            hashed_password=user_data["hashed_password"],
            salt=user_data["salt"],
            registration_date=datetime.fromisoformat(user_data["registration_date"])
        )


class PortfolioManager:
    def __init__(self, user: User):
        self.user = user
        self.portfolios = load_portfolios()
        self.portfolio_data = next(
            (p for p in self.portfolios if p["user_id"] == user.user_id), None
        )
        if not self.portfolio_data:
            self.portfolio_data = {"user_id": user.user_id, "wallets": {}}
            self.portfolios.append(self.portfolio_data)
            save_portfolios(self.portfolios)

    def get_portfolio(self) -> Portfolio:
        # Восстанавливаем объекты Wallet из JSON
        wallets = {}
        for code, data in self.portfolio_data["wallets"].items():
            wallets[code] = Wallet(code, data["balance"])
        return Portfolio(self.user.user_id, wallets)

    def save(self, portfolio: Portfolio):
        # Сохраняем в JSON
        self.portfolio_data["wallets"] = {
            code: {"balance": w.balance}
            for code, w in portfolio.wallets.items()
        }
        save_portfolios(self.portfolios)

    @log_action("BUY")
    def buy_currency(self, currency_code, amount):
        portfolio = self.get_portfolio()
        if currency_code not in portfolio.wallets:
            portfolio.add_currency(currency_code)
        wallet = portfolio.get_wallet(currency_code)
        wallet.deposit(amount)
        self.save(portfolio)
        return wallet

    @log_action("SELL")
    def sell_currency(self, currency_code, amount):
        portfolio = self.get_portfolio()
        wallet = portfolio.get_wallet(currency_code)
        wallet.withdraw(amount)
        self.save(portfolio)
        return wallet


class RateManager:
    def __init__(self):
        self.rates = load_rates()
        self.settings = SettingsLoader()

    def _is_fresh(self, updated_at_str: str) -> bool:
        """Проверяет, не устарел ли курс (TTL)."""
        try:
            updated_at = datetime.fromisoformat(updated_at_str)
            ttl = self.settings.get("rates_ttl_seconds", 300)
            return datetime.now() - updated_at < timedelta(seconds=ttl)
        except (ValueError, TypeError):
            return False

    def get_rate(self, from_code: str, to_code: str) -> float:
        """Возвращает курс из кэша (загружает актуальный файл)."""

        self.rates = load_rates()
        
        from_code = from_code.upper()
        to_code = to_code.upper()
        pairs = self.rates.get("pairs", {})

        if from_code == to_code:
            return 1.0

        key = f"{from_code}_{to_code}"

        # 1. Прямой курс
        if key in pairs and self._is_fresh(pairs[key]["updated_at"]):
            return pairs[key]["rate"]

        # 2. Обратный курс
        reverse_key = f"{to_code}_{from_code}"
        if reverse_key in pairs and self._is_fresh(pairs[reverse_key]["updated_at"]):
            return 1.0 / pairs[reverse_key]["rate"]

        # 3. Кросс-курс через USD
        if from_code != "USD" and to_code != "USD":
            key_from_usd = f"{from_code}_USD"
            key_to_usd = f"{to_code}_USD"
            
            if key_from_usd in pairs and key_to_usd in pairs:
                rate_from = pairs[key_from_usd]["rate"]
                rate_to = pairs[key_to_usd]["rate"]
                return rate_from / rate_to

        raise CurrencyNotFoundError(
            f"Курс {from_code}→{to_code} недоступен. "
            f"Выполните 'update-rates', чтобы загрузить данные."
        )