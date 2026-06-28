import json
from types import SimpleNamespace
from urllib import error

from fastapi.testclient import TestClient

import app.tasks.telemetry as task_telemetry_module
from app.api.state import telemetry_signature
from app.api.telemetry import record_admin_audit_telemetry, record_task_completed
from app.core.config import get_settings
from app.main import create_app
from app.providers import telemetry as telemetry_module
from app.providers.telemetry import TelemetryService, _chunk_payloads


class FakeUrlopenResponse:
    status = 202

    def __enter__(self) -> "FakeUrlopenResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeTelemetry:
    def __init__(self) -> None:
        self.environment = "test"
        self.version = "1.0.0"
        self.metrics: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.logs: list[dict[str, object]] = []
        self.spans: list[dict[str, object]] = []
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

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


def test_disabled_telemetry_service_does_not_queue_items() -> None:
    service = TelemetryService(
        endpoint="http://telemetry.local",
        api_key="tlm_test",
        enabled=False,
        source="blog-backend",
        environment="test",
        version="1.0.0",
    )

    service.record_metric(name="blog.test.count", value=1)
    service.record_event(type="blog.test.event", payload={})
    service.record_log(level="info", message="hello")

    assert service._queue.empty()


def test_telemetry_sends_utf8_json_with_project_api_key(monkeypatch) -> None:
    sent_requests: list[object] = []

    def fake_urlopen(request: object, *, timeout: float) -> FakeUrlopenResponse:
        assert timeout == 1.0
        sent_requests.append(request)
        return FakeUrlopenResponse()

    monkeypatch.setattr(telemetry_module.urllib_request, "urlopen", fake_urlopen)
    service = TelemetryService(
        endpoint="http://telemetry.local",
        api_key="tlm_project_key",
        enabled=True,
        source="blog-backend",
        environment="test",
        version="1.0.0",
        timeout_seconds=1.0,
        retry_attempts=1,
    )

    service._flush_kind(
        "metrics",
        [
            {
                "name": "blog.test.count",
                "value": 1,
                "source": "blog-backend",
                "payload": {"note": "中文"},
            },
        ],
    )

    request = sent_requests[0]
    headers = {key.lower(): value for key, value in request.header_items()}
    body = request.data.decode("utf-8")
    payload = json.loads(body)

    assert request.full_url == "http://telemetry.local/api/v1/ingest/metrics"
    assert headers["x-api-key"] == "tlm_project_key"
    assert headers["content-type"] == "application/json; charset=utf-8"
    assert payload["metrics"][0]["payload"]["note"] == "中文"
    assert "\\u4e2d\\u6587" not in body


def test_multiple_events_use_batch_endpoint(monkeypatch) -> None:
    sent_urls: list[str] = []

    def fake_urlopen(request: object, *, timeout: float) -> FakeUrlopenResponse:
        sent_urls.append(request.full_url)
        return FakeUrlopenResponse()

    monkeypatch.setattr(telemetry_module.urllib_request, "urlopen", fake_urlopen)
    service = TelemetryService(
        endpoint="http://telemetry.local/api/v1",
        api_key="tlm_project_key",
        enabled=True,
        source="blog-backend",
        environment="test",
        version="1.0.0",
        retry_attempts=1,
    )

    service._flush_kind(
        "events",
        [
            {"type": "blog.one", "payload": {}, "source": "blog-backend"},
            {"type": "blog.two", "payload": {}, "source": "blog-backend"},
        ],
    )

    assert sent_urls == ["http://telemetry.local/api/v1/ingest/batch"]


