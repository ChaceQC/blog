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
from app.core.encryption_sid import (
    EncryptionSidError,
    create_encryption_sid,
    validate_encryption_sid,
)

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


def test_esid_stable_token_validates_for_session_scope() -> None:
    esid = create_encryption_sid(
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    validate_encryption_sid(
        esid,
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
    )

    with pytest.raises(EncryptionSidError):
        validate_encryption_sid(
            esid,
            session_id="session-2",
            scope="public",
            key_material=b"k" * 32,
        )

    with pytest.raises(EncryptionSidError):
        validate_encryption_sid(
            esid,
            session_id="session-1",
            scope="admin",
            key_material=b"k" * 32,
        )


def test_esid_uses_session_specific_key_material() -> None:
    esid = create_encryption_sid(
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    with pytest.raises(EncryptionSidError):
        validate_encryption_sid(
            esid,
            session_id="session-1",
            scope="public",
            key_material=b"x" * 32,
        )


def test_esid_rejects_expired_token() -> None:
    esid = create_encryption_sid(
        session_id="session-1",
        scope="public",
        key_material=b"k" * 32,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    with pytest.raises(EncryptionSidError):
        validate_encryption_sid(
            esid,
            session_id="session-1",
            scope="public",
            key_material=b"k" * 32,
        )


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")
