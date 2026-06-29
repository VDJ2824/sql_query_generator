"""Tests for the role-aware schema endpoint."""

from fastapi.testclient import TestClient

from backend.main import app


def auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def table_by_name(payload: dict, table_name: str) -> dict:
    for table in payload["allowed_tables"]:
        if table["table_name"] == table_name:
            return table
    raise AssertionError(f"Missing table {table_name}")


def column_names(table: dict) -> set[str]:
    return {column["name"] for column in table["allowed_columns"]}


def assert_no_internal_schema(payload: dict) -> None:
    serialized = str(payload)
    assert "password_hash" not in serialized
    assert "QueryHistory" not in serialized
    assert "query_history" not in serialized
    assert "AuditLogs" not in serialized
    assert "audit_logs" not in serialized


def test_admin_schema_includes_employee_and_students_without_password_hash() -> None:
    with TestClient(app) as client:
        response = client.get("/schema", headers=auth_headers(client, "admin", "admin123"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "admin"
    assert_no_internal_schema(payload)
    assert column_names(table_by_name(payload, "Employee")) == {
        "employee_id",
        "name",
        "email",
        "department",
        "salary",
        "joining_date",
        "manager_id",
    }
    assert column_names(table_by_name(payload, "Students")) == {
        "student_id",
        "name",
        "email",
        "course",
        "cgpa",
        "faculty_id",
    }


def test_manager_schema_includes_employee_columns_only() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/schema",
            headers=auth_headers(client, "it_manager", "manager123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "manager"
    assert_no_internal_schema(payload)
    assert len(payload["allowed_tables"]) == 1
    employee = table_by_name(payload, "Employee")
    assert "manager's department" in employee["row_access_rule"]
    assert "manager_id" in column_names(employee)


def test_employee_schema_hides_manager_id() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/schema",
            headers=auth_headers(client, "employee_6", "employee123"),
        )

    assert response.status_code == 200
    payload = response.json()
    employee = table_by_name(payload, "Employee")
    assert payload["role"] == "employee"
    assert_no_internal_schema(payload)
    assert column_names(employee) == {
        "employee_id",
        "name",
        "email",
        "department",
        "salary",
        "joining_date",
    }
    assert "manager_id" not in column_names(employee)


def test_faculty_schema_includes_students_only() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/schema",
            headers=auth_headers(client, "faculty_it", "faculty123"),
        )

    assert response.status_code == 200
    payload = response.json()
    students = table_by_name(payload, "Students")
    assert payload["role"] == "faculty"
    assert_no_internal_schema(payload)
    assert len(payload["allowed_tables"]) == 1
    assert "assigned to the logged-in faculty" in students["row_access_rule"]
    assert "faculty_id" in column_names(students)


def test_student_schema_hides_faculty_id() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/schema",
            headers=auth_headers(client, "student_1", "student123"),
        )

    assert response.status_code == 200
    payload = response.json()
    students = table_by_name(payload, "Students")
    assert payload["role"] == "student"
    assert_no_internal_schema(payload)
    assert column_names(students) == {"student_id", "name", "email", "course", "cgpa"}
    assert "faculty_id" not in column_names(students)


def test_schema_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/schema")

    assert response.status_code == 401

