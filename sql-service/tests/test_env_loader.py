from __future__ import annotations

import os

from app.env_loader import load_environment
from app.config import database_url_from_env


def test_fastapi_env_loader_reads_root_env_cloud(tmp_path, monkeypatch) -> None:
    service_root = tmp_path / "sql-service"
    service_root.mkdir()
    (tmp_path / ".env.cloud").write_text("CLOUD_LOADER_TEST_VALUE=from-cloud\n", encoding="utf-8")

    load_environment(tmp_path, service_root)

    assert os.getenv("CLOUD_LOADER_TEST_VALUE") == "from-cloud"


def test_fastapi_env_loader_keeps_existing_process_values(tmp_path, monkeypatch) -> None:
    service_root = tmp_path / "sql-service"
    service_root.mkdir()
    monkeypatch.setenv("CLOUD_LOADER_TEST_VALUE", "from-process")
    (tmp_path / ".env.cloud").write_text("CLOUD_LOADER_TEST_VALUE=from-cloud\n", encoding="utf-8")

    load_environment(tmp_path, service_root)

    assert os.getenv("CLOUD_LOADER_TEST_VALUE") == "from-process"


def test_fastapi_env_loader_uses_service_env_only_for_missing_values(tmp_path, monkeypatch) -> None:
    service_root = tmp_path / "sql-service"
    service_root.mkdir()
    (tmp_path / ".env.cloud").write_text("CLOUD_LOADER_TEST_VALUE=from-cloud\n", encoding="utf-8")
    (service_root / ".env").write_text(
        "CLOUD_LOADER_TEST_VALUE=from-service\nCLOUD_LOADER_SERVICE_VALUE=service-only\n",
        encoding="utf-8",
    )

    load_environment(tmp_path, service_root)

    assert os.getenv("CLOUD_LOADER_TEST_VALUE") == "from-cloud"
    assert os.getenv("CLOUD_LOADER_SERVICE_VALUE") == "service-only"


def test_database_url_from_env_normalizes_generic_cloud_drivers(monkeypatch) -> None:
    monkeypatch.setenv("TEST_POSTGRES_URL", "postgresql://user:pass@example.com/demo")
    monkeypatch.setenv("TEST_MYSQL_URL", "mysql://user:pass@example.com/demo")

    assert database_url_from_env("TEST_POSTGRES_URL").startswith("postgresql+psycopg://")
    assert database_url_from_env("TEST_MYSQL_URL").startswith("mysql+pymysql://")
