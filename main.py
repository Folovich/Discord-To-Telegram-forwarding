from __future__ import annotations

import argparse
import asyncio

import discord

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
    try:
        asyncio.run(run(args.config))
    except discord.LoginFailure:
        print("Discord rejected the token from .env. Replace DISCORD_BOT_TOKEN with a fresh bot token.")
    except ValueError as error:
        print(f"Configuration error: {error}")
    except FileNotFoundError as error:
        print(f"Missing file: {error}")


if __name__ == "__main__":
    main()
