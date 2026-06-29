"""Shared environment loading for local non-Docker development."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_environment(repo_root: Path | None = None, service_root: Path | None = None) -> None:
    root = repo_root or resolve_repo_root()
    service = service_root or root / "sql-service"

    load_dotenv(root / ".env.cloud", override=False)
    load_dotenv(service / ".env", override=False)
