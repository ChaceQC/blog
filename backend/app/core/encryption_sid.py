import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime
from hmac import compare_digest, digest
from os import urandom
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.schemas.encryption import EncryptionSessionScope

ESID_COOKIE_NAME = "esid"
ESID_MAX_LENGTH = 1024

_VERSION = 1
_NONCE_LENGTH = 16
_TAG_LENGTH = 16
_ROUNDS = 8
_PURPOSE = "encryption-session-binding"
_SALT = b"blog-cms-esid-v1"


class EncryptionSidError(Exception):
    pass


def create_encryption_sid(
    *,
    session_id: str,
    scope: EncryptionSessionScope,
    key_material: bytes,
    expires_at: datetime,
    issued_at: datetime | None = None,
    nonce: bytes | None = None,
) -> str:
    now = issued_at or datetime.now(UTC)
    payload = {
        "exp": _timestamp(expires_at),
        "iat": _timestamp(now),
        "purpose": _PURPOSE,
        "scope": scope,
        "session_id": session_id,
    }
    key = _derive_sid_key(key_material, scope)
    token_nonce = nonce or urandom(_NONCE_LENGTH)
    if len(token_nonce) != _NONCE_LENGTH:
        raise EncryptionSidError("invalid esid nonce")

    plaintext = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    transformed = _transform_forward(plaintext, key=key, nonce=token_nonce)
    body = bytes([_VERSION]) + token_nonce + transformed
    tag = _mac(key, body)[:_TAG_LENGTH]
    return _base64url_encode(body + tag)


def validate_encryption_sid(
    esid: str | None,
    *,
    session_id: str,
    scope: EncryptionSessionScope,
    key_material: bytes,
    now: datetime | None = None,
) -> None:
    if esid is None:
        raise EncryptionSidError("missing esid")
    if not esid or len(esid) > ESID_MAX_LENGTH:
        raise EncryptionSidError("invalid esid")

    try:
        raw = _base64url_decode(esid)
    except (ValueError, TypeError) as exc:
        raise EncryptionSidError("invalid esid") from exc

    min_length = 1 + _NONCE_LENGTH + 1 + _TAG_LENGTH
    if len(raw) < min_length or raw[0] != _VERSION:
        raise EncryptionSidError("invalid esid")

    body = raw[:-_TAG_LENGTH]
    tag = raw[-_TAG_LENGTH:]
    nonce = raw[1 : 1 + _NONCE_LENGTH]
    transformed = raw[1 + _NONCE_LENGTH : -_TAG_LENGTH]
    key = _derive_sid_key(key_material, scope)
    if not compare_digest(_mac(key, body)[:_TAG_LENGTH], tag):
        raise EncryptionSidError("invalid esid")

    try:
        plaintext = _transform_reverse(transformed, key=key, nonce=nonce)
        payload = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise EncryptionSidError("invalid esid") from exc

    _validate_payload(
        payload,
        session_id=session_id,
        scope=scope,
        now=now or datetime.now(UTC),
    )


def _validate_payload(
    payload: object,
    *,
    session_id: str,
    scope: EncryptionSessionScope,
    now: datetime,
) -> None:
    if not isinstance(payload, dict):
        raise EncryptionSidError("invalid esid payload")
    if payload.get("purpose") != _PURPOSE:
        raise EncryptionSidError("invalid esid payload")
    if payload.get("session_id") != session_id:
        raise EncryptionSidError("esid session mismatch")
    if payload.get("scope") != scope:
        raise EncryptionSidError("esid scope mismatch")

    iat = _number(payload.get("iat"))
    exp = _number(payload.get("exp"))
    current = now.timestamp()
    if iat is None or exp is None or iat > current + 60 or exp <= current:
        raise EncryptionSidError("expired esid")


def _transform_forward(data: bytes, *, key: bytes, nonce: bytes) -> bytes:
    value = bytearray(data)
    for round_index in range(_ROUNDS):
        permutation = _permutation(
            len(value),
            key=key,
            nonce=nonce,
            round_index=round_index,
        )
        value = bytearray(value[index] for index in permutation)
        mask = _hmac_stream(
            key,
            nonce=nonce,
            label=b"mask",
            round_index=round_index,
            length=len(value),
        )
        shifts = _hmac_stream(
            key,
            nonce=nonce,
            label=b"rotate",
            round_index=round_index,
            length=len(value),
        )
        for index, item in enumerate(value):
            value[index] = _rotate_left(item ^ mask[index], shifts[index] & 7)
    return bytes(value)


def _transform_reverse(data: bytes, *, key: bytes, nonce: bytes) -> bytes:
    value = bytearray(data)
    for round_index in range(_ROUNDS - 1, -1, -1):
        mask = _hmac_stream(
            key,
            nonce=nonce,
            label=b"mask",
            round_index=round_index,
            length=len(value),
        )
        shifts = _hmac_stream(
            key,
            nonce=nonce,
            label=b"rotate",
            round_index=round_index,
            length=len(value),
        )
        for index, item in enumerate(value):
            value[index] = _rotate_right(item, shifts[index] & 7) ^ mask[index]

        permutation = _permutation(
            len(value),
            key=key,
            nonce=nonce,
            round_index=round_index,
        )
        restored = bytearray(len(value))
        for index, original_index in enumerate(permutation):
            restored[original_index] = value[index]
        value = restored
    return bytes(value)


def _permutation(
    length: int,
    *,
    key: bytes,
    nonce: bytes,
    round_index: int,
) -> list[int]:
    indexes = list(range(length))
    if length <= 1:
        return indexes

    stream = _hmac_stream(
        key,
        nonce=nonce,
        label=b"perm",
        round_index=round_index,
        length=(length - 1) * 4,
    )
    offset = 0
    for index in range(length - 1, 0, -1):
        value = int.from_bytes(stream[offset : offset + 4], "big")
        offset += 4
        swap_index = value % (index + 1)
        indexes[index], indexes[swap_index] = indexes[swap_index], indexes[index]
    return indexes


def _hmac_stream(
    key: bytes,
    *,
    nonce: bytes,
    label: bytes,
    round_index: int,
    length: int,
) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < length:
        message = (
            b"blog-cms-esid:"
            + label
            + b":"
            + bytes([round_index])
            + nonce
            + counter.to_bytes(4, "big")
        )
        output.extend(_mac(key, message))
        counter += 1
    return bytes(output[:length])


def _derive_sid_key(
    key_material: bytes,
    scope: EncryptionSessionScope,
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        info=f"blog-cms:esid:{scope}".encode(),
    ).derive(key_material)


def _mac(key: bytes, message: bytes) -> bytes:
    return digest(key, message, "sha256")


def _timestamp(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _rotate_left(value: int, shift: int) -> int:
    if shift == 0:
        return value
    return ((value << shift) | (value >> (8 - shift))) & 0xFF


def _rotate_right(value: int, shift: int) -> int:
    if shift == 0:
        return value
    return ((value >> shift) | (value << (8 - shift))) & 0xFF


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")
