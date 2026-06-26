"""Tests for history and audit log endpoints."""

from fastapi.testclient import TestClient

from backend.database import SessionLocal
from backend.main import app
from backend.models import AuditLogs, QueryHistory, User
from backend.audit_logger import log_audit_event


TEST_PROMPT_PREFIX = "audit-test:"


def auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def cleanup_audit_test_data() -> None:
    with SessionLocal() as db:
        histories = (
            db.query(QueryHistory)
            .filter(QueryHistory.user_prompt.like(f"{TEST_PROMPT_PREFIX}%"))
            .all()
        )
        for history in histories:
            db.delete(history)

        logs = (
            db.query(AuditLogs)
            .filter(AuditLogs.user_prompt.like(f"{TEST_PROMPT_PREFIX}%"))
            .all()
        )
        for log in logs:
            db.delete(log)
        db.commit()


def add_history(username: str, prompt_suffix: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        db.add(
            QueryHistory(
                user_id=user.user_id,
                user_prompt=f"{TEST_PROMPT_PREFIX} {prompt_suffix}",
                selected_option_id=1,
                generated_sql="SELECT employee_id FROM employees",
                final_enforced_sql="SELECT employee_id FROM employees",
                query_type="SELECT",
                execution_status="executed",
                rows_affected=1,
            )
        )
        db.commit()


def add_audit_log(username: str, prompt_suffix: str, query_type: str = "SELECT") -> int:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        db.add(
            AuditLogs(
                user_id=user.user_id,
                action_type="audit_test_event",
                user_prompt=f"{TEST_PROMPT_PREFIX} {prompt_suffix}",
                generated_sql="SELECT employee_id FROM employees",
                final_enforced_sql="SELECT employee_id FROM employees",
                query_type=query_type,
                execution_status="executed",
                rows_affected=1,
            )
        )
        db.commit()
        return user.user_id


def test_user_can_see_only_own_history() -> None:
    cleanup_audit_test_data()
    add_history("admin", "admin history")
    add_history("employee_6", "employee history")

    with TestClient(app) as client:
        response = client.get(
            "/history",
            headers=auth_headers(client, "employee_6", "employee123"),
        )

    assert response.status_code == 200
    payload = response.json()
    prompts = [item["prompt"] for item in payload]
    assert f"{TEST_PROMPT_PREFIX} employee history" in prompts
    assert f"{TEST_PROMPT_PREFIX} admin history" not in prompts
    cleanup_audit_test_data()


def test_admin_can_see_audit_logs_with_filters() -> None:
    cleanup_audit_test_data()
    employee_user_id = add_audit_log("employee_6", "employee audit", "SELECT")
    add_audit_log("admin", "admin audit", "UPDATE")

    with TestClient(app) as client:
        response = client.get(
            f"/admin/audit-logs?user_id={employee_user_id}&query_type=SELECT&execution_status=executed",
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 200
    payload = response.json()
    prompts = [item["user_prompt"] for item in payload]
    assert f"{TEST_PROMPT_PREFIX} employee audit" in prompts
    assert f"{TEST_PROMPT_PREFIX} admin audit" not in prompts
    cleanup_audit_test_data()


def test_non_admin_cannot_access_audit_logs() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/admin/audit-logs",
            headers=auth_headers(client, "employee_6", "employee123"),
        )

    assert response.status_code == 403


def test_audit_logger_redacts_passwords_tokens_and_secrets() -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "admin").one()
        audit_log = log_audit_event(
            db,
            user_id=user.user_id,
            action_type="audit_redaction_test",
            user_prompt="password=plain123 token=abc.def.ghi Authorization: Bearer live-token",
            generated_sql="SELECT 'api_key=sk-test-secret' AS note",
            final_enforced_sql="SELECT 'secret=my-secret' AS note",
            query_type="SELECT",
            execution_status="tested",
            rows_affected=0,
        )

        assert "plain123" not in audit_log.user_prompt
        assert "abc.def.ghi" not in audit_log.user_prompt
        assert "live-token" not in audit_log.user_prompt
        assert "sk-test-secret" not in audit_log.generated_sql
        assert "my-secret" not in audit_log.final_enforced_sql
        assert "[REDACTED]" in audit_log.user_prompt

        db.delete(audit_log)
        db.commit()
