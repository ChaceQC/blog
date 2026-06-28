from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import Request

from app.providers.telemetry import TelemetryService

_SLOW_REQUEST_MS = 1_000.0
_PUBLIC_GET_SAMPLE_RATE_PERCENT = 5

_WRITE_ACTION_PREFIXES = (
    "post.",
    "page.",
    "file.",
    "friend_link.",
    "link_group.",
    "site_nav.",
    "settings.",
)


def telemetry_context(request: Request) -> dict[str, str]:
    context = getattr(request.state, "telemetry_context", None)
    if isinstance(context, dict):
        return context

    context = {
        "request_id": uuid4().hex,
        "trace_id": uuid4().hex,
        "span_id": uuid4().hex[:16],
    }
    request.state.telemetry_context = context
    return context


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return _with_api_prefix(
            template=template,
            path=str(request.scope.get("path") or "/"),
        )

    path = str(request.scope.get("path") or "/")
    if path == "/":
        return "/"
    if path.startswith("/api/admin"):
        return "/api/admin/{unmatched}"
    if path.startswith("/api/public"):
        return "/api/public/{unmatched}"
    return "/{unmatched}"


def _with_api_prefix(*, template: str, path: str) -> str:
    if template.startswith("/api/"):
        return template
    for prefix in ("/api/admin", "/api/public"):
        if path == prefix or path.startswith(f"{prefix}/"):
            return f"{prefix}{template}"
    return template


def request_scope_component(request: Request) -> tuple[str, str]:
    route = route_template(request)
    if route.startswith("/api/admin/encryption") or route.startswith(
        "/api/public/encryption",
    ):
        return _scope_from_route(route), "encryption"
    if "/files" in route:
        return _scope_from_route(route), "files"
    if route.startswith("/api/admin/auth"):
        return "admin", "auth"
    if route.startswith("/api/admin"):
        return "admin", "admin-api"
    if route.startswith("/api/public"):
        return "public", "public-api"
    if route in {"/rss.xml", "/sitemap.xml", "/robots.txt"}:
        return "public", "feeds"
    return "system", "system"


def request_tags(
    telemetry: TelemetryService,
    request: Request,
    *,
    status_code: int,
    outcome: str,
) -> dict[str, str]:
    scope, component = request_scope_component(request)
    return telemetry.request_tags(
        component=component,
        scope=scope,
        route=route_template(request),
        method=request.method,
        status_code=status_code,
        outcome=outcome,
    )


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
        outcome=_outcome_from_status(status_code),
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
            "error_type": _reason_class(error_type or f"http_{status_code}"),
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
    profile = _safe_value(detail_json.get("profile"))
    credential = _safe_value(detail_json.get("credential"))
    action = _safe_value(detail_json.get("action"))
    tags = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "event_type": _safe_value(event_type) or "rate_limit",
        "scope": _safe_value(detail_json.get("scope")) or scope,
        "component": component,
        "rate_limit_backend": _safe_value(rate_limit_backend) or "memory",
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


def record_admin_audit_telemetry(
    telemetry: TelemetryService,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None,
    actor_id: int | None,
    after_json: dict[str, Any] | None,
) -> None:
    sanitized = sanitize_business_payload(after_json)
    payload: dict[str, object] = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "action": action,
        "entity_type": entity_type,
    }
    if entity_id is not None:
        payload["entity_id"] = entity_id
    if actor_id is not None:
        payload["actor_id"] = actor_id
    payload.update(sanitized)
    telemetry.record_event(type="blog.admin.audit", payload=payload)
    if _is_write_action(action):
        telemetry.record_metric(
            name="blog.content.write.count",
            value=1,
            unit="count",
            type="counter",
            tags={
                "environment": telemetry.environment,
                "version": telemetry.version,
                "component": "admin-api",
                "scope": "admin",
                "action": action,
                "entity_type": entity_type,
                "status": str(sanitized.get("status") or "unknown"),
                "visibility": str(sanitized.get("visibility") or "unknown"),
                "outcome": "ok",
            },
            payload={
                "entity_id": entity_id,
                "changed_fields_count": _changed_fields_count(sanitized),
            },
        )
        telemetry.record_event(
            type="blog.content.lifecycle",
            payload=payload,
        )


def record_access_telemetry(
    telemetry: TelemetryService,
    *,
    access_type: str,
    status_code: int,
    entity_type: str | None,
    entity_id: int | None,
) -> None:
    outcome = _access_outcome(access_type=access_type, status_code=status_code)
    metric_name = _access_metric_name(access_type)
    if metric_name is None:
        return
    tags = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "component": _access_component(access_type),
        "scope": "admin" if access_type.startswith("admin_") else "public",
        "access_type": access_type,
        "status_code": str(status_code),
        "outcome": outcome,
    }
    payload: dict[str, object] = {}
    if entity_id is not None and entity_id > 0:
        payload["entity_id"] = entity_id
    telemetry.record_metric(
        name=metric_name,
        value=1,
        unit="count",
        type="counter",
        tags=tags,
        payload=payload or None,
    )
    if access_type == "public_site_item_visit" and status_code == 302:
        telemetry.record_event(
            type="blog.site_nav.visit.recorded",
            payload={
                "environment": telemetry.environment,
                "version": telemetry.version,
                "entity_id": entity_id,
                "status_code": status_code,
            },
        )


