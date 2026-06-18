from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Lock
from typing import Any, Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings
from app.models.log import AccessLog, AuditLog, LoginLog, SecurityEvent


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


class LogRepositoryProtocol(Protocol):
    async def list_audit_logs(self, *, limit: int, offset: int) -> Sequence[AuditLog]:
        ...

    async def list_access_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AccessLog]: ...

    async def list_login_logs(self, *, limit: int, offset: int) -> Sequence[LoginLog]:
        ...

    async def list_security_events(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SecurityEvent]: ...

    async def record_security_event(
        self,
        *,
        event_type: str,
        severity: str,
        actor_id: int | None,
        ip: str | None,
        user_agent: str | None,
        path: str | None,
        detail_json: dict[str, Any] | None,
    ) -> None: ...

    async def record_audit_log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: int | None,
        actor_id: int | None,
        ip: str | None,
        user_agent: str | None,
        before_json: dict[str, Any] | None,
        after_json: dict[str, Any] | None,
    ) -> None: ...

    async def record_access_log(
        self,
        *,
        access_type: str,
        method: str,
        path: str,
        status_code: int,
        entity_type: str | None,
        entity_id: int | None,
        ip: str | None,
        user_agent: str | None,
        detail_json: dict[str, Any] | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class LogService:
    def __init__(
        self,
        repository: LogRepositoryProtocol,
        dedupe_backend: AccessLogDedupeBackend | None = None,
    ) -> None:
        self.repository = repository
        self._dedupe_backend = dedupe_backend or InMemoryAccessLogDedupeBackend()

    async def list_audit_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AuditLog]:
        return await self.repository.list_audit_logs(limit=limit, offset=offset)

    async def list_access_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AccessLog]:
        return await self.repository.list_access_logs(limit=limit, offset=offset)

    async def list_login_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[LoginLog]:
        return await self.repository.list_login_logs(limit=limit, offset=offset)

    async def list_security_events(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SecurityEvent]:
        return await self.repository.list_security_events(limit=limit, offset=offset)

    async def record_security_event(
        self,
        *,
        event_type: str,
        severity: str,
        ip: str | None,
        user_agent: str | None,
        path: str | None,
        detail_json: dict[str, Any] | None,
        actor_id: int | None = None,
    ) -> None:
        await self.repository.record_security_event(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            ip=ip,
            user_agent=user_agent,
            path=path,
            detail_json=detail_json,
        )
        await self.repository.commit()

    async def record_audit_log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: int | None,
        actor_id: int | None,
        ip: str | None,
        user_agent: str | None,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
    ) -> None:
        await self.repository.record_audit_log(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            ip=ip,
            user_agent=user_agent,
            before_json=before_json,
            after_json=after_json,
        )
        await self.repository.commit()

    async def record_access_log(
        self,
        *,
        access_type: str,
        method: str,
        path: str,
        status_code: int,
        ip: str | None,
        user_agent: str | None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        detail_json: dict[str, Any] | None = None,
    ) -> None:
        if not self._should_record_access_log(
            method=method,
            path=path,
            status_code=status_code,
            ip=ip,
        ):
            return
        await self.repository.record_access_log(
            access_type=access_type,
            method=method,
            path=path,
            status_code=status_code,
            entity_type=entity_type,
            entity_id=entity_id,
            ip=ip,
            user_agent=user_agent,
            detail_json=detail_json,
        )
        await self.repository.commit()

    def _should_record_access_log(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        ip: str | None,
    ) -> bool:
        settings = get_settings()
        if status_code < 200 or status_code >= 400:
            return True
        if method.upper() not in {"GET", "HEAD"}:
            return True
        if settings.access_log_dedupe_seconds <= 0:
            return True

        dedupe_key = build_access_log_dedupe_key(
            ip=ip,
            method=method,
            path=path,
        )
        return self._dedupe_backend.should_record(
            key=dedupe_key,
            rule=AccessLogDedupeRule(
                window_seconds=settings.access_log_dedupe_seconds,
            ),
        )


def build_access_log_dedupe_key(
    *,
    ip: str | None,
    method: str,
    path: str,
) -> str:
    normalized_ip = ip or "unknown"
    normalized_method = method.upper()
    return f"{normalized_ip}:{normalized_method}:{path}"


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
