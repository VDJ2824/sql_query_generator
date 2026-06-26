"""Smoke tests for authentication helpers."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.auth import create_access_token, hash_password, verify_password
from backend.database import SessionLocal
from backend.main import app
from backend.models import User


def test_valid_login() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/login",
            json={"username": "admin", "password": "admin123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["role"] == "admin"
    assert data["username"] == "admin"
    assert "password_hash" not in data


def test_invalid_password_returns_401() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/login",
            json={"username": "admin", "password": "wrong-password"},
        )

    assert response.status_code == 401


def test_missing_token_returns_401() -> None:
    with TestClient(app) as client:
        response = client.get("/me")

    assert response.status_code == 401


def test_invalid_token_returns_401() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401


def test_expired_token_returns_401() -> None:
    expired_token = create_access_token({"sub": "admin"}, expires_minutes=-1)
    with TestClient(app) as client:
        response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

    assert response.status_code == 401


def test_protected_endpoint_access() -> None:
    with TestClient(app) as client:
        login_response = client.post(
            "/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_response.json()["access_token"]
        me_response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert me_response.status_code == 200
    data = me_response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert "password_hash" not in data


def test_register_never_returns_password_hash() -> None:
    username = f"test_user_{uuid4().hex}"
    try:
        with TestClient(app) as client:
            response = client.post(
                "/register",
                json={
                    "username": username,
                    "password": "test123",
                    "role": "student",
                    "department": None,
                    "employee_id": None,
                    "student_id": None,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == username
        assert "password_hash" not in data
    finally:
        with SessionLocal() as db:
            db.query(User).filter(User.username == username).delete()
            db.commit()


def test_duplicate_username_returns_409() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/register",
            json={
                "username": "admin",
                "password": "admin123",
                "role": "admin",
            },
        )

    assert response.status_code == 409


def test_password_hash_round_trip() -> None:
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)


def test_access_token_creation() -> None:
    token = create_access_token({"sub": "admin"})
    assert isinstance(token, str)
    assert token
