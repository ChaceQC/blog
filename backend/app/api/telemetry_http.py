from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request

from app.api.telemetry_common import (
    deterministic_sample,
    error_fingerprint,
    outcome_from_status,
    reason_class,
    request_tags,
    telemetry_context,
)
from app.providers.telemetry import TelemetryService

_SLOW_REQUEST_MS = 1_000.0
_PUBLIC_GET_SAMPLE_RATE_PERCENT = 5


def record_http_request(
    telemetry: TelemetryService,
    request: Request,
    *,
    status_code: int,
    duration_ms: float,
    error_type: str | None = None,
) -> None:
    tags = request_tags(
        telemetry,
        request,
        status_code=status_code,
        outcome=outcome_from_status(status_code),
    )
    telemetry.record_metric(
        name="blog.http.server.request.count",
        value=1,
        unit="count",
        type="counter",
        tags=tags,
    )
    telemetry.record_metric(
        name="blog.http.server.duration",
        value=duration_ms,
        unit="ms",
        type="histogram",
        tags=tags,
    )
    if status_code >= 400 or error_type is not None:
        error_tags = {
            "environment": telemetry.environment,
            "version": telemetry.version,
            "route": tags["route"],
            "status_code": tags["status_code"],
            "error_type": reason_class(error_type or f"http_{status_code}"),
            "component": tags["component"],
        }
        telemetry.record_metric(
            name="blog.http.server.error.count",
            value=1,
            unit="count",
            type="counter",
            tags=error_tags,
            payload={"request_id": telemetry_context(request)["request_id"]},
        )
    if status_code >= 500 or error_type is not None:
        _record_request_error_log(
            telemetry,
            request,
            status_code=status_code,
            error_type=error_type or f"http_{status_code}",
        )
    _record_request_span(
        telemetry,
        request,
        tags=tags,
        status_code=status_code,
        duration_ms=duration_ms,
    )


def _record_request_error_log(
    telemetry: TelemetryService,
    request: Request,
    *,
    status_code: int,
    error_type: str,
) -> None:
    tags = request_tags(
        telemetry,
        request,
        status_code=status_code,
        outcome="error",
    )
    context = telemetry_context(request)
    telemetry.record_log(
        level="error",
        message="Unhandled request error",
        logger="blog.http",
        trace_id=context["trace_id"],
        span_id=context["span_id"],
        attributes={
            "route": tags["route"],
            "method": tags["method"],
            "component": tags["component"],
            "status_code": tags["status_code"],
            "error_type": reason_class(error_type),
            "request_id": context["request_id"],
        },
        payload={"error_fingerprint": error_fingerprint(error_type)},
    )


def _record_request_span(
    telemetry: TelemetryService,
    request: Request,
    *,
    tags: dict[str, str],
    status_code: int,
    duration_ms: float,
) -> None:
    if not _should_sample_request_span(
        request,
        status_code=status_code,
        duration_ms=duration_ms,
        tags=tags,
    ):
        return
    context = telemetry_context(request)
    start_time = getattr(request.state, "telemetry_started_at", None)
    if not isinstance(start_time, datetime):
        start_time = datetime.now(UTC)
    telemetry.record_span(
        trace_id=context["trace_id"],
        span_id=context["span_id"],
        name=f"HTTP {request.method.upper()} {tags['route']}",
        start_time=start_time,
        end_time=datetime.now(UTC),
        duration_ms=duration_ms,
        status_code=str(status_code),
        source="blog-backend",
        attributes={
            "route": tags["route"],
            "method": tags["method"],
            "scope": tags["scope"],
            "status_code": tags["status_code"],
            "outcome": tags["outcome"],
        },
    )


def _should_sample_request_span(
    request: Request,
    *,
    status_code: int,
    duration_ms: float,
    tags: dict[str, str],
) -> bool:
    if status_code >= 500 or status_code == 429:
        return True
    if duration_ms >= _SLOW_REQUEST_MS:
        return True
    if tags.get("scope") == "admin" and request.method.upper() in {
        "POST",
        "PATCH",
        "PUT",
        "DELETE",
    }:
        return True
    if (
        tags.get("scope") == "public"
        and request.method.upper() == "GET"
        and 200 <= status_code < 400
    ):
        return deterministic_sample(
            telemetry_context(request)["request_id"],
            _PUBLIC_GET_SAMPLE_RATE_PERCENT,
        )
    return False
