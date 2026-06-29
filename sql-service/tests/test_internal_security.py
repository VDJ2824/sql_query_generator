from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db import dialect_for_connection
from app.execution import execute_sql, preview_sql
from app.main import app
from app.row_level_security_service import RowLevelSecurityService
from app.schemas import AccessPolicy, DatabaseConnectionContext, InternalRequest, VerifiedUser
from app.sql_security import classify_query, classify_sql_command, validate_sql
from app.workspaces import validate_workspace_identifier, workspace_name_for


def _create_sqlite_db(path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            region TEXT,
            amount REAL,
            created_at TEXT
        )
        """
    )
    connection.execute("INSERT INTO sales (id, region, amount, created_at) VALUES (1, 'West', 125.0, '2026-01-01')")
    connection.execute("INSERT INTO sales (id, region, amount, created_at) VALUES (2, 'East', 250.0, '2026-01-02')")
    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT)")
    connection.commit()
    connection.close()


def _create_student_sqlite_db(path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE Student (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            roll_no TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE
        )
        """
    )
    connection.commit()
    connection.close()


def _policy(role: str = "USER", operations: list[str] | None = None, columns: list[str] | None = None) -> dict:
    return {
        "role": role,
        "databaseConnectionId": "connection-1",
        "allowedOperations": operations or ["SELECT"],
        "allowedSchemas": [],
        "allowedTables": ["sales"],
        "blockedTables": ["users", "audit_logs", "query_history", "selected_queries"],
        "allowedColumns": columns or ["id", "region", "amount", "created_at"],
        "requiresPreviewFor": ["INSERT", "UPDATE", "DELETE", "DDL"],
        "requiresConfirmationFor": ["INSERT", "UPDATE", "DELETE", "DDL"],
        "active": True,
    }


def _payload(env_name: str, sql: str = "SELECT id, region, amount FROM sales", role: str = "USER") -> dict:
    return {
        "verifiedUser": {
            "userId": "user-1",
            "role": role,
            "workspaceIdentifier": "user_test_abcdef",
            "postgresWorkspaceName": "user_test_abcdef",
            "tidbWorkspaceName": "user_test_abcdef",
        },
        "databaseConnection": {
            "connectionId": "connection-1",
            "databaseType": "SQLITE",
            "credentialEnvironmentVariableName": env_name,
        },
        "accessPolicies": [_policy(role)],
        "prompt": "show sales",
        "generatedSql": sql,
    }


def _request(sql: str, role: str = "USER", operations: list[str] | None = None, confirmed: bool = False) -> InternalRequest:
    return InternalRequest(
        verifiedUser=VerifiedUser(
            userId="user-1",
            role=role,
            workspaceIdentifier="user_test_abcdef",
            postgresWorkspaceName="user_test_abcdef",
            tidbWorkspaceName="user_test_abcdef",
        ),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="SQLITE",
            credentialEnvironmentVariableName="SQLITE_TEST_URL",
        ),
        accessPolicies=[AccessPolicy(**_policy(role, operations))],
        generatedSql=sql,
        confirmed=confirmed,
    )


