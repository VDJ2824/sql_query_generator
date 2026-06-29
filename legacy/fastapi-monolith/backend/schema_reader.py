"""Read the database schema while applying role-based visibility rules."""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .authorization import get_allowed_tables


TABLE_LABELS = {
    "employees": "Employee",
    "students": "Students",
}

SAFE_COLUMNS_BY_ROLE = {
    "admin": {
        "employees": {"employee_id", "name", "email", "department", "salary", "joining_date", "manager_id"},
        "students": {"student_id", "name", "email", "course", "cgpa", "faculty_id"},
    },
    "manager": {
        "employees": {"employee_id", "name", "email", "department", "salary", "joining_date", "manager_id"},
    },
    "employee": {
        "employees": {"employee_id", "name", "email", "department", "salary", "joining_date"},
    },
    "faculty": {
        "students": {"student_id", "name", "email", "course", "cgpa", "faculty_id"},
    },
    "student": {
        "students": {"student_id", "name", "email", "course", "cgpa"},
    },
}

ROW_ACCESS_MESSAGES = {
    "admin": {
        "employees": "All Employee rows can be accessed.",
        "students": "All Students rows can be accessed.",
    },
    "manager": {
        "employees": "Only Employee records from the manager's department can be accessed.",
    },
    "employee": {
        "employees": "Only the logged-in employee's record can be accessed.",
    },
    "faculty": {
        "students": "Only students assigned to the logged-in faculty can be accessed.",
    },
    "student": {
        "students": "Only the logged-in student's record can be accessed.",
    },
}


def _role(current_user: Any) -> str:
    return str(getattr(current_user, "role", "")).lower()


def _format_type(column_type: Any) -> str:
    return str(column_type).upper()


def read_schema(engine: Engine) -> dict[str, list[str]]:
    """Return the raw database schema as table names mapped to column names."""
    inspector = inspect(engine)
    schema: dict[str, list[str]] = {}
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        schema[table_name] = [column["name"] for column in columns]
    return schema


def read_accessible_schema(engine: Engine, current_user: Any) -> dict[str, Any]:
    """Return schema details that the logged-in user's role is allowed to see."""
    inspector = inspect(engine)
    role = _role(current_user)
    visible_tables = set(get_allowed_tables(current_user))
    schema_tables = []

    for table_name in inspector.get_table_names():
        if table_name not in TABLE_LABELS or table_name not in visible_tables:
            continue

        allowed_column_names = SAFE_COLUMNS_BY_ROLE.get(role, {}).get(table_name, set())
        columns = [
            {
                "name": column["name"],
                "type": _format_type(column["type"]),
            }
            for column in inspector.get_columns(table_name)
            if column["name"] in allowed_column_names and column["name"] != "password_hash"
        ]

        schema_tables.append(
            {
                "table_name": TABLE_LABELS[table_name],
                "allowed_columns": columns,
                "row_access_rule": ROW_ACCESS_MESSAGES.get(role, {}).get(
                    table_name,
                    "No rows can be accessed for this role.",
                ),
            }
        )

    return {
        "role": role,
        "allowed_tables": schema_tables,
    }

