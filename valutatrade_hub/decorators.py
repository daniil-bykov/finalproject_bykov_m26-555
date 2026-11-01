import functools
import inspect
import logging

logger = logging.getLogger("valutatrade_hub.actions")


def _error_message(error, arguments):
    """Сохраняет причину ошибки, скрывая секретные аргументы метода."""
    message = str(error)
    secrets = {
        value
        for name in ("password", "hashed_password", "salt")
        if isinstance(value := arguments.get(name), str) and value
    }
    # Учитываем и обычное значение, и его представление с escape-последовательностями.
    variants = secrets | {repr(secret)[1:-1] for secret in secrets}
    for secret in sorted(variants, key=len, reverse=True):
        message = message.replace(secret, "***")
    return message


def log_action(action_name, *, verbose=False):
    """Записывает в журнал результат операции.

    Если операция завершилась ошибкой, записывает её и передаёт дальше.
    При verbose=True также записывает баланс до и после операции."""

    def decorator(func):
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            manager = arguments.get("self")
            user = arguments.get(
                "username", getattr(getattr(manager, "user", None), "username", None)
            )

            def context(details=None):
                values = dict(arguments)
                if isinstance(details, dict):
                    values.update(details)
                fields = [f"user={user!r}"]
                # Только разрешённые поля: пароли, соль и хеш сюда не попадают.
                for argument, field in (
                    ("currency_code", "currency"),
                    ("amount", "amount"),
                    ("rate", "rate"),
                    ("base", "base"),
                ):
                    if argument in values:
                        fields.append(f"{field}={values[argument]!r}")
                return " ".join(fields)

            def balances(details):
                if not verbose or not isinstance(details, dict):
                    return ""
                if "balance_before" not in details:
                    return ""
                return (
                    f" balance_before={details['balance_before']!r}"
                    f" balance_after={details['balance_after']!r}"
                )

            logger.debug(f"{action_name} {context()} result=START")
            try:
                result = func(*args, **kwargs)
            except Exception as error:
                details = getattr(error, "action_details", None)
                logger.info(
                    f"{action_name} {context(details)} result=ERROR "
                    f"error_type={type(error).__name__} "
                    f"error_message={_error_message(error, arguments)!r}"
                    f"{balances(details)}"
                )
                raise
            logger.info(f"{action_name} {context(result)} result=OK{balances(result)}")
            return result

        return wrapper

    return decorator
