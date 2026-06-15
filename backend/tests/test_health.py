from fastapi.testclient import TestClient

from app.main import app


def test_healthz_returns_service_status() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_public_status_endpoint_is_mounted() -> None:
    client = TestClient(app)

    response = client.get("/api/public/status")

    assert response.status_code == 200
    assert response.json() == {"status": "public-api-ready"}


def test_admin_auth_login_endpoint_is_mounted() -> None:
    client = TestClient(app)

    response = client.post("/api/admin/auth/login", json={})

    assert response.status_code == 422


def test_admin_auth_me_requires_bearer_token() -> None:
    client = TestClient(app)

    response = client.get("/api/admin/auth/me")

    assert response.status_code == 401
