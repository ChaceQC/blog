from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.state import (
    get_app_access_log_dedupe_backend,
    get_app_rate_limit_service,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.storage import LocalStorageProvider
from app.repositories.content import ContentRepository
from app.repositories.encryption import EncryptionSessionRepository
from app.repositories.files import FileRepository
from app.repositories.links import LinkRepository
from app.repositories.logs import LogRepository
from app.repositories.settings import SettingRepository
from app.services.avatar_cache import AvatarCacheService
from app.services.content import ContentService
from app.services.encryption import EncryptionSessionManager
from app.services.files import FileService
from app.services.links import LinkService
from app.services.logs import (
    AccessLogDedupeBackend,
    LogService,
)
from app.services.rate_limit import RateLimitService
from app.services.settings import SettingService

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_content_service(session: SessionDependency) -> ContentService:
    return ContentService(repository=ContentRepository(session))


ContentServiceDependency = Annotated[ContentService, Depends(get_content_service)]


def get_file_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> FileService:
    return FileService(
        repository=FileRepository(session),
        storage=LocalStorageProvider(settings.upload_root),
    )


FileServiceDependency = Annotated[FileService, Depends(get_file_service)]


def get_link_service(session: SessionDependency) -> LinkService:
    return LinkService(repository=LinkRepository(session))


LinkServiceDependency = Annotated[LinkService, Depends(get_link_service)]


def get_avatar_cache_service(settings: SettingsDependency) -> AvatarCacheService:
    return AvatarCacheService(settings=settings)


AvatarCacheServiceDependency = Annotated[
    AvatarCacheService,
    Depends(get_avatar_cache_service),
]


def get_encryption_session_manager(
    session: SessionDependency,
    settings: SettingsDependency,
) -> EncryptionSessionManager:
    return EncryptionSessionManager(
        repository=EncryptionSessionRepository(session),
        settings=settings,
    )


EncryptionSessionManagerDependency = Annotated[
    EncryptionSessionManager,
    Depends(get_encryption_session_manager),
]


def get_access_log_dedupe_backend(
    request: Request,
    settings: SettingsDependency,
) -> AccessLogDedupeBackend:
    return get_app_access_log_dedupe_backend(request.app, settings)


AccessLogDedupeDependency = Annotated[
    AccessLogDedupeBackend,
    Depends(get_access_log_dedupe_backend),
]


def get_log_service(
    session: SessionDependency,
    dedupe_backend: AccessLogDedupeDependency,
) -> LogService:
    return LogService(
        repository=LogRepository(session),
        dedupe_backend=dedupe_backend,
    )


LogServiceDependency = Annotated[LogService, Depends(get_log_service)]


def get_setting_service(session: SessionDependency) -> SettingService:
    return SettingService(repository=SettingRepository(session))


SettingServiceDependency = Annotated[SettingService, Depends(get_setting_service)]


def get_rate_limit_service(
    request: Request,
    settings: SettingsDependency,
) -> RateLimitService:
    return get_app_rate_limit_service(request.app, settings)


RateLimitServiceDependency = Annotated[
    RateLimitService,
    Depends(get_rate_limit_service),
]
