from fastapi import APIRouter, Request, status

from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    SettingsDependency,
    SettingServiceDependency,
)
from app.api.encrypted_response import encrypted_response
from app.api.public.common import (
    record_public_access,
    validate_public_content_session,
)
from app.core.encryption import EncryptionProfile
from app.schemas.settings import PublicSiteProfileResponse
from app.services.avatar_cache import public_avatar_cache_url

router = APIRouter(tags=["public-settings"])


@router.get("/settings/site-profile")
async def get_public_site_profile(
    request: Request,
    service: SettingServiceDependency,
    settings: SettingsDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
):
    await validate_public_content_session(request, encryption_manager)
    profile = await service.get_public_site_profile()
    profile = profile.with_avatar_url(
        public_avatar_cache_url(
            profile.avatar_url,
            settings=settings,
            request_base_url=str(request.base_url),
        ),
    )
    response = await encrypted_response(
        PublicSiteProfileResponse.model_validate(profile),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_site_profile",
        status_code=status.HTTP_200_OK,
        entity_type="setting",
    )
    return response
