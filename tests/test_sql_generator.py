"""Tests for SQL generation endpoint and AI response handling."""

from fastapi.testclient import TestClient

import backend.sql_generator as sql_generator
from backend.main import app


def auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_generate_uses_mocked_ai_response(monkeypatch) -> None:
    def fake_ai_response(prompt: str) -> dict:
        assert "User role: admin" in prompt
        assert "Allowed schema:" in prompt
        return {
            "user_prompt": "show IT salaries",
            "query_options": [
                {
                    "option_id": 1,
                    "title": "Detailed IT employees",
                    "sql": "SELECT employee_id, name, salary FROM employees WHERE department = 'IT';",
                    "query_type": "SELECT",
                    "tables_used": ["Employee"],
                    "columns_used": ["employee_id", "name", "salary"],
                    "explanation": "Detailed rows.",
                    "risk_level": "low",
                    "execution_allowed": True,
                    "requires_confirmation": False,
                    "warnings": [],
                },
                {
                    "option_id": 2,
                    "title": "IT employee count",
                    "sql": "SELECT COUNT(*) AS employee_count FROM employees WHERE department = 'IT';",
                    "query_type": "SELECT",
                    "tables_used": ["Employee"],
                    "columns_used": ["department"],
                    "explanation": "Summary count.",
                    "risk_level": "low",
                    "execution_allowed": True,
                    "requires_confirmation": False,
                    "warnings": [],
                },
            ],
        }

    monkeypatch.setattr(sql_generator, "call_gemini_for_sql_options", fake_ai_response)

    with TestClient(app) as client:
        response = client.post(
            "/generate",
            json={"prompt": "show IT salaries"},
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_prompt"] == "show IT salaries"
    assert len(payload["query_options"]) == 2
    assert payload["query_options"][0]["sql"].startswith("SELECT")


def test_generate_sanitizes_unsafe_mocked_ai_response(monkeypatch) -> None:
    def fake_ai_response(prompt: str) -> dict:
        return {
            "user_prompt": "show passwords",
            "query_options": [
                {
                    "option_id": 1,
                    "title": "Unsafe users query",
                    "sql": "SELECT username, password_hash FROM users;",
                    "query_type": "SELECT",
                    "tables_used": ["users"],
                    "columns_used": ["username", "password_hash"],
                    "explanation": "Unsafe.",
                    "risk_level": "high",
                    "execution_allowed": True,
                    "requires_confirmation": False,
                    "warnings": [],
                }
            ],
        }

    monkeypatch.setattr(sql_generator, "call_gemini_for_sql_options", fake_ai_response)

    with TestClient(app) as client:
        response = client.post(
            "/generate",
            json={"prompt": "show passwords"},
            headers=auth_headers(client, "admin", "admin123"),
        )

    assert response.status_code == 200
    option = response.json()["query_options"][0]
    assert option["sql"] == ""
    assert option["execution_allowed"] is False
    assert "password_hash" not in str(response.json())


def test_generate_fallback_salary_for_employee_enforces_own_row(monkeypatch) -> None:
    monkeypatch.setattr(sql_generator, "call_gemini_for_sql_options", lambda prompt: None)

    with TestClient(app) as client:
        response = client.post(
            "/generate",
            json={"prompt": "show salary greater than 60000"},
            headers=auth_headers(client, "employee_6", "employee123"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["query_options"]) >= 2
    assert "employee_id = 6" in payload["query_options"][0]["sql"]
    assert "manager_id" not in str(payload)


def test_generate_fallback_blocks_employee_salary_update(monkeypatch) -> None:
    monkeypatch.setattr(sql_generator, "call_gemini_for_sql_options", lambda prompt: None)

    with TestClient(app) as client:
        response = client.post(
            "/generate",
            json={"prompt": "update salary by 10 percent"},
            headers=auth_headers(client, "employee_6", "employee123"),
        )

    assert response.status_code == 200
    option = response.json()["query_options"][0]
    assert option["query_type"] == "UPDATE"
    assert option["sql"] == ""
    assert option["execution_allowed"] is False


def test_generate_requires_login() -> None:
    with TestClient(app) as client:
        response = client.post("/generate", json={"prompt": "count records"})

    assert response.status_code == 401
