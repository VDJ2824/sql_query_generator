"""Role-based access control helpers."""

from __future__ import annotations

from typing import Any


EMPLOYEE_TABLE = "employees"
STUDENT_TABLE = "students"

EMPLOYEE_COLUMNS = {
    "employee_id",
    "name",
    "email",
    "department",
    "salary",
    "joining_date",
    "manager_id",
}
STUDENT_COLUMNS = {
    "student_id",
    "name",
    "email",
    "course",
    "cgpa",
    "faculty_id",
}


def _role(current_user: Any) -> str:
    return str(getattr(current_user, "role", "")).lower()


def _normalize_table_name(table_name: str) -> str:
    normalized = table_name.strip().lower()
    aliases = {
        "employee": EMPLOYEE_TABLE,
        "employees": EMPLOYEE_TABLE,
        "student": STUDENT_TABLE,
        "students": STUDENT_TABLE,
    }
    return aliases.get(normalized, normalized)


def get_allowed_tables(current_user: Any) -> list[str]:
    """Return tables the current user is allowed to query."""
    role = _role(current_user)
    if role in {"admin", "manager", "employee"}:
        return [EMPLOYEE_TABLE, STUDENT_TABLE] if role == "admin" else [EMPLOYEE_TABLE]
    if role in {"faculty", "student"}:
        return [STUDENT_TABLE]
    return []


def get_allowed_columns(current_user: Any, table_name: str) -> list[str]:
    """Return columns the current user may read from a table."""
    normalized_table = _normalize_table_name(table_name)
    if not can_access_table(current_user, normalized_table):
        return []
    if normalized_table == EMPLOYEE_TABLE:
        return sorted(EMPLOYEE_COLUMNS)
    if normalized_table == STUDENT_TABLE:
        return sorted(STUDENT_COLUMNS)
    return []


def get_row_level_rule(current_user: Any, table_name: str) -> dict[str, Any]:
    """Return the row filter that must be enforced for the user's role."""
    role = _role(current_user)
    normalized_table = _normalize_table_name(table_name)

    if not can_access_table(current_user, normalized_table):
        return {
            "allowed": False,
            "message": f"{role or 'unknown'} users cannot access {normalized_table}.",
        }

    if role == "admin":
        return {
            "allowed": True,
            "rule": "all_rows",
            "message": "Admin can access all allowed rows.",
        }

    if role == "manager" and normalized_table == EMPLOYEE_TABLE:
        return {
            "allowed": True,
            "column": "department",
            "operator": "=",
            "value": getattr(current_user, "department", None),
            "message": "Manager can access Employee rows only in their own department.",
        }

    if role == "employee" and normalized_table == EMPLOYEE_TABLE:
        return {
            "allowed": True,
            "column": "employee_id",
            "operator": "=",
            "value": getattr(current_user, "employee_id", None),
            "message": "Employee can access only their own Employee record.",
        }

    if role == "faculty" and normalized_table == STUDENT_TABLE:
        return {
            "allowed": True,
            "column": "faculty_id",
            "operator": "=",
            "value": getattr(current_user, "user_id", None),
            "message": "Faculty can access only Students assigned to their user_id.",
        }

    if role == "student" and normalized_table == STUDENT_TABLE:
        return {
            "allowed": True,
            "column": "student_id",
            "operator": "=",
            "value": getattr(current_user, "student_id", None),
            "message": "Student can access only their own Student record.",
        }

    return {
        "allowed": False,
        "message": f"{role or 'unknown'} users do not have a row-level rule for {normalized_table}.",
    }


def can_execute_query_type(current_user: Any, query_type: str) -> bool:
    """Return whether the role may execute the requested SQL operation."""
    role = _role(current_user)
    normalized_query_type = query_type.strip().upper()

    allowed_query_types = {
        "admin": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "manager": {"SELECT", "UPDATE"},
        "employee": {"SELECT"},
        "faculty": {"SELECT"},
        "student": {"SELECT"},
    }
    return normalized_query_type in allowed_query_types.get(role, set())


def can_access_table(current_user: Any, table_name: str) -> bool:
    """Return whether the current user can access a table at all."""
    normalized_table = _normalize_table_name(table_name)
    return normalized_table in get_allowed_tables(current_user)


def can_access_column(current_user: Any, table_name: str, column_name: str) -> bool:
    """Return whether the current user can access a table column."""
    normalized_column = column_name.strip().lower()
    return normalized_column in get_allowed_columns(current_user, table_name)


def can_access_row(current_user: Any, table_name: str, row: dict[str, Any]) -> bool:
    """Evaluate a row against the role's row-level rule."""
    rule = get_row_level_rule(current_user, table_name)
    if not rule.get("allowed"):
        return False
    if rule.get("rule") == "all_rows":
        return True
    column = rule.get("column")
    return row.get(column) == rule.get("value")


def get_authorization_error(current_user: Any, action: str, table_name: str) -> str:
    """Return a clear message for denied access."""
    role = _role(current_user) or "unknown"
    normalized_table = _normalize_table_name(table_name)
    return f"{role} is not allowed to {action} on {normalized_table}."

