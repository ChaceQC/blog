from enum import IntEnum
from hashlib import sha256
from typing import Any

CONTEXT_SEED_BYTES = 32
CONTEXT_VERSION = 3


class ContextOpcode(IntEnum):
    JSON_KEY = 1
    JSON_AAD = 2
    WSS_WRAP_KEY = 3
    WSS_WRAP_AAD = 4
    ESID_KEY = 5
    ESID_STREAM = 6
    LOGIN_ENC = 7
    LOGIN_MAC = 8


def scope_id(scope: str) -> int:
    if scope == "admin":
        return 1
    if scope == "public":
        return 2
    raise ValueError("invalid encryption scope")


def profile_id(profile: Any | None) -> int:
    if profile is None:
        return 0
    value = str(getattr(profile, "value", profile))
    if value == "sensitive-v1":
        return 1
    if value == "content-v1":
        return 2
    raise ValueError("invalid encryption profile")


def purpose_id(purpose: Any | None) -> int:
    if purpose is None:
        return 0
    value = str(getattr(purpose, "value", purpose))
    if value == "esid":
        return 1
    if value == "login_capsule":
        return 2
    if value == "request":
        return 3
    if value == "response":
        return 4
    raise ValueError("invalid salt purpose")


def binary_context(
    *,
    seed: bytes,
    opcode: ContextOpcode,
    scope: str,
    profile: Any | None = None,
    purpose: Any | None = None,
    session_id: str,
    lease_id: str | None = None,
    challenge_id: str | None = None,
    label_id: int = 0,
    round_index: int = 0,
    counter: int = 0,
) -> bytes:
    if len(seed) != CONTEXT_SEED_BYTES:
        raise ValueError("invalid context seed")
    return b"".join(
        (
            seed,
            bytes(
                (
                    CONTEXT_VERSION,
                    int(opcode),
                    scope_id(scope),
                    profile_id(profile),
                    purpose_id(purpose),
                    label_id & 0xFF,
                    round_index & 0xFF,
                ),
            ),
            counter.to_bytes(4, "big"),
            _digest(session_id),
            _digest(lease_id),
            _digest(challenge_id),
        ),
    )


def _digest(value: str | None) -> bytes:
    if value is None:
        return b"\x00" * 32
    return sha256(value.encode("utf-8")).digest()
