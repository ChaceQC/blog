from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.admin.limits import enforce_rate_limit
from app.services.rate_limit import (
    RateLimitExceeded,
    RateLimitRule,
    RateLimitService,
)


class FakeLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record_security_event(self, **payload: object) -> None:
        self.events.append(payload)


def test_rate_limit_blocks_after_window_is_full() -> None:
    service = RateLimitService()
    rule = RateLimitRule(max_attempts=2, window_seconds=60)
    now = datetime(2026, 6, 16, tzinfo=UTC)

    service.check(key="admin-login:127.0.0.1:admin", rule=rule, now=now)
    service.check(
        key="admin-login:127.0.0.1:admin",
        rule=rule,
        now=now + timedelta(seconds=1),
    )

    with pytest.raises(RateLimitExceeded) as exc_info:
        service.check(
            key="admin-login:127.0.0.1:admin",
            rule=rule,
            now=now + timedelta(seconds=2),
        )

    assert exc_info.value.retry_after_seconds == 58


def test_rate_limit_allows_after_window_moves_forward() -> None:
    service = RateLimitService()
    rule = RateLimitRule(max_attempts=1, window_seconds=60)
    now = datetime(2026, 6, 16, tzinfo=UTC)

    service.check(key="encryption-session:127.0.0.1", rule=rule, now=now)
    service.check(
        key="encryption-session:127.0.0.1",
        rule=rule,
        now=now + timedelta(seconds=60),
    )


@pytest.mark.anyio
async def test_enforce_rate_limit_records_security_event() -> None:
    service = RateLimitService()
    logs = FakeLogService()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/admin/auth/login",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
        },
    )
    rule = RateLimitRule(max_attempts=1, window_seconds=60)

    await enforce_rate_limit(
        request=request,
        limiter=service,
        logs=logs,
        key="admin-login:127.0.0.1:admin",
        rule=rule,
        event_type="rate_limit.admin_login",
        detail_json={"username": "admin"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await enforce_rate_limit(
            request=request,
            limiter=service,
            logs=logs,
            key="admin-login:127.0.0.1:admin",
            rule=rule,
            event_type="rate_limit.admin_login",
            detail_json={"username": "admin"},
        )

    assert exc_info.value.status_code == 429
    assert logs.events == [
        {
            "event_type": "rate_limit.admin_login",
            "severity": "medium",
            "ip": "127.0.0.1",
            "user_agent": "pytest",
            "path": "/api/admin/auth/login",
            "detail_json": {"username": "admin"},
        },
    ]
