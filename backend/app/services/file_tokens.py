import hashlib
import hmac
import json
import re
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from dataclasses import dataclass
from datetime import datetime

from app.core.auth import utc_now


@dataclass(frozen=True)
class ArticleRenderToken:
    token: str
    expires: int


def sign_file_token(
    *,
    file_id: int,
    sha256: str,
    expires_at: datetime,
    secret_key: str,
) -> str:
    payload = {
        "exp": int(expires_at.timestamp()),
        "file_id": file_id,
        "sha256": sha256,
    }
    payload_part = _signed_payload_part(payload)
    signature = _signature(payload_part=payload_part, secret_key=secret_key)
    return f"{payload_part}.{_base64url_encode(signature)}"


def verify_file_token(
    token: str,
    *,
    file_id: int,
    sha256: str,
    secret_key: str,
) -> bool:
    payload = _verified_payload(token, secret_key=secret_key)
    if payload is None:
        return False
    return (
        payload.get("file_id") == file_id
        and payload.get("sha256") == sha256
        and isinstance(payload.get("exp"), int)
        and payload["exp"] > int(utc_now().timestamp())
    )


def create_article_render_token(
    *,
    post_slug: str,
    file_id: int,
    expires_seconds: int,
    secret_key: str,
) -> ArticleRenderToken:
    expires = _stable_token_expires(expires_seconds)
    payload = {
        "exp": expires,
        "file_id": file_id,
        "scope": "post_image_render",
        "slug": post_slug,
    }
    return _create_token(payload=payload, secret_key=secret_key, expires=expires)


def create_admin_file_preview_token(
    *,
    file_id: int,
    expires_seconds: int,
    secret_key: str,
) -> ArticleRenderToken:
    expires = _stable_token_expires(expires_seconds)
    payload = {
        "exp": expires,
        "file_id": file_id,
        "scope": "admin_file_preview",
    }
    return _create_token(payload=payload, secret_key=secret_key, expires=expires)


def verify_article_render_token(
    *,
    token: str,
    expires: int,
    post_slug: str,
    file_id: int,
    secret_key: str,
) -> bool:
    payload = _verified_payload(token, secret_key=secret_key)
    if payload is None:
        return False
    return (
        payload.get("scope") == "post_image_render"
        and payload.get("slug") == post_slug
        and payload.get("file_id") == file_id
        and payload.get("exp") == expires
        and expires > int(utc_now().timestamp())
    )


def verify_admin_file_preview_token(
    *,
    token: str,
    expires: int,
    file_id: int,
    secret_key: str,
) -> bool:
    payload = _verified_payload(token, secret_key=secret_key)
    if payload is None:
        return False
    return (
        payload.get("scope") == "admin_file_preview"
        and payload.get("file_id") == file_id
        and payload.get("exp") == expires
        and expires > int(utc_now().timestamp())
    )


def sign_article_render_urls(
    *,
    content_html: str,
    post_slug: str,
    expires_seconds: int,
    secret_key: str,
) -> str:
    pattern = _post_image_src_pattern(post_slug)

    def replace(match: re.Match[str]) -> str:
        file_id = int(match.group("file_id"))
        access = create_article_render_token(
            post_slug=post_slug,
            file_id=file_id,
            expires_seconds=expires_seconds,
            secret_key=secret_key,
        )
        path = match.group("path")
        signed_path = f"{path}?expires={access.expires}&token={access.token}"
        return f"{match.group('prefix')}{signed_path}{match.group('suffix')}"

    return pattern.sub(replace, content_html)


def sign_admin_preview_image_urls(
    *,
    content_html: str,
    post_slug: str,
    expires_seconds: int,
    secret_key: str,
) -> str:
    pattern = _post_image_src_pattern(post_slug)

    def replace(match: re.Match[str]) -> str:
        file_id = int(match.group("file_id"))
        access = create_admin_file_preview_token(
            file_id=file_id,
            expires_seconds=expires_seconds,
            secret_key=secret_key,
        )
        preview_path = (
            f"/api/admin/files/{file_id}/preview?"
            f"expires={access.expires}&token={access.token}"
        )
        return f"{match.group('prefix')}{preview_path}{match.group('suffix')}"

    return pattern.sub(replace, content_html)


def _create_token(
    *,
    payload: dict[str, object],
    secret_key: str,
    expires: int,
) -> ArticleRenderToken:
    payload_part = _signed_payload_part(payload)
    signature = _signature(payload_part=payload_part, secret_key=secret_key)
    return ArticleRenderToken(
        token=f"{payload_part}.{_base64url_encode(signature)}",
        expires=expires,
    )


def _stable_token_expires(expires_seconds: int) -> int:
    now_ts = int(utc_now().timestamp())
    window_seconds = max(1, expires_seconds // 2)
    window_start = (now_ts // window_seconds) * window_seconds
    return window_start + expires_seconds


def _signed_payload_part(payload: dict[str, object]) -> str:
    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _base64url_encode(payload_bytes)


def _signature(*, payload_part: str, secret_key: str) -> bytes:
    return hmac.new(
        secret_key.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()


def _verified_payload(token: str, *, secret_key: str) -> dict[str, object] | None:
    try:
        payload_part, signature_part = token.split(".", maxsplit=1)
        expected_signature = _signature(
            payload_part=payload_part,
            secret_key=secret_key,
        )
        if not hmac.compare_digest(
            signature_part,
            _base64url_encode(expected_signature),
        ):
            return None
        payload = json.loads(_base64url_decode(payload_part))
    except (BinasciiError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _post_image_src_pattern(post_slug: str) -> re.Pattern[str]:
    return re.compile(
        r'(?P<prefix>\bsrc=["\'])'
        r'(?P<path>/?api/public/posts/'
        + re.escape(post_slug)
        + r'/files/(?P<file_id>\d+)/render)'
        r'(?P<suffix>["\'])',
    )


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}").decode("utf-8")
