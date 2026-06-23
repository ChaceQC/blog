import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from enum import StrEnum
from os import urandom
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.crypto_context import ContextOpcode, binary_context


class EncryptionProfile(StrEnum):
    SENSITIVE = "sensitive-v1"
    CONTENT = "content-v1"


@dataclass(frozen=True)
class EncryptedEnvelope:
    profile: EncryptionProfile
    nonce: str
    ciphertext: str


class EncryptionError(Exception):
    pass


def encrypt_json_payload(
    payload: dict[str, Any],
    *,
    secret_key: str,
    context_seed: bytes,
    profile: EncryptionProfile,
    salt: bytes,
    scope: str,
    session_id: str,
    lease_id: str,
) -> EncryptedEnvelope:
    return encrypt_json_payload_with_key_material(
        payload,
        key_material=secret_key.encode("utf-8"),
        context_seed=context_seed,
        profile=profile,
        salt=salt,
        scope=scope,
        session_id=session_id,
        lease_id=lease_id,
    )


def encrypt_json_payload_with_key_material(
    payload: dict[str, Any],
    *,
    key_material: bytes,
    context_seed: bytes,
    profile: EncryptionProfile,
    salt: bytes,
    scope: str,
    session_id: str,
    lease_id: str,
) -> EncryptedEnvelope:
    nonce = urandom(12)
    plaintext = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    ciphertext = AESGCM(
        _derive_profile_key(
            key_material,
            context_seed=context_seed,
            profile=profile,
            salt=salt,
            scope=scope,
            session_id=session_id,
            lease_id=lease_id,
        ),
    ).encrypt(
        nonce,
        plaintext,
        _associated_data(
            context_seed=context_seed,
            profile=profile,
            scope=scope,
            session_id=session_id,
            lease_id=lease_id,
        ),
    )
    return EncryptedEnvelope(
        profile=profile,
        nonce=_base64url_encode(nonce),
        ciphertext=_base64url_encode(ciphertext),
    )


def decrypt_json_payload(
    envelope: EncryptedEnvelope,
    *,
    secret_key: str,
    context_seed: bytes,
    expected_profile: EncryptionProfile,
    salt: bytes,
    scope: str,
    session_id: str,
    lease_id: str,
) -> dict[str, Any]:
    return decrypt_json_payload_with_key_material(
        envelope,
        key_material=secret_key.encode("utf-8"),
        context_seed=context_seed,
        expected_profile=expected_profile,
        salt=salt,
        scope=scope,
        session_id=session_id,
        lease_id=lease_id,
    )


def decrypt_json_payload_with_key_material(
    envelope: EncryptedEnvelope,
    *,
    key_material: bytes,
    context_seed: bytes,
    expected_profile: EncryptionProfile,
    salt: bytes,
    scope: str,
    session_id: str,
    lease_id: str,
) -> dict[str, Any]:
    if envelope.profile != expected_profile:
        raise EncryptionError("unexpected encryption profile")

    try:
        plaintext = AESGCM(
            _derive_profile_key(
                key_material,
                context_seed=context_seed,
                profile=expected_profile,
                salt=salt,
                scope=scope,
                session_id=session_id,
                lease_id=lease_id,
            ),
        ).decrypt(
            _base64url_decode(envelope.nonce),
            _base64url_decode(envelope.ciphertext),
            _associated_data(
                context_seed=context_seed,
                profile=expected_profile,
                scope=scope,
                session_id=session_id,
                lease_id=lease_id,
            ),
        )
    except (InvalidTag, ValueError) as exc:
        raise EncryptionError("invalid encrypted payload") from exc

    decoded = json.loads(plaintext.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise EncryptionError("encrypted payload must be an object")
    return decoded


def _derive_profile_key(
    key_material: bytes,
    *,
    context_seed: bytes,
    profile: EncryptionProfile,
    salt: bytes,
    scope: str,
    session_id: str,
    lease_id: str,
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=binary_context(
            seed=context_seed,
            opcode=ContextOpcode.JSON_KEY,
            scope=scope,
            profile=profile,
            session_id=session_id,
            lease_id=lease_id,
        ),
    ).derive(key_material)


def _associated_data(
    *,
    context_seed: bytes,
    profile: EncryptionProfile,
    scope: str,
    session_id: str,
    lease_id: str,
) -> bytes:
    return binary_context(
        seed=context_seed,
        opcode=ContextOpcode.JSON_AAD,
        scope=scope,
        profile=profile,
        session_id=session_id,
        lease_id=lease_id,
    )


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")
