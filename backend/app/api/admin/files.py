from fastapi import APIRouter

from app.api.admin.file_access import router as access_router
from app.api.admin.file_management import router as management_router

router = APIRouter()
router.include_router(management_router)
router.include_router(access_router)
