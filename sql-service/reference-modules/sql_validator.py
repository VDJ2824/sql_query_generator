"""SQL validation and security checks built on sqlglot."""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp

from .authorization import can_access_column, can_access_table, can_execute_query_type


TCL_COMMANDS = ("COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE SAVEPOINT", "SET TRANSACTION")
DCL_COMMANDS = ("GRANT", "REVOKE")
DDL_COMMANDS = ("DROP", "ALTER", "TRUNCATE", "CREATE", "ATTACH", "PRAGMA")
RESTRICTED_TABLES = {"users", "query_history", "audit_logs"}
RESTRICTED_COLUMNS = {"password_hash"}


def _response(
    *,
    is_valid: bool,
    query_type: str,
    execution_allowed: bool,
    requires_confirmation: bool,
    normalized_sql: str,
    warnings: list[str] | None = None,
    security_errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "is_valid": is_valid,
        "query_type": query_type,
        "execution_allowed": execution_allowed,
        "requires_confirmation": requires_confirmation,
        "normalized_sql": normalized_sql,
        "warnings": warnings or [],
        "security_errors": security_errors or [],
    }


def classify_query(sql: str) -> str:
    """Classify SQL into SELECT, INSERT, UPDATE, DELETE, TCL, DCL, DDL, or UNKNOWN."""
    cleaned = sql.strip().rstrip(";").strip()
    upper_sql = re.sub(r"\s+", " ", cleaned.upper())
    first_word = upper_sql.split(" ", 1)[0] if upper_sql else ""

    if any(upper_sql.startswith(command) for command in TCL_COMMANDS):
        return "TCL"
    if first_word in DCL_COMMANDS:
        return "DCL"
    if first_word in DDL_COMMANDS:
        return "DDL"
    if first_word in {"SELECT", "WITH"}:
        return "SELECT"
    if first_word == "INSERT":
        return "INSERT"
    if first_word == "UPDATE":
        return "UPDATE"
    if first_word == "DELETE":
        return "DELETE"
    return "UNKNOWN"


def validate_sql_syntax(sql: str) -> dict[str, Any]:
    """Validate that sqlglot can parse the SQL."""
    query_type = classify_query(sql)
    if query_type in {"TCL", "DCL"}:
        return _response(
            is_valid=True,
            query_type=query_type,
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql=sql.strip(),
        )

    try:
        sqlglot.parse_one(sql, dialect="sqlite")
    except sqlglot.errors.ParseError as exc:
        return _response(
            is_valid=False,
            query_type=query_type,
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql="",
            security_errors=[f"Invalid SQL syntax: {exc}"],
        )

    return _response(
        is_valid=True,
        query_type=query_type,
        execution_allowed=False,
        requires_confirmation=False,
        normalized_sql=_safe_normalize(sql),
    )


def validate_single_statement(sql: str) -> dict[str, Any]:
    """Reject comments and multiple SQL statements."""
    query_type = classify_query(sql)
    security_errors = []
    if _has_sql_comment(sql):
        security_errors.append("SQL comments are not allowed because they can bypass security checks.")

    try:
        statements = sqlglot.parse(sql, dialect="sqlite")
    except sqlglot.errors.ParseError:
        statements = []

    stripped = sql.strip()
    semicolon_count = stripped.count(";")
    if len(statements) > 1 or semicolon_count > 1 or (";" in stripped.rstrip(";")):
        security_errors.append("Only one SQL statement is allowed.")

    if security_errors:
        return _response(
            is_valid=False,
            query_type=query_type,
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql="",
            security_errors=security_errors,
        )

    return _response(
        is_valid=True,
        query_type=query_type,
        execution_allowed=False,
        requires_confirmation=False,
        normalized_sql=normalize_sql(sql),
    )


def validate_allowed_tables_and_columns(sql: str, current_user: Any) -> dict[str, Any]:
    """Validate that referenced tables and columns are permitted for the user."""
    query_type = classify_query(sql)
    errors = []

    if query_type in {"TCL", "DCL", "DDL", "UNKNOWN"}:
        return _response(
            is_valid=query_type == "TCL",
            query_type=query_type,
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql="" if query_type in {"DCL", "DDL", "UNKNOWN"} else sql.strip(),
            security_errors=[] if query_type == "TCL" else [f"{query_type} queries are not allowed."],
        )

    try:
        expression = sqlglot.parse_one(sql, dialect="sqlite")
    except sqlglot.errors.ParseError as exc:
        return _response(
            is_valid=False,
            query_type=query_type,
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql="",
            security_errors=[f"Invalid SQL syntax: {exc}"],
        )

    if _has_unsafe_join_or_union(expression):
        errors.append("JOIN and UNION queries are not allowed because they can bypass row-level security.")

    tables = _referenced_tables(expression)
    columns = _referenced_columns(expression)
    for table_name in tables:
        if table_name in RESTRICTED_TABLES or not can_access_table(current_user, table_name):
            errors.append(f"Table '{table_name}' is not allowed for this user.")

    for column_name in columns:
        if column_name in RESTRICTED_COLUMNS:
            errors.append(f"Column '{column_name}' is restricted.")
            continue
        if tables and not any(can_access_column(current_user, table_name, column_name) for table_name in tables):
            errors.append(f"Column '{column_name}' is not allowed for this user.")

    return _response(
        is_valid=not errors,
        query_type=query_type,
        execution_allowed=False,
        requires_confirmation=False,
        normalized_sql=normalize_sql(sql) if not errors else "",
        security_errors=errors,
    )


