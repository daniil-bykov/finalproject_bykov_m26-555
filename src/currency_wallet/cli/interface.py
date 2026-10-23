import shlex

from currency_wallet.core.usecases import UserManager, PortfolioManager


def run_cli():
    """Запускает основной цикл CLI."""
    user_manager = UserManager()
    current_user = None
    portfolio_manager = None

    print("Добро пожаловать в Currency Wallet!")

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
            elif command == "register":
                # register --username alice --password 1234
                username = args[args.index("--username") + 1]
                password = args[args.index("--password") + 1]
                user_id = user_manager.register(username, password)
                print(f"Пользователь '{username}' зарегистрирован (id={user_id}).")
            elif command == "login":
                # login --username alice --password 1234
                username = args[args.index("--username") + 1]
                password = args[args.index("--password") + 1]
                current_user = user_manager.login(username, password)
                portfolio_manager = PortfolioManager(current_user)
                print(f"Вы вошли как '{current_user.username}'")
            elif command == "show-portfolio":
                if not current_user:
                    print("Сначала выполните login")
                    continue
                portfolio = portfolio_manager.get_portfolio()
                print(f"Портфель пользователя '{current_user.username}':")
                total = portfolio.get_total_value()
                for code, wallet in portfolio.wallets.items():
                    print(f"- {code}: {wallet.balance:.4f}")
                print(f"ИТОГО: {total:.2f} USD")
            elif command == "buy":
                # buy --currency BTC --amount 0.05
                if not current_user:
                    print("Сначала выполните login")
                    continue
                currency = args[args.index("--currency") + 1].upper()
                amount = float(args[args.index("--amount") + 1])
                portfolio_manager.buy_currency(currency, amount)
                print(f"Покупка выполнена: {amount} {currency}")
            elif command == "sell":
                if not current_user:
                    print("Сначала выполните login")
                    continue
                currency = args[args.index("--currency") + 1].upper()
                amount = float(args[args.index("--amount") + 1])
                portfolio_manager.sell_currency(currency, amount)
                print(f"Продажа выполнена: {amount} {currency}")
            else:
                print(f"Неизвестная команда: {command}")
                
        except Exception as e:
            print(f"Ошибка: {e}")