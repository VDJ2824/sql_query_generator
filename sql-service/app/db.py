"""Dynamic SQLAlchemy connection helpers for target relational databases."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from .schemas import DatabaseConnectionContext, InternalRequest, VerifiedUser
from .workspaces import provisioned_workspace_engine, workspace_name_for


DIALECT_BY_TYPE = {
    "POSTGRESQL": "postgres",
    "POSTGRES": "postgres",
    "MYSQL": "mysql",
    "SQLITE": "sqlite",
}


def dialect_for(database_type: str) -> str:
    normalized_type = database_type.strip().upper()
    if normalized_type not in DIALECT_BY_TYPE:
        raise ValueError("Unsupported target database type.")
    return DIALECT_BY_TYPE[normalized_type]


def dialect_for_connection(connection: DatabaseConnectionContext) -> str:
    if connection.dialect:
        normalized_dialect = connection.dialect.strip().lower()
        if normalized_dialect in {"sqlite", "postgres", "mysql"}:
            return normalized_dialect
    return dialect_for(connection.databaseType)


def engine_for(connection: DatabaseConnectionContext, user: VerifiedUser | None = None) -> Engine:
    """Create a workspace-scoped engine for the selected managed cloud database."""
    dialect = dialect_for_connection(connection)
    if user is not None:
        return provisioned_workspace_engine(connection, user, dialect).engine
    raise ValueError("Verified user context is required for private SQL workspace access.")


def ensure_workspace_for_request(request: InternalRequest) -> str:
    """Compatibility helper kept for older callers.

    Returns the validated private workspace identifier and provisions lazily.
    """
    workspace = workspace_name_for(request.databaseConnection, request.verifiedUser)
    engine_for(request.databaseConnection, request.verifiedUser).dispose()
    return workspace
