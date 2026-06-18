from fastapi import APIRouter

from app.api.public.encryption import router as public_encryption_router
from app.api.public.files import router as public_files_router
from app.api.public.links import router as public_links_router
from app.api.public.posts import router as public_posts_router
from app.api.public.settings import router as public_settings_router
from app.api.public.taxonomy import router as public_taxonomy_router

router = APIRouter(tags=["public"])
router.include_router(public_encryption_router)
router.include_router(public_files_router)
router.include_router(public_taxonomy_router)
router.include_router(public_posts_router)
router.include_router(public_settings_router)
router.include_router(public_links_router)


@router.get("/status")
async def public_status() -> dict[str, str]:
    return {"status": "public-api-ready"}
