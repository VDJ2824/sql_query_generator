"""Private SQL workspace provisioning and scoping helpers."""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, URL, make_url

from .config import database_url_from_env
from .schemas import DatabaseConnectionContext, VerifiedUser


WorkspaceMode = Literal["database", "schema", "file", "shared"]

WORKSPACE_RE = re.compile(r"^user_[a-z0-9_]+_[a-f0-9]{6}$")
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class WorkspaceContext:
    engine: Engine
    dialect: str
    workspace_name: str
    mode: WorkspaceMode
    schema_name: str | None = None


def workspace_name_for(connection: DatabaseConnectionContext, user: VerifiedUser) -> str:
    database_type = connection.databaseType.upper()
    if database_type == "MYSQL":
        workspace = user.tidbWorkspaceName or user.workspaceIdentifier
    elif database_type in {"POSTGRES", "POSTGRESQL"}:
        workspace = user.postgresWorkspaceName or user.workspaceIdentifier
    else:
        workspace = user.workspaceIdentifier
    if not workspace or not WORKSPACE_RE.fullmatch(workspace):
        raise ValueError("Invalid or missing private workspace identifier.")
    return workspace


def provisioned_workspace_engine(
    connection: DatabaseConnectionContext,
    user: VerifiedUser,
    dialect: str,
) -> WorkspaceContext:
    workspace_name = workspace_name_for(connection, user)
    database_type = connection.databaseType.upper()
    if database_type == "MYSQL":
        return _mysql_workspace(connection, workspace_name, dialect)
    if database_type in {"POSTGRES", "POSTGRESQL"}:
        return _postgres_workspace(connection, workspace_name, dialect)
    if database_type == "SQLITE":
        return _sqlite_workspace(connection, workspace_name, dialect)
    raise ValueError("Unsupported target database type.")


def postgres_create_database_supported(connection: DatabaseConnectionContext) -> bool:
    url = _url_for(connection)
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            value = conn.execute(
                text("SELECT COALESCE((SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user), false)")
            ).scalar()
            return bool(value)
    finally:
        engine.dispose()


def _mysql_workspace(connection: DatabaseConnectionContext, workspace_name: str, dialect: str) -> WorkspaceContext:
    base_url = _url_for(connection)
    provisioner = create_engine(base_url, connect_args=_connect_args_for("mysql"), pool_pre_ping=True)
    lock = _lock_for(f"mysql:{workspace_name}")
    with lock:
        with provisioner.begin() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{workspace_name}`"))
    provisioner.dispose()

    workspace_url = make_url(base_url).set(database=workspace_name).render_as_string(hide_password=False)
    return WorkspaceContext(
        engine=create_engine(workspace_url, connect_args=_connect_args_for("mysql"), pool_pre_ping=True),
        dialect=dialect,
        workspace_name=workspace_name,
        mode="database",
    )


def _postgres_workspace(connection: DatabaseConnectionContext, workspace_name: str, dialect: str) -> WorkspaceContext:
    base_url = _url_for(connection)
    if postgres_create_database_supported(connection):
        return _postgres_database_workspace(base_url, workspace_name, dialect)
    return _postgres_schema_workspace(base_url, workspace_name, dialect)


def _postgres_database_workspace(base_url: str, workspace_name: str, dialect: str) -> WorkspaceContext:
    provisioner = create_engine(base_url, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    lock = _lock_for(f"postgres-db:{workspace_name}")
    with lock:
        with provisioner.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": workspace_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{workspace_name}"'))
    provisioner.dispose()

    workspace_url = make_url(base_url).set(database=workspace_name).render_as_string(hide_password=False)
    return WorkspaceContext(
        engine=create_engine(workspace_url, pool_pre_ping=True),
        dialect=dialect,
        workspace_name=workspace_name,
        mode="database",
    )


def _postgres_schema_workspace(base_url: str, workspace_name: str, dialect: str) -> WorkspaceContext:
    engine = create_engine(base_url, pool_pre_ping=True)
    setattr(engine, "_workspace_schema", workspace_name)
    lock = _lock_for(f"postgres-schema:{workspace_name}")
    with lock:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{workspace_name}"'))

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f'SET search_path TO "{workspace_name}"')
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def _set_local_search_path(conn) -> None:  # type: ignore[no-untyped-def]
        conn.exec_driver_sql(f'SET LOCAL search_path TO "{workspace_name}"')

    return WorkspaceContext(
        engine=engine,
        dialect=dialect,
        workspace_name=workspace_name,
        mode="schema",
        schema_name=workspace_name,
    )


def _sqlite_workspace(connection: DatabaseConnectionContext, workspace_name: str, dialect: str) -> WorkspaceContext:
    # SQLite private files are reserved for local/offline expansion. The managed
    # cloud workflow currently focuses on PostgreSQL and TiDB workspaces.
    url = _url_for(connection)
    return WorkspaceContext(
        engine=create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True),
        dialect=dialect,
        workspace_name=workspace_name,
        mode="file",
    )


def _url_for(connection: DatabaseConnectionContext) -> str:
    return database_url_from_env(connection.credentialEnvironmentVariableName)


def _connect_args_for(dialect: str) -> dict[str, str]:
    if dialect != "mysql":
        return {}
    ssl_ca_path = os.getenv("MYSQL_SSL_CA_PATH", "")
    return {"ssl_ca": ssl_ca_path} if ssl_ca_path else {}


def _lock_for(name: str) -> threading.Lock:
    with _LOCKS_GUARD:
        if name not in _LOCKS:
            _LOCKS[name] = threading.Lock()
        return _LOCKS[name]


def validate_workspace_identifier(value: str) -> bool:
    return bool(WORKSPACE_RE.fullmatch(value or ""))
