"""Application configuration, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Telegram ---
    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")
    shop_name: str = Field(default="Kinetix", alias="SHOP_NAME")
    support_username: str = Field(default="", alias="SUPPORT_USERNAME")
    channel_username: str = Field(default="", alias="CHANNEL_USERNAME")
    reviews_username: str = Field(default="", alias="REVIEWS_USERNAME")

    # --- Storage ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/kinetix.db", alias="DATABASE_URL"
    )

    # --- Money ---
    currency: str = Field(default="RUB", alias="CURRENCY")
    min_topup: int = Field(default=5000, alias="MIN_TOPUP")  # minor units
    max_topup: int = Field(default=10_000_000, alias="MAX_TOPUP")

    # --- Referrals ---
    referral_percent: int = Field(default=5, alias="REFERRAL_PERCENT")

    # --- Manual bank transfer (staff confirm the payment by hand) ---
    manual_payment_enabled: bool = Field(default=True, alias="MANUAL_PAYMENT_ENABLED")
    manual_requisites: str = Field(default="", alias="MANUAL_REQUISITES")
    manual_ttl_minutes: int = Field(default=180, alias="MANUAL_TTL_MINUTES")

    # --- CryptoBot (https://t.me/CryptoBot -> Crypto Pay API) ---
    crypto_pay_token: str = Field(default="", alias="CRYPTO_PAY_TOKEN")
    crypto_pay_testnet: bool = Field(default=False, alias="CRYPTO_PAY_TESTNET")
    payment_poll_interval: int = Field(default=15, alias="PAYMENT_POLL_INTERVAL")
    invoice_ttl_minutes: int = Field(default=60, alias="INVOICE_TTL_MINUTES")

    # --- Misc ---
    default_locale: Literal["ru", "en"] = Field(default="ru", alias="DEFAULT_LOCALE")
    throttle_rate: float = Field(default=0.4, alias="THROTTLE_RATE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> list[int]:
        """Accept "1", "1,2", "1;2", [1, 2] — and a bare int.

        pydantic-settings JSON-decodes env values for complex types first, so a
        single id like ADMIN_IDS=123 arrives here as an int, not a string.
        """
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(chunk) for chunk in value.replace(";", ",").split(",") if chunk.strip()]
        if isinstance(value, (list, tuple)):
            return [int(v) for v in value]
        raise TypeError(f"Cannot parse ADMIN_IDS from {value!r}")

    @field_validator("referral_percent")
    @classmethod
    def _check_percent(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("REFERRAL_PERCENT must be between 0 and 100")
        return value

    @property
    def crypto_pay_enabled(self) -> bool:
        return bool(self.crypto_pay_token)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