def validate_query_security(sql: str, current_user: Any) -> dict[str, Any]:
    """Run syntax, authorization, and execution-policy checks."""
    query_type = classify_query(sql)
    normalized = ""
    warnings = []
    errors = []

    single_statement = validate_single_statement(sql)
    if not single_statement["is_valid"]:
        return single_statement

    if query_type == "TCL":
        return _response(
            is_valid=True,
            query_type="TCL",
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql=sql.strip(),
            warnings=["Transaction control commands are view-only and are never executed by this system."],
        )

    if query_type == "DCL":
        return _response(
            is_valid=False,
            query_type="DCL",
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql="",
            security_errors=["Permission changes are not allowed. DCL commands are fully blocked."],
        )

    if query_type == "DDL":
        return _response(
            is_valid=False,
            query_type="DDL",
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql="",
            security_errors=["Schema changes are not allowed. DDL commands are fully blocked."],
        )

    if query_type == "UNKNOWN":
        return _response(
            is_valid=False,
            query_type="UNKNOWN",
            execution_allowed=False,
            requires_confirmation=False,
            normalized_sql="",
            security_errors=["Unknown query types are not allowed."],
        )

    syntax = validate_sql_syntax(sql)
    if not syntax["is_valid"]:
        return syntax
    normalized = syntax["normalized_sql"]

    authorization = validate_allowed_tables_and_columns(sql, current_user)
    if not authorization["is_valid"]:
        return authorization

    if not can_execute_query_type(current_user, query_type):
        errors.append(f"{query_type} queries are not allowed for role '{getattr(current_user, 'role', '')}'.")

    expression = sqlglot.parse_one(sql, dialect="sqlite")
    if query_type == "UPDATE":
        if not _has_where(expression):
            errors.append("UPDATE queries must include a WHERE clause.")
        if str(getattr(current_user, "role", "")).lower() == "manager" and not _manager_update_is_scoped(expression, current_user):
            errors.append("Manager UPDATE queries must be scoped to their own department.")
        warnings.append("UPDATE requires preview, impact analysis, and explicit confirmation before execution.")

    if query_type == "DELETE":
        if not _has_where(expression):
            errors.append("DELETE queries must include a WHERE clause.")
        warnings.append("DELETE requires preview, impact analysis, and explicit confirmation before execution.")

    requires_confirmation = query_type in {"UPDATE", "DELETE"}
    execution_allowed = not errors and query_type in {"SELECT", "INSERT", "UPDATE", "DELETE"}

    return _response(
        is_valid=not errors,
        query_type=query_type,
        execution_allowed=execution_allowed,
        requires_confirmation=requires_confirmation,
        normalized_sql=normalized if not errors else "",
        warnings=warnings,
        security_errors=errors,
    )


def normalize_sql(sql: str) -> str:
    """Return a normalized SQL string without a trailing semicolon."""
    query_type = classify_query(sql)
    if query_type in {"TCL", "DCL"}:
        return re.sub(r"\s+", " ", sql.strip().rstrip(";"))
    expression = sqlglot.parse_one(sql, dialect="sqlite")
    return expression.sql(dialect="sqlite").rstrip(";")


def _safe_normalize(sql: str) -> str:
    try:
        return normalize_sql(sql)
    except Exception:
        return re.sub(r"\s+", " ", sql.strip().rstrip(";"))


def is_select_only(sql: str) -> tuple[bool, str]:
    """Compatibility wrapper for older starter tests."""
    result = validate_query_security(sql, _ReadOnlyUser())
    if result["is_valid"] and result["query_type"] == "SELECT":
        return True, "SQL is read-only and structurally valid."
    message = "; ".join(result["security_errors"] or result["warnings"])
    return False, message or "Only SELECT statements are allowed."


class _ReadOnlyUser:
    role = "admin"
    user_id = 0
    department = None
    employee_id = None
    student_id = None


def _has_sql_comment(sql: str) -> bool:
    return bool(re.search(r"(--|/\*|\*/|#)", sql))


def _referenced_tables(expression: exp.Expression) -> set[str]:
    return {table.name.lower() for table in expression.find_all(exp.Table) if table.name}


def _referenced_columns(expression: exp.Expression) -> set[str]:
    columns = set()
    for column in expression.find_all(exp.Column):
        if column.name != "*":
            columns.add(column.name.lower())
    return columns


def _has_where(expression: exp.Expression) -> bool:
    return expression.args.get("where") is not None


def _has_unsafe_join_or_union(expression: exp.Expression) -> bool:
    union_node = getattr(exp, "Union", None)
    has_union = union_node is not None and (
        isinstance(expression, union_node) or expression.find(union_node) is not None
    )
    has_join = expression.find(exp.Join) is not None
    return has_join or has_union


def _manager_update_is_scoped(expression: exp.Expression, current_user: Any) -> bool:
    where = expression.args.get("where")
    if where is None:
        return False
    where_sql = where.sql(dialect="sqlite").lower()
    department = str(getattr(current_user, "department", "")).lower().replace("'", "''")
    return "department" in where_sql and department in where_sql
