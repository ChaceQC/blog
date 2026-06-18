from dataclasses import dataclass

from fastapi import FastAPI

from app.core.config import Settings
from app.services.logs import (
    AccessLogDedupeBackend,
    create_access_log_dedupe_backend,
)
from app.services.rate_limit import RateLimitService, create_rate_limit_service


@dataclass(frozen=True)
class SharedBackendSignature:
    rate_limit_backend: str
    redis_url: str | None
    redis_key_prefix: str


def shared_backend_signature(settings: Settings) -> SharedBackendSignature:
    return SharedBackendSignature(
        rate_limit_backend=settings.rate_limit_backend,
        redis_url=settings.redis_url,
        redis_key_prefix=settings.redis_key_prefix,
    )


def configure_api_state(app: FastAPI, settings: Settings) -> None:
    signature = shared_backend_signature(settings)
    app.state.access_log_dedupe_backend = create_access_log_dedupe_backend(settings)
    app.state.access_log_dedupe_signature = signature
    app.state.rate_limit_service = create_rate_limit_service(settings)
    app.state.rate_limit_signature = signature


def get_app_access_log_dedupe_backend(
    app: FastAPI,
    settings: Settings,
) -> AccessLogDedupeBackend:
    signature = shared_backend_signature(settings)
    if getattr(app.state, "access_log_dedupe_signature", None) != signature:
        app.state.access_log_dedupe_backend = create_access_log_dedupe_backend(
            settings,
        )
        app.state.access_log_dedupe_signature = signature
    return app.state.access_log_dedupe_backend


def get_app_rate_limit_service(
    app: FastAPI,
    settings: Settings,
) -> RateLimitService:
    signature = shared_backend_signature(settings)
    if getattr(app.state, "rate_limit_signature", None) != signature:
        app.state.rate_limit_service = create_rate_limit_service(settings)
        app.state.rate_limit_signature = signature
    return app.state.rate_limit_service
