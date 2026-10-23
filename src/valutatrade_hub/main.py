#!/usr/bin/env python3
from valutatrade_hub.cli.interface import run_cli
from valutatrade_hub.logging_config import setup_logging


def main():
    setup_logging()
    run_cli()


if __name__ == "__main__":
    main()