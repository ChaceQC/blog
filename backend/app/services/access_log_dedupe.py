from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Lock
from typing import Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings


@dataclass(frozen=True)
class AccessLogDedupeRule:
    window_seconds: int


class AccessLogDedupeBackend(Protocol):
    def should_record(
        self,
        *,
        key: str,
        rule: AccessLogDedupeRule,
        now: datetime | None = None,
    ) -> bool: ...


class InMemoryAccessLogDedupeBackend:
    def __init__(self) -> None:
        self._expires_at: dict[str, datetime] = {}
        self._lock = Lock()

    def should_record(
        self,
        *,
        key: str,
        rule: AccessLogDedupeRule,
        now: datetime | None = None,
    ) -> bool:
        if rule.window_seconds <= 0:
            return True

        current_time = now or datetime.now(UTC)
        expires_at = current_time + timedelta(seconds=rule.window_seconds)
        with self._lock:
            existing_expires_at = self._expires_at.get(key)
            if (
                existing_expires_at is not None
                and existing_expires_at > current_time
            ):
                return False

            self._expires_at[key] = expires_at
            self._cleanup_expired(current_time)
            return True

    def _cleanup_expired(self, current_time: datetime) -> None:
        expired_keys = [
            key
            for key, expires_at in self._expires_at.items()
            if expires_at <= current_time
        ]
        for key in expired_keys:
            self._expires_at.pop(key, None)


class RedisAccessLogDedupeBackend:
    def __init__(
        self,
        *,
        redis_client: Redis,
        key_prefix: str,
        fallback: InMemoryAccessLogDedupeBackend | None = None,
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix.rstrip(":")
        self._fallback = fallback or InMemoryAccessLogDedupeBackend()

    def should_record(
        self,
        *,
        key: str,
        rule: AccessLogDedupeRule,
        now: datetime | None = None,
    ) -> bool:
        if rule.window_seconds <= 0:
            return True

        redis_key = self._redis_key(key)
        try:
            return bool(
                self._redis.set(
                    redis_key,
                    "1",
                    ex=rule.window_seconds,
                    nx=True,
                ),
            )
        except RedisError:
            return self._fallback.should_record(key=key, rule=rule, now=now)

    def _redis_key(self, key: str) -> str:
        digest = sha256(key.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:access-log-dedupe:{digest}"


def build_access_log_dedupe_key(
    *,
    ip: str | None,
    method: str,
    path: str,
) -> str:
    normalized_ip = ip or "unknown"
    normalized_method = method.upper()
    return f"{normalized_ip}:{normalized_method}:{path}"


def create_access_log_dedupe_backend(settings: Settings) -> AccessLogDedupeBackend:
    if settings.rate_limit_backend != "redis" or not settings.redis_url:
        return InMemoryAccessLogDedupeBackend()

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        protocol=2,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    return RedisAccessLogDedupeBackend(
        redis_client=redis_client,
        key_prefix=settings.redis_key_prefix,
    )
