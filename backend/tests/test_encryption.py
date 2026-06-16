from base64 import urlsafe_b64decode, urlsafe_b64encode

import pytest

from app.core.encryption import (
    EncryptedEnvelope,
    EncryptionError,
    EncryptionProfile,
    decrypt_json_payload,
    encrypt_json_payload,
)

SECRET_KEY = "test-secret-key-with-at-least-32-characters"


def test_sensitive_encryption_round_trip() -> None:
    payload = {"username": "admin", "display_name": "管理员"}

    envelope = encrypt_json_payload(
        payload,
        secret_key=SECRET_KEY,
        profile=EncryptionProfile.SENSITIVE,
    )

    assert envelope.profile == EncryptionProfile.SENSITIVE
    assert decrypt_json_payload(
        envelope,
        secret_key=SECRET_KEY,
        expected_profile=EncryptionProfile.SENSITIVE,
    ) == payload


def test_content_profile_uses_separate_key_context() -> None:
    payload = {"title": "第一篇文章", "content_md": "$E=mc^2$"}
    envelope = encrypt_json_payload(
        payload,
        secret_key=SECRET_KEY,
        profile=EncryptionProfile.CONTENT,
    )

    with pytest.raises(EncryptionError):
        decrypt_json_payload(
            envelope,
            secret_key=SECRET_KEY,
            expected_profile=EncryptionProfile.SENSITIVE,
        )


def test_encryption_rejects_tampered_ciphertext() -> None:
    payload = {"id": 1, "title": "草稿"}
    envelope = encrypt_json_payload(
        payload,
        secret_key=SECRET_KEY,
        profile=EncryptionProfile.CONTENT,
    )
    ciphertext_bytes = bytearray(_base64url_decode(envelope.ciphertext))
    ciphertext_bytes[-1] ^= 1
    tampered = EncryptedEnvelope(
        profile=envelope.profile,
        nonce=envelope.nonce,
        ciphertext=_base64url_encode(bytes(ciphertext_bytes)),
    )

    with pytest.raises(EncryptionError):
        decrypt_json_payload(
            tampered,
            secret_key=SECRET_KEY,
            expected_profile=EncryptionProfile.CONTENT,
        )


def test_encrypted_envelope_does_not_expose_plaintext() -> None:
    envelope = encrypt_json_payload(
        {"username": "admin"},
        secret_key=SECRET_KEY,
        profile=EncryptionProfile.SENSITIVE,
    )

    assert "admin" not in envelope.ciphertext


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")
