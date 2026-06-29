"""Tests for temporary selected query storage."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.database import Base, SessionLocal, engine
from backend.main import app
from backend.models import AuditLogs, QueryHistory, SelectedQueries, User


TEST_PROMPT_PREFIX = "selection-test:"


def auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def cleanup_selection_test_data() -> None:
    ensure_tables()
    with SessionLocal() as db:
        histories = (
            db.query(QueryHistory)
            .filter(QueryHistory.user_prompt.like(f"{TEST_PROMPT_PREFIX}%"))
            .all()
        )
        for history in histories:
            db.delete(history)

        selected_queries = db.query(SelectedQueries).all()
        for selected_query in selected_queries:
            if selected_query.title.startswith(TEST_PROMPT_PREFIX):
                db.delete(selected_query)

        logs = db.query(AuditLogs).filter(AuditLogs.action_type == "select_query").all()
        for log in logs:
            if log.user_prompt and log.user_prompt.startswith(TEST_PROMPT_PREFIX):
                db.delete(log)
        db.commit()


def save_generated_option(username: str, option_id: int, sql: str, query_type: str) -> None:
    ensure_tables()
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        db.add(
            QueryHistory(
                user_id=user.user_id,
                user_prompt=f"{TEST_PROMPT_PREFIX} {username} latest",
                selected_option_id=option_id,
                generated_sql=sql,
                final_enforced_sql="",
                query_type=query_type,
                execution_status="generated",
                rows_affected=None,
            )
        )
        db.commit()


def create_expired_selection(username: str, option_id: int) -> None:
    ensure_tables()
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        db.add(
            SelectedQueries(
                user_id=user.user_id,
                option_id=option_id,
                title=f"{TEST_PROMPT_PREFIX} expired",
                generated_sql="SELECT employee_id FROM employees",
                query_type="SELECT",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        db.commit()


def test_selecting_valid_option_uses_server_side_sql() -> None:
    cleanup_selection_test_data()
    server_sql = "SELECT employee_id, name FROM employees WHERE department = 'IT'"
    save_generated_option("admin", 301, server_sql, "SELECT")

    with TestClient(app) as client:
        headers = auth_headers(client, "admin", "admin123")
        response = client.post(
            "/select-query",
            json={
                "option_id": 301,
                "title": f"{TEST_PROMPT_PREFIX} Detailed employee records",
                "sql": "DROP TABLE employees",
                "query_type": "DDL",
            },
            headers=headers,
        )
        get_response = client.get("/selected-query", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["option_id"] == 301
    assert payload["generated_sql"] == server_sql
    assert payload["query_type"] == "SELECT"
    assert get_response.status_code == 200
    assert get_response.json()["generated_sql"] == server_sql
    cleanup_selection_test_data()


def test_selecting_another_users_option_is_blocked() -> None:
    cleanup_selection_test_data()
    save_generated_option("admin", 302, "SELECT employee_id FROM employees", "SELECT")

    with TestClient(app) as client:
        response = client.post(
            "/select-query",
            json={
                "option_id": 302,
                "title": f"{TEST_PROMPT_PREFIX} other user option",
                "sql": "SELECT employee_id FROM employees",
                "query_type": "SELECT",
            },
            headers=auth_headers(client, "employee_6", "employee123"),
        )

    assert response.status_code == 404
    cleanup_selection_test_data()


def test_expired_selected_query_is_not_returned() -> None:
    cleanup_selection_test_data()
    create_expired_selection("admin", 303)

    with TestClient(app) as client:
        response = client.get(
            "/selected-query",
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 404
    cleanup_selection_test_data()


def test_selecting_nonexistent_option_is_blocked() -> None:
    cleanup_selection_test_data()
    save_generated_option("admin", 304, "SELECT employee_id FROM employees", "SELECT")

    with TestClient(app) as client:
        response = client.post(
            "/select-query",
            json={
                "option_id": 999,
                "title": f"{TEST_PROMPT_PREFIX} missing option",
                "sql": "SELECT employee_id FROM employees",
                "query_type": "SELECT",
            },
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 404
    cleanup_selection_test_data()

