from fastapi import APIRouter

from app.api.admin.friend_links import router as friend_links_router
from app.api.admin.link_groups import router as link_groups_router
from app.api.admin.site_nav import router as site_nav_router

router = APIRouter(tags=["admin-links"])
router.include_router(link_groups_router)
router.include_router(friend_links_router)
router.include_router(site_nav_router)
