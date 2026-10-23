#!/usr/bin/env python3
from currency_wallet.cli.interface import run_cli
from currency_wallet.logging_config import setup_logging


def main():
    setup_logging()
    run_cli()


if __name__ == "__main__":
    main()