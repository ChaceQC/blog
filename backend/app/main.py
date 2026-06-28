from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.api.admin.router import router as admin_router
from app.api.public.feeds import router as feeds_router
from app.api.public.health import router as health_router
from app.api.public.router import router as public_router
from app.api.state import configure_api_state, get_app_telemetry_service
from app.api.telemetry import record_http_request, telemetry_context
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.security import configure_security_middleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    configure_api_state(app, settings)
    configure_security_middleware(app, settings)
    _configure_telemetry(app, settings)

    app.include_router(health_router)
    app.include_router(feeds_router)
    app.include_router(public_router, prefix="/api/public")
    app.include_router(admin_router, prefix="/api/admin")

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": settings.version,
        }

    return app


def _configure_telemetry(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def telemetry_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        telemetry = get_app_telemetry_service(request.app, settings)
        telemetry_context(request)
        request.state.telemetry_started_at = datetime.now(UTC)
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (perf_counter() - started_at) * 1000
            record_http_request(
                telemetry,
                request,
                status_code=500,
                duration_ms=duration_ms,
                error_type=exc.__class__.__name__,
            )
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        record_http_request(
            telemetry,
            request,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    def _start_telemetry() -> None:
        get_app_telemetry_service(app, settings).start()

    def _stop_telemetry() -> None:
        get_app_telemetry_service(app, settings).stop()

    app.router.on_startup.append(_start_telemetry)
    app.router.on_shutdown.append(_stop_telemetry)


app = create_app()
