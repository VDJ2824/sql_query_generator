"""Allow-listed infrastructure DDL helpers.

Normal user SQL always runs through the restricted application database URL.
This module intentionally supports only admin-confirmed CREATE DATABASE
statements through separate privileged admin URLs.
"""

from __future__ import annotations

import os
import re

from sqlalchemy import create_engine, text

from .schemas import ExecuteResponse, InternalRequest, PreviewResponse


BLOCKED_INFRASTRUCTURE_PATTERNS = (
    "DROP DATABASE",
    "CREATE ROLE",
    "CREATE USER",
    "ALTER SYSTEM",
    "GRANT",
    "REVOKE",
    "SUPERUSER",
)

CREATE_DATABASE_RE = re.compile(r"^\s*CREATE\s+DATABASE\s+([A-Za-z_][A-Za-z0-9_]*)\s*;?\s*$", re.IGNORECASE)


def preview_admin_ddl(request: InternalRequest, dialect: str) -> PreviewResponse:
    sql = request.generatedSql or ""
    allowed, message, final_sql = _validate_admin_create_database(sql, request, dialect)
    return PreviewResponse(
        generatedSql=sql,
        finalEnforcedSql=final_sql if allowed else "",
        previewSql="",
        queryType="DDL",
        estimatedRows=0,
        previewRows=[],
        impactMessage=message,
        riskLevel="high",
        executionAllowed=allowed,
        requiresConfirmation=allowed,
        warnings=["CREATE DATABASE uses a separate privileged admin connection."] if allowed else [],
        securityErrors=[] if allowed else [message],
    )


def execute_admin_ddl(request: InternalRequest, dialect: str) -> ExecuteResponse:
    sql = request.generatedSql or ""
    allowed, message, final_sql = _validate_admin_create_database(sql, request, dialect)
    if not allowed:
        return _blocked(sql, message)
    if not request.confirmed:
        return _blocked(sql, "CREATE DATABASE requires explicit confirmation.")

    admin_url = _admin_url_for(request.databaseConnection.databaseType)
    if not admin_url:
        return _blocked(sql, "Privileged admin database URL is not configured.")

    engine = create_engine(admin_url, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text(final_sql))

    return ExecuteResponse(
        success=True,
        message="Allow-listed CREATE DATABASE command executed successfully.",
        generatedSql=sql,
        finalEnforcedSql=final_sql,
        queryType="DDL",
        rowsAffected=0,
        resultRows=[],
        executionAllowed=True,
    )


def _validate_admin_create_database(sql: str, request: InternalRequest, dialect: str) -> tuple[bool, str, str]:
    upper_sql = re.sub(r"\s+", " ", sql.strip().upper())
    if any(pattern in upper_sql for pattern in BLOCKED_INFRASTRUCTURE_PATTERNS):
        return False, "Unsafe infrastructure command is blocked.", ""
    if request.verifiedUser.role.upper() != "ADMIN":
        return False, "Only admin users may request allow-listed infrastructure DDL.", ""

    match = CREATE_DATABASE_RE.match(sql)
    if not match:
        return False, "Only CREATE DATABASE database_name is allow-listed for admin DDL.", ""

    database_name = match.group(1)
    if dialect == "postgres":
        final_sql = f'CREATE DATABASE "{database_name}"'
    elif dialect == "mysql":
        final_sql = f"CREATE DATABASE `{database_name}`"
    else:
        return False, "Allow-listed infrastructure DDL is supported only for PostgreSQL and MySQL.", ""

    return True, "CREATE DATABASE is allow-listed but requires explicit confirmation.", final_sql


def _admin_url_for(database_type: str) -> str | None:
    normalized = database_type.upper()
    if normalized in {"POSTGRES", "POSTGRESQL"}:
        return os.getenv("POSTGRES_ADMIN_URL")
    if normalized == "MYSQL":
        return os.getenv("MYSQL_ADMIN_URL")
    return None


def _blocked(sql: str, message: str) -> ExecuteResponse:
    return ExecuteResponse(
        success=False,
        message=message,
        generatedSql=sql,
        finalEnforcedSql="",
        queryType="DDL",
        rowsAffected=0,
        resultRows=[],
        executionAllowed=False,
    )