def test_internal_endpoints_require_valid_api_key(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "reporting.db"
    env_name = "TEST_TARGET_DATABASE_URL"
    _create_sqlite_db(db_path)
    monkeypatch.setenv("SQL_SERVICE_API_KEY", "test-internal-key")
    monkeypatch.setenv(env_name, f"sqlite:///{db_path}")

    client = TestClient(app)
    missing = client.post("/internal/schema", json=_payload(env_name))
    invalid = client.post(
        "/internal/schema",
        json=_payload(env_name),
        headers={"x-internal-api-key": "wrong"},
    )
    valid = client.post(
        "/internal/schema",
        json=_payload(env_name),
        headers={"x-internal-api-key": "test-internal-key"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 200
    assert valid.json()["allowedTables"][0]["tableName"] == "sales"


def test_health_endpoint_does_not_expose_secrets(monkeypatch) -> None:
    monkeypatch.setenv("SQL_SERVICE_API_KEY", "secret-internal-key")
    monkeypatch.setenv("POSTGRES_DEMO_URL", "postgresql+psycopg://user:secret@example.invalid/db")
    monkeypatch.setenv("MYSQL_DEMO_URL", "mysql+pymysql://user:secret@example.invalid/db")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-gemini-key")

    response = TestClient(app).get("/health")
    body = response.text

    assert response.status_code == 200
    assert "secret" not in body
    assert "POSTGRES_DEMO_URL" not in body
    assert "MYSQL_DEMO_URL" not in body
    assert response.json() == {"status": "ok", "service": "sql-service"}


def test_active_fastapi_code_has_no_mongodb_client_usage() -> None:
    app_dir = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(path.read_text() for path in app_dir.rglob("*.py"))

    assert "pymongo" not in source
    assert "motor.motor_asyncio" not in source
    assert "MongoClient" not in source
    assert "MONGODB_URI" not in source


def test_workspace_identifiers_are_strictly_validated() -> None:
    assert validate_workspace_identifier("user_varima_8f31a9") is True
    assert validate_workspace_identifier("workspace_varima") is False
    assert validate_workspace_identifier("user_Varima_8f31a9") is False
    assert validate_workspace_identifier("user_varima_8f31a9;drop") is False


def test_workspace_name_for_uses_engine_specific_verified_context() -> None:
    user = VerifiedUser(
        userId="user-1",
        role="USER",
        workspaceIdentifier="user_common_111aaa",
        postgresWorkspaceName="user_postgres_222bbb",
        tidbWorkspaceName="user_tidb_333ccc",
    )
    postgres = DatabaseConnectionContext(
        connectionId="postgres",
        databaseType="POSTGRESQL",
        credentialEnvironmentVariableName="POSTGRES_DEMO_URL",
    )
    mysql = DatabaseConnectionContext(
        connectionId="mysql",
        databaseType="MYSQL",
        credentialEnvironmentVariableName="MYSQL_DEMO_URL",
    )

    assert workspace_name_for(postgres, user) == "user_postgres_222bbb"
    assert workspace_name_for(mysql, user) == "user_tidb_333ccc"


def test_generate_uses_policy_schema_when_target_database_is_unreachable(tmp_path, monkeypatch) -> None:
    missing_parent = tmp_path / "missing" / "reporting.db"
    env_name = "UNREACHABLE_TARGET_DATABASE_URL"
    monkeypatch.setenv("SQL_SERVICE_API_KEY", "test-internal-key")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv(env_name, f"sqlite:///{missing_parent}")

    client = TestClient(app)
    response = client.post(
        "/internal/generate",
        json=_payload(env_name, "SELECT id, region, amount FROM sales"),
        headers={"x-internal-api-key": "test-internal-key"},
    )

    assert response.status_code == 200
    options = response.json()["queryOptions"]
    assert options
    assert "Target database was not reachable" in " ".join(options[0]["warnings"])


def test_generate_creates_safe_ddl_option_instead_of_selecting_existing_students(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "reporting.db"
    env_name = "TEST_TARGET_DATABASE_URL"
    _create_sqlite_db(db_path)
    monkeypatch.setenv("SQL_SERVICE_API_KEY", "test-internal-key")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv(env_name, f"sqlite:///{db_path}")
    payload = _payload(env_name)
    payload["prompt"] = "create table named Student with columns: id, name, roll_no and email."
    payload["accessPolicies"] = [_policy(operations=["DQL", "DML", "DDL"])]

    client = TestClient(app)
    response = client.post(
        "/internal/generate",
        json=payload,
        headers={"x-internal-api-key": "test-internal-key"},
    )

    assert response.status_code == 200
    option = response.json()["queryOptions"][0]
    assert option["queryType"] == "DDL"
    assert option["executionAllowed"] is True
    assert option["requiresConfirmation"] is True
    assert option["generatedSql"].startswith("CREATE TABLE Student")
    assert "id INTEGER PRIMARY KEY" in option["generatedSql"]
    assert "name" in option["generatedSql"]
    assert "roll_no" in option["generatedSql"]
    assert "email" in option["generatedSql"]
    assert "DDL requires preview" in " ".join(option["warnings"])


def test_ai_insert_missing_required_columns_is_rejected_and_fallback_uses_schema() -> None:
    from app.sql_generation_service import SqlGenerationService

    request = InternalRequest(
        verifiedUser=VerifiedUser(
            userId="user-1",
            role="USER",
            workspaceIdentifier="user_test_abcdef",
            postgresWorkspaceName="user_test_abcdef",
            tidbWorkspaceName="user_test_abcdef",
        ),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="SQLITE",
            credentialEnvironmentVariableName="SQLITE_TEST_URL",
        ),
        accessPolicies=[
            AccessPolicy(
                **{
                    **_policy(operations=["DQL", "DML"], columns=["id", "name", "roll_no", "email"]),
                    "allowedTables": ["Student"],
                }
            )
        ],
        prompt="give a query to insert 5 records in the table Student.",
    )
    allowed_schema = {
        "role": "USER",
        "dialect": "sqlite",
        "allowedTables": [
            {
                "tableName": "Student",
                "allowedColumns": [
                    {"name": "id", "type": "INTEGER", "nullable": True, "default": None, "primaryKey": True, "requiredForInsert": True},
                    {"name": "name", "type": "TEXT", "nullable": False, "default": None, "primaryKey": False, "requiredForInsert": True},
                    {"name": "roll_no", "type": "TEXT", "nullable": False, "default": None, "primaryKey": False, "requiredForInsert": True},
                    {"name": "email", "type": "TEXT", "nullable": False, "default": None, "primaryKey": False, "requiredForInsert": True},
                ],
                "rowAccessRule": "Private workspace.",
            }
        ],
    }
    service = SqlGenerationService(None, request, "sqlite", allowed_schema=allowed_schema)
    service._call_ai = lambda: {  # noqa: SLF001
        "queryOptions": [
            {
                "title": "Bad assumed auto increment",
                "generatedSql": "INSERT INTO Student (name, email) VALUES ('Alice', 'alice@example.com')",
            },
            {
                "title": "Bad missing roll number",
                "generatedSql": "INSERT INTO Student (id, name, email) VALUES (1, 'Bob', 'bob@example.com')",
            },
        ]
    }

    option = service.generate().queryOptions[0]

    assert "INSERT INTO Student (id, name, roll_no, email)" in option.generatedSql
    assert "R001" in option.generatedSql
    assert option.queryType == "DML"


def test_insert_options_differing_only_by_literals_are_deduplicated() -> None:
    from app.sql_generation_service import SqlGenerationService

    request = InternalRequest(
        verifiedUser=VerifiedUser(
            userId="user-1",
            role="USER",
            workspaceIdentifier="user_test_abcdef",
            postgresWorkspaceName="user_test_abcdef",
            tidbWorkspaceName="user_test_abcdef",
        ),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="SQLITE",
            credentialEnvironmentVariableName="SQLITE_TEST_URL",
        ),
        accessPolicies=[
            AccessPolicy(
                **{
                    **_policy(operations=["DQL", "DML"], columns=["id", "name", "roll_no", "email"]),
                    "allowedTables": ["Student"],
                }
            )
        ],
        prompt="give a query to insert 2 records in the table Student.",
    )
    allowed_schema = {
        "role": "USER",
        "dialect": "sqlite",
        "allowedTables": [
            {
                "tableName": "Student",
                "allowedColumns": [
                    {"name": "id", "type": "INTEGER", "nullable": True, "default": None, "primaryKey": True, "requiredForInsert": True},
                    {"name": "name", "type": "TEXT", "nullable": False, "default": None, "primaryKey": False, "requiredForInsert": True},
                    {"name": "roll_no", "type": "TEXT", "nullable": False, "default": None, "primaryKey": False, "requiredForInsert": True},
                    {"name": "email", "type": "TEXT", "nullable": False, "default": None, "primaryKey": False, "requiredForInsert": True},
                ],
                "rowAccessRule": "Private workspace.",
            }
        ],
    }
    service = SqlGenerationService(None, request, "sqlite", allowed_schema=allowed_schema)
    service._call_ai = lambda: {  # noqa: SLF001
        "queryOptions": [
            {
                "title": "Dataset A",
                "generatedSql": (
                    "INSERT INTO Student (id, name, roll_no, email) VALUES "
                    "(1, 'Alice', 'STU001', 'alice@example.com'), "
                    "(2, 'Bob', 'STU002', 'bob@example.com')"
                ),
            },
            {
                "title": "Dataset B",
                "generatedSql": (
                    "INSERT INTO Student (id, name, roll_no, email) VALUES "
                    "(101, 'Maya', 'ABC101', 'maya@example.com'), "
                    "(102, 'Noah', 'ABC102', 'noah@example.com')"
                ),
            },
        ]
    }

    options = service.generate().queryOptions

    assert len(options) == 1
    assert options[0].title == "Dataset A"


def test_insert_into_missing_private_workspace_table_returns_clear_message() -> None:
    from app.sql_generation_service import SqlGenerationService

    request = InternalRequest(
        verifiedUser=VerifiedUser(
            userId="user-1",
            role="USER",
            workspaceIdentifier="user_test_abcdef",
            postgresWorkspaceName="user_test_abcdef",
            tidbWorkspaceName="user_test_abcdef",
        ),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="MYSQL",
            credentialEnvironmentVariableName="MYSQL_DEMO_URL",
        ),
        accessPolicies=[AccessPolicy(**{**_policy(operations=["DQL", "DML"]), "allowedTables": []})],
        prompt="Give a query to insert five records in the table Student.",
    )

    option = SqlGenerationService(None, request, "mysql", allowed_schema={"role": "USER", "dialect": "mysql", "allowedTables": []}).generate().queryOptions[0]

    assert option.executionAllowed is False
    assert option.queryType == "UNKNOWN"
    assert "Student table is not available" in option.title
    assert "private MYSQL workspace" in option.explanation


def test_insert_preview_blocks_missing_required_columns(tmp_path) -> None:
    db_path = tmp_path / "student_required.db"
    _create_student_sqlite_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    request = InternalRequest(
        verifiedUser=VerifiedUser(
            userId="user-1",
            role="USER",
            workspaceIdentifier="user_test_abcdef",
            postgresWorkspaceName="user_test_abcdef",
            tidbWorkspaceName="user_test_abcdef",
        ),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="SQLITE",
            credentialEnvironmentVariableName="SQLITE_TEST_URL",
        ),
        accessPolicies=[
            AccessPolicy(
                **{
                    **_policy(operations=["DQL", "DML"], columns=["id", "name", "roll_no", "email"]),
                    "allowedTables": ["Student"],
                }
            )
        ],
        generatedSql="INSERT INTO Student (name, email) VALUES ('Alice', 'alice@example.com')",
        confirmed=True,
    )

    preview = preview_sql(engine, request, "sqlite")
    execution = execute_sql(engine, request, "sqlite")

    assert preview.executionAllowed is False
    assert "roll_no" in " ".join(preview.securityErrors)
    assert execution.success is False
    assert "roll_no" in execution.message


