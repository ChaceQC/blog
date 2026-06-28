from __future__ import annotations

from app.providers.telemetry import TelemetryService


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
