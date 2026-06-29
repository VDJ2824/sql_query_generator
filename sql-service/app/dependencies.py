"""FastAPI dependencies for internal service protection."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from .config import internal_api_key


def require_internal_api_key(x_internal_api_key: str | None = Header(default=None)) -> None:
    if not x_internal_api_key or x_internal_api_key != internal_api_key():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid x-internal-api-key header is required.",
        )
