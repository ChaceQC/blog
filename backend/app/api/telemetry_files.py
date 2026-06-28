from __future__ import annotations

from app.providers.telemetry import TelemetryService


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
