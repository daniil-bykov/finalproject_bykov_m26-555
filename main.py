#!/usr/bin/env python3
import sys

from valutatrade_hub.cli.interface import run_cli
from valutatrade_hub.logging_config import setup_logging


def main():
    """Настраивает логирование и запускает обработку команд кошелька."""
    try:
        setup_logging()
        run_cli()
    except (OSError, ValueError) as error:
        print(f"Ошибка запуска: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nВыход...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