def test_insert_preview_estimates_multirow_values_count(tmp_path) -> None:
    db_path = tmp_path / "student_multi_insert.db"
    _create_student_sqlite_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    request = InternalRequest(
        verifiedUser=VerifiedUser(
            userId="user-1",
            role="USER",
            workspaceIdentifier="user_test_abcdef",
            postgresWorkspaceName="user_test_abcdef",
            tidbWorkspaceName="user_test_abcdef",
        ),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="SQLITE",
            credentialEnvironmentVariableName="SQLITE_TEST_URL",
        ),
        accessPolicies=[
            AccessPolicy(
                **{
                    **_policy(operations=["DQL", "DML"], columns=["id", "name", "roll_no", "email"]),
                    "allowedTables": ["Student"],
                }
            )
        ],
        generatedSql=(
            "INSERT INTO Student (id, name, roll_no, email) VALUES "
            "(1, 'Alice Smith', 'STU001', 'alice@example.com'), "
            "(2, 'Bob Johnson', 'STU002', 'bob@example.com'), "
            "(3, 'Charlie Brown', 'STU003', 'charlie@example.com'), "
            "(4, 'Diana Prince', 'STU004', 'diana@example.com'), "
            "(5, 'Eve Adams', 'STU005', 'eve@example.com')"
        ),
    )

    preview = preview_sql(engine, request, "sqlite")

    assert preview.executionAllowed is True
    assert preview.estimatedRows == 5
    assert "may add 5 rows" in preview.impactMessage


