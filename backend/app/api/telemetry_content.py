from __future__ import annotations

from typing import Any

from app.providers.telemetry import TelemetryService

_WRITE_ACTION_PREFIXES = (
    "post.",
    "page.",
    "file.",
    "friend_link.",
    "link_group.",
    "site_nav.",
    "settings.",
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
        telemetry.record_event(type="blog.content.lifecycle", payload=payload)


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


def _is_write_action(action: str) -> bool:
    return action.startswith(_WRITE_ACTION_PREFIXES)


def _changed_fields_count(payload: dict[str, Any]) -> int:
    changed_fields = payload.get("changed_fields")
    if not isinstance(changed_fields, list):
        return 0
    return len([item for item in changed_fields if isinstance(item, str)])
