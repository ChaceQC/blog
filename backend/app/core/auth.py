from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ACCESS_TOKEN_TYPE = "access"
JWT_ALGORITHM = "HS256"

_password_hasher = PasswordHasher()


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def create_access_token(
    *,
    user_id: int,
    roles: list[str],
    permissions: list[str],
    secret_key: str,
    expires_delta: timedelta,
    now: datetime | None = None,
) -> str:
    issued_at = now or utc_now()
    expires_at = issued_at + expires_delta
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "roles": roles,
        "permissions": permissions,
        "iat": _timestamp(issued_at),
        "exp": _timestamp(expires_at),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    payload = jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("invalid token type")
    return payload


def generate_refresh_token() -> str:
    return token_urlsafe(48)


def hash_refresh_token(refresh_token: str) -> str:
    return sha256(refresh_token.encode("utf-8")).hexdigest()


def _timestamp(value: datetime) -> int:
    return int(value.replace(tzinfo=UTC).timestamp())
