import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import Settings
from app.services.avatar_cache_fetch import (
    ALLOWED_AVATAR_CONTENT_TYPES,
    AvatarCacheFetchError,
    FetchedAvatar,
    fetch_avatar,
)
from app.services.avatar_cache_tokens import (
    AVATAR_CACHE_API_PREFIX,
    create_avatar_cache_token,
    verify_avatar_cache_token,
)


@dataclass(frozen=True)
class AvatarCacheResult:
    path: Path
    media_type: str
    max_age_seconds: int


class AvatarCacheService:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings
        self.cache_root = settings.upload_root / "avatar-cache"

    async def get_cached_avatar(self, token: str) -> AvatarCacheResult:
        source_url = verify_avatar_cache_token(
            token,
            secret_key=self.settings.secret_key,
        )
        return await asyncio.to_thread(self._get_cached_avatar, source_url)

    def _get_cached_avatar(self, source_url: str) -> AvatarCacheResult:
        self.cache_root.mkdir(parents=True, exist_ok=True)
        data_path, metadata_path = _cache_paths(self.cache_root, source_url)
        cached = _read_cache_metadata(metadata_path)
        ttl_seconds = self.settings.avatar_cache_ttl_seconds

        if _is_fresh_cached_avatar(
            data_path=data_path,
            metadata=cached,
            source_url=source_url,
            ttl_seconds=ttl_seconds,
        ):
            return _cached_result(
                data_path=data_path,
                metadata=cached,
                max_age_seconds=ttl_seconds,
            )

        try:
            fetched = fetch_avatar(
                source_url,
                timeout_seconds=self.settings.avatar_cache_request_timeout_seconds,
                max_size_bytes=self.settings.avatar_cache_max_size_bytes,
            )
        except AvatarCacheFetchError:
            if _is_usable_cached_avatar(
                data_path=data_path,
                metadata=cached,
                source_url=source_url,
            ):
                return _cached_result(
                    data_path=data_path,
                    metadata=cached,
                    max_age_seconds=min(ttl_seconds, 300),
                )
            raise

        _write_cached_avatar(
            data_path=data_path,
            metadata_path=metadata_path,
            source_url=source_url,
            fetched=fetched,
        )
        return AvatarCacheResult(
            path=data_path,
            media_type=fetched.media_type,
            max_age_seconds=ttl_seconds,
        )


def public_avatar_cache_url(
    source_url: str | None,
    *,
    settings: Settings,
    request_base_url: str,
) -> str | None:
    if source_url is None:
        return None
    parsed = urlparse(source_url)
    if parsed.scheme.lower() not in {"http", "https"}:
        return source_url
    token = create_avatar_cache_token(source_url, secret_key=settings.secret_key)
    return (
        f"{_public_origin(settings=settings, request_base_url=request_base_url)}"
        f"{AVATAR_CACHE_API_PREFIX}/{token}"
    )


def _public_origin(*, settings: Settings, request_base_url: str) -> str:
    if settings.environment == "production":
        return settings.public_base_url.rstrip("/")
    return request_base_url.rstrip("/")


def _cache_paths(cache_root: Path, source_url: str) -> tuple[Path, Path]:
    cache_key = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    return cache_root / f"{cache_key}.bin", cache_root / f"{cache_key}.json"


def _read_cache_metadata(path: Path) -> dict[str, str] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    url = payload.get("url")
    media_type = payload.get("media_type")
    fetched_at = payload.get("fetched_at")
    if not all(isinstance(item, str) for item in (url, media_type, fetched_at)):
        return None
    if media_type not in ALLOWED_AVATAR_CONTENT_TYPES:
        return None
    return {
        "url": url,
        "media_type": media_type,
        "fetched_at": fetched_at,
    }


def _is_fresh_cached_avatar(
    *,
    data_path: Path,
    metadata: dict[str, str] | None,
    source_url: str,
    ttl_seconds: int,
) -> bool:
    if not _is_usable_cached_avatar(
        data_path=data_path,
        metadata=metadata,
        source_url=source_url,
    ):
        return False
    try:
        fetched_at = datetime.fromisoformat(metadata["fetched_at"])
    except (TypeError, ValueError):
        return False
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - fetched_at < timedelta(seconds=ttl_seconds)


def _is_usable_cached_avatar(
    *,
    data_path: Path,
    metadata: dict[str, str] | None,
    source_url: str,
) -> bool:
    return bool(
        metadata is not None
        and metadata.get("url") == source_url
        and data_path.is_file()
        and data_path.stat().st_size > 0
    )


def _cached_result(
    *,
    data_path: Path,
    metadata: dict[str, str],
    max_age_seconds: int,
) -> AvatarCacheResult:
    return AvatarCacheResult(
        path=data_path,
        media_type=metadata["media_type"],
        max_age_seconds=max_age_seconds,
    )


def _write_cached_avatar(
    *,
    data_path: Path,
    metadata_path: Path,
    source_url: str,
    fetched: FetchedAvatar,
) -> None:
    temporary_data = data_path.with_suffix(".bin.tmp")
    temporary_metadata = metadata_path.with_suffix(".json.tmp")
    temporary_data.write_bytes(fetched.content)
    temporary_metadata.write_text(
        json.dumps(
            {
                "url": source_url,
                "media_type": fetched.media_type,
                "fetched_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    temporary_data.replace(data_path)
    temporary_metadata.replace(metadata_path)
