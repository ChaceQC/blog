from fastapi.testclient import TestClient

from app.main import app


def test_healthz_returns_service_status() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_omits_environment_details() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "service" in response.json()
    assert "version" in response.json()
    assert "environment" not in response.json()


def test_public_status_endpoint_is_mounted() -> None:
    client = TestClient(app)

    response = client.get("/api/public/status")

    assert response.status_code == 200
    assert response.json() == {"status": "public-api-ready"}


def test_admin_auth_login_endpoint_is_mounted() -> None:
    client = TestClient(app)

    response = client.post("/api/admin/auth/login", json={})

    assert response.status_code == 422


def test_admin_auth_me_requires_encryption_session_before_bearer_token() -> None:
    client = TestClient(app)

    response = client.get("/api/admin/auth/me")

    assert response.status_code == 400
    assert response.json()["detail"] == "missing encryption session"


def test_admin_cors_allows_encryption_session_header() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/admin/auth/login",
        headers={
            "Origin": "http://127.0.0.1:15173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "content-type,x-encryption-session"
            ),
        },
    )

    assert response.status_code == 200
    assert "x-encryption-session" in response.headers[
        "access-control-allow-headers"
    ].lower()