def test_insert_execution_returns_inserted_rows(tmp_path) -> None:
    db_path = tmp_path / "student_execute_insert.db"
    _create_student_sqlite_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    request = InternalRequest(
        verifiedUser=VerifiedUser(
            userId="user-1",
            role="USER",
            workspaceIdentifier="user_test_abcdef",
            postgresWorkspaceName="user_test_abcdef",
            tidbWorkspaceName="user_test_abcdef",
        ),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="SQLITE",
            credentialEnvironmentVariableName="SQLITE_TEST_URL",
        ),
        accessPolicies=[
            AccessPolicy(
                **{
                    **_policy(operations=["DQL", "DML"], columns=["id", "name", "roll_no", "email"]),
                    "allowedTables": ["Student"],
                }
            )
        ],
        generatedSql=(
            "INSERT INTO Student (id, name, roll_no, email) VALUES "
            "(1, 'Alice Smith', 'STU001', 'alice@example.com'), "
            "(2, 'Bob Johnson', 'STU002', 'bob@example.com')"
        ),
        confirmed=True,
    )

    execution = execute_sql(engine, request, "sqlite")

    assert execution.success is True
    assert execution.rowsAffected == 2
    assert len(execution.resultRows) == 2
    assert {row["roll_no"] for row in execution.resultRows} == {"STU001", "STU002"}


