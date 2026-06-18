from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.storage import LocalStorageProvider
from app.repositories.content import ContentRepository
from app.repositories.encryption import EncryptionSessionRepository
from app.repositories.files import FileRepository
from app.repositories.links import LinkRepository
from app.repositories.logs import LogRepository
from app.repositories.settings import SettingRepository
from app.services.content import ContentService
from app.services.encryption import EncryptionSessionManager
from app.services.files import FileService
from app.services.links import LinkService
from app.services.logs import (
    AccessLogDedupeBackend,
    LogService,
    create_access_log_dedupe_backend,
)
from app.services.rate_limit import RateLimitService, create_rate_limit_service
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


_access_log_dedupe_backend: AccessLogDedupeBackend | None = None
_access_log_dedupe_signature: tuple[str, str | None, str] | None = None


def get_access_log_dedupe_backend(
    settings: SettingsDependency,
) -> AccessLogDedupeBackend:
    global _access_log_dedupe_backend, _access_log_dedupe_signature
    signature = (
        settings.rate_limit_backend,
        settings.redis_url,
        settings.redis_key_prefix,
    )
    if (
        _access_log_dedupe_backend is None
        or _access_log_dedupe_signature != signature
    ):
        _access_log_dedupe_backend = create_access_log_dedupe_backend(settings)
        _access_log_dedupe_signature = signature
    return _access_log_dedupe_backend


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


_rate_limit_service: RateLimitService | None = None
_rate_limit_signature: tuple[str, str | None, str] | None = None


def get_rate_limit_service(settings: SettingsDependency) -> RateLimitService:
    global _rate_limit_service, _rate_limit_signature
    signature = (
        settings.rate_limit_backend,
        settings.redis_url,
        settings.redis_key_prefix,
    )
    if _rate_limit_service is None or _rate_limit_signature != signature:
        _rate_limit_service = create_rate_limit_service(settings)
        _rate_limit_signature = signature
    return _rate_limit_service


RateLimitServiceDependency = Annotated[
    RateLimitService,
    Depends(get_rate_limit_service),
]
