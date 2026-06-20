from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import FileResponse, Response

from app.api.dependencies import AvatarCacheServiceDependency
from app.services.avatar_cache_fetch import AvatarCacheFetchError
from app.services.avatar_cache_tokens import AvatarCacheTokenError

router = APIRouter(tags=["public-avatar-cache"])

DEFAULT_AVATAR_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" '
    'role="img" aria-label="默认头像">'
    "<defs>"
    '<linearGradient id="bg" x1="18" x2="78" y1="14" y2="84" '
    'gradientUnits="userSpaceOnUse">'
    '<stop stop-color="#fefefb"/>'
    '<stop offset="1" stop-color="#f4efea"/>'
    "</linearGradient>"
    "</defs>"
    '<rect width="96" height="96" rx="48" fill="url(#bg)"/>'
    '<circle cx="48" cy="38" r="15" fill="#c56473" opacity=".72"/>'
    '<path fill="#262321" fill-opacity=".16" '
    'd="M22 77c3.8-16.4 13.5-24.8 26-24.8S70.2 60.6 74 77'
    'c-6.8 6.2-15.9 10-26 10s-19.2-3.8-26-10Z"/>'
    '<path fill="none" stroke="#c56473" stroke-linecap="round" '
    'stroke-width="3" '
    'd="M29 25c5.1-6.2 11.5-9.3 19-9.3s13.9 3.1 19 9.3" '
    'opacity=".38"/>'
    "</svg>"
)


@router.get("/avatar-cache/{token}", response_model=None)
async def get_public_avatar_cache(
    service: AvatarCacheServiceDependency,
    token: Annotated[str, Path(min_length=1, max_length=2000)],
) -> FileResponse | Response:
    try:
        cached = await service.get_cached_avatar(token)
    except AvatarCacheTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="avatar not found",
        ) from exc
    except AvatarCacheFetchError:
        return _default_avatar_response()

    return FileResponse(
        cached.path,
        media_type=cached.media_type,
        headers={
            "Cache-Control": f"public, max-age={cached.max_age_seconds}",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _default_avatar_response() -> Response:
    return Response(
        content=DEFAULT_AVATAR_SVG,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=300",
            "X-Avatar-Fallback": "1",
            "X-Content-Type-Options": "nosniff",
        },
    )