def test_payload_chunking_respects_item_count_and_size_limits() -> None:
    metrics = [
        {"name": f"blog.test.{index}", "value": index, "source": "blog-backend"}
        for index in range(105)
    ]
    batches = _chunk_payloads("metrics", metrics)

    assert [len(batch["metrics"]) for batch in batches] == [100, 5]

    oversized = {
        "name": "blog.test.oversized",
        "value": 1,
        "source": "blog-backend",
        "payload": {"blob": "x" * (300 * 1024)},
    }
    assert _chunk_payloads("metrics", [oversized]) == []

    oversized_event = {
        "type": "blog.test.event",
        "payload": {f"field_{index}": "x" * 8192 for index in range(10)},
        "source": "blog-backend",
    }
    assert _chunk_payloads("events", [oversized_event]) == []


def test_oversized_single_event_payload_is_not_queued() -> None:
    service = TelemetryService(
        endpoint="http://telemetry.local",
        api_key="tlm_project_key",
        enabled=True,
        source="blog-backend",
        environment="test",
        version="1.0.0",
    )

    service.record_event(
        type="blog.test.event",
        payload={f"field_{index}": "x" * 8192 for index in range(10)},
    )

    assert service._queue.empty()


def test_retryable_telemetry_errors_use_retry_after(monkeypatch) -> None:
    calls: list[str] = []
    waits: list[float] = []

    def fake_urlopen(request: object, *, timeout: float) -> FakeUrlopenResponse:
        calls.append(request.full_url)
        if len(calls) == 1:
            raise error.HTTPError(
                request.full_url,
                429,
                "too many requests",
                {"Retry-After": "0.5"},
                None,
            )
        return FakeUrlopenResponse()

    monkeypatch.setattr(telemetry_module.urllib_request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        telemetry_module.threading.Event,
        "wait",
        lambda _, value: waits.append(value) or False,
    )
    service = TelemetryService(
        endpoint="http://telemetry.local",
        api_key="tlm_project_key",
        enabled=True,
        source="blog-backend",
        environment="test",
        version="1.0.0",
        retry_attempts=2,
    )

    service._send_with_retry(
        kind="metrics",
        payload={
            "metrics": [
                {"name": "blog.test.count", "value": 1, "source": "blog-backend"},
            ],
        },
    )

    assert len(calls) == 2
    assert waits == [0.5]


def test_retry_after_is_capped(monkeypatch) -> None:
    sleeps: list[float] = []

    def fake_urlopen(request: object, *, timeout: float) -> FakeUrlopenResponse:
        raise error.HTTPError(
            request.full_url,
            429,
            "too many requests",
            {"Retry-After": "600"},
            None,
        )

    monkeypatch.setattr(telemetry_module.urllib_request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        telemetry_module.threading.Event,
        "wait",
        lambda _, value: sleeps.append(value) or False,
    )
    service = TelemetryService(
        endpoint="http://telemetry.local",
        api_key="tlm_project_key",
        enabled=True,
        source="blog-backend",
        environment="test",
        version="1.0.0",
        retry_attempts=1,
    )

    service._send_with_retry(
        kind="metrics",
        payload={
            "metrics": [
                {"name": "blog.test.count", "value": 1, "source": "blog-backend"},
            ],
        },
    )

    assert sleeps == [30.0]


def test_permanent_error_worker_can_be_stopped(monkeypatch) -> None:
    def fake_urlopen(request: object, *, timeout: float) -> FakeUrlopenResponse:
        raise error.HTTPError(
            request.full_url,
            401,
            "unauthorized",
            {},
            None,
        )

    monkeypatch.setattr(telemetry_module.urllib_request, "urlopen", fake_urlopen)
    service = TelemetryService(
        endpoint="http://telemetry.local",
        api_key="tlm_bad",
        enabled=True,
        source="blog-backend",
        environment="test",
        version="1.0.0",
        timeout_seconds=1.0,
        retry_attempts=1,
    )

    service._send_with_retry(
        kind="metrics",
        payload={
            "metrics": [
                {"name": "blog.test.count", "value": 1, "source": "blog-backend"},
            ],
        },
    )
    service._worker_thread = type(
        "FakeThread",
        (),
        {
            "joined": False,
            "alive": True,
            "join": lambda self, timeout: (
                setattr(self, "joined", True),
                setattr(self, "alive", False),
            ),
            "is_alive": lambda self: self.alive,
        },
    )()

    service.stop()

    assert service._worker_thread is None


