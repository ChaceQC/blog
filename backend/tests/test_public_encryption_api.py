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


class FakeTelemetry:
    environment = "test"
    version = "1.0.0"

    def __init__(self) -> None:
        self.metrics: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.logs: list[dict[str, object]] = []
        self.spans: list[dict[str, object]] = []

    def request_tags(
        self,
        *,
        component: str,
        scope: str,
        route: str,
        method: str,
        status_code: int,
        outcome: str,
    ) -> dict[str, str]:
        return {
            "environment": self.environment,
            "version": self.version,
            "component": component,
            "scope": scope,
            "route": route,
            "method": method,
            "status_code": str(status_code),
            "status_family": f"{status_code // 100}xx",
            "outcome": outcome,
        }

    def record_metric(self, **kwargs: object) -> None:
        self.metrics.append(dict(kwargs))

    def record_event(self, **kwargs: object) -> None:
        self.events.append(dict(kwargs))

    def record_log(self, **kwargs: object) -> None:
        self.logs.append(dict(kwargs))

    def record_span(self, **kwargs: object) -> None:
        self.spans.append(dict(kwargs))


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
    telemetry = FakeTelemetry()
    original_telemetry = getattr(app.state, "telemetry_service", None)
    app.state.telemetry_service = telemetry
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
        app.state.telemetry_service = original_telemetry

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "9"
    assert logs.events[0]["event_type"] == "rate_limit.public_encryption_session"
    rejected_metric = next(
        metric
        for metric in telemetry.metrics
        if metric["name"] == "blog.encryption.session.rejected.count"
    )
    assert rejected_metric["tags"]["reason"] == "rate_limited"

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
    assert logs.events[0]["detail_json"] == {
        "scope": "public",
        "profile": "content-v1",
    }
