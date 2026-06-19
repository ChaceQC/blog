from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.limits import enforce_rate_limit
from app.services.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    RateLimitRule,
    RateLimitService,
    RedisRateLimiter,
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


def test_in_memory_rate_limit_caps_tracked_keys() -> None:
    limiter = InMemoryRateLimiter(max_keys=2)
    service = RateLimitService(limiter)
    rule = RateLimitRule(max_attempts=2, window_seconds=60)
    now = datetime(2026, 6, 16, tzinfo=UTC)

    service.check(key="one", rule=rule, now=now)
    service.check(key="two", rule=rule, now=now + timedelta(seconds=1))
    service.check(key="three", rule=rule, now=now + timedelta(seconds=2))

    assert len(limiter._hits) == 2
    assert "one" not in limiter._hits


def test_redis_rate_limit_blocks_with_shared_window() -> None:
    service = RateLimitService(
        RedisRateLimiter(
            redis_client=FakeRedis(),
            key_prefix="test:rate-limit",
        ),
    )
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


def test_redis_rate_limit_falls_back_to_memory_when_redis_fails() -> None:
    service = RateLimitService(
        RedisRateLimiter(
            redis_client=FailingRedis(),
            key_prefix="test:rate-limit",
            fallback=InMemoryRateLimiter(),
        ),
    )
    rule = RateLimitRule(max_attempts=1, window_seconds=60)
    now = datetime(2026, 6, 16, tzinfo=UTC)

    service.check(key="encryption-session:127.0.0.1", rule=rule, now=now)
    with pytest.raises(RateLimitExceeded):
        service.check(
            key="encryption-session:127.0.0.1",
            rule=rule,
            now=now + timedelta(seconds=1),
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
        detail_json={"credential": "username"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await enforce_rate_limit(
            request=request,
            limiter=service,
            logs=logs,
            key="admin-login:127.0.0.1:admin",
            rule=rule,
            event_type="rate_limit.admin_login",
            detail_json={"credential": "username"},
        )

    assert exc_info.value.status_code == 429
    assert logs.events == [
        {
            "event_type": "rate_limit.admin_login",
            "severity": "medium",
            "ip": "127.0.0.1",
            "user_agent": "pytest",
            "path": "/api/admin/auth/login",
            "detail_json": {"credential": "username"},
        },
    ]


class FakeRedis:
    def __init__(self) -> None:
        self._hits: dict[str, list[int]] = {}

    def eval(
        self,
        _: str,
        __: int,
        key: str,
        now: int,
        window: int,
        max_attempts: int,
        member: str,
        ___: int,
    ) -> list[int]:
        hits = [
            score
            for score in self._hits.get(key, [])
            if now - score < window
        ]
        self._hits[key] = hits
        if len(hits) >= max_attempts:
            retry_after = window - (now - hits[0])
            return [0, max(1, retry_after)]
        self._hits.setdefault(key, []).append(now + len(member) * 0)
        return [1, 0]


class FailingRedis:
    def eval(self, *_: object) -> list[int]:
        from redis.exceptions import RedisError

        raise RedisError("redis is unavailable")
