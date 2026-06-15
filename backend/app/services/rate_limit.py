from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from threading import Lock


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("rate limit exceeded")


@dataclass(frozen=True)
class RateLimitRule:
    max_attempts: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

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
            hits = self._hits[key]
            while hits and current_time - hits[0] >= window:
                hits.popleft()

            if len(hits) >= rule.max_attempts:
                retry_after = window - (current_time - hits[0])
                return max(1, ceil(retry_after.total_seconds()))

            hits.append(current_time)
            return None


class RateLimitService:
    def __init__(self, limiter: InMemoryRateLimiter | None = None) -> None:
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
