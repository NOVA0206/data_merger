"""Environment-driven configuration. No secrets are hardcoded here."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Load .env from the parent directory (project root)
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

def _get(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _get_str(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val is not None else default


class Settings:
    GOOGLE_CLIENT_ID: str | None = _get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = _get("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str | None = _get("GOOGLE_REDIRECT_URI")
    GOOGLE_TOKEN_ENCRYPTION_KEY: str | None = _get("GOOGLE_TOKEN_ENCRYPTION_KEY")
    FRONTEND_URL: str = _get_str("FRONTEND_URL", "http://localhost:3000")
    DATABASE_URL: str | None = _get("DATABASE_URL")
    JOB_BATCH_SIZE: int = int(_get_str("JOB_BATCH_SIZE", "8"))
    CRON_SECRET: str | None = _get("CRON_SECRET")


settings = Settings()
