from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ValidationError

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import (
    AdminCsrfDependency,
    require_admin_permission,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    SettingServiceDependency,
)
from app.api.encrypted_response import (
    decrypt_encrypted_request,
    encrypted_response,
)
from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.settings import (
    AdminSettingItem,
    AdminSettingListResponse,
    SettingUpdateRequest,
)
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager

router = APIRouter(tags=["admin-settings"])
SettingWriterDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("setting:write")),
]


@router.get("/settings", response_model=EncryptedApiResponse)
async def list_settings(
    _: SettingWriterDependency,
    request: Request,
    service: SettingServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    settings = await service.list_settings()
    return await _settings_response(
        AdminSettingListResponse(
            items=[AdminSettingItem.model_validate(setting) for setting in settings],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/settings/{key_name}", response_model=EncryptedApiResponse)
async def update_setting(
    key_name: Annotated[
        str,
        Path(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
    ],
    payload: EncryptedApiRequest,
    current_user: SettingWriterDependency,
    request: Request,
    _: AdminCsrfDependency,
    service: SettingServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )
    setting_payload = _validate_decrypted_payload(
        SettingUpdateRequest,
        decrypted_payload,
    )
    try:
        setting = await service.update_setting(
            key_name=key_name,
            value_json=setting_payload.value_json,
            group_name=setting_payload.group_name,
            is_public=setting_payload.is_public,
            updated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid setting value",
        ) from exc
    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="setting.update",
        entity_type="setting",
        entity_id=setting.id,
        after_json={
            "changed_fields": sorted(setting_payload.model_fields_set),
            "is_public": setting.is_public,
        },
    )
    return await _settings_response(
        AdminSettingItem.model_validate(service.admin_setting_response(setting)),
        request=request,
        encryption_manager=encryption_manager,
    )


async def _settings_response(
    payload: AdminSettingItem | AdminSettingListResponse,
    *,
    request: Request,
    encryption_manager: EncryptionSessionManager,
) -> EncryptedApiResponse:
    return await encrypted_response(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )


def _validate_decrypted_payload[T: BaseModel](
    model: type[T],
    payload: dict[str, object],
) -> T:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid encrypted request payload",
        ) from exc
