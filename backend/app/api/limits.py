from typing import Any

from fastapi import HTTPException, Request, status

from app.api.telemetry import record_rate_limit_hit
from app.core.request import client_ip
from app.services.logs import LogService, sanitize_security_event_detail
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
        security_detail = sanitize_security_event_detail(detail_json) or {}
        telemetry_detail = _rate_limit_telemetry_detail(detail_json, security_detail)
        await logs.record_security_event(
            event_type=event_type,
            severity="medium",
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
            path=str(request.url.path),
            detail_json=security_detail or None,
        )
        app = request.scope.get("app")
        app_state = getattr(app, "state", None)
        telemetry = getattr(app_state, "telemetry_service", None)
        if telemetry is not None:
            record_rate_limit_hit(
                telemetry,
                request,
                event_type=event_type,
                detail_json=telemetry_detail,
                retry_after_seconds=exc.retry_after_seconds,
                rate_limit_backend=getattr(
                    getattr(app_state, "rate_limit_signature", None),
                    "rate_limit_backend",
                    "memory",
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


def _rate_limit_telemetry_detail(
    detail_json: dict[str, Any],
    security_detail: dict[str, Any],
) -> dict[str, Any]:
    detail = dict(security_detail)
    action = detail_json.get("action")
    if isinstance(action, str) and action.strip():
        detail["action"] = action.strip()[:128]
    return detail
