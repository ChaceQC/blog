from fastapi import APIRouter

from app.api.admin.content_pages import router as pages_router
from app.api.admin.content_posts import router as posts_router

router = APIRouter()
router.include_router(posts_router)
router.include_router(pages_router)
