"""Tests for secure selected-query execution."""

from fastapi.testclient import TestClient

from backend.database import SessionLocal
from backend.main import app
from backend.models import AuditLogs, QueryHistory, User


TEST_PROMPT_PREFIX = "execute-test:"


def auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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


def cleanup_execution_test_data() -> None:
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
            .filter(
                AuditLogs.action_type.in_(
                    ["execute_selected_query", "preview_selected_query"]
                )
            )
            .all()
        )
        for log in logs:
            if log.user_prompt and log.user_prompt.startswith(TEST_PROMPT_PREFIX):
                db.delete(log)
        db.commit()


def execution_audit_count(username: str) -> int:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        return (
            db.query(AuditLogs)
            .filter(
                AuditLogs.user_id == user.user_id,
                AuditLogs.action_type == "execute_selected_query",
            )
            .count()
        )


def preview_option(client: TestClient, headers: dict[str, str], option_id: int) -> None:
    response = client.post(
        "/preview-selected-query",
        json={"selected_option_id": option_id},
        headers=headers,
    )
    assert response.status_code == 200


def test_employee_can_execute_only_own_select_query() -> None:
    cleanup_execution_test_data()
    save_option("employee_6", 201, "SELECT employee_id, name, department FROM employees", "SELECT")

    with TestClient(app) as client:
        headers = auth_headers(client, "employee_6", "employee123")
        response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 201, "confirmed": False},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["query_type"] == "SELECT"
    assert "employee_id = 6" in payload["final_enforced_sql"]
    assert {row["employee_id"] for row in payload["result_rows"]} == {6}
    assert execution_audit_count("employee_6") >= 1
    cleanup_execution_test_data()


def test_manager_can_update_only_department_after_confirmation() -> None:
    cleanup_execution_test_data()
    save_option(
        "it_manager",
        202,
        "UPDATE employees SET salary = salary WHERE department = 'IT'",
        "UPDATE",
    )

    with TestClient(app) as client:
        headers = auth_headers(client, "it_manager", "manager123")
        preview_option(client, headers, 202)
        response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 202, "confirmed": True},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["query_type"] == "UPDATE"
    assert payload["rows_affected"] > 0
    assert "department = 'IT'" in payload["final_enforced_sql"]
    assert "department = 'HR'" not in payload["final_enforced_sql"]
    cleanup_execution_test_data()


def test_update_requires_confirmation() -> None:
    cleanup_execution_test_data()
    save_option(
        "it_manager",
        208,
        "UPDATE employees SET salary = salary WHERE department = 'IT'",
        "UPDATE",
    )

    with TestClient(app) as client:
        headers = auth_headers(client, "it_manager", "manager123")
        preview_option(client, headers, 208)
        response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 208, "confirmed": False},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "requires explicit confirmation" in payload["message"]
    cleanup_execution_test_data()


def test_manager_cannot_update_another_department() -> None:
    cleanup_execution_test_data()
    save_option(
        "it_manager",
        209,
        "UPDATE employees SET salary = salary WHERE department = 'HR'",
        "UPDATE",
    )

    with TestClient(app) as client:
        headers = auth_headers(client, "it_manager", "manager123")
        preview_option(client, headers, 209)
        response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 209, "confirmed": True},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["execution_allowed"] is False
    assert "Manager UPDATE queries must be scoped to their own department." in payload["message"]
    cleanup_execution_test_data()


def test_employee_cannot_update_salary() -> None:
    cleanup_execution_test_data()
    save_option(
        "employee_6",
        210,
        "UPDATE employees SET salary = salary WHERE employee_id = 6",
        "UPDATE",
    )

    with TestClient(app) as client:
        response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 210, "confirmed": True},
            headers=auth_headers(client, "employee_6", "employee123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "UPDATE queries are not allowed for role 'employee'." in payload["message"]
    cleanup_execution_test_data()


def test_student_cannot_access_other_students() -> None:
    cleanup_execution_test_data()
    save_option("student_1", 203, "SELECT student_id, name FROM students WHERE student_id = 2", "SELECT")

    with TestClient(app) as client:
        headers = auth_headers(client, "student_1", "student123")
        response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 203, "confirmed": False},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "student_id = 1" in payload["final_enforced_sql"]
    assert payload["result_rows"] == []
    cleanup_execution_test_data()


def test_delete_without_confirmation_is_blocked() -> None:
    cleanup_execution_test_data()
    save_option("admin", 204, "DELETE FROM employees WHERE department = 'Operations'", "DELETE")

    with TestClient(app) as client:
        headers = auth_headers(client, "admin", "admin123")
        preview_option(client, headers, 204)
        response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 204, "confirmed": False},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["execution_allowed"] is False
    assert "requires explicit confirmation" in payload["message"]
    cleanup_execution_test_data()


def test_tcl_is_never_executed() -> None:
    cleanup_execution_test_data()
    save_option("admin", 205, "ROLLBACK", "TCL")

    with TestClient(app) as client:
        response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 205, "confirmed": True},
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["query_type"] == "TCL"
    assert payload["message"] == "TCL commands are view-only and cannot be executed in this application."
    cleanup_execution_test_data()


def test_ddl_and_dcl_are_blocked() -> None:
    cleanup_execution_test_data()
    save_option("admin", 206, "DROP TABLE employees", "DDL")
    save_option("admin", 207, "GRANT SELECT ON employees TO analyst", "DCL")

    with TestClient(app) as client:
        headers = auth_headers(client, "admin", "admin123")
        ddl_response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 206, "confirmed": True},
            headers=headers,
        )
        dcl_response = client.post(
            "/execute-selected-query",
            json={"selected_option_id": 207, "confirmed": True},
            headers=headers,
        )

    assert ddl_response.status_code == 200
    assert dcl_response.status_code == 200
    assert ddl_response.json()["success"] is False
    assert ddl_response.json()["query_type"] == "DDL"
    assert dcl_response.json()["success"] is False
    assert dcl_response.json()["query_type"] == "DCL"
    cleanup_execution_test_data()
