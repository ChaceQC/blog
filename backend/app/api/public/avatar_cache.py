from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import FileResponse

from app.api.dependencies import AvatarCacheServiceDependency
from app.services.avatar_cache_fetch import AvatarCacheFetchError
from app.services.avatar_cache_tokens import AvatarCacheTokenError

router = APIRouter(tags=["public-avatar-cache"])


@router.get("/avatar-cache/{token}")
async def get_public_avatar_cache(
    service: AvatarCacheServiceDependency,
    token: Annotated[str, Path(min_length=1, max_length=2000)],
) -> FileResponse:
    try:
        cached = await service.get_cached_avatar(token)
    except AvatarCacheTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="avatar not found",
        ) from exc
    except AvatarCacheFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="avatar source unavailable",
        ) from exc

    return FileResponse(
        cached.path,
        media_type=cached.media_type,
        headers={
            "Cache-Control": f"public, max-age={cached.max_age_seconds}",
            "X-Content-Type-Options": "nosniff",
        },
    )
