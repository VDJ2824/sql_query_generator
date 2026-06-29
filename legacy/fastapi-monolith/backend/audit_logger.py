"""Audit logging helpers for query generation and execution."""

from __future__ import annotations

from datetime import datetime, time
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLogs, QueryHistory


logger = logging.getLogger("secure_ai_sql_query_generator.audit")

SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)\b(password|token|secret|api[_-]?key)\b\s*[:=]\s*['\"]?[^'\"\s,;}]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
)


def configure_logging() -> None:
    """Set up a basic logger for the starter project."""
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_query_event(message: str) -> None:
    """Record a query-related event."""
    configure_logging()
    logger.info(message)


def log_audit_event(
    db: Session,
    *,
    user_id: int,
    action_type: str,
    execution_status: str,
    user_prompt: str | None = None,
    generated_sql: str | None = None,
    final_enforced_sql: str | None = None,
    query_type: str | None = None,
    rows_affected: int | None = None,
) -> AuditLogs:
    """Persist an audit event without storing credentials or tokens."""
    audit_log = AuditLogs(
        user_id=user_id,
        action_type=action_type,
        user_prompt=redact_sensitive_text(user_prompt),
        generated_sql=redact_sensitive_text(generated_sql),
        final_enforced_sql=redact_sensitive_text(final_enforced_sql),
        query_type=query_type,
        execution_status=execution_status,
        rows_affected=rows_affected,
    )
    try:
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
    except Exception:
        db.rollback()
        raise
    return audit_log


def redact_sensitive_text(value: str | None) -> str | None:
    """Redact common secret patterns before writing audit records."""
    if value is None:
        return None
    redacted = str(value)
    redacted = SENSITIVE_TEXT_PATTERNS[0].sub(r"\1=[REDACTED]", redacted)
    redacted = SENSITIVE_TEXT_PATTERNS[1].sub("Bearer [REDACTED]", redacted)
    return redacted


def get_user_history(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Return query history rows owned by one user."""
    rows = (
        db.query(QueryHistory)
        .filter(QueryHistory.user_id == user_id)
        .order_by(QueryHistory.created_at.desc(), QueryHistory.history_id.desc())
        .all()
    )
    return [
        {
            "prompt": row.user_prompt,
            "selected_query": row.generated_sql,
            "query_type": row.query_type,
            "status": row.execution_status,
            "rows_affected": row.rows_affected,
            "timestamp": _to_iso(row.created_at),
        }
        for row in rows
    ]


def get_audit_logs(
    db: Session,
    *,
    user_id: int | None = None,
    query_type: str | None = None,
    execution_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return audit logs with optional admin filters."""
    query = db.query(AuditLogs)
    if user_id is not None:
        query = query.filter(AuditLogs.user_id == user_id)
    if query_type:
        query = query.filter(AuditLogs.query_type == query_type)
    if execution_status:
        query = query.filter(AuditLogs.execution_status == execution_status)
    if date_from:
        query = query.filter(AuditLogs.created_at >= _parse_date_start(date_from))
    if date_to:
        query = query.filter(AuditLogs.created_at <= _parse_date_end(date_to))

    rows = query.order_by(AuditLogs.created_at.desc(), AuditLogs.log_id.desc()).all()
    return [
        {
            "log_id": row.log_id,
            "user_id": row.user_id,
            "action_type": row.action_type,
            "user_prompt": row.user_prompt,
            "generated_sql": row.generated_sql,
            "final_enforced_sql": row.final_enforced_sql,
            "query_type": row.query_type,
            "execution_status": row.execution_status,
            "rows_affected": row.rows_affected,
            "created_at": _to_iso(row.created_at),
        }
        for row in rows
    ]


def _parse_date_start(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.time() == time.min:
        return parsed
    return parsed


def _parse_date_end(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.time() == time.min:
        return datetime.combine(parsed.date(), time.max)
    return parsed


def _to_iso(value: datetime) -> str:
    return value.isoformat()
