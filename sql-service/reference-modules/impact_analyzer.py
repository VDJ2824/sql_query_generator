"""Preview and impact analysis helpers for selected SQL options."""

from __future__ import annotations

from typing import Any

import sqlglot
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit_logger import log_audit_event
from .authorization import get_allowed_columns, get_row_level_rule
from .models import QueryHistory, User
from .sql_validator import classify_query, validate_query_security


def preview_selected_query(
    *,
    db: Session,
    current_user: User,
    selected_option_id: int,
) -> dict[str, Any]:
    """Preview a previously generated query option without executing writes."""
    query_history = (
        db.query(QueryHistory)
        .filter(
            QueryHistory.user_id == current_user.user_id,
            QueryHistory.selected_option_id == selected_option_id,
            QueryHistory.execution_status == "generated",
        )
        .order_by(QueryHistory.history_id.desc())
        .first()
    )
    if query_history is None:
        log_audit_event(
            db,
            user_id=current_user.user_id,
            action_type="preview_selected_query",
            execution_status="not_found",
            rows_affected=0,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No generated query option was found for this user and option id.",
        )

    generated_sql = query_history.generated_sql or ""
    query_type = classify_query(generated_sql)
    validation = validate_query_security(generated_sql, current_user)
    warnings = list(validation["warnings"])

    if query_type == "TCL":
        response = _preview_response(
            selected_option_id=selected_option_id,
            generated_sql=generated_sql,
            final_enforced_sql="",
            preview_sql="",
            query_type="TCL",
            estimated_rows=0,
            preview_rows=[],
            impact_message="Transaction control commands are shown for explanation only and are never executed.",
            risk_level="medium",
            execution_allowed=False,
            requires_confirmation=False,
            warnings=warnings or ["TCL commands cannot be previewed or executed."],
        )
        _log_preview(db, current_user, query_history, response, "view_only")
        return response

    if not validation["is_valid"]:
        response = _preview_response(
            selected_option_id=selected_option_id,
            generated_sql=generated_sql,
            final_enforced_sql="",
            preview_sql="",
            query_type=query_type,
            estimated_rows=0,
            preview_rows=[],
            impact_message="The selected SQL did not pass validation or authorization checks.",
            risk_level=_risk_level(query_type),
            execution_allowed=False,
            requires_confirmation=validation["requires_confirmation"],
            warnings=warnings + validation["security_errors"],
        )
        _log_preview(db, current_user, query_history, response, "blocked")
        return response

    if query_type == "SELECT":
        final_sql = enforce_row_level_filter(validation["normalized_sql"], current_user)
        preview_sql = _preview_select_sql(final_sql)
        estimated_rows = _count_rows(db, final_sql)
        preview_rows = _fetch_preview_rows(db, preview_sql)
        response = _preview_response(
            selected_option_id=selected_option_id,
            generated_sql=generated_sql,
            final_enforced_sql=final_sql,
            preview_sql=preview_sql,
            query_type="SELECT",
            estimated_rows=estimated_rows,
            preview_rows=preview_rows,
            impact_message=f"SELECT preview is limited to 20 rows. Estimated matching rows: {estimated_rows}.",
            risk_level="low",
            execution_allowed=True,
            requires_confirmation=False,
            warnings=warnings,
        )
        _log_preview(db, current_user, query_history, response, "previewed")
        return response

    if query_type in {"UPDATE", "DELETE"}:
        final_sql = enforce_row_level_filter(validation["normalized_sql"], current_user)
        preview_sql = build_write_preview_sql(final_sql, current_user)
        estimated_rows = _count_rows(db, preview_sql)
        preview_rows = _fetch_preview_rows(db, _preview_select_sql(preview_sql))
        response = _preview_response(
            selected_option_id=selected_option_id,
            generated_sql=generated_sql,
            final_enforced_sql=final_sql,
            preview_sql=preview_sql,
            query_type=query_type,
            estimated_rows=estimated_rows,
            preview_rows=preview_rows,
            impact_message=f"{query_type} would affect approximately {estimated_rows} rows after enforcement.",
            risk_level="high",
            execution_allowed=True,
            requires_confirmation=True,
            warnings=warnings + [f"{query_type} was not executed. This is only a preview."],
        )
        _log_preview(db, current_user, query_history, response, "previewed")
        return response

    response = _preview_response(
        selected_option_id=selected_option_id,
        generated_sql=generated_sql,
        final_enforced_sql="",
        preview_sql="",
        query_type=query_type,
        estimated_rows=0,
        preview_rows=[],
        impact_message=f"{query_type} queries cannot be previewed or executed by this endpoint.",
        risk_level=_risk_level(query_type),
        execution_allowed=False,
        requires_confirmation=False,
        warnings=warnings or [f"{query_type} is blocked."],
    )
    _log_preview(db, current_user, query_history, response, "blocked")
    return response


