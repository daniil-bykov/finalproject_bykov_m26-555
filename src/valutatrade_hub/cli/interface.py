import json
import shlex

from valutatrade_hub.core.usecases import (
    PortfolioManager,
    RateManager,
    UserManager,
)


def get_arg(args, name, default=None):
    """Безопасно извлекает значение аргумента из списка."""
    if name in args:
        return args[args.index(name) + 1]
    return default


def print_help():
    print("\nДоступные команды:")
    print("  register --username <имя> --password <пароль>")
    print("  login --username <имя> --password <пароль>")
    print("  show-portfolio [--base USD]")
    print("  buy --currency <код> --amount <число>")
    print("  sell --currency <код> --amount <число>")
    print("  get-rate --from <код> --to <код>")
    print("  show-rates [--currency <код>] [--top <N>]")
    print("  update-rates [--source coingecko|exchangerate]")
    print("  exit")


def cmd_register(args, user_manager, **_):
    """Регистрирует нового пользователя."""
    username = get_arg(args, "--username")
    password = get_arg(args, "--password")
    if not username or not password:
        print("Ошибка: нужны --username и --password")
        return None
    user_id = user_manager.register(username, password)
    print(f"Пользователь '{username}' зарегистрирован (id={user_id}).")
    print(f"Войдите: login --username {username} --password ****")
    return None


def cmd_login(args, user_manager, **_):
    """Выполняет вход пользователя в систему."""
    username = get_arg(args, "--username")
    password = get_arg(args, "--password")
    if not username or not password:
        print("Ошибка: нужны --username и --password")
        return None
    user = user_manager.login(username, password)
    print(f"Вы вошли как '{user.username}'")
    return user


def cmd_show_portfolio(args, current_user, portfolio_manager, rate_manager, **_):
    """Показывает портфель пользователя."""
    if not current_user:
        print("Сначала выполните login")
        return None
    base = get_arg(args, "--base", "USD").upper()
    portfolio = portfolio_manager.get_portfolio()
    print(f"Портфель пользователя '{current_user.username}' (база: {base}):")
    total = 0.0
    for code, wallet in portfolio.wallets.items():
        try:
            if code == base:
                value = wallet.balance
            else:
                rate = rate_manager.get_rate(code, base)
                value = wallet.balance * rate
            print(f"- {code}: {wallet.balance:.4f} → {value:.2f} {base}")
            total += value
        except Exception:
            print(f"- {code}: {wallet.balance:.4f} (курс недоступен)")
    print(f"{'-'*33}\nИТОГО: {total:.2f} {base}")
    return None


def cmd_buy(args, current_user, portfolio_manager, rate_manager, **_):
    """Покупает валюту."""
    if not current_user:
        print("Сначала выполните login")
        return None
    currency = get_arg(args, "--currency", "").upper()
    amount = float(get_arg(args, "--amount", 0))
    try:
        rate = rate_manager.get_rate(currency, "USD")
    except Exception as e:
        print(f"Ошибка: {e}")
        return None
    wallet = portfolio_manager.buy_currency(currency, amount)
    print(f"Покупка выполнена: {amount} {currency} по курсу {rate} USD/{currency}")
    print(f"Изменения в портфеле: - {currency}: стало {wallet.balance:.4f}")
    print(f"Оценочная стоимость покупки: {amount * rate:.2f} USD")
    return None


def cmd_sell(args, current_user, portfolio_manager, rate_manager, **_):
    """Продает валюту."""
    if not current_user:
        print("Сначала выполните login")
        return None
    currency = get_arg(args, "--currency", "").upper()
    amount = float(get_arg(args, "--amount", 0))
    try:
        rate = rate_manager.get_rate(currency, "USD")
    except Exception as e:
        print(f"Ошибка: {e}")
        return None
    wallet = portfolio_manager.sell_currency(currency, amount)
    print(f"Продажа выполнена: {amount} {currency} по курсу {rate} USD/{currency}")
    print(f"Изменения в портфеле: - {currency}: стало {wallet.balance:.4f}")
    print(f"Оценочная выручка: {amount * rate:.2f} USD")
    return None


def cmd_get_rate(args, rate_manager, **_):
    """Показывает курс между валютами."""
    from_currency = get_arg(args, "--from", "").upper()
    to_currency = get_arg(args, "--to", "").upper()
    try:
        rate = rate_manager.get_rate(from_currency, to_currency)
        reverse_rate = 1 / rate
        print(f"Курс {from_currency}→{to_currency}: {rate:.8f}")
        print(f"Обратный курс {to_currency}→{from_currency}: {reverse_rate:.2f}")
    except Exception as e:
        print(f"Ошибка: {e}")
    return None


def cmd_show_rates(args, **_):
    """Показывает кэш курсов."""
    from valutatrade_hub.parser_service.config import ParserConfig

    config = ParserConfig()
    try:
        with open(config.RATES_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Локальный кеш курсов пуст. Выполните 'update-rates'.")
        return None

    pairs = data.get("pairs", {})
    last_refresh = data.get("last_refresh", "неизвестно")

    if "--currency" in args:
        cur = get_arg(args, "--currency").upper()
        filtered = {k: v for k, v in pairs.items() if cur in k}
    else:
        filtered = pairs

    items = list(filtered.items())
    if "--top" in args:
        n = int(get_arg(args, "--top"))
        items.sort(key=lambda x: x[1]["rate"], reverse=True)
        items = items[:n]

    print(f"Rates from cache (updated at {last_refresh}):")
    for pair, info in items:
        print(f"- {pair}: {info['rate']}")
    return None


def cmd_update_rates(args, **_):
    """Обновляет курсы из внешних API."""
    from valutatrade_hub.parser_service.updater import RatesUpdater

    source = get_arg(args, "--source", "all")
    try:
        updater = RatesUpdater()
        updater.run_update(source=source)
        print("Курсы успешно обновлены.")
    except Exception as e:
        print(f"Ошибка при обновлении курсов: {e}")
    return None


def run_cli():
    """Запускает основной цикл CLI."""
    user_manager = UserManager()
    rate_manager = RateManager()
    current_user = None
    portfolio_manager = None

    commands = {
        "register": cmd_register,
        "login": cmd_login,
        "show-portfolio": cmd_show_portfolio,
        "buy": cmd_buy,
        "sell": cmd_sell,
        "get-rate": cmd_get_rate,
        "show-rates": cmd_show_rates,
        "update-rates": cmd_update_rates,
    }

    print("Добро пожаловать в ValutaTrade Hub! Введите 'help' для списка команд.")

    while True:
        try:
            command_line = input("> ").strip()
            if not command_line:
                continue
            args = shlex.split(command_line)
            command = args[0]

            if command == "exit":
                print("Выход...")
                break
            elif command == "help":
                print_help()
            elif command in commands:
                context = {
                    "user_manager": user_manager,
                    "rate_manager": rate_manager,
                    "current_user": current_user,
                    "portfolio_manager": portfolio_manager,
                }
                result = commands[command](args, **context)
                if command == "login" and result is not None:
                    current_user = result
                    portfolio_manager = PortfolioManager(current_user)
            else:
                print(f"Неизвестная команда: {command}. Введите 'help' для справки.")
        except Exception as e:
            print(f"Ошибка: {e}")