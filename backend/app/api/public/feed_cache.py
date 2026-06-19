from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from fastapi import Request, status
from fastapi.responses import Response

FEED_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"
FEED_CACHE_SECONDS = 300


@dataclass(frozen=True)
class CachedFeed:
    content: str
    media_type: str
    etag: str
    count: int
    expires_at: float


def cacheable_response(*, request: Request, content: str, media_type: str) -> Response:
    etag = f'"{sha256(content.encode("utf-8")).hexdigest()}"'
    headers = {
        "Cache-Control": FEED_CACHE_CONTROL,
        "ETag": etag,
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=content, media_type=media_type, headers=headers)


def cached_or_new_feed_response(
    *,
    request: Request,
    key: str,
    content: str,
    media_type: str,
    count: int,
) -> Response:
    entry = CachedFeed(
        content=content,
        media_type=media_type,
        etag=f'"{sha256(content.encode("utf-8")).hexdigest()}"',
        count=count,
        expires_at=monotonic() + FEED_CACHE_SECONDS,
    )
    _feed_cache(request)[key] = entry
    return _feed_entry_response(request=request, entry=entry)


def cached_feed_response(
    request: Request,
    *,
    key: str,
) -> tuple[Response, int] | None:
    entry = _feed_cache(request).get(key)
    if entry is None:
        return None
    if entry.expires_at <= monotonic():
        _feed_cache(request).pop(key, None)
        return None
    return _feed_entry_response(request=request, entry=entry), entry.count


def _feed_entry_response(*, request: Request, entry: CachedFeed) -> Response:
    headers = {
        "Cache-Control": FEED_CACHE_CONTROL,
        "ETag": entry.etag,
    }
    if request.headers.get("if-none-match") == entry.etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=entry.content, media_type=entry.media_type, headers=headers)


def _feed_cache(request: Request) -> dict[str, CachedFeed]:
    cache = getattr(request.app.state, "feed_response_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        request.app.state.feed_response_cache = cache
    return cache
