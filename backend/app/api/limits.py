from typing import Any

from fastapi import HTTPException, Request, status

from app.core.request import client_ip
from app.services.logs import LogService
from app.services.rate_limit import RateLimitExceeded, RateLimitRule, RateLimitService


async def enforce_rate_limit(
    *,
    request: Request,
    limiter: RateLimitService,
    logs: LogService,
    key: str,
    rule: RateLimitRule,
    event_type: str,
    detail_json: dict[str, Any],
) -> None:
    try:
        limiter.check(key=key, rule=rule)
    except RateLimitExceeded as exc:
        await logs.record_security_event(
            event_type=event_type,
            severity="medium",
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
            path=str(request.url.path),
            detail_json=detail_json,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
