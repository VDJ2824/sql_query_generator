"""Dynamic schema reader for target relational databases."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .policies import all_workspace_tables_allowed, allowed_columns_for_table, allowed_tables, blocked_tables
from .schemas import AccessPolicy, VerifiedUser


def read_allowed_schema(engine: Engine, user: VerifiedUser, policies: list[AccessPolicy], dialect: str) -> dict:
    inspector = inspect(engine)
    policy_tables = allowed_tables(policies, user)
    allow_all_tables = all_workspace_tables_allowed(policies, user)
    blocked = blocked_tables(policies, user)
    tables = []

    schema_name = getattr(engine, "_workspace_schema", None)
    table_names = inspector.get_table_names(schema=schema_name) if schema_name else inspector.get_table_names()

    for table_name in table_names:
        normalized_table = table_name.lower()
        if normalized_table in blocked:
            continue
        if not allow_all_tables and normalized_table not in policy_tables:
            continue

        allowed_columns = allowed_columns_for_table(policies, user, normalized_table)
        columns = []
        for column in inspector.get_columns(table_name, schema=schema_name):
            column_name = column["name"].lower()
            if allowed_columns and column_name not in allowed_columns:
                continue
            columns.append(
                {
                    "name": column["name"],
                    "type": str(column["type"]).upper(),
                    "nullable": bool(column.get("nullable", True)),
                    "default": str(column.get("default")) if column.get("default") is not None else None,
                    "primaryKey": bool(column.get("primary_key", False)),
                    "requiredForInsert": _required_for_insert(column),
                }
            )

        row_rule = "Rows allowed by connection, table, column, and operation policy. No business-profile row filter is applied."

        tables.append(
            {
                "tableName": table_name,
                "allowedColumns": columns,
                "rowAccessRule": row_rule,
            }
        )

    return {"role": user.role, "dialect": dialect, "allowedTables": tables}


def schema_from_policies(user: VerifiedUser, policies: list[AccessPolicy], dialect: str) -> dict:
    """Build a conservative schema from access policies when the DB is offline.

    This is used for query generation only. Preview and execution still require
    a live target database connection.
    """
    blocked = blocked_tables(policies, user)
    tables = []

    for table_name in sorted(allowed_tables(policies, user)):
        normalized_table = table_name.lower()
        if normalized_table in blocked:
            continue

        allowed_columns = sorted(allowed_columns_for_table(policies, user, normalized_table))
        columns = [
            {
                "name": column,
                "type": "UNKNOWN",
                "nullable": True,
                "default": None,
                "primaryKey": False,
                "requiredForInsert": False,
            }
            for column in allowed_columns
        ]
        row_rule = (
            "Schema was derived from access policies because the target database was not reachable during generation. "
            "Preview and execution will reconnect and validate against the real database."
        )
        tables.append(
            {
                "tableName": table_name,
                "allowedColumns": columns,
                "rowAccessRule": row_rule,
            }
        )

    return {"role": user.role, "dialect": dialect, "allowedTables": tables}


def _required_for_insert(column: dict) -> bool:
    if column.get("default") is not None:
        return False
    if column.get("primary_key", False):
        return True
    if column.get("nullable", True):
        return False
    return True