def enforce_row_level_filter(sql: str, current_user: User) -> str:
    """Append the user's row-level rule to SELECT, UPDATE, or DELETE SQL."""
    query_type = classify_query(sql)
    if query_type not in {"SELECT", "UPDATE", "DELETE"}:
        return sql

    expression = sqlglot.parse_one(sql, dialect="sqlite")
    table_name = _first_table_name(expression)
    row_condition = _row_level_condition(current_user, table_name)
    if not row_condition:
        return expression.sql(dialect="sqlite").rstrip(";")

    enforced = expression.where(row_condition, append=True)
    return enforced.sql(dialect="sqlite").rstrip(";")


def build_write_preview_sql(sql: str, current_user: User) -> str:
    """Create a SELECT preview query for UPDATE or DELETE using the enforced WHERE."""
    expression = sqlglot.parse_one(sql, dialect="sqlite")
    table_name = _first_table_name(expression)
    if not table_name:
        raise ValueError("Could not determine target table for write preview.")

    where = expression.args.get("where")
    where_sql = where.this.sql(dialect="sqlite") if where is not None else "1 = 0"
    columns = get_allowed_columns(current_user, table_name)
    select_columns = ", ".join(columns) if columns else "*"
    return f"SELECT {select_columns} FROM {table_name} WHERE {where_sql}"


def analyze_query_impact(sql: str) -> dict[str, str]:
    """Return a simple standalone impact summary."""
    query_type = classify_query(sql)
    return {
        "risk_level": _risk_level(query_type),
        "message": f"{query_type} requires validation and authorization before execution.",
    }


def _count_rows(db: Session, select_sql: str) -> int:
    count_sql = f"SELECT COUNT(*) AS estimated_rows FROM ({select_sql}) AS preview_source"
    try:
        return int(db.execute(text(count_sql)).scalar_one())
    except Exception:
        db.rollback()
        raise


def _fetch_preview_rows(db: Session, preview_sql: str) -> list[dict[str, Any]]:
    try:
        rows = db.execute(text(preview_sql)).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        db.rollback()
        raise


def _preview_select_sql(select_sql: str) -> str:
    return f"SELECT * FROM ({select_sql}) AS preview_source LIMIT 20"


def _first_table_name(expression: sqlglot.Expression) -> str:
    table = next(expression.find_all(sqlglot.exp.Table), None)
    return table.name.lower() if table is not None and table.name else ""


def _row_level_condition(current_user: User, table_name: str) -> str:
    if not table_name:
        return "1 = 0"
    rule = get_row_level_rule(current_user, table_name)
    if not rule.get("allowed"):
        return "1 = 0"
    if rule.get("rule") == "all_rows":
        return ""
    column = rule.get("column")
    value = rule.get("value")
    if value is None:
        return "1 = 0"
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"{column} = '{escaped}'"
    return f"{column} = {value}"


def _preview_response(
    *,
    selected_option_id: int,
    generated_sql: str,
    final_enforced_sql: str,
    preview_sql: str,
    query_type: str,
    estimated_rows: int,
    preview_rows: list[dict[str, Any]],
    impact_message: str,
    risk_level: str,
    execution_allowed: bool,
    requires_confirmation: bool,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "selected_option_id": selected_option_id,
        "generated_sql": generated_sql,
        "final_enforced_sql": final_enforced_sql,
        "preview_sql": preview_sql,
        "query_type": query_type,
        "estimated_rows": estimated_rows,
        "preview_rows": preview_rows,
        "impact_message": impact_message,
        "risk_level": risk_level,
        "execution_allowed": execution_allowed,
        "requires_confirmation": requires_confirmation,
        "warnings": warnings,
    }


def _risk_level(query_type: str) -> str:
    if query_type == "SELECT":
        return "low"
    if query_type in {"UPDATE", "DELETE", "DDL", "DCL"}:
        return "high"
    return "medium"


def _log_preview(
    db: Session,
    current_user: User,
    query_history: QueryHistory,
    response: dict[str, Any],
    execution_status: str,
) -> None:
    log_audit_event(
        db,
        user_id=current_user.user_id,
        action_type="preview_selected_query",
        user_prompt=query_history.user_prompt,
        generated_sql=response["generated_sql"],
        final_enforced_sql=response["final_enforced_sql"],
        query_type=response["query_type"],
        execution_status=execution_status,
        rows_affected=response["estimated_rows"],
    )
