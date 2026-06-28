from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from app.api.state import (
    get_app_access_log_dedupe_backend,
    get_app_rate_limit_service,
    get_app_salt_lease_service,
    get_app_telemetry_service,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.storage import LocalStorageProvider
from app.providers.telemetry import TelemetryService
from app.repositories.comments import CommentRepository
from app.repositories.content import ContentRepository
from app.repositories.encryption import EncryptionSessionRepository
from app.repositories.files import FileRepository
from app.repositories.links import LinkRepository
from app.repositories.logs import LogRepository
from app.repositories.settings import SettingRepository
from app.services.avatar_cache import AvatarCacheService
from app.services.comment_identity import CommentIdentityService
from app.services.comments import CommentService
from app.services.content import ContentService
from app.services.encryption import EncryptionSessionManager
from app.services.encryption_salts import SaltLeaseService
from app.services.files import FileService
from app.services.links import LinkService
from app.services.logs import (
    AccessLogDedupeBackend,
    LogService,
)
from app.services.post_interactions import PostInteractionService
from app.services.rate_limit import RateLimitService
from app.services.settings import SettingService

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_telemetry_service(
    connection: HTTPConnection,
    settings: SettingsDependency,
) -> TelemetryService:
    return get_app_telemetry_service(connection.app, settings)


TelemetryServiceDependency = Annotated[
    TelemetryService,
    Depends(get_telemetry_service),
]


def get_content_service(session: SessionDependency) -> ContentService:
    return ContentService(repository=ContentRepository(session))


ContentServiceDependency = Annotated[ContentService, Depends(get_content_service)]


def get_comment_service(
    session: SessionDependency,
    settings: SettingsDependency,
    telemetry: TelemetryServiceDependency,
) -> CommentService:
    return CommentService(
        repository=CommentRepository(session),
        identity=CommentIdentityService(secret_key=settings.secret_key),
        pending_limit=settings.comment_pending_limit,
        duplicate_window_seconds=settings.comment_duplicate_window_seconds,
        risk_limit_max_attempts=settings.comment_risk_rate_limit_max_attempts,
        risk_limit_window_seconds=settings.comment_risk_rate_limit_window_seconds,
        author_limit_max_attempts=settings.comment_author_rate_limit_max_attempts,
        author_limit_window_seconds=settings.comment_author_rate_limit_window_seconds,
        auto_publish=settings.comment_auto_publish,
        telemetry=telemetry,
    )


CommentServiceDependency = Annotated[CommentService, Depends(get_comment_service)]


def get_file_service(
    session: SessionDependency,
    settings: SettingsDependency,
    telemetry: TelemetryServiceDependency,
) -> FileService:
    return FileService(
        repository=FileRepository(session),
        storage=LocalStorageProvider(settings.upload_root),
        telemetry=telemetry,
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
    connection: HTTPConnection,
    session: SessionDependency,
    settings: SettingsDependency,
    telemetry: TelemetryServiceDependency,
) -> EncryptionSessionManager:
    return EncryptionSessionManager(
        repository=EncryptionSessionRepository(session),
        settings=settings,
        salt_leases=get_app_salt_lease_service(connection.app, settings),
        telemetry=telemetry,
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
    telemetry: TelemetryServiceDependency,
) -> LogService:
    return LogService(
        repository=LogRepository(session),
        dedupe_backend=dedupe_backend,
        telemetry=telemetry,
    )


LogServiceDependency = Annotated[LogService, Depends(get_log_service)]


def get_post_interaction_service(
    session: SessionDependency,
    dedupe_backend: AccessLogDedupeDependency,
    settings: SettingsDependency,
    telemetry: TelemetryServiceDependency,
) -> PostInteractionService:
    return PostInteractionService(
        repository=ContentRepository(session),
        dedupe_backend=dedupe_backend,
        secret_key=settings.secret_key,
        view_dedupe_seconds=settings.post_view_dedupe_seconds,
        like_risk_window_seconds=settings.post_like_risk_window_seconds,
        telemetry=telemetry,
    )


PostInteractionServiceDependency = Annotated[
    PostInteractionService,
    Depends(get_post_interaction_service),
]


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


def get_salt_lease_service(
    connection: HTTPConnection,
    settings: SettingsDependency,
) -> SaltLeaseService:
    return get_app_salt_lease_service(connection.app, settings)


SaltLeaseServiceDependency = Annotated[
    SaltLeaseService,
    Depends(get_salt_lease_service),
]
