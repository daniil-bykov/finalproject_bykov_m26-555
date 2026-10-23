from currency_wallet.infra.database import DatabaseManager


def load_users():
    return DatabaseManager().load("users.json")


def save_users(users):
    DatabaseManager().save("users.json", users)


def load_portfolios():
    return DatabaseManager().load("portfolios.json")


def save_portfolios(portfolios):
    DatabaseManager().save("portfolios.json", portfolios)


def load_rates():
    return DatabaseManager().load("rates.json")


def save_rates(rates):
    DatabaseManager().save("rates.json", rates)