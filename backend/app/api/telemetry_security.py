from __future__ import annotations

from typing import Any

from fastapi import Request

from app.api.telemetry_common import reason_class as normalize_reason_class
from app.api.telemetry_common import (
    request_scope_component,
    route_template,
    safe_value,
    telemetry_context,
)
from app.providers.telemetry import TelemetryService


def record_rate_limit_hit(
    telemetry: TelemetryService,
    request: Request,
    *,
    event_type: str,
    detail_json: dict[str, Any],
    retry_after_seconds: int,
    rate_limit_backend: str,
) -> None:
    scope, component = request_scope_component(request)
    profile = safe_value(detail_json.get("profile"))
    credential = safe_value(detail_json.get("credential"))
    action = safe_value(detail_json.get("action"))
    tags = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "event_type": safe_value(event_type) or "rate_limit",
        "scope": safe_value(detail_json.get("scope")) or scope,
        "component": component,
        "rate_limit_backend": safe_value(rate_limit_backend) or "memory",
    }
    telemetry.record_metric(
        name="blog.rate_limit.hit.count",
        value=1,
        unit="count",
        type="counter",
        tags=tags,
        payload={"retry_after_seconds": retry_after_seconds},
    )
    payload: dict[str, object] = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "event_type": event_type,
        "scope": tags["scope"],
        "retry_after_seconds": retry_after_seconds,
    }
    if profile:
        payload["profile"] = profile
    if credential:
        payload["credential"] = credential
    if action:
        payload["action"] = action
    telemetry.record_event(type="blog.security.rate_limit.hit", payload=payload)
    telemetry.record_log(
        level="warn",
        message="Rate limit hit",
        logger="blog.rate_limit",
        trace_id=telemetry_context(request)["trace_id"],
        span_id=telemetry_context(request)["span_id"],
        attributes={
            "event_type": event_type,
            "route": route_template(request),
            "scope": tags["scope"],
            "component": component,
        },
        payload={"retry_after_seconds": retry_after_seconds},
    )


def record_encryption_session_telemetry(
    telemetry: TelemetryService,
    *,
    scope: str,
    profile: str,
    outcome: str,
    active_limit: int | None = None,
    reason: str | None = None,
) -> None:
    metric_name = (
        "blog.encryption.session.created.count"
        if outcome == "created"
        else "blog.encryption.session.rejected.count"
    )
    tags = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "component": "encryption",
        "scope": scope,
    }
    if outcome == "created":
        tags["profile"] = profile
    else:
        tags["reason"] = normalize_reason_class(reason or "rejected")
    telemetry.record_metric(
        name=metric_name,
        value=1,
        unit="count",
        type="counter",
        tags=tags,
        payload={"active_limit": active_limit} if active_limit is not None else None,
    )
    if reason == "active_limited":
        telemetry.record_event(
            type="blog.security.encryption_session_active_limited",
            payload={
                "environment": telemetry.environment,
                "version": telemetry.version,
                "scope": scope,
                "profile": profile,
            },
        )


def record_salt_websocket_closed(
    telemetry: TelemetryService,
    *,
    scope: str,
    close_code: int,
    reason_class: str,
) -> None:
    telemetry.record_metric(
        name="blog.encryption.salt.websocket.closed.count",
        value=1,
        unit="count",
        type="counter",
        tags={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "component": "encryption",
            "scope": scope,
            "close_code": str(close_code),
            "reason_class": normalize_reason_class(reason_class),
        },
    )


def record_salt_lease_telemetry(
    telemetry: TelemetryService,
    *,
    scope: str,
    purpose: str,
    profile: str | None,
    stage: str,
    count: int = 1,
) -> None:
    telemetry.record_metric(
        name="blog.encryption.salt.lease.count",
        value=count,
        unit="count",
        type="counter",
        tags={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "component": "encryption",
            "scope": scope,
            "purpose": purpose,
            "profile": profile or "none",
            "stage": stage,
        },
    )


def record_auth_login_telemetry(
    telemetry: TelemetryService,
    *,
    outcome: str,
    reason_class: str,
    actor_id: int | None = None,
) -> None:
    telemetry.record_metric(
        name="blog.auth.login.count",
        value=1,
        unit="count",
        type="counter",
        tags={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "component": "auth",
            "scope": "admin",
            "outcome": outcome,
            "reason_class": normalize_reason_class(reason_class),
        },
        payload={"actor_id": actor_id} if actor_id is not None else None,
    )
