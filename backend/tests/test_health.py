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