def test_http_middleware_records_route_template_without_query() -> None:
    settings = get_settings()
    app = create_app(settings)
    fake = FakeTelemetry()
    app.state.telemetry_service = fake
    app.state.telemetry_signature = telemetry_signature(settings)

    with TestClient(app) as client:
        response = client.get("/api/public/status?token=secret")

    assert response.status_code == 200
    request_count = next(
        metric
        for metric in fake.metrics
        if metric["name"] == "blog.http.server.request.count"
    )
    tags = request_count["tags"]
    assert tags["route"] == "/api/public/status"
    assert "secret" not in json.dumps(tags, ensure_ascii=False)


def test_admin_audit_telemetry_sanitizes_business_payload() -> None:
    fake = FakeTelemetry()

    record_admin_audit_telemetry(
        fake,
        action="post.publish",
        entity_type="post",
        entity_id=12,
        actor_id=1,
        after_json={
            "title": "不能外传的标题",
            "slug": "secret-slug",
            "url": "https://example.com/private",
            "status": "published",
            "visibility": "public",
            "changed_fields": ["slug", "title", "status"],
            "published_at_set": True,
        },
    )

    event = fake.events[0]
    payload = event["payload"]
    assert event["type"] == "blog.admin.audit"
    assert "title" not in payload
    assert "slug" not in payload
    assert "url" not in payload
    assert payload["changed_fields"] == ["slug", "status", "title"]
    assert payload["status"] == "published"


def test_admin_audit_telemetry_ignores_invalid_changed_fields() -> None:
    fake = FakeTelemetry()

    record_admin_audit_telemetry(
        fake,
        action="post.update",
        entity_type="post",
        entity_id=12,
        actor_id=1,
        after_json={
            "status": "published",
            "changed_fields": "title",
        },
    )

    payload = fake.events[0]["payload"]
    write_metric = next(
        metric
        for metric in fake.metrics
        if metric["name"] == "blog.content.write.count"
    )
    assert "changed_fields" not in payload
    assert write_metric["payload"]["changed_fields_count"] == 0


def test_task_completed_event_uses_stable_summary_fields() -> None:
    fake = FakeTelemetry()

    record_task_completed(
        fake,
        task_name="cleanup-logs",
        outcome="ok",
        duration_ms=12.5,
        deleted_rows={"access": 2, "audit": 0},
        friend_link_counts={"healthy": 3, "unhealthy": 1, "skipped": 0},
    )

    event = next(
        item for item in fake.events if item["type"] == "blog.task.completed"
    )
    payload = event["payload"]
    assert payload["deleted_count"] == 2
    assert payload["healthy_count"] == 3
    assert payload["unhealthy_count"] == 1
    assert payload["skipped_count"] == 0
    assert payload["deleted_rows"] == {"access": 2, "audit": 0}
    assert payload["friend_link_counts"] == {
        "healthy": 3,
        "unhealthy": 1,
        "skipped": 0,
    }


def test_deployment_finished_event_uses_backend_settings(monkeypatch) -> None:
    fake = FakeTelemetry()
    monkeypatch.setattr(
        task_telemetry_module,
        "get_settings",
        lambda: SimpleNamespace(version="1.0.0", environment="production"),
    )
    monkeypatch.setattr(
        task_telemetry_module,
        "create_telemetry_service",
        lambda settings: fake,
    )

    task_telemetry_module.record_deployment_finished(
        status="ok",
        duration_seconds=12.5,
        git_sha="abc123",
    )

    assert fake.events == [
        {
            "type": "blog.deployment.finished",
            "source": "blog-deploy",
            "payload": {
                "version": "1.0.0",
                "environment": "production",
                "status": "ok",
                "duration_seconds": 12.5,
                "git_sha": "abc123",
            },
        },
    ]
    assert fake.stopped is True
