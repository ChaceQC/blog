from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.database import check_database
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/healthz", response_model=HealthResponse)
async def healthz(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.version,
        environment=settings.environment,
        checks={"api": "ok"},
    )


@router.get("/readyz", response_model=HealthResponse)
async def readyz(settings: SettingsDependency) -> HealthResponse:
    checks = {"api": "ok"}

    if settings.readiness_check_database:
        try:
            await check_database()
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database is not ready",
            ) from exc
        checks["database"] = "ok"

    return HealthResponse(
        status="ready",
        service=settings.app_name,
        version=settings.version,
        environment=settings.environment,
        checks=checks,
    )
