"""Tests for selected-query preview and impact analysis."""

from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.database import SessionLocal
from backend.impact_analyzer import enforce_row_level_filter
from backend.main import app
from backend.models import AuditLogs, QueryHistory, User


TEST_PROMPT_PREFIX = "impact-test:"


def auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def user_id_for(username: str) -> int:
    with SessionLocal() as db:
        return db.query(User).filter(User.username == username).one().user_id


def save_option(username: str, option_id: int, sql: str, query_type: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        db.add(
            QueryHistory(
                user_id=user.user_id,
                user_prompt=f"{TEST_PROMPT_PREFIX} {username} {option_id}",
                selected_option_id=option_id,
                generated_sql=sql,
                final_enforced_sql="",
                query_type=query_type,
                execution_status="generated",
                rows_affected=None,
            )
        )
        db.commit()


def cleanup_preview_test_data() -> None:
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
            .filter(AuditLogs.action_type == "preview_selected_query")
            .all()
        )
        for log in logs:
            if log.user_prompt is None or log.user_prompt.startswith(TEST_PROMPT_PREFIX):
                db.delete(log)
        db.commit()


def audit_count_for_user(username: str) -> int:
    with SessionLocal() as db:
        return (
            db.query(AuditLogs)
            .filter(
                AuditLogs.user_id == user_id_for(username),
                AuditLogs.action_type == "preview_selected_query",
            )
            .count()
        )


def employee_count() -> int:
    with SessionLocal() as db:
        return int(db.execute(text("SELECT COUNT(*) FROM employees")).scalar_one())


def salary_for_employee(employee_id: int) -> float:
    with SessionLocal() as db:
        return float(
            db.execute(
                text("SELECT salary FROM employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            ).scalar_one()
        )


def db_user(username: str) -> User:
    with SessionLocal() as db:
        return db.query(User).filter(User.username == username).one()


def test_row_level_enforcement_adds_employee_student_and_manager_filters() -> None:
    employee = db_user("employee_6")
    student = db_user("student_1")
    manager = db_user("it_manager")

    employee_sql = enforce_row_level_filter("SELECT employee_id FROM employees", employee)
    student_sql = enforce_row_level_filter("SELECT student_id FROM students", student)
    manager_sql = enforce_row_level_filter("SELECT employee_id FROM employees", manager)

    assert "employee_id = 6" in employee_sql
    assert "student_id = 1" in student_sql
    assert "department = 'IT'" in manager_sql


def test_existing_where_clause_is_combined_safely() -> None:
    employee = db_user("employee_6")

    enforced_sql = enforce_row_level_filter(
        "SELECT employee_id FROM employees WHERE salary > 50000",
        employee,
    )

    assert "salary > 50000" in enforced_sql
    assert "employee_id = 6" in enforced_sql
    assert " AND " in enforced_sql


def test_preview_select_returns_count_rows_and_logs_audit() -> None:
    cleanup_preview_test_data()
    save_option("admin", 101, "SELECT employee_id, name FROM employees WHERE department = 'IT'", "SELECT")

    with TestClient(app) as client:
        response = client.post(
            "/preview-selected-query",
            json={"selected_option_id": 101},
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "SELECT"
    assert payload["estimated_rows"] > 0
    assert len(payload["preview_rows"]) <= 20
    assert payload["execution_allowed"] is True
    assert payload["requires_confirmation"] is False
    assert audit_count_for_user("admin") >= 1
    cleanup_preview_test_data()


def test_preview_update_uses_select_preview_and_requires_confirmation() -> None:
    cleanup_preview_test_data()
    original_salary = salary_for_employee(6)
    save_option(
        "it_manager",
        102,
        "UPDATE employees SET salary = salary WHERE department = 'IT'",
        "UPDATE",
    )

    with TestClient(app) as client:
        response = client.post(
            "/preview-selected-query",
            json={"selected_option_id": 102},
            headers=auth_headers(client, "it_manager", "manager123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "UPDATE"
    assert payload["preview_sql"].startswith("SELECT")
    assert "UPDATE" not in payload["preview_sql"]
    assert "department = 'IT'" in payload["final_enforced_sql"]
    assert payload["requires_confirmation"] is True
    assert payload["estimated_rows"] > 0
    assert salary_for_employee(6) == original_salary
    cleanup_preview_test_data()


def test_preview_delete_uses_select_preview_and_requires_confirmation() -> None:
    cleanup_preview_test_data()
    original_count = employee_count()
    save_option("admin", 103, "DELETE FROM employees WHERE department = 'HR'", "DELETE")

    with TestClient(app) as client:
        response = client.post(
            "/preview-selected-query",
            json={"selected_option_id": 103},
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "DELETE"
    assert payload["preview_sql"].startswith("SELECT")
    assert "DELETE" not in payload["preview_sql"]
    assert payload["requires_confirmation"] is True
    assert payload["estimated_rows"] > 0
    assert employee_count() == original_count
    cleanup_preview_test_data()


def test_preview_tcl_returns_explanation_only() -> None:
    cleanup_preview_test_data()
    save_option("admin", 104, "ROLLBACK", "TCL")

    with TestClient(app) as client:
        response = client.post(
            "/preview-selected-query",
            json={"selected_option_id": 104},
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "TCL"
    assert payload["preview_sql"] == ""
    assert payload["preview_rows"] == []
    assert payload["execution_allowed"] is False
    assert "never executed" in payload["impact_message"]
    cleanup_preview_test_data()


def test_preview_blocks_unauthorized_query() -> None:
    cleanup_preview_test_data()
    save_option("employee_6", 105, "SELECT username FROM users", "SELECT")

    with TestClient(app) as client:
        response = client.post(
            "/preview-selected-query",
            json={"selected_option_id": 105},
            headers=auth_headers(client, "employee_6", "employee123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_allowed"] is False
    assert payload["preview_sql"] == ""
    assert "not pass validation" in payload["impact_message"]
    cleanup_preview_test_data()


def test_preview_zero_row_result() -> None:
    cleanup_preview_test_data()
    save_option("admin", 106, "SELECT employee_id, name FROM employees WHERE department = 'Legal'", "SELECT")

    with TestClient(app) as client:
        response = client.post(
            "/preview-selected-query",
            json={"selected_option_id": 106},
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["estimated_rows"] == 0
    assert payload["preview_rows"] == []
    assert payload["execution_allowed"] is True
    cleanup_preview_test_data()


def test_preview_ignores_non_generated_history_rows() -> None:
    cleanup_preview_test_data()
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "admin").one()
        db.add(
            QueryHistory(
                user_id=user.user_id,
                user_prompt=f"{TEST_PROMPT_PREFIX} non generated row",
                selected_option_id=107,
                generated_sql="SELECT employee_id FROM employees",
                final_enforced_sql="SELECT employee_id FROM employees",
                query_type="SELECT",
                execution_status="executed",
                rows_affected=1,
            )
        )
        db.commit()

    with TestClient(app) as client:
        response = client.post(
            "/preview-selected-query",
            json={"selected_option_id": 107},
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 404
    cleanup_preview_test_data()
