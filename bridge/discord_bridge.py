from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass

import discord

from bridge.config import AppConfig, ConfigManager, RouteConfig
from bridge.telegram_sender import AttachmentPayload, TelegramSender


NOTICE_EDITED = "(исправлено)"
NOTICE_DELETED = "(удалено)"


@dataclass(slots=True)
class ForwardRecord:
    route: RouteConfig
    telegram_target: str
    telegram_message_ids: list[int]


class DiscordTelegramBridge(discord.Client):
    def __init__(self, config_manager: ConfigManager, telegram_sender: TelegramSender) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        super().__init__(intents=intents)

        self.config_manager = config_manager
        self.telegram_sender = telegram_sender
        self.logger = logging.getLogger(__name__)
        self._forward_index: dict[int, list[ForwardRecord]] = {}
        self._forward_order: list[int] = []
        self._reload_task: asyncio.Task[None] | None = None
        self._max_tracked_messages = 5000

    async def setup_hook(self) -> None:
        config = await self.config_manager.get()
        self._reload_task = asyncio.create_task(self._reload_loop(config.reload_interval_seconds))

    async def close(self) -> None:
        if self._reload_task is not None:
            self._reload_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reload_task
        await super().close()

    async def on_ready(self) -> None:
        self.logger.info("Discord bridge connected as %s", self.user)

    async def on_message(self, message: discord.Message) -> None:
        if not self._should_forward_message(message):
            return
        await self._forward_message(message)

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.author.bot or after.author.bot:
            return
        records = self._forward_index.get(after.id, [])
        if not records:
            return

        notice = self._format_notice(after, NOTICE_EDITED)
        results = await asyncio.gather(
            *[
                self.telegram_sender.send_text(record.telegram_target, notice, disable_preview=True)
                for record in records
                if record.route.forward_edits
            ],
            return_exceptions=True,
        )
        self._log_gather_errors(results, f"edit notification for Discord message {after.id}")

    async def on_message_delete(self, message: discord.Message) -> None:
        if message.author and message.author.bot:
            return
        records = self._forward_index.pop(message.id, [])
        if not records:
            return

        notice = self._format_notice(message, NOTICE_DELETED)
        results = await asyncio.gather(
            *[
                self.telegram_sender.send_text(record.telegram_target, notice, disable_preview=True)
                for record in records
                if record.route.forward_deletes
            ],
            return_exceptions=True,
        )
        self._log_gather_errors(results, f"delete notification for Discord message {message.id}")

    async def _forward_message(self, message: discord.Message) -> None:
        config = await self.config_manager.get()
        routes = config.routes_for_channel(message.channel.id)
        if not routes:
            return

        records: list[ForwardRecord] = []
        tasks = [self._forward_to_route(message, route, config.telegram_file_limit_bytes) for route in routes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                self.logger.exception("Forwarding failed for Discord message %s", message.id, exc_info=result)
                continue
            records.extend(result)

        if records:
            self._forward_index[message.id] = records
            self._forward_order.append(message.id)
            self._trim_forward_history()

    async def _forward_to_route(
        self,
        message: discord.Message,
        route: RouteConfig,
        telegram_file_limit_bytes: int,
    ) -> list[ForwardRecord]:
        if not self._passes_filters(message, route):
            return []

        rendered_text = self._render_message_text(message, route)
        attachments = await self._load_attachments(message, telegram_file_limit_bytes)
        records: list[ForwardRecord] = []

        for target in route.telegram_targets:
            telegram_message_ids: list[int] = []
            if rendered_text.strip():
                tg_message = await self.telegram_sender.send_text(target, rendered_text, disable_preview=False)
                telegram_message_ids.append(tg_message.message_id)

            for attachment in attachments:
                tg_message = await self.telegram_sender.send_attachment(target, attachment)
                telegram_message_ids.append(tg_message.message_id)

            self.logger.info(
                "Forwarded Discord message %s from channel %s to Telegram target %s",
                message.id,
                message.channel.id,
                target,
            )
            records.append(
                ForwardRecord(
                    route=route,
                    telegram_target=target,
                    telegram_message_ids=telegram_message_ids,
                )
            )

        return records

    def _passes_filters(self, message: discord.Message, route: RouteConfig) -> bool:
        patterns = route.compiled_filters()
        if not patterns:
            return True

        candidate = self._message_body(message)
        return any(pattern.search(candidate) for pattern in patterns)

    def _render_message_text(self, message: discord.Message, route: RouteConfig) -> str:
        content = self._message_body(message).strip()
        if not content and message.attachments:
            content = ""

        author = message.author.display_name
        avatar_url = message.author.display_avatar.url if route.include_author_avatar_url else ""
        rendered = route.message_template.format(
            author=author,
            content=content,
            author_avatar_url=avatar_url,
            discord_channel_id=message.channel.id,
            discord_message_id=message.id,
        )
        return rendered.strip()

    def _format_notice(self, message: discord.Message, suffix: str) -> str:
        author = message.author.display_name if message.author else "Unknown"
        content = self._message_body(message).strip() or ""
        return f"[Discord] {author}: {content} {suffix}"

    @staticmethod
    def _message_body(message: discord.Message) -> str:
        parts = []
        if message.clean_content:
            parts.append(message.clean_content)
        poll = getattr(message, "poll", None)
        if poll is not None and getattr(poll, "question", None):
            parts.append(f"Poll: {poll.question}")
        return "\n".join(part for part in parts if part)

    async def _load_attachments(
        self,
        message: discord.Message,
        telegram_file_limit_bytes: int,
    ) -> list[AttachmentPayload]:
        payloads: list[AttachmentPayload] = []
        for attachment in message.attachments:
            if attachment.size > telegram_file_limit_bytes:
                self.logger.warning(
                    "Skipping attachment %s (%s bytes): exceeds Telegram limit",
                    attachment.filename,
                    attachment.size,
                )
                continue

            data = await attachment.read(use_cached=True)
            payloads.append(
                AttachmentPayload(
                    filename=attachment.filename,
                    data=data,
                    size=attachment.size,
                    content_type=attachment.content_type,
                )
            )
        return payloads

    @staticmethod
    def _should_forward_message(message: discord.Message) -> bool:
        return not message.author.bot and message.guild is not None

    async def _reload_loop(self, interval_seconds: float) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                new_config = await self.config_manager.reload_if_changed()
                if new_config is not None:
                    logging.getLogger().setLevel(new_config.log_level)
            except Exception:
                self.logger.exception("Failed to reload configuration")

    def _trim_forward_history(self) -> None:
        while len(self._forward_order) > self._max_tracked_messages:
            message_id = self._forward_order.pop(0)
            self._forward_index.pop(message_id, None)

    def _log_gather_errors(self, results: list[object], action: str) -> None:
        for result in results:
            if isinstance(result, Exception):
                self.logger.exception("Failed %s", action, exc_info=result)
