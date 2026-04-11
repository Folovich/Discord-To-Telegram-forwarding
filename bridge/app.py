from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from bridge.config import ConfigManager
from bridge.discord_bridge import DiscordTelegramBridge
from bridge.logging_setup import configure_logging
from bridge.telegram_sender import TelegramSender


async def run(config_path: str) -> None:
    configure_logging("INFO")
    config_manager = ConfigManager(config_path)
    config = await config_manager.load_initial()
    configure_logging(config.log_level)

    logger = logging.getLogger(__name__)
    sender = TelegramSender(
        token=config.telegram_token,
        send_retries=config.send_retries,
        retry_base_delay_seconds=config.retry_base_delay_seconds,
    )
    bridge = DiscordTelegramBridge(config_manager=config_manager, telegram_sender=sender)

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, shutdown_event.set)

    await sender.initialize()
    discord_task = asyncio.create_task(bridge.start(config.discord_token), name="discord-bridge")
    wait_task = asyncio.create_task(shutdown_event.wait(), name="shutdown-wait")

    try:
        done, pending = await asyncio.wait(
            {discord_task, wait_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if discord_task in done and discord_task.exception() is not None:
            raise discord_task.exception()

        logger.info("Shutdown requested, stopping bridge")
        for task in pending:
            task.cancel()
    finally:
        await bridge.close()
        discord_task.cancel()
        wait_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await discord_task
        with contextlib.suppress(asyncio.CancelledError):
            await wait_task
        await sender.shutdown()
