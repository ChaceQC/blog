from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil
from threading import Lock
from typing import Protocol
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("rate limit exceeded")


@dataclass(frozen=True)
class RateLimitRule:
    max_attempts: int
    window_seconds: int


class RateLimiterBackend(Protocol):
    def hit(
        self,
        *,
        key: str,
        rule: RateLimitRule,
        now: datetime | None = None,
    ) -> int | None: ...


class InMemoryRateLimiter:
    def __init__(self, *, max_keys: int = 10_000) -> None:
        self._hits: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()
        self._max_keys = max(1, max_keys)

    def hit(
        self,
        *,
        key: str,
        rule: RateLimitRule,
        now: datetime | None = None,
    ) -> int | None:
        current_time = now or datetime.now(UTC)
        window = timedelta(seconds=rule.window_seconds)

        with self._lock:
            if key not in self._hits and len(self._hits) >= self._max_keys:
                self._evict_oldest_key()
            hits = self._hits[key]
            while hits and current_time - hits[0] >= window:
                hits.popleft()
            if not hits:
                self._hits.pop(key, None)
                hits = self._hits[key]

            if len(hits) >= rule.max_attempts:
                retry_after = window - (current_time - hits[0])
                return max(1, ceil(retry_after.total_seconds()))

            hits.append(current_time)
            return None

    def _evict_oldest_key(self) -> None:
        oldest_key = min(
            self._hits,
            key=lambda item: self._hits[item][0]
            if self._hits[item]
            else datetime.min.replace(tzinfo=UTC),
        )
        self._hits.pop(oldest_key, None)


class RedisRateLimiter:
    _SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_attempts = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

redis.call("ZREMRANGEBYSCORE", key, "-inf", now - window)
local count = redis.call("ZCARD", key)
if count >= max_attempts then
  local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
  if oldest[2] then
    return {0, math.max(1, math.ceil(window - (now - tonumber(oldest[2]))))}
  end
  return {0, window}
end

redis.call("ZADD", key, now, member)
redis.call("EXPIRE", key, ttl)
return {1, 0}
"""

    def __init__(
        self,
        *,
        redis_client: Redis,
        key_prefix: str,
        fallback: InMemoryRateLimiter | None = None,
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix.rstrip(":")
        self._fallback = fallback or InMemoryRateLimiter()

    def hit(
        self,
        *,
        key: str,
        rule: RateLimitRule,
        now: datetime | None = None,
    ) -> int | None:
        current_time = now or datetime.now(UTC)
        timestamp_ms = int(current_time.timestamp() * 1000)
        redis_key = self._redis_key(key)
        member = f"{timestamp_ms}:{uuid4().hex}"
        try:
            allowed, retry_after = self._redis.eval(
                self._SCRIPT,
                1,
                redis_key,
                timestamp_ms,
                rule.window_seconds * 1000,
                rule.max_attempts,
                member,
                rule.window_seconds * 2,
            )
        except RedisError:
            return self._fallback.hit(key=key, rule=rule, now=now)

        if int(allowed) == 1:
            return None
        return max(1, ceil(int(retry_after) / 1000))

    def _redis_key(self, key: str) -> str:
        digest = sha256(key.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:{digest}"


class RateLimitService:
    def __init__(self, limiter: RateLimiterBackend | None = None) -> None:
        self._limiter = limiter or InMemoryRateLimiter()

    def check(
        self,
        *,
        key: str,
        rule: RateLimitRule,
        now: datetime | None = None,
    ) -> None:
        retry_after_seconds = self._limiter.hit(key=key, rule=rule, now=now)
        if retry_after_seconds is not None:
            raise RateLimitExceeded(retry_after_seconds)


def create_rate_limit_service(settings: Settings) -> RateLimitService:
    if settings.rate_limit_backend != "redis" or not settings.redis_url:
        return RateLimitService()

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        protocol=2,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    return RateLimitService(
        RedisRateLimiter(
            redis_client=redis_client,
            key_prefix=settings.redis_key_prefix,
        ),
    )
