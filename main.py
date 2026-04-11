from __future__ import annotations

import argparse
import asyncio

from bridge.app import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forward Discord channel messages to Telegram.")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML or JSON config file. Defaults to config.yaml.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run(args.config))


if __name__ == "__main__":
    main()
