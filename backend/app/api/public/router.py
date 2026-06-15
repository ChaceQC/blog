from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.content import ContentRepository
from app.schemas.content import (
    PublicPostDetail,
    PublicPostItem,
    PublicPostListResponse,
)
from app.services.content import ContentNotFoundError, ContentService

router = APIRouter(tags=["public"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_public_content_service(session: SessionDependency) -> ContentService:
    return ContentService(repository=ContentRepository(session))


PublicContentServiceDependency = Annotated[
    ContentService,
    Depends(get_public_content_service),
]


@router.get("/status")
async def public_status() -> dict[str, str]:
    return {"status": "public-api-ready"}


@router.get("/posts", response_model=PublicPostListResponse)
async def list_public_posts(
    service: PublicContentServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PublicPostListResponse:
    posts = await service.list_public_posts(limit=limit, offset=offset)
    return PublicPostListResponse(
        items=[PublicPostItem.model_validate(post) for post in posts],
    )


@router.get("/posts/{slug}", response_model=PublicPostDetail)
async def get_public_post(
    slug: str,
    service: PublicContentServiceDependency,
) -> PublicPostDetail:
    try:
        post = await service.get_public_post_by_slug(slug)
    except ContentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="post not found",
        ) from exc

    return PublicPostDetail.model_validate(post)
