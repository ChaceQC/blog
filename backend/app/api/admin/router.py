from fastapi import APIRouter

from app.api.admin.auth import router as auth_router

router = APIRouter(tags=["admin"])
router.include_router(auth_router)