def record_site_nav_visit_telemetry(
    telemetry: TelemetryService,
    *,
    outcome: str,
    entity_id: int,
    status_code: int = 302,
) -> None:
    telemetry.record_metric(
        name="blog.site_nav.visit.count",
        value=1,
        unit="count",
        type="counter",
        tags={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "component": "public-api",
            "scope": "public",
            "access_type": "public_site_item_visit",
            "status_code": str(status_code),
            "outcome": outcome,
        },
        payload={"entity_id": entity_id},
    )


def record_post_view_telemetry(
    telemetry: TelemetryService,
    *,
    outcome: str,
    entity_id: int | None,
) -> None:
    telemetry.record_metric(
        name="blog.public.post.view.count",
        value=1,
        unit="count",
        type="counter",
        tags={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "component": "public-api",
            "scope": "public",
            "outcome": outcome,
        },
        payload={"entity_id": entity_id},
    )


def record_post_like_telemetry(
    telemetry: TelemetryService,
    *,
    outcome: str,
    liked: bool,
    entity_id: int | None,
) -> None:
    telemetry.record_metric(
        name="blog.public.post.like.count",
        value=1,
        unit="count",
        type="counter",
        tags={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "component": "public-api",
            "scope": "public",
            "outcome": outcome,
            "liked": str(liked).lower(),
        },
        payload={"entity_id": entity_id},
    )


def record_file_upload_telemetry(
    telemetry: TelemetryService,
    *,
    outcome: str,
    visibility: str,
    public_listed: bool,
    entity_id: int | None = None,
    size_bytes: int | None = None,
) -> None:
    tags = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "component": "files",
        "scope": "admin",
        "outcome": outcome,
        "visibility": visibility,
        "public_listed": str(public_listed).lower(),
    }
    payload: dict[str, object] = {}
    if entity_id is not None:
        payload["entity_id"] = entity_id
    telemetry.record_metric(
        name="blog.file.upload.count",
        value=1,
        unit="count",
        type="counter",
        tags=tags,
        payload=payload or None,
    )
    if outcome == "ok" and size_bytes is not None:
        telemetry.record_metric(
            name="blog.file.upload.bytes",
            value=size_bytes,
            unit="bytes",
            type="histogram",
            tags={
                "environment": telemetry.environment,
                "version": telemetry.version,
                "component": "files",
                "scope": "admin",
                "visibility": visibility,
                "public_listed": str(public_listed).lower(),
            },
        )
        telemetry.record_event(
            type="blog.file.uploaded",
            payload={
                "environment": telemetry.environment,
                "version": telemetry.version,
                "entity_id": entity_id,
                "visibility": visibility,
                "public_listed": public_listed,
                "size_bytes": size_bytes,
            },
        )


def record_file_deleted_telemetry(
    telemetry: TelemetryService,
    *,
    entity_id: int,
    actor_id: int | None,
) -> None:
    payload: dict[str, object] = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "entity_id": entity_id,
    }
    if actor_id is not None:
        payload["actor_id"] = actor_id
    telemetry.record_event(type="blog.file.deleted", payload=payload)


def record_temporary_url_telemetry(
    telemetry: TelemetryService,
    *,
    scope: str,
    entity_id: int,
    expires_seconds: int,
) -> None:
    telemetry.record_event(
        type="blog.file.temporary_url.created",
        payload={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "scope": scope,
            "entity_id": entity_id,
            "expires_seconds": expires_seconds,
        },
    )


def record_friend_link_application_telemetry(
    telemetry: TelemetryService,
    *,
    outcome: str,
    entity_id: int | None = None,
) -> None:
    payload: dict[str, object] = {}
    if entity_id is not None:
        payload["entity_id"] = entity_id
    telemetry.record_metric(
        name="blog.friend_link.application.count",
        value=1,
        unit="count",
        type="counter",
        tags={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "component": "public-api",
            "scope": "public",
            "outcome": outcome,
        },
        payload=payload or None,
    )
    if outcome == "accepted" and entity_id is not None:
        telemetry.record_event(
            type="blog.friend_link.application.created",
            payload={
                "environment": telemetry.environment,
                "version": telemetry.version,
                "entity_id": entity_id,
                "status": "pending",
            },
        )


def record_friend_link_reviewed_telemetry(
    telemetry: TelemetryService,
    *,
    entity_id: int,
    actor_id: int | None,
    review_status: str,
) -> None:
    payload: dict[str, object] = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "entity_id": entity_id,
        "review_status": review_status,
    }
    if actor_id is not None:
        payload["actor_id"] = actor_id
    telemetry.record_event(type="blog.friend_link.reviewed", payload=payload)


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
        tags["reason"] = _reason_class(reason or "rejected")
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
            "reason_class": _reason_class(reason_class),
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
            "reason_class": _reason_class(reason_class),
        },
        payload={"actor_id": actor_id} if actor_id is not None else None,
    )