def test_selected_database_type_and_dialect_are_used_for_validation() -> None:
    sqlite_connection = DatabaseConnectionContext(
        connectionId="sqlite-id",
        databaseType="sqlite",
        dialect="sqlite",
        credentialEnvironmentVariableName="SQLITE_DEMO_PATH",
    )
    postgres_connection = DatabaseConnectionContext(
        connectionId="postgres-id",
        databaseType="postgresql",
        dialect="postgres",
        credentialEnvironmentVariableName="POSTGRES_DEMO_URL",
    )
    mysql_connection = DatabaseConnectionContext(
        connectionId="mysql-id",
        databaseType="mysql",
        dialect="mysql",
        credentialEnvironmentVariableName="MYSQL_DEMO_URL",
    )

    assert dialect_for_connection(sqlite_connection) == "sqlite"
    assert dialect_for_connection(postgres_connection) == "postgres"
    assert dialect_for_connection(mysql_connection) == "mysql"


def test_sql_classification_covers_command_types() -> None:
    assert classify_query("SELECT id FROM sales") == "DQL"
    assert classify_query("INSERT INTO sales (id) VALUES (3)") == "DML"
    assert classify_query("UPDATE sales SET amount = 1 WHERE id = 1") == "DML"
    assert classify_query("DELETE FROM sales WHERE id = 1") == "DML"
    assert classify_query("COMMIT") == "TCL"
    assert classify_query("GRANT SELECT ON sales TO someone") == "DCL"
    assert classify_query("DROP TABLE sales") == "DDL"
    assert classify_query("CALL dangerous_proc()") == "UNKNOWN"
    assert classify_sql_command("UPDATE sales SET amount = 1 WHERE id = 1") == "UPDATE"


def test_valid_select_is_accepted_for_user_policy() -> None:
    user = VerifiedUser(userId="user-1", role="USER")
    policies = [AccessPolicy(**_policy())]

    result = validate_sql("SELECT id, region, amount FROM sales", user, policies, "sqlite")

    assert result.isValid is True
    assert result.executionAllowed is True
    assert result.requiresConfirmation is False


def test_restricted_table_and_column_are_rejected() -> None:
    user = VerifiedUser(userId="user-1", role="USER")
    policies = [AccessPolicy(**_policy(columns=["id", "region"]))]

    table_result = validate_sql("SELECT username FROM users", user, policies, "sqlite")
    column_result = validate_sql("SELECT amount FROM sales", user, policies, "sqlite")

    assert table_result.isValid is False
    assert "blocked by policy" in " ".join(table_result.securityErrors)
    assert column_result.isValid is False
    assert "not allowed by policy" in " ".join(column_result.securityErrors)


def test_write_operations_require_explicit_policy_where_preview_and_confirmation() -> None:
    user = VerifiedUser(userId="user-1", role="USER")
    select_only = [AccessPolicy(**_policy())]
    write_policy = [AccessPolicy(**_policy(operations=["SELECT", "UPDATE", "DELETE", "INSERT"]))]

    blocked_update = validate_sql("UPDATE sales SET amount = 1 WHERE id = 1", user, select_only, "sqlite")
    unsafe_update = validate_sql("UPDATE sales SET amount = 1", user, write_policy, "sqlite")
    allowed_update = validate_sql("UPDATE sales SET amount = 1 WHERE id = 1", user, write_policy, "sqlite")

    assert blocked_update.isValid is False
    assert "UPDATE is not allowed" in " ".join(blocked_update.securityErrors)
    assert unsafe_update.isValid is False
    assert "requires a WHERE" in " ".join(unsafe_update.securityErrors)
    assert allowed_update.isValid is True
    assert allowed_update.requiresConfirmation is True


