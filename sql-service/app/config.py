"""Environment-driven configuration for the internal SQL service."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import make_url

from .env_loader import load_environment


load_environment()


def internal_api_key() -> str:
    return os.getenv("SQL_SERVICE_API_KEY") or ""


def gemini_api_key() -> str | None:
    value = os.getenv("GEMINI_API_KEY")
    if not value or value.startswith("your_"):
        return None
    return value


def gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def database_url_from_env(env_name: str) -> str:
    value = os.getenv(env_name)
    if not value:
        raise ValueError(f"Database credential environment variable '{env_name}' is not configured.")
    if "://" in value:
        url = make_url(value)
        if url.drivername == "postgresql":
            return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
        if url.drivername == "mysql":
            return url.set(drivername="mysql+pymysql").render_as_string(hide_password=False)
        return value
    if env_name.endswith("_PATH") or value.endswith(".db"):
        return f"sqlite:///{Path(value).expanduser()}"
    return value
