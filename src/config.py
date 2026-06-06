from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseModel):
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    resend_api_key: str | None = None
    report_emails: list[str] = Field(default_factory=list)
    sender_email: str | None = None
    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'investment_radar.sqlite3'}"
    timezone: str = "Europe/Helsinki"
    email_dry_run: bool = True
    max_report_items: int = 10
    min_ai_score: float = 8.0
    report_lookback_hours: int = 24
    fetch_timeout_seconds: int = 20

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite:/// DATABASE_URL values are supported by this MVP.")
        return Path(self.database_url.removeprefix(prefix)).expanduser().resolve()


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_settings(env_file: str | Path | None = None, **overrides: Any) -> Settings:
    load_dotenv(env_file or ROOT_DIR / ".env")
    data: dict[str, Any] = {
        "openai_api_key": _clean_env(os.getenv("OPENAI_API_KEY")),
        "openai_model": _clean_env(os.getenv("OPENAI_MODEL")) or "gpt-4.1-mini",
        "resend_api_key": _clean_env(os.getenv("RESEND_API_KEY")),
        "report_emails": _split_csv(os.getenv("REPORT_EMAILS")),
        "sender_email": _clean_env(os.getenv("SENDER_EMAIL")),
        "database_url": _clean_env(os.getenv("DATABASE_URL")) or f"sqlite:///{ROOT_DIR / 'data' / 'investment_radar.sqlite3'}",
        "timezone": _clean_env(os.getenv("TIMEZONE")) or "Europe/Helsinki",
        "email_dry_run": _bool_env(os.getenv("EMAIL_DRY_RUN"), True),
        "max_report_items": int(os.getenv("MAX_REPORT_ITEMS", "10")),
        "min_ai_score": float(os.getenv("MIN_AI_SCORE", "8")),
        "report_lookback_hours": int(os.getenv("REPORT_LOOKBACK_HOURS", "24")),
        "fetch_timeout_seconds": int(os.getenv("FETCH_TIMEOUT_SECONDS", "20")),
    }
    data.update(overrides)
    return Settings(**data)
