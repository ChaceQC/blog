from fastapi import APIRouter

from app.api.admin.auth import router as auth_router
from app.api.admin.encryption import router as encryption_router
from app.api.admin.logs import router as logs_router

router = APIRouter(tags=["admin"])
router.include_router(auth_router)
router.include_router(encryption_router)
router.include_router(logs_router)
