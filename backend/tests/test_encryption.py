import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta

import pytest

from app.core.encryption import (
    EncryptedEnvelope,
    EncryptionError,
    EncryptionProfile,
    decrypt_json_payload,
    encrypt_json_payload,
)
from app.core.encryption_sid import create_encryption_sid, validate_encryption_sid

SECRET_KEY = "test-secret-key-with-at-least-32-characters"
TEST_SALT = b"test-dynamic-salt-for-json-envelope"


def test_sensitive_encryption_round_trip() -> None:
    payload = {"username": "admin", "display_name": "管理员"}

    envelope = encrypt_json_payload(
        payload,
        secret_key=SECRET_KEY,
        profile=EncryptionProfile.SENSITIVE,
        salt=TEST_SALT,
    )

    assert envelope.profile == EncryptionProfile.SENSITIVE
    assert decrypt_json_payload(
        envelope,
        secret_key=SECRET_KEY,
        expected_profile=EncryptionProfile.SENSITIVE,
        salt=TEST_SALT,
    ) == payload


def test_content_profile_uses_separate_key_context() -> None:
    payload = {"title": "第一篇文章", "content_md": "$E=mc^2$"}
    envelope = encrypt_json_payload(
        payload,
        secret_key=SECRET_KEY,
        profile=EncryptionProfile.CONTENT,
        salt=TEST_SALT,
    )

    with pytest.raises(EncryptionError):
        decrypt_json_payload(
            envelope,
            secret_key=SECRET_KEY,
            expected_profile=EncryptionProfile.SENSITIVE,
            salt=TEST_SALT,
        )


def test_encryption_rejects_tampered_ciphertext() -> None:
    payload = {"id": 1, "title": "草稿"}
    envelope = encrypt_json_payload(
        payload,
        secret_key=SECRET_KEY,
        profile=EncryptionProfile.CONTENT,
        salt=TEST_SALT,
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
            salt=TEST_SALT,
        )


def test_encrypted_envelope_does_not_expose_plaintext() -> None:
    envelope = encrypt_json_payload(
        {"username": "admin"},
        secret_key=SECRET_KEY,
        profile=EncryptionProfile.SENSITIVE,
        salt=TEST_SALT,
    )

    assert "admin" not in envelope.ciphertext


def test_esid_bundle_selects_token_by_salt_id() -> None:
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    first_salt = b"1" * 32
    second_salt = b"2" * 32
    first_esid = create_encryption_sid(
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
        expires_at=expires_at,
        salt=first_salt,
    )
    second_esid = create_encryption_sid(
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
        expires_at=expires_at,
        salt=second_salt,
    )
    bundle = _base64url_encode(
        json.dumps(
            {
                "v": 1,
                "session_id": "session-1",
                "scope": "public",
                "items": [["salt-1", first_esid], ["salt-2", second_esid]],
            },
            separators=(",", ":"),
        ).encode(),
    )

    validate_encryption_sid(
        bundle,
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
        salt=second_salt,
        salt_id="salt-2",
    )


def test_esid_still_accepts_legacy_single_token() -> None:
    salt = b"1" * 32
    esid = create_encryption_sid(
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        salt=salt,
    )

    validate_encryption_sid(
        esid,
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
        salt=salt,
        salt_id="salt-1",
    )


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")
