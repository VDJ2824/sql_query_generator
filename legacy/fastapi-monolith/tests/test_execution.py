"""Smoke tests for query execution helpers."""

from backend.query_executor import execute_read_only_query


def test_module_imports() -> None:
    assert callable(execute_read_only_query)

