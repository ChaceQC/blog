from tests.public_content_api_helpers import (
    FakeEncryptionSessionManager,
    FakeLogService,
    RateLimitService,
    RejectingRateLimitService,
    TestClient,
    app,
    get_encryption_session_manager,
    get_log_service,
    get_rate_limit_service,
)


def test_public_encryption_session_uses_public_scope() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        response = client.post(
            "/api/public/encryption/sessions",
            json={
                "client_public_key": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "client-x",
                    "y": "client-y",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["scope"] == "public"

def test_public_encryption_session_records_rate_limit_hit() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = (
        lambda: RejectingRateLimitService()
    )

    try:
        response = client.post(
            "/api/public/encryption/sessions",
            json={
                "client_public_key": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "client-x",
                    "y": "client-y",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "9"
    assert logs.events[0]["event_type"] == "rate_limit.public_encryption_session"

def test_public_encryption_session_rejects_active_session_overflow() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager(raise_active_limit=True)
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        response = client.post(
            "/api/public/encryption/sessions",
            json={
                "client_public_key": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "client-x",
                    "y": "client-y",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == "too many active encryption sessions"
    assert logs.events[0]["event_type"] == "rate_limit.public_encryption_session_active"
