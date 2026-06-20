import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services import avatar_cache as avatar_cache_module
from app.services.avatar_cache import AvatarCacheService, public_avatar_cache_url
from app.services.avatar_cache_fetch import (
    AvatarCacheFetchError,
    FetchedAvatar,
    UnsafeAvatarSourceError,
    safe_http_target,
)
from app.services.avatar_cache_tokens import (
    AvatarCacheTokenError,
    create_avatar_cache_token,
    verify_avatar_cache_token,
)


def test_avatar_cache_token_rejects_tampering() -> None:
    token = create_avatar_cache_token(
        "https://example.com/avatar.png",
        secret_key="secret-key",
    )

    assert (
        verify_avatar_cache_token(token, secret_key="secret-key")
        == "https://example.com/avatar.png"
    )

    with pytest.raises(AvatarCacheTokenError):
        verify_avatar_cache_token(f"{token}x", secret_key="secret-key")

    with pytest.raises(AvatarCacheTokenError):
        verify_avatar_cache_token("%%%.'bad-signature'", secret_key="secret-key")


def test_public_avatar_cache_url_uses_request_origin_in_development(tmp_path) -> None:
    settings = _settings(tmp_path)

    avatar_url = public_avatar_cache_url(
        "https://example.com/avatar.png",
        settings=settings,
        request_base_url="http://127.0.0.1:18080/",
    )

    assert avatar_url is not None
    assert avatar_url.startswith("http://127.0.0.1:18080/api/public/avatar-cache/")


def test_avatar_cache_reuses_fresh_file(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    token = create_avatar_cache_token(
        "https://example.com/avatar.png",
        secret_key=settings.secret_key,
    )
    fetch_calls: list[str] = []

    def fake_fetch(url: str, **_: object) -> FetchedAvatar:
        fetch_calls.append(url)
        return FetchedAvatar(content=b"png-1", media_type="image/png")

    monkeypatch.setattr(avatar_cache_module, "fetch_avatar", fake_fetch)
    service = AvatarCacheService(settings=settings)

    first = asyncio.run(service.get_cached_avatar(token))
    second = asyncio.run(service.get_cached_avatar(token))

    assert first.path == second.path
    assert first.path.read_bytes() == b"png-1"
    assert fetch_calls == ["https://example.com/avatar.png"]


def test_avatar_cache_refreshes_expired_file(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    token = create_avatar_cache_token(
        "https://example.com/avatar.png",
        secret_key=settings.secret_key,
    )
    contents = [b"old", b"new"]

    def fake_fetch(url: str, **_: object) -> FetchedAvatar:
        assert url == "https://example.com/avatar.png"
        return FetchedAvatar(content=contents.pop(0), media_type="image/png")

    monkeypatch.setattr(avatar_cache_module, "fetch_avatar", fake_fetch)
    service = AvatarCacheService(settings=settings)

    first = asyncio.run(service.get_cached_avatar(token))
    metadata_path = first.path.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["fetched_at"] = (
        datetime.now(UTC) - timedelta(seconds=settings.avatar_cache_ttl_seconds + 5)
    ).isoformat()
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    second = asyncio.run(service.get_cached_avatar(token))

    assert second.path.read_bytes() == b"new"
    assert contents == []


def test_avatar_cache_retries_transient_fetch_failures(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    token = create_avatar_cache_token(
        "https://example.com/avatar.png",
        secret_key=settings.secret_key,
    )
    attempts = 0

    def fake_fetch(url: str, **_: object) -> FetchedAvatar:
        nonlocal attempts
        assert url == "https://example.com/avatar.png"
        attempts += 1
        if attempts < 3:
            raise AvatarCacheFetchError("temporary failure")
        return FetchedAvatar(content=b"retried", media_type="image/png")

    monkeypatch.setattr(avatar_cache_module, "fetch_avatar", fake_fetch)
    service = AvatarCacheService(settings=settings)

    cached = asyncio.run(service.get_cached_avatar(token))

    assert attempts == 3
    assert cached.path.read_bytes() == b"retried"


def test_avatar_cache_rejects_private_targets(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.avatar_cache_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (
                0,
                0,
                0,
                "",
                ("127.0.0.1", 80),
            ),
        ],
    )

    with pytest.raises(UnsafeAvatarSourceError):
        safe_http_target("https://example.test/avatar.png")


def _settings(tmp_path):
    return SimpleNamespace(
        environment="development",
        public_base_url="https://example.com",
        secret_key="dev-only-change-me",
        upload_root=tmp_path,
        avatar_cache_ttl_seconds=3600,
        avatar_cache_max_size_bytes=1024 * 1024,
        avatar_cache_request_timeout_seconds=5.0,
        avatar_cache_retry_attempts=2,
    )
