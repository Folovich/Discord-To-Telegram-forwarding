from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from telegram import Bot, InputFile, Message
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError, TimedOut


PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}


@dataclass(slots=True)
class AttachmentPayload:
    filename: str
    data: bytes
    size: int
    content_type: str | None = None
    caption: str | None = None


class TelegramSender:
    def __init__(self, token: str, send_retries: int, retry_base_delay_seconds: float) -> None:
        self._bot = Bot(token=token)
        self._send_retries = send_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._logger = logging.getLogger(__name__)

    @property
    def bot(self) -> Bot:
        return self._bot

    async def initialize(self) -> None:
        await self._bot.initialize()

    async def shutdown(self) -> None:
        await self._bot.shutdown()

    async def send_text(self, chat_id: str, text: str, disable_preview: bool = False) -> Message:
        return await self._with_retries(
            lambda: self._bot.send_message(
                chat_id=chat_id,
                text=text,
                disable_web_page_preview=disable_preview,
            ),
            action=f"send text to {chat_id}",
        )

    async def send_attachment(self, chat_id: str, attachment: AttachmentPayload) -> Message:
        extension = Path(attachment.filename).suffix.lower()
        input_file = InputFile(attachment.data, filename=attachment.filename)
        caption = attachment.caption

        if self._is_photo(attachment, extension):
            method = lambda: self._bot.send_photo(chat_id=chat_id, photo=input_file, caption=caption)
        elif self._is_video(attachment, extension):
            method = lambda: self._bot.send_video(chat_id=chat_id, video=input_file, caption=caption)
        elif self._is_audio(attachment, extension):
            method = lambda: self._bot.send_audio(chat_id=chat_id, audio=input_file, caption=caption)
        else:
            method = lambda: self._bot.send_document(chat_id=chat_id, document=input_file, caption=caption)

        return await self._with_retries(method, action=f"send attachment {attachment.filename} to {chat_id}")

    async def _with_retries(self, operation, action: str) -> Message:
        last_error: Exception | None = None
        for attempt in range(1, self._send_retries + 1):
            try:
                return await operation()
            except RetryAfter as error:
                last_error = error
                delay = max(float(error.retry_after), self._retry_base_delay_seconds)
                self._logger.warning("%s hit Telegram rate limit, retrying in %.2fs", action, delay)
                await asyncio.sleep(delay)
            except (BadRequest, Forbidden) as error:
                self._logger.error("%s failed permanently: %s", action, error)
                raise
            except (TimedOut, TelegramError) as error:
                last_error = error
                if attempt == self._send_retries:
                    break
                delay = self._retry_base_delay_seconds * (2 ** (attempt - 1))
                self._logger.warning("%s failed on attempt %s/%s: %s", action, attempt, self._send_retries, error)
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    @staticmethod
    def _is_photo(attachment: AttachmentPayload, extension: str) -> bool:
        return (attachment.content_type or "").startswith("image/") or extension in PHOTO_EXTENSIONS

    @staticmethod
    def _is_video(attachment: AttachmentPayload, extension: str) -> bool:
        return (attachment.content_type or "").startswith("video/") or extension in VIDEO_EXTENSIONS

    @staticmethod
    def _is_audio(attachment: AttachmentPayload, extension: str) -> bool:
        return (attachment.content_type or "").startswith("audio/") or extension in AUDIO_EXTENSIONS
