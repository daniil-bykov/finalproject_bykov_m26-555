import shlex
from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.core.usecases import (
    PortfolioManager,
    RateManager,
    UserManager,
    get_supported_currency_codes,
)

COMMAND_ARGUMENTS = {
    "register": {"--username", "--password"},
    "login": {"--username", "--password"},
    "show-portfolio": {"--base"},
    "buy": {"--currency", "--amount"},
    "sell": {"--currency", "--amount"},
    "get-rate": {"--from", "--to"},
    "show-rates": {"--currency", "--top", "--base"},
    "update-rates": {"--source"},
    "help": set(),
    "exit": set(),
}


def format_update_time(value):
    """Показывает дату и время обновления в UTC без долей секунды."""
    try:
        timestamp = datetime.fromisoformat(value).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return "неизвестно"
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")


def print_error(error):
    """Показывает ошибку и подсказку для неизвестной валюты или сбоя API."""
    print(f"Ошибка: {error}")
    if isinstance(error, CurrencyNotFoundError):
        codes = ", ".join(get_supported_currency_codes())
        print(f"Поддерживаемые валюты: {codes}")
    elif isinstance(error, ApiRequestError):
        print("Повторите попытку позже; при сетевой ошибке проверьте подключение.")


def get_arg(args, name, default=None):
    """Находит значение параметра команды и проверяет, что оно указано."""
    if name not in args:
        return default
    if args.count(name) > 1:
        raise ValueError(f"Аргумент {name} указан несколько раз")

    value_index = args.index(name) + 1
    if value_index >= len(args):
        raise ValueError(f"Укажите значение для {name}")
    value = args[value_index]
    if not value.strip() or value.startswith("--"):
        raise ValueError(f"Укажите значение для {name}")
    return value


def validate_args(args):
    """Проверяет, что параметры команды допустимы и для них указаны значения."""
    command = args[0]
    allowed = COMMAND_ARGUMENTS[command]
    index = 1
    while index < len(args):
        name = args[index]
        if name not in allowed:
            if name.startswith("--"):
                raise ValueError(
                    f"Неизвестный аргумент '{name}' для команды '{command}'"
                )
            raise ValueError(f"Лишний позиционный аргумент для команды '{command}'")
        get_arg(args, name)
        index += 2


def get_number_arg(args, name, conversion, message, default=None):
    """Преобразует аргумент в число, сохраняя понятное сообщение при опечатке."""
    value = get_arg(args, name, default)
    if value is None:
        return None
    try:
        return conversion(value)
    except (ValueError, TypeError) as error:
        raise ValueError(message) from error


def print_help():
    """Выводит список доступных команд и показывает, как их вводить."""
    print("\nДоступные команды:")
    print("  register --username <имя> --password <пароль>")
    print("  login --username <имя> --password <пароль>")
    print("  show-portfolio [--base <код>]")
    print("  buy --currency <код> --amount <число>")
    print("  sell --currency <код> --amount <число>")
    print("  get-rate --from <код> --to <код>")
    print("  show-rates [--currency <код>] [--top <N>] [--base <код>]")
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


def refresh_rates_after_login(rate_manager):
    """Обновляет курсы после входа и сообщает об ошибках."""
    print("Обновляем курсы валют...")
    try:
        rate_manager.refresh_after_login()
    except ApiRequestError as error:
        print(f"Не удалось обновить курсы: {error}")
        print("Таймер повторит обновление автоматически.")


def cmd_show_portfolio(args, current_user, portfolio_manager, **_):
    """Показывает кошельки и общую оценку, полученные из usecase."""
    if not current_user:
        print("Сначала выполните login")
        return
    summary = portfolio_manager.get_summary(get_arg(args, "--base"))
    base = summary["base"]
    total = f"{summary['total']:.2f}".rstrip("0").rstrip(".")
    note = "" if summary["complete"] else " (по доступным курсам)"
    print(f"Портфель пользователя '{current_user.username}': {total} {base}{note}")
    if not summary["items"]:
        print("Портфель пуст.")
        return
    for item in summary["items"]:
        code, balance = item["currency_code"], item["balance"]
        if item["value"] is None:
            print(f"- {code}: {balance:.4f} (курс недоступен: {item['error']})")
        else:
            print(f"- {code}: {balance:.4f} → {item['value']:.2f} {base}")
    label = "ИТОГО" if summary["complete"] else "ИТОГО по доступным курсам"
    print(f"{'-' * 33}\n{label}: {summary['total']:.2f} {base}")


def print_balance_change(result):
    """Показывает сохранённые балансы до и после операции."""
    print("Изменения в портфеле:")
    print(
        f"- {result['currency_code']}: было {result['balance_before']:.4f} "
        f"→ стало {result['balance_after']:.4f}"
    )


