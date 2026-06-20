import base64
import binascii
import hashlib
import hmac
import json

from app.core.url_validation import validate_http_url

AVATAR_CACHE_API_PREFIX = "/api/public/avatar-cache"
AVATAR_CACHE_TOKEN_VERSION = 1


class AvatarCacheTokenError(ValueError):
    pass


def create_avatar_cache_token(source_url: str, *, secret_key: str) -> str:
    safe_url = validate_http_url(source_url)
    payload = _base64url_encode(
        json.dumps(
            {"version": AVATAR_CACHE_TOKEN_VERSION, "url": safe_url},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
    )
    signature = _sign_payload(payload, secret_key=secret_key)
    return f"{payload}.{signature}"


def verify_avatar_cache_token(token: str, *, secret_key: str) -> str:
    try:
        payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise AvatarCacheTokenError("invalid avatar cache token") from exc
    if not payload or not signature:
        raise AvatarCacheTokenError("invalid avatar cache token")
    expected_signature = _sign_payload(payload, secret_key=secret_key)
    if not hmac.compare_digest(signature, expected_signature):
        raise AvatarCacheTokenError("invalid avatar cache token")
    try:
        data = json.loads(_base64url_decode(payload))
    except (binascii.Error, ValueError, json.JSONDecodeError) as exc:
        raise AvatarCacheTokenError("invalid avatar cache token") from exc
    if not isinstance(data, dict):
        raise AvatarCacheTokenError("invalid avatar cache token")
    if data.get("version") != AVATAR_CACHE_TOKEN_VERSION:
        raise AvatarCacheTokenError("invalid avatar cache token")
    url = data.get("url")
    if not isinstance(url, str):
        raise AvatarCacheTokenError("invalid avatar cache token")
    try:
        return validate_http_url(url)
    except ValueError as exc:
        raise AvatarCacheTokenError("invalid avatar cache token") from exc


def _sign_payload(payload: str, *, secret_key: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(digest)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> str:
    padded = f"{value}{'=' * (-len(value) % 4)}"
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
