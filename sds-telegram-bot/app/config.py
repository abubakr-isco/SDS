"""Application settings loaded from environment variables (and a local .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class DatabaseSettings(BaseSettings):
    """Only what Alembic and the CLI need — no bot token required."""

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    database_url: SecretStr = Field(
        description="SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@localhost:5432/sds_bot"
    )

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value()
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            # Accept the common libpq form and switch it to the async driver.
            url = "postgresql+asyncpg://" + url.split("://", 1)[1]
        if not (url.startswith("postgresql+asyncpg://") or url.startswith("sqlite+aiosqlite://")):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg:// (or sqlite+aiosqlite:// for tests)")
        return SecretStr(url)


class Settings(DatabaseSettings):
    bot_token: SecretStr = Field(description="Telegram bot token from @BotFather")

    environment: Literal["development", "production"] = "production"
    timezone: str = "America/Chicago"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    # Comma-separated Telegram user IDs that are synced into the administrators table at startup.
    admin_telegram_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    company_config_path: Path = PROJECT_ROOT / "config" / "company.toml"

    # Customer data retention. Completed/cancelled requests older than this are deleted. 0 disables purging.
    data_retention_days: int = Field(default=730, ge=0)

    quote_session_timeout_minutes: int = Field(default=60, ge=5)
    quote_submissions_per_hour: int = Field(default=3, ge=1)
    tracking_lookups_per_10_minutes: int = Field(default=10, ge=1)

    notification_retry_interval_seconds: int = Field(default=120, ge=10)
    notification_max_attempts: int = Field(default=10, ge=1)

    # Website quote form endpoint (POST /api/quote), served by the bot process next to polling.
    web_enabled: bool = True
    web_host: str = "127.0.0.1"  # keep local; publish through an HTTPS reverse proxy (see docs/DEPLOYMENT.md)
    web_port: int = Field(default=8080, ge=1, le=65535)
    # Comma-separated origins allowed to submit from a browser, e.g. https://www.sdsuzinc.com
    website_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    web_trust_proxy: bool = False  # true only behind a reverse proxy that sets X-Forwarded-For
    website_quotes_per_hour_per_ip: int = Field(default=5, ge=1)

    # Shipment tracking backend. Only "none" ships with the bot; see app/services/tracking.py to add one.
    tracking_provider: Literal["none"] = "none"

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            try:
                return [int(p) for p in parts]
            except ValueError as exc:
                raise ValueError("ADMIN_TELEGRAM_IDS must be comma-separated numeric Telegram user IDs") from exc
        if isinstance(value, int):
            return [value]
        return value

    @field_validator("website_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = [p.strip() for p in value.split(",") if p.strip()]
        if isinstance(value, list):
            for origin in value:
                if not str(origin).startswith(("http://", "https://")):
                    raise ValueError("WEBSITE_ALLOWED_ORIGINS entries must start with http:// or https://")
            return [str(o).rstrip("/") for o in value]
        return value

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value!r}") from exc
        return value

    @field_validator("bot_token")
    @classmethod
    def _token_shape(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        left, _, right = token.partition(":")
        if not left.isdigit() or len(right) < 30:
            raise ValueError("BOT_TOKEN does not look like a Telegram bot token")
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
