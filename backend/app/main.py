from fastapi import FastAPI

from app.api.admin.router import router as admin_router
from app.api.public.feeds import router as feeds_router
from app.api.public.health import router as health_router
from app.api.public.router import router as public_router
from app.api.state import configure_api_state
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

    app.include_router(health_router)
    app.include_router(feeds_router)
    app.include_router(public_router, prefix="/api/public")
    app.include_router(admin_router, prefix="/api/admin")

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": settings.version,
            "environment": settings.environment,
        }

    return app


app = create_app()
