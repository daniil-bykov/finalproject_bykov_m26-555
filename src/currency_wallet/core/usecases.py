import hashlib
import os
from datetime import datetime

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

    def buy_currency(self, currency_code, amount):
        portfolio = self.get_portfolio()
        if currency_code not in portfolio.wallets:
            portfolio.add_currency(currency_code)
        wallet = portfolio.get_wallet(currency_code)
        wallet.deposit(amount)
        self.save(portfolio)
        return wallet

    def sell_currency(self, currency_code, amount):
        portfolio = self.get_portfolio()
        wallet = portfolio.get_wallet(currency_code)
        wallet.withdraw(amount)
        self.save(portfolio)
        return wallet