from fastapi import HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from app.api.dependencies import (
    ContentServiceDependency,
    EncryptionSessionManagerDependency,
    LinkServiceDependency,
    LogServiceDependency,
)
from app.api.encrypted_response import validate_encryption_session
from app.core.encryption import EncryptionProfile
from app.core.request import client_ip

PublicContentServiceDependency = ContentServiceDependency
PublicLinkServiceDependency = LinkServiceDependency


async def validate_public_content_session(
    request: Request,
    encryption_manager: EncryptionSessionManagerDependency,
) -> None:
    await validate_encryption_session(
        request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )


async def record_public_access(
    logs: LogServiceDependency,
    *,
    request: Request,
    access_type: str,
    status_code: int,
    entity_type: str | None,
    entity_id: int | None = None,
    detail_json: dict[str, object] | None = None,
) -> None:
    await logs.record_access_log(
        access_type=access_type,
        method=request.method,
        path=str(request.url.path),
        status_code=status_code,
        entity_type=entity_type,
        entity_id=entity_id,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        detail_json=None,
    )


def validate_decrypted_payload[TBaseModel: BaseModel](
    model: type[TBaseModel],
    payload: dict[str, object],
) -> TBaseModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid encrypted request payload",
        ) from exc