def record_task_completed(
    telemetry: TelemetryService,
    *,
    task_name: str,
    outcome: str,
    duration_ms: float,
    deleted_rows: dict[str, int] | None = None,
    friend_link_counts: dict[str, int] | None = None,
) -> None:
    tags = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "component": "tasks",
        "scope": "system",
        "task_name": task_name,
        "outcome": outcome,
    }
    telemetry.record_metric(
        name="blog.task.completed.count",
        value=1,
        unit="count",
        type="counter",
        tags=tags,
        payload={"duration_ms": duration_ms},
    )
    if deleted_rows:
        for table, count in deleted_rows.items():
            telemetry.record_metric(
                name="blog.task.deleted.rows",
                value=count,
                unit="count",
                type="gauge",
                tags={
                    "environment": telemetry.environment,
                    "version": telemetry.version,
                    "component": "tasks",
                    "scope": "system",
                    "task_name": task_name,
                    "table": table,
                },
            )
    if friend_link_counts:
        for item_outcome, count in friend_link_counts.items():
            telemetry.record_metric(
                name="blog.friend_link.health.count",
                value=count,
                unit="count",
                type="gauge",
                tags={
                    "environment": telemetry.environment,
                    "version": telemetry.version,
                    "component": "tasks",
                    "scope": "system",
                    "outcome": item_outcome,
                },
            )
    telemetry.record_event(
        type="blog.task.completed",
        payload={
            "environment": telemetry.environment,
            "version": telemetry.version,
            "task_name": task_name,
            "outcome": outcome,
            "duration_ms": duration_ms,
            **(deleted_rows or {}),
            **(friend_link_counts or {}),
        },
    )
    telemetry.record_log(
        level="info",
        message="Maintenance task completed",
        logger="blog.tasks",
        attributes={"task_name": task_name, "outcome": outcome},
        payload={
            "duration_ms": duration_ms,
            **(deleted_rows or {}),
            **(friend_link_counts or {}),
        },
    )
    telemetry.record_span(
        trace_id=uuid4().hex,
        span_id=uuid4().hex[:16],
        name=f"task {task_name}",
        start_time=datetime.fromtimestamp(
            time.time() - duration_ms / 1000,
            tz=UTC,
        ),
        end_time=datetime.now(UTC),
        duration_ms=duration_ms,
        status_code=outcome,
        source="blog-maintenance",
        attributes={"task_name": task_name, "outcome": outcome},
    )


def sanitize_business_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    allowed = {
        "changed_fields",
        "status",
        "visibility",
        "public_listed",
        "show_in_nav",
        "review_status",
        "deleted",
        "is_public",
        "published_at_set",
    }
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "changed_fields":
            if isinstance(value, (list, tuple, set)):
                fields = sorted(str(item) for item in value if isinstance(item, str))
                if fields:
                    sanitized[key] = fields[:64]
            continue
        if isinstance(value, (str, bool, int, float)):
            sanitized[key] = value
    return sanitized


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
            "error_type": _reason_class(error_type),
            "request_id": context["request_id"],
        },
        payload={"error_fingerprint": _error_fingerprint(error_type)},
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
        return _deterministic_sample(
            telemetry_context(request)["request_id"],
            _PUBLIC_GET_SAMPLE_RATE_PERCENT,
        )
    return False


def _scope_from_route(route: str) -> str:
    if route.startswith("/api/admin"):
        return "admin"
    if route.startswith("/api/public"):
        return "public"
    return "system"


def _outcome_from_status(status_code: int) -> str:
    if status_code == 429:
        return "limited"
    if status_code in {401, 403}:
        return "denied"
    if status_code >= 500:
        return "error"
    if status_code >= 400:
        return "error"
    return "ok"


def _access_metric_name(access_type: str) -> str | None:
    if access_type == "public_site_item_visit":
        return "blog.site_nav.visit.count"
    if "file" in access_type or "image" in access_type:
        return "blog.file.access.count"
    return None


def _access_component(access_type: str) -> str:
    if "file" in access_type or "image" in access_type:
        return "files"
    if "site_item" in access_type or "friend_link" in access_type:
        return "public-api"
    return "public-api"


def _access_outcome(*, access_type: str, status_code: int) -> str:
    if status_code == 302:
        return "redirect"
    if status_code == 404:
        return "not_found"
    if status_code in {401, 403}:
        return "denied"
    if status_code >= 400:
        return "error"
    return "ok"


def _is_write_action(action: str) -> bool:
    return action.startswith(_WRITE_ACTION_PREFIXES)


def _changed_fields_count(payload: dict[str, Any]) -> int:
    changed_fields = payload.get("changed_fields")
    if not isinstance(changed_fields, list):
        return 0
    return len([item for item in changed_fields if isinstance(item, str)])


def _safe_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:128]


def _reason_class(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"_", "-", "."} else "_"
        for char in value.lower()
    ).strip("_")
    return cleaned[:64] or "unknown"


def _error_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _deterministic_sample(seed: str, percent: int) -> bool:
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return digest[0] < int(256 * percent / 100)
