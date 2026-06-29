"""Internal FastAPI SQL/NLP microservice."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine

from .db import dialect_for_connection, engine_for
from .dependencies import require_internal_api_key
from .execution import execute_sql, preview_sql
from .schema_reader import read_allowed_schema, schema_from_policies
from .schemas import (
    ExecuteResponse,
    GenerateResponse,
    InternalRequest,
    PreviewResponse,
    SchemaResponse,
)
from .sql_generation_service import SqlGenerationService


app = FastAPI(
    title="Internal SQL Service",
    description="Internal-only SQL intelligence service called by Express.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sql-service"}


@app.post("/internal/schema", response_model=SchemaResponse, dependencies=[Depends(require_internal_api_key)])
def internal_schema(request: InternalRequest) -> dict:
    dialect, engine = _target_context(request)
    return read_allowed_schema(engine, request.verifiedUser, request.accessPolicies, dialect)


@app.post("/internal/generate", response_model=GenerateResponse, dependencies=[Depends(require_internal_api_key)])
def internal_generate(request: InternalRequest) -> GenerateResponse:
    dialect = dialect_for_connection(request.databaseConnection)
    try:
        engine = engine_for(request.databaseConnection, request.verifiedUser)
        allowed_schema = read_allowed_schema(engine, request.verifiedUser, request.accessPolicies, dialect)
        return SqlGenerationService(engine, request, dialect, allowed_schema=allowed_schema).generate()
    except (SQLAlchemyError, ValueError):
        warning = (
            "Target database was not reachable during generation, so schema context came from access policies only. "
            "Preview and execution will require a successful database connection."
        )
        return SqlGenerationService(
            None,
            request,
            dialect,
            allowed_schema=schema_from_policies(request.verifiedUser, request.accessPolicies, dialect),
            schema_warning=warning,
        ).generate()


@app.post("/internal/preview", response_model=PreviewResponse, dependencies=[Depends(require_internal_api_key)])
def internal_preview(request: InternalRequest) -> PreviewResponse:
    dialect, engine = _target_context(request)
    return preview_sql(engine, request, dialect)


@app.post("/internal/execute", response_model=ExecuteResponse, dependencies=[Depends(require_internal_api_key)])
def internal_execute(request: InternalRequest) -> ExecuteResponse:
    dialect, engine = _target_context(request)
    return execute_sql(engine, request, dialect)


def _target_context(request: InternalRequest) -> tuple[str, Engine]:
    try:
        dialect = dialect_for_connection(request.databaseConnection)
        engine = engine_for(request.databaseConnection, request.verifiedUser)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Selected target database is not reachable or credentials are invalid.",
        ) from exc
    return dialect, engine