def test_multiple_statements_comments_ddl_dcl_and_tcl_policy() -> None:
    user = VerifiedUser(userId="user-1", role="USER")
    policies = [AccessPolicy(**_policy(operations=["SELECT", "DELETE"]))]

    multiple = validate_sql("SELECT id FROM sales; DELETE FROM sales WHERE id = 1", user, policies, "sqlite")
    comment = validate_sql("SELECT id FROM sales -- bypass", user, policies, "sqlite")
    ddl = validate_sql("DROP TABLE sales", user, policies, "sqlite")
    dcl = validate_sql("GRANT SELECT ON sales TO someone", user, policies, "sqlite")
    tcl = validate_sql("COMMIT", user, policies, "sqlite")

    assert multiple.isValid is False
    assert comment.isValid is False
    assert ddl.executionAllowed is False
    assert dcl.executionAllowed is False
    assert tcl.isValid is True
    assert tcl.executionAllowed is False


def test_row_level_service_does_not_add_business_identity_filters() -> None:
    user = VerifiedUser(userId="user-1", role="USER")
    policies = [AccessPolicy(**_policy())]

    result = RowLevelSecurityService(user, policies, "sqlite").enforce("SELECT id, region FROM sales WHERE amount > 100")

    assert result.isEnforced is True
    assert result.finalEnforcedSql == "SELECT id, region FROM sales WHERE amount > 100"
    assert result.parameters == {}
    assert "No identity-based" in result.securityFilterExplanation