def cmd_buy(args, current_user, portfolio_manager, **_):
    """Вызывает покупку указанной валюты и выводит сведения о выполненной операции."""
    if not current_user:
        print("Сначала выполните login")
        return
    result = portfolio_manager.buy_currency(
        get_arg(args, "--currency", ""),
        get_number_arg(
            args, "--amount", float, "'amount' должен быть положительным числом", 0
        ),
    )
    currency = result["currency_code"]
    print(
        f"Покупка выполнена: {result['amount']} {currency} "
        f"по курсу {result['rate']:.2f} {result['base']}/{currency}"
    )
    print_balance_change(result)
    print(
        f"Оценочная стоимость покупки: {result['estimated_value']:.2f} {result['base']}"
    )


def cmd_sell(args, current_user, portfolio_manager, **_):
    """Вызывает продажу указанной валюты и выводит сведения о выполненной операции."""
    if not current_user:
        print("Сначала выполните login")
        return
    result = portfolio_manager.sell_currency(
        get_arg(args, "--currency", ""),
        get_number_arg(
            args, "--amount", float, "'amount' должен быть положительным числом", 0
        ),
    )
    currency = result["currency_code"]
    print(
        f"Продажа выполнена: {result['amount']} {currency} "
        f"по курсу {result['rate']:.2f} {result['base']}/{currency}"
    )
    print_balance_change(result)
    print(f"Оценочная выручка: {result['estimated_value']:.2f} {result['base']}")


def cmd_get_rate(args, rate_manager, **_):
    """Показывает курс обмена в обоих направлениях или сообщает об ошибке."""
    try:
        quote = rate_manager.get_rate_details(
            get_arg(args, "--from", ""), get_arg(args, "--to", "")
        )
        print(
            f"Курс {quote['from_currency']}→{quote['to_currency']}: {quote['rate']:.2f}"
        )
        print(
            f"Обратный курс {quote['to_currency']}→{quote['from_currency']}: "
            f"{quote['reverse_rate']:.2f}"
        )
        print(f"Обновлено: {format_update_time(quote['updated_at'])}")
    except Exception as error:
        print_error(error)


def cmd_show_rates(args, rate_manager, **_):
    """Показывает сохранённые курсы по заданным условиям и отмечает устаревшие."""
    result = rate_manager.show_rates(
        currency=get_arg(args, "--currency"),
        top=get_number_arg(
            args,
            "--top",
            int,
            "Количество курсов должно быть положительным целым числом",
        ),
        base=get_arg(args, "--base"),
    )
    last_refresh = format_update_time(result["last_refresh"])
    print(f"Курсы из кэша (последнее обновление: {last_refresh}):")
    for pair, info in result["items"]:
        status = " — устарел, выполните 'update-rates'" if info["is_stale"] else ""
        updated_at = format_update_time(info["updated_at"])
        print(f"- {pair}: {info['rate']:.2f} (обновлено: {updated_at}){status}")


def cmd_update_rates(args, rate_manager, **_):
    """Запускает ручное обновление и показывает отчёт по источникам."""
    try:
        report = rate_manager.update_rates_details(
            source=get_arg(args, "--source", "all")
        )
        if report["errors"]:
            sources = ", ".join(report["errors"])
            print(f"Обновление завершено с ошибками. Недоступные источники: {sources}.")
            print(f"Подробности: {report['log_file']}")
        else:
            print("Обновление завершено успешно.")
        print(f"Обновлено валютных пар: {len(report['rates'])}.")
        print(f"Последнее обновление: {format_update_time(report['last_refresh'])}")
    except ApiRequestError as error:
        print_error(error)


def run_cli():
    """Принимает и выполняет команды пользователя до выхода из программы."""
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
    try:
        while True:
            try:
                command_line = input("> ").strip()
                if not command_line:
                    continue
                args = shlex.split(command_line)
                command = args[0]
                if command in COMMAND_ARGUMENTS:
                    validate_args(args)
                if command == "exit":
                    print("Выход...")
                    break
                if command == "help":
                    print_help()
                elif command in commands:
                    result = commands[command](
                        args,
                        user_manager=user_manager,
                        rate_manager=rate_manager,
                        current_user=current_user,
                        portfolio_manager=portfolio_manager,
                    )
                    if command == "login" and result is not None:
                        current_user = result
                        portfolio_manager = PortfolioManager(current_user, rate_manager)
                        refresh_rates_after_login(rate_manager)
                else:
                    print(
                        f"Неизвестная команда: {command}. Введите 'help' для справки."
                    )
            except (EOFError, KeyboardInterrupt):
                print("\nВыход...")
                break
            except Exception as error:
                print_error(error)
    finally:
        rate_manager.close()
