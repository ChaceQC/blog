from typing import Any

from fastapi import Request

from app.api.telemetry import record_admin_audit_telemetry
from app.core.request import client_ip
from app.services.auth import AuthenticatedUser
from app.services.logs import LogService, sanitize_audit_log_payload


async def record_admin_audit(
    *,
    logs: LogService,
    request: Request,
    actor: AuthenticatedUser,
    action: str,
    entity_type: str,
    entity_id: int | None,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
) -> None:
    sanitized_before = sanitize_audit_log_payload(before_json)
    sanitized_after = sanitize_audit_log_payload(after_json)
    await logs.record_audit_log(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor.id,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        before_json=sanitized_before,
        after_json=sanitized_after,
    )
    telemetry = getattr(request.app.state, "telemetry_service", None)
    if telemetry is not None:
        record_admin_audit_telemetry(
            telemetry,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor.id,
            after_json=sanitized_after,
        )
