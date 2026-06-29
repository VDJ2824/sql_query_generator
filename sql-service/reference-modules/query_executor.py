"""Validated query execution helpers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .audit_logger import log_audit_event
from .impact_analyzer import enforce_row_level_filter
from .models import AuditLogs, QueryHistory, User
from .sql_validator import classify_query, validate_query_security


def execute_selected_query(
    *,
    db: Session,
    current_user: User,
    selected_option_id: int,
    confirmed: bool,
) -> dict[str, Any]:
    """Execute a saved query option only after all security checks pass."""
    saved_option = _get_saved_generated_option(db, current_user, selected_option_id)
    generated_sql = saved_option.generated_sql or ""
    query_type = classify_query(generated_sql)
    validation = validate_query_security(generated_sql, current_user)

    if query_type == "TCL":
        return _blocked_response(
            db,
            current_user,
            saved_option,
            message="TCL commands are view-only and cannot be executed in this application.",
            query_type="TCL",
        )

    if query_type in {"DCL", "DDL"}:
        return _blocked_response(
            db,
            current_user,
            saved_option,
            message=f"{query_type} commands are blocked and cannot be executed in this application.",
            query_type=query_type,
        )

    if not validation["is_valid"]:
        return _blocked_response(
            db,
            current_user,
            saved_option,
            message="The selected query failed validation or authorization checks.",
            query_type=query_type,
            warnings=validation["security_errors"] + validation["warnings"],
        )

    final_sql = enforce_row_level_filter(validation["normalized_sql"], current_user)

    if query_type == "SELECT":
        execution_sql = _limit_select(final_sql, 100)
        rows = _fetch_rows(db, execution_sql)
        response = _execution_response(
            success=True,
            message="SELECT query executed successfully.",
            generated_sql=generated_sql,
            final_enforced_sql=execution_sql,
            query_type="SELECT",
            rows_affected=len(rows),
            result_rows=rows,
            execution_allowed=True,
        )
        _log_execution(db, current_user, saved_option, response, "executed")
        return response

    if query_type == "INSERT":
        if not confirmed:
            return _blocked_response(
                db,
                current_user,
                saved_option,
                message="INSERT requires explicit confirmation before execution.",
                query_type="INSERT",
                final_enforced_sql=final_sql,
            )
        rows_affected = _execute_write(db, final_sql)
        response = _execution_response(
            success=True,
            message="INSERT query executed successfully.",
            generated_sql=generated_sql,
            final_enforced_sql=final_sql,
            query_type="INSERT",
            rows_affected=rows_affected,
            result_rows=[],
            execution_allowed=True,
        )
        _log_execution(db, current_user, saved_option, response, "executed")
        return response

    if query_type in {"UPDATE", "DELETE"}:
        if not _has_successful_preview(db, current_user, saved_option):
            return _blocked_response(
                db,
                current_user,
                saved_option,
                message=f"{query_type} must be previewed before execution.",
                query_type=query_type,
                final_enforced_sql=final_sql,
            )
        if not confirmed:
            return _blocked_response(
                db,
                current_user,
                saved_option,
                message=f"{query_type} requires explicit confirmation before execution.",
                query_type=query_type,
                final_enforced_sql=final_sql,
            )
        rows_affected = _execute_write(db, final_sql)
        response = _execution_response(
            success=True,
            message=f"{query_type} query executed successfully.",
            generated_sql=generated_sql,
            final_enforced_sql=final_sql,
            query_type=query_type,
            rows_affected=rows_affected,
            result_rows=[],
            execution_allowed=True,
        )
        _log_execution(db, current_user, saved_option, response, "executed")
        return response

    return _blocked_response(
        db,
        current_user,
        saved_option,
        message="Unknown query types cannot be executed.",
        query_type=query_type,
    )


def execute_read_only_query(engine: Engine, sql: str) -> list[dict]:
    """Execute a validated SQL query and return rows as dictionaries."""
    with engine.connect() as connection:
        result = connection.execute(text(sql))
        rows = result.mappings().all()
        return [dict(row) for row in rows]


def _get_saved_generated_option(db: Session, current_user: User, selected_option_id: int) -> QueryHistory:
    saved_option = (
        db.query(QueryHistory)
        .filter(
            QueryHistory.user_id == current_user.user_id,
            QueryHistory.selected_option_id == selected_option_id,
            QueryHistory.execution_status == "generated",
        )
        .order_by(QueryHistory.history_id.desc())
        .first()
    )
    if saved_option is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved generated query option was found for this user and option id.",
        )
    return saved_option


def _fetch_rows(db: Session, sql: str) -> list[dict[str, Any]]:
    try:
        rows = db.execute(text(sql)).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        db.rollback()
        raise


def _execute_write(db: Session, sql: str) -> int:
    try:
        result = db.execute(text(sql))
        db.commit()
        return int(result.rowcount or 0)
    except Exception:
        db.rollback()
        raise


def _limit_select(sql: str, limit: int) -> str:
    return f"SELECT * FROM ({sql}) AS execution_source LIMIT {limit}"


def _has_successful_preview(db: Session, current_user: User, saved_option: QueryHistory) -> bool:
    return (
        db.query(AuditLogs)
        .filter(
            AuditLogs.user_id == current_user.user_id,
            AuditLogs.action_type == "preview_selected_query",
            AuditLogs.generated_sql == saved_option.generated_sql,
            AuditLogs.execution_status == "previewed",
        )
        .count()
        > 0
    )


def _blocked_response(
    db: Session,
    current_user: User,
    saved_option: QueryHistory,
    *,
    message: str,
    query_type: str,
    final_enforced_sql: str = "",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    response = _execution_response(
        success=False,
        message=message,
        generated_sql=saved_option.generated_sql or "",
        final_enforced_sql=final_enforced_sql,
        query_type=query_type,
        rows_affected=0,
        result_rows=[],
        execution_allowed=False,
    )
    if warnings:
        response["message"] = f"{message} {' '.join(warnings)}"
    _log_execution(db, current_user, saved_option, response, "blocked")
    return response


def _execution_response(
    *,
    success: bool,
    message: str,
    generated_sql: str,
    final_enforced_sql: str,
    query_type: str,
    rows_affected: int,
    result_rows: list[dict[str, Any]],
    execution_allowed: bool,
) -> dict[str, Any]:
    return {
        "success": success,
        "message": message,
        "generated_sql": generated_sql,
        "final_enforced_sql": final_enforced_sql,
        "query_type": query_type,
        "rows_affected": rows_affected,
        "result_rows": result_rows,
        "execution_allowed": execution_allowed,
    }


def _log_execution(
    db: Session,
    current_user: User,
    saved_option: QueryHistory,
    response: dict[str, Any],
    execution_status: str,
) -> None:
    try:
        db.add(
            QueryHistory(
                user_id=current_user.user_id,
                user_prompt=saved_option.user_prompt,
                selected_option_id=saved_option.selected_option_id,
                generated_sql=response["generated_sql"],
                final_enforced_sql=response["final_enforced_sql"],
                query_type=response["query_type"],
                execution_status=execution_status,
                rows_affected=response["rows_affected"],
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    log_audit_event(
        db,
        user_id=current_user.user_id,
        action_type="execute_selected_query",
        user_prompt=saved_option.user_prompt,
        generated_sql=response["generated_sql"],
        final_enforced_sql=response["final_enforced_sql"],
        query_type=response["query_type"],
        execution_status=execution_status,
        rows_affected=response["rows_affected"],
    )
