import json
from base64 import urlsafe_b64decode
from dataclasses import dataclass
from hmac import compare_digest, digest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.schemas.auth import LoginCapsuleRequest, LoginRequest

LOGIN_CAPSULE_SCHEME = "login-capsule-v2"

_BUCKETS = (256, 512, 1024, 2048)
_NONCE_LENGTH = 16


@dataclass(frozen=True)
class LoginCapsuleKeys:
    encryption_key: bytes
    mac_key: bytes


class LoginCapsuleError(Exception):
    pass


def derive_login_capsule_keys(
    *,
    key_material: bytes,
    challenge_salt: bytes,
    transport_salt: bytes,
    session_id: str,
    challenge_id: str,
) -> LoginCapsuleKeys:
    return LoginCapsuleKeys(
        encryption_key=_derive_key(
            key_material=key_material,
            challenge_salt=challenge_salt,
            transport_salt=transport_salt,
            purpose="enc",
            session_id=session_id,
            challenge_id=challenge_id,
        ),
        mac_key=_derive_key(
            key_material=key_material,
            challenge_salt=challenge_salt,
            transport_salt=transport_salt,
            purpose="mac",
            session_id=session_id,
            challenge_id=challenge_id,
        ),
    )


def verify_login_capsule_tag(
    capsule: LoginCapsuleRequest,
    *,
    keys: LoginCapsuleKeys,
    method: str,
    path: str,
) -> None:
    try:
        tag = _base64url_decode(capsule.tag)
    except ValueError as exc:
        raise LoginCapsuleError("invalid login capsule tag") from exc
    expected = digest(
        keys.mac_key,
        _signing_input(capsule, method=method, path=path),
        "sha256",
    )
    if not compare_digest(expected, tag):
        raise LoginCapsuleError("invalid login capsule tag")


def decrypt_login_capsule_payload(
    capsule: LoginCapsuleRequest,
    *,
    keys: LoginCapsuleKeys,
) -> LoginRequest:
    try:
        nonce = _base64url_decode(capsule.nonce)
        ciphertext = _base64url_decode(capsule.ciphertext)
    except ValueError as exc:
        raise LoginCapsuleError("invalid login capsule encoding") from exc
    if len(nonce) != _NONCE_LENGTH or len(ciphertext) not in _BUCKETS:
        raise LoginCapsuleError("invalid login capsule size")

    decryptor = Cipher(
        algorithms.AES(keys.encryption_key),
        modes.CTR(nonce),
    ).decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    if len(plaintext) < 2:
        raise LoginCapsuleError("invalid login capsule padding")

    payload_length = int.from_bytes(plaintext[:2], "big")
    if payload_length <= 0 or payload_length > len(plaintext) - 2:
        raise LoginCapsuleError("invalid login capsule padding")
    try:
        decoded = json.loads(plaintext[2 : 2 + payload_length].decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise LoginCapsuleError("invalid login capsule json") from exc
    try:
        return LoginRequest.model_validate(decoded)
    except ValueError as exc:
        raise LoginCapsuleError("invalid login capsule payload") from exc


def _derive_key(
    *,
    key_material: bytes,
    challenge_salt: bytes,
    transport_salt: bytes,
    purpose: str,
    session_id: str,
    challenge_id: str,
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=transport_salt + challenge_salt,
        info=f"blog-login-v2:{purpose}:{session_id}:{challenge_id}".encode(),
    ).derive(key_material)


def _signing_input(
    capsule: LoginCapsuleRequest,
    *,
    method: str,
    path: str,
) -> bytes:
    return "\n".join(
        (
            capsule.scheme,
            capsule.session_id,
            capsule.challenge_id,
            capsule.salt_id,
            method.upper(),
            path,
            str(capsule.issued_at),
            capsule.nonce,
            capsule.ciphertext,
        ),
    ).encode("utf-8")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")
