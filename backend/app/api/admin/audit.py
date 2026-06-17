from typing import Any

from fastapi import Request

from app.services.auth import AuthenticatedUser
from app.services.logs import LogService


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
    await logs.record_audit_log(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor.id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        before_json=before_json,
        after_json=after_json,
    )
