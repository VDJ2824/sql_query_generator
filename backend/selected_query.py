"""Server-side selected query storage helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .audit_logger import log_audit_event
from .models import QueryHistory, SelectedQueries, User


SELECTION_TTL_MINUTES = 15


def select_query_option(
    *,
    db: Session,
    current_user: User,
    option_id: int,
    title: str,
) -> SelectedQueries:
    """Select an option from the current user's latest generated response."""
    generated_option = _get_latest_generated_option(db, current_user, option_id)
    now = _utc_now()
    expires_at = now + timedelta(minutes=SELECTION_TTL_MINUTES)

    _clear_active_selection(db, current_user.user_id)
    selected_query = SelectedQueries(
        user_id=current_user.user_id,
        option_id=option_id,
        title=title,
        generated_sql=generated_option.generated_sql,
        query_type=generated_option.query_type,
        expires_at=expires_at,
    )
    db.add(selected_query)
    db.flush()
    log_audit_event(
        db,
        user_id=current_user.user_id,
        action_type="select_query",
        user_prompt=generated_option.user_prompt,
        generated_sql=generated_option.generated_sql,
        query_type=generated_option.query_type,
        execution_status="selected",
        rows_affected=None,
    )
    db.refresh(selected_query)
    return selected_query


def get_active_selected_query(*, db: Session, current_user: User) -> SelectedQueries | None:
    """Return the current user's active selection, or None if it expired."""
    selected_query = (
        db.query(SelectedQueries)
        .filter(SelectedQueries.user_id == current_user.user_id)
        .order_by(SelectedQueries.selected_query_id.desc())
        .first()
    )
    if selected_query is None:
        return None
    if _is_expired(selected_query):
        db.delete(selected_query)
        db.commit()
        return None
    return selected_query


def selected_query_to_dict(selected_query: SelectedQueries) -> dict[str, Any]:
    return {
        "selected_query_id": selected_query.selected_query_id,
        "user_id": selected_query.user_id,
        "option_id": selected_query.option_id,
        "title": selected_query.title,
        "generated_sql": selected_query.generated_sql,
        "query_type": selected_query.query_type,
        "created_at": _to_iso(selected_query.created_at),
        "expires_at": _to_iso(selected_query.expires_at),
    }


def _get_latest_generated_option(db: Session, current_user: User, option_id: int) -> QueryHistory:
    latest_generated = (
        db.query(QueryHistory)
        .filter(
            QueryHistory.user_id == current_user.user_id,
            QueryHistory.execution_status == "generated",
        )
        .order_by(QueryHistory.history_id.desc())
        .first()
    )
    if latest_generated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No generated query options were found for this user.",
        )

    generated_option = (
        db.query(QueryHistory)
        .filter(
            QueryHistory.user_id == current_user.user_id,
            QueryHistory.execution_status == "generated",
            QueryHistory.user_prompt == latest_generated.user_prompt,
            QueryHistory.selected_option_id == option_id,
        )
        .order_by(QueryHistory.history_id.desc())
        .first()
    )
    if generated_option is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The selected option was not found in the latest generated response.",
        )
    return generated_option


def _clear_active_selection(db: Session, user_id: int) -> None:
    active_selections = db.query(SelectedQueries).filter(SelectedQueries.user_id == user_id).all()
    for selected_query in active_selections:
        db.delete(selected_query)


def _is_expired(selected_query: SelectedQueries) -> bool:
    expires_at = selected_query.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _utc_now()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()

