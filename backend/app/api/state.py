from dataclasses import dataclass

from fastapi import FastAPI

from app.core.config import Settings
from app.providers.telemetry import TelemetryService, create_telemetry_service
from app.services.encryption_salts import (
    SaltLeaseService,
    create_salt_lease_service,
)
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


@dataclass(frozen=True)
class TelemetrySignature:
    telemetry_enabled: bool
    telemetry_endpoint: str | None
    telemetry_api_key: str | None
    environment: str
    version: str


def shared_backend_signature(settings: Settings) -> SharedBackendSignature:
    return SharedBackendSignature(
        rate_limit_backend=settings.rate_limit_backend,
        redis_url=settings.redis_url,
        redis_key_prefix=settings.redis_key_prefix,
    )


def telemetry_signature(settings: Settings) -> TelemetrySignature:
    return TelemetrySignature(
        telemetry_enabled=settings.telemetry_enabled,
        telemetry_endpoint=settings.telemetry_endpoint,
        telemetry_api_key=settings.telemetry_api_key,
        environment=settings.environment,
        version=settings.version,
    )


def configure_api_state(app: FastAPI, settings: Settings) -> None:
    signature = shared_backend_signature(settings)
    app.state.access_log_dedupe_backend = create_access_log_dedupe_backend(settings)
    app.state.access_log_dedupe_signature = signature
    app.state.rate_limit_service = create_rate_limit_service(settings)
    app.state.rate_limit_signature = signature
    app.state.salt_lease_service = create_salt_lease_service(settings)
    app.state.salt_lease_signature = signature
    app.state.telemetry_service = create_telemetry_service(settings)
    app.state.telemetry_signature = telemetry_signature(settings)


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


def get_app_salt_lease_service(
    app: FastAPI,
    settings: Settings,
) -> SaltLeaseService:
    signature = shared_backend_signature(settings)
    if getattr(app.state, "salt_lease_signature", None) != signature:
        app.state.salt_lease_service = create_salt_lease_service(settings)
        app.state.salt_lease_signature = signature
    return app.state.salt_lease_service


def get_app_telemetry_service(
    app: FastAPI,
    settings: Settings,
) -> TelemetryService:
    signature = telemetry_signature(settings)
    if getattr(app.state, "telemetry_signature", None) != signature:
        current = getattr(app.state, "telemetry_service", None)
        if isinstance(current, TelemetryService):
            current.stop()
        app.state.telemetry_service = create_telemetry_service(settings)
        app.state.telemetry_signature = signature
    return app.state.telemetry_service