def test_select_preview_and_execute_work_without_identity_filter(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "reporting.db"
    env_name = "TEST_TARGET_DATABASE_URL"
    _create_sqlite_db(db_path)
    monkeypatch.setenv("SQL_SERVICE_API_KEY", "test-internal-key")
    monkeypatch.setenv(env_name, f"sqlite:///{db_path}")

    client = TestClient(app)
    preview = client.post(
        "/internal/preview",
        json=_payload(env_name),
        headers={"x-internal-api-key": "test-internal-key"},
    )
    execute = client.post(
        "/internal/execute",
        json=_payload(env_name),
        headers={"x-internal-api-key": "test-internal-key"},
    )

    assert preview.status_code == 200
    assert preview.json()["estimatedRows"] == 2
    assert preview.json()["finalEnforcedSql"] == "SELECT id, region, amount FROM sales"
    assert execute.status_code == 200
    assert execute.json()["success"] is True
    assert len(execute.json()["resultRows"]) == 2


def test_user_can_execute_dql_and_dml_in_own_workspace(tmp_path) -> None:
    db_path = tmp_path / "workspace.db"
    _create_sqlite_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    policy = [AccessPolicy(**_policy(operations=["DQL", "DML"]))]

    select_request = _request("SELECT id, region, amount FROM sales", operations=["DQL", "DML"])
    insert_request = _request(
        "INSERT INTO sales (id, region, amount, created_at) VALUES (3, 'North', 300, '2026-01-03')",
        operations=["DQL", "DML"],
        confirmed=True,
    )
    update_request = _request(
        "UPDATE sales SET amount = amount + 25 WHERE id = 3",
        operations=["DQL", "DML"],
        confirmed=True,
    )
    delete_request = _request("DELETE FROM sales WHERE id = 3", operations=["DQL", "DML"], confirmed=True)
    for request in [select_request, insert_request, update_request, delete_request]:
        request.accessPolicies = policy

    assert execute_sql(engine, select_request, "sqlite").success is True
    assert execute_sql(engine, insert_request, "sqlite").success is True
    assert execute_sql(engine, update_request, "sqlite").rowsAffected == 1
    assert execute_sql(engine, delete_request, "sqlite").rowsAffected == 1


def test_safe_table_ddl_requires_preview_and_confirmation(tmp_path) -> None:
    db_path = tmp_path / "workspace_ddl.db"
    _create_sqlite_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    create_request = _request(
        "CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)",
        operations=["DQL", "DML", "DDL"],
        confirmed=False,
    )
    drop_request = _request(
        "DROP TABLE notes",
        operations=["DQL", "DML", "DDL"],
        confirmed=True,
    )
    drop_request.typedConfirmation = "notes"

    create_preview = preview_sql(engine, create_request, "sqlite")
    create_blocked = execute_sql(engine, create_request, "sqlite")
    create_request.confirmed = True
    create_result = execute_sql(engine, create_request, "sqlite")
    drop_preview = preview_sql(engine, drop_request, "sqlite")
    drop_result = execute_sql(engine, drop_request, "sqlite")

    assert create_preview.executionAllowed is True
    assert create_preview.requiresConfirmation is True
    assert create_blocked.success is False
    assert create_result.success is True
    assert drop_preview.requiresConfirmation is True
    assert drop_preview.executionAllowed is True
    assert drop_result.success is True


def test_create_table_sql_is_dialect_correct_for_postgres_and_mysql() -> None:
    request = InternalRequest(
        verifiedUser=VerifiedUser(userId="user-1", role="USER"),
        databaseConnection=DatabaseConnectionContext(
            connectionId="postgres-id",
            databaseType="postgresql",
            dialect="postgres",
            credentialEnvironmentVariableName="POSTGRES_DEMO_URL",
        ),
        accessPolicies=[AccessPolicy(**_policy(operations=["DQL", "DML", "DDL"]))],
        prompt="create table named Student with columns: id, name, roll_no and email",
    )

    from app.sql_generation_service import SqlGenerationService

    postgres_option = SqlGenerationService(None, request, "postgres").generate().queryOptions[0]
    request.databaseConnection.databaseType = "mysql"
    request.databaseConnection.dialect = "mysql"
    mysql_option = SqlGenerationService(None, request, "mysql").generate().queryOptions[0]

    assert postgres_option.queryType == "DDL"
    assert "id INTEGER PRIMARY KEY" in postgres_option.generatedSql
    assert mysql_option.queryType == "DDL"
    assert "id INT PRIMARY KEY" in mysql_option.generatedSql


def test_create_database_prompt_returns_blocked_admin_ddl_option() -> None:
    request = InternalRequest(
        verifiedUser=VerifiedUser(userId="user-1", role="USER"),
        databaseConnection=DatabaseConnectionContext(
            connectionId="postgres-id",
            databaseType="postgresql",
            dialect="postgres",
            credentialEnvironmentVariableName="POSTGRES_DEMO_URL",
        ),
        accessPolicies=[AccessPolicy(**_policy(operations=["DQL", "DML", "DDL"]))],
        prompt="create database college_demo",
    )

    from app.sql_generation_service import SqlGenerationService

    option = SqlGenerationService(None, request, "postgres").generate().queryOptions[0]

    assert option.queryType == "DDL"
    assert option.generatedSql == ""
    assert option.executionAllowed is False
    assert "Database-level administration is restricted" in " ".join(option.warnings)


def test_drop_table_preview_requires_existing_simple_table_and_typed_confirmation(tmp_path) -> None:
    db_path = tmp_path / "drop_preview.db"
    _create_sqlite_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    request = _request("DROP TABLE sales", operations=["DQL", "DML", "DDL"], confirmed=False)

    preview = preview_sql(engine, request, "sqlite")
    blocked = execute_sql(engine, request, "sqlite")
    request.confirmed = True
    request.typedConfirmation = "sales"
    executed = execute_sql(engine, request, "sqlite")

    assert preview.executionAllowed is True
    assert preview.requiredTypedConfirmation == "sales"
    assert preview.ddlDetails["tableName"] == "sales"
    assert preview.ddlDetails["approximateRowCount"] == 2
    assert blocked.success is False
    assert executed.success is True


def test_drop_table_fails_when_table_missing_or_identifier_malformed(tmp_path) -> None:
    db_path = tmp_path / "drop_missing.db"
    _create_sqlite_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    missing = _request("DROP TABLE missing_table", operations=["DQL", "DML", "DDL"], confirmed=True)
    missing.typedConfirmation = "missing_table"
    malformed = validate_sql("DROP TABLE public.sales", VerifiedUser(userId="user-1", role="USER"), [AccessPolicy(**_policy(operations=["DDL"]))], "postgres")

    preview = preview_sql(engine, missing, "sqlite")
    execution = execute_sql(engine, missing, "sqlite")

    assert preview.executionAllowed is False
    assert "does not exist" in " ".join(preview.securityErrors)
    assert execution.success is False
    assert malformed.isValid is False


def test_user_cannot_access_another_workspace() -> None:
    user = VerifiedUser(userId="user-1", role="USER", workspaceIdentifier="workspace_user_1")
    policies = [AccessPolicy(**_policy(operations=["DQL", "DML", "DDL"]))]

    cross_schema = validate_sql("SELECT id FROM workspace_user_2.sales", user, policies, "postgres")
    cross_database = validate_sql("SELECT id FROM workspace_user_2.sales", user, policies, "mysql")

    assert cross_schema.executionAllowed is False
    assert "Cross-schema or cross-database access is blocked" in " ".join(cross_schema.securityErrors)
    assert cross_database.executionAllowed is False
    assert "Cross-schema or cross-database access is blocked" in " ".join(cross_database.securityErrors)


def test_user_cannot_create_or_drop_databases_users_or_roles() -> None:
    user = VerifiedUser(userId="user-1", role="USER")
    policies = [AccessPolicy(**_policy(operations=["DQL", "DML", "DDL"]))]
    commands = [
        "CREATE DATABASE unsafe_db",
        "DROP DATABASE unsafe_db",
        "CREATE USER attacker",
        "DROP USER attacker",
        "CREATE ROLE attacker",
        "DROP ROLE attacker",
        "ALTER SYSTEM SET max_connections = 500",
    ]

    for sql in commands:
        result = validate_sql(sql, user, policies, "postgres")
        assert result.executionAllowed is False
        assert "Database-level administration is restricted for security." in result.securityErrors


def test_update_preview_does_not_modify_and_execution_requires_confirmation(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "reporting.db"
    env_name = "TEST_TARGET_DATABASE_URL"
    _create_sqlite_db(db_path)
    monkeypatch.setenv("SQL_SERVICE_API_KEY", "test-internal-key")
    monkeypatch.setenv(env_name, f"sqlite:///{db_path}")
    payload = _payload(env_name, "UPDATE sales SET amount = amount + 10 WHERE id = 1")
    payload["accessPolicies"] = [_policy(operations=["SELECT", "UPDATE"])]

    client = TestClient(app)
    preview = client.post(
        "/internal/preview",
        json=payload,
        headers={"x-internal-api-key": "test-internal-key"},
    )
    blocked = client.post(
        "/internal/execute",
        json=payload | {"confirmed": False},
        headers={"x-internal-api-key": "test-internal-key"},
    )
    executed = client.post(
        "/internal/execute",
        json=payload | {"confirmed": True},
        headers={"x-internal-api-key": "test-internal-key"},
    )

    assert preview.json()["estimatedRows"] == 1
    assert preview.json()["requiresConfirmation"] is True
    assert blocked.json()["success"] is False
    assert executed.json()["success"] is True
    assert executed.json()["rowsAffected"] == 1


def test_tcl_never_executes_and_dcl_ddl_are_blocked(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "reporting.db"
    env_name = "TEST_TARGET_DATABASE_URL"
    _create_sqlite_db(db_path)
    monkeypatch.setenv("SQL_SERVICE_API_KEY", "test-internal-key")
    monkeypatch.setenv(env_name, f"sqlite:///{db_path}")
    client = TestClient(app)

    tcl = client.post(
        "/internal/execute",
        json=_payload(env_name, "COMMIT"),
        headers={"x-internal-api-key": "test-internal-key"},
    )
    dcl = client.post(
        "/internal/execute",
        json=_payload(env_name, "GRANT SELECT ON sales TO someone"),
        headers={"x-internal-api-key": "test-internal-key"},
    )
    ddl = client.post(
        "/internal/execute",
        json=_payload(env_name, "DROP TABLE sales"),
        headers={"x-internal-api-key": "test-internal-key"},
    )

    assert tcl.json()["success"] is False
    assert "explained but cannot be executed" in tcl.json()["message"]
    assert dcl.json()["success"] is False
    assert ddl.json()["success"] is False


def test_database_administration_ddl_is_restricted() -> None:
    request = InternalRequest(
        verifiedUser=VerifiedUser(userId="admin-1", role="ADMIN"),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="POSTGRESQL",
            credentialEnvironmentVariableName="POSTGRES_APP_URL",
        ),
        accessPolicies=[],
        generatedSql="CREATE DATABASE college_demo",
        confirmed=False,
    )
    engine = create_engine("sqlite://")

    preview = preview_sql(engine, request, "postgres")
    execution = execute_sql(engine, request, "postgres")

    assert preview.executionAllowed is False
    assert execution.success is False
    assert "database-level administration is restricted" in execution.message.lower()


def test_unsafe_infrastructure_ddl_remains_blocked() -> None:
    request = InternalRequest(
        verifiedUser=VerifiedUser(userId="admin-1", role="ADMIN"),
        databaseConnection=DatabaseConnectionContext(
            connectionId="connection-1",
            databaseType="POSTGRESQL",
            credentialEnvironmentVariableName="POSTGRES_APP_URL",
        ),
        accessPolicies=[],
        generatedSql="DROP DATABASE production_db",
        confirmed=True,
    )
    engine = create_engine("sqlite://")

    preview = preview_sql(engine, request, "postgres")
    execution = execute_sql(engine, request, "postgres")

    assert preview.executionAllowed is False
    assert execution.success is False
    assert "database-level administration is restricted" in execution.message.lower()
