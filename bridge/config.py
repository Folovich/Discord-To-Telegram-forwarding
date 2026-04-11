from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_TEMPLATE = "[Discord] {author}: {content}"


@dataclass(slots=True)
class RouteConfig:
    discord_channel_id: int
    telegram_targets: list[str]
    message_template: str = DEFAULT_TEMPLATE
    forward_edits: bool = True
    forward_deletes: bool = True
    include_author_avatar_url: bool = False
    filters: list[str] = field(default_factory=list)

    def compiled_filters(self) -> list[re.Pattern[str]]:
        return [re.compile(pattern, re.IGNORECASE) for pattern in self.filters]


@dataclass(slots=True)
class AppConfig:
    discord_token: str
    telegram_token: str
    routes: list[RouteConfig]
    config_path: Path
    reload_interval_seconds: float = 3.0
    telegram_file_limit_mb: int = 20
    log_level: str = "INFO"
    download_timeout_seconds: float = 30.0
    send_retries: int = 5
    retry_base_delay_seconds: float = 1.0

    @property
    def telegram_file_limit_bytes(self) -> int:
        return self.telegram_file_limit_mb * 1024 * 1024

    def routes_for_channel(self, channel_id: int) -> list[RouteConfig]:
        return [route for route in self.routes if route.discord_channel_id == channel_id]


class ConfigManager:
    def __init__(self, config_path: str | os.PathLike[str]) -> None:
        self._config_path = Path(config_path)
        self._env_path = self._config_path.parent / ".env"
        self._lock = asyncio.Lock()
        self._config: AppConfig | None = None
        self._last_mtime_ns: int | None = None
        self._logger = logging.getLogger(__name__)

    @property
    def path(self) -> Path:
        return self._config_path

    async def load_initial(self) -> AppConfig:
        async with self._lock:
            config = self._load_from_disk()
            self._config = config
            self._last_mtime_ns = self._config_path.stat().st_mtime_ns
            return config

    async def get(self) -> AppConfig:
        async with self._lock:
            if self._config is None:
                self._config = self._load_from_disk()
                self._last_mtime_ns = self._config_path.stat().st_mtime_ns
            return self._config

    async def reload_if_changed(self) -> AppConfig | None:
        try:
            current_mtime_ns = self._config_path.stat().st_mtime_ns
        except FileNotFoundError:
            self._logger.error("Config file not found: %s", self._config_path)
            return None

        async with self._lock:
            if self._last_mtime_ns == current_mtime_ns and self._config is not None:
                return None

            config = self._load_from_disk()
            self._config = config
            self._last_mtime_ns = current_mtime_ns
            self._logger.info("Configuration reloaded from %s", self._config_path)
            return config

    def _load_from_disk(self) -> AppConfig:
        if not self._config_path.exists():
            raise FileNotFoundError(f"Config file does not exist: {self._config_path}")

        env_values = self._load_dotenv()
        raw = self._read_structured_file(self._config_path)
        discord_token = env_values.get("DISCORD_BOT_TOKEN")
        telegram_token = env_values.get("TELEGRAM_BOT_TOKEN")

        if not discord_token:
            raise ValueError("Discord bot token must be provided in .env as DISCORD_BOT_TOKEN.")
        if not telegram_token:
            raise ValueError("Telegram bot token must be provided in .env as TELEGRAM_BOT_TOKEN.")

        routes_raw = raw.get("routes", [])
        routes = [self._parse_route(item) for item in routes_raw]
        if not routes:
            raise ValueError("At least one route must be configured.")

        return AppConfig(
            discord_token=discord_token,
            telegram_token=telegram_token,
            routes=routes,
            config_path=self._config_path,
            reload_interval_seconds=float(raw.get("reload_interval_seconds", 3.0)),
            telegram_file_limit_mb=int(raw.get("telegram_file_limit_mb", 20)),
            log_level=str(raw.get("log_level", "INFO")).upper(),
            download_timeout_seconds=float(raw.get("download_timeout_seconds", 30.0)),
            send_retries=int(raw.get("send_retries", 5)),
            retry_base_delay_seconds=float(raw.get("retry_base_delay_seconds", 1.0)),
        )

    @staticmethod
    def _read_structured_file(path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        return yaml.safe_load(text) or {}

    def _load_dotenv(self) -> dict[str, str]:
        if not self._env_path.exists():
            raise FileNotFoundError(f".env file does not exist: {self._env_path}")

        values: dict[str, str] = {}
        for line in self._env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value

        return values

    @staticmethod
    def _parse_route(raw: dict[str, Any]) -> RouteConfig:
        targets = raw.get("telegram_targets")
        if targets is None and raw.get("telegram_channel_id") is not None:
            targets = [raw["telegram_channel_id"]]
        if not targets:
            raise ValueError(f"Route is missing telegram target(s): {raw!r}")

        return RouteConfig(
            discord_channel_id=int(raw["discord_channel_id"]),
            telegram_targets=[str(target) for target in targets],
            message_template=str(raw.get("message_template", DEFAULT_TEMPLATE)),
            forward_edits=bool(raw.get("forward_edits", True)),
            forward_deletes=bool(raw.get("forward_deletes", True)),
            include_author_avatar_url=bool(raw.get("include_author_avatar_url", False)),
            filters=[str(pattern) for pattern in raw.get("filters", [])],
        )
