"""Compatibility wrapper for SQL generation.

New code should use `SqlGenerationService` directly.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from .schemas import GenerateResponse, InternalRequest
from .sql_generation_service import SqlGenerationService


def generate_options(engine: Engine, request: InternalRequest, dialect: str) -> GenerateResponse:
    return SqlGenerationService(engine, request, dialect).generate()
