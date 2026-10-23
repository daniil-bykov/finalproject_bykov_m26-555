import shlex

from valutatrade_hub.core.usecases import PortfolioManager, RateManager, UserManager


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


def run_cli():
    """Запускает основной цикл CLI."""
    user_manager = UserManager()
    rate_manager = RateManager()
    current_user = None
    portfolio_manager = None

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
            
            elif command == "register":
                username = args[args.index("--username") + 1]
                password = args[args.index("--password") + 1]
                user_id = user_manager.register(username, password)
                print(f"Пользователь '{username}' зарегистрирован (id={user_id}).")
                print(f"Войдите: login --username {username} --password ****")
            
            elif command == "login":
                username = args[args.index("--username") + 1]
                password = args[args.index("--password") + 1]
                current_user = user_manager.login(username, password)
                portfolio_manager = PortfolioManager(current_user)
                print(f"Вы вошли как '{current_user.username}'")
            
            elif command == "show-portfolio":
                if not current_user:
                    print("Сначала выполните login")
                    continue
                
                base = "USD"
                if "--base" in args:
                    base = args[args.index("--base") + 1].upper()
                
                portfolio = portfolio_manager.get_portfolio()
                print(f"Портфель пользователя '{current_user.username}' "
                      f"(база: {base}):")
                
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
            
            elif command == "buy":
                if not current_user:
                    print("Сначала выполните login")
                    continue
                
                currency = args[args.index("--currency") + 1].upper()
                amount = float(args[args.index("--amount") + 1])
                
                try:
                    rate = rate_manager.get_rate(currency, "USD")
                except Exception as e:
                    print(f"Ошибка: {e}")
                    continue
                
                wallet = portfolio_manager.buy_currency(currency, amount)
                print(f"Покупка выполнена: {amount} {currency} "
                      f"по курсу {rate} USD/{currency}")
                print(f"Изменения в портфеле: - {currency}: стало {wallet.balance:.4f}")
                print(f"Оценочная стоимость покупки: {amount * rate:.2f} USD")
            
            elif command == "sell":
                if not current_user:
                    print("Сначала выполните login")
                    continue
                
                currency = args[args.index("--currency") + 1].upper()
                amount = float(args[args.index("--amount") + 1])
                
                try:
                    rate = rate_manager.get_rate(currency, "USD")
                except Exception as e:
                    print(f"Ошибка: {e}")
                    continue
                
                wallet = portfolio_manager.sell_currency(currency, amount)
                print(f"Продажа выполнена: {amount} {currency} "
                      f"по курсу {rate} USD/{currency}")
                print(f"Изменения в портфеле: - {currency}: стало {wallet.balance:.4f}")
                print(f"Оценочная выручка: {amount * rate:.2f} USD")
         
            elif command == "get-rate":
                from_currency = args[args.index("--from") + 1].upper()
                to_currency = args[args.index("--to") + 1].upper()
                
                try:
                    rate = rate_manager.get_rate(from_currency, to_currency)
                    reverse_rate = 1 / rate
                    print(f"Курс {from_currency}→{to_currency}: {rate:.8f}")
                    print(f"Обратный курс {to_currency}→{from_currency}: "
                          f"{reverse_rate:.2f}")
                except Exception as e:
                    print(f"Ошибка: {e}")

            elif command == "show-rates":
                # show-rates [--currency BTC] [--top 2] [--base USD]
                import json

                from valutatrade_hub.parser_service.config import ParserConfig
                
                config = ParserConfig()
                try:
                    with open(config.RATES_FILE_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except FileNotFoundError:
                    print("Локальный кеш курсов пуст. Выполните 'update-rates'.")
                    continue
                
                pairs = data.get("pairs", {})
                last_refresh = data.get("last_refresh", "неизвестно")
                
                # Фильтр по валюте
                if "--currency" in args:
                    cur = args[args.index("--currency") + 1].upper()
                    filtered = {k: v for k, v in pairs.items() if cur in k}
                else:
                    filtered = pairs
                
                # Сортировка по значению для --top
                items = list(filtered.items())
                if "--top" in args:
                    n = int(args[args.index("--top") + 1])
                    items.sort(key=lambda x: x[1]["rate"], reverse=True)
                    items = items[:n]
                
                print(f"Rates from cache (updated at {last_refresh}):")
                for pair, info in items:
                    print(f"- {pair}: {info['rate']}")

            elif command == "update-rates":
                # update-rates --source coingecko
                from valutatrade_hub.parser_service.updater import RatesUpdater
                
                source = "all"
                if "--source" in args:
                    source = args[args.index("--source") + 1]
                
                try:
                    updater = RatesUpdater()
                    updater.run_update(source=source)
                    print("Курсы успешно обновлены.")
                except Exception as e:
                    print(f"Ошибка при обновлении курсов: {e}")
            
            else:
                print(f"Неизвестная команда: {command}. Введите 'help' для справки.")
                
        except Exception as e:
            print(f"Ошибка: {e}")