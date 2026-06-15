from base64 import urlsafe_b64decode, urlsafe_b64encode

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_auth_service
from app.core.encryption import (
    EncryptedEnvelope,
    EncryptionProfile,
    decrypt_json_payload_with_key_material,
)
from app.main import app
from app.services.auth import AuthenticatedUser, TokenPair


class FakeAuthService:
    async def login(
        self,
        *,
        username: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        return TokenPair(
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            expires_in=900,
            user=AuthenticatedUser(
                id=1,
                username=username,
                display_name="管理员",
                roles=["editor"],
                permissions=["post:read"],
            ),
        )


def test_login_response_can_use_sensitive_encryption_session() -> None:
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(app)

    session_response = client.post(
        "/api/admin/encryption/sessions",
        json={
            "client_public_key": _export_public_key(
                client_private_key.public_key(),
            ),
        },
    )

    assert session_response.status_code == 200
    session_payload = session_response.json()
    shared_key = client_private_key.exchange(
        ec.ECDH(),
        _load_public_key(session_payload["server_public_key"]),
    )

    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    try:
        login_response = client.post(
            "/api/admin/auth/login",
            headers={"X-Encryption-Session": session_payload["session_id"]},
            json={"username": "admin", "password": "correct-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert login_response.status_code == 200
    envelope_payload = login_response.json()
    assert envelope_payload["encrypted"] is True
    assert envelope_payload["profile"] == EncryptionProfile.SENSITIVE
    decrypted = decrypt_json_payload_with_key_material(
        EncryptedEnvelope(
            profile=EncryptionProfile(envelope_payload["profile"]),
            algorithm=envelope_payload["algorithm"],
            nonce=envelope_payload["nonce"],
            ciphertext=envelope_payload["ciphertext"],
        ),
        key_material=shared_key,
        expected_profile=EncryptionProfile.SENSITIVE,
    )

    assert decrypted["user"]["username"] == "admin"
    assert decrypted["user"]["display_name"] == "管理员"
    assert decrypted["csrf_token"]


def _export_public_key(public_key: ec.EllipticCurvePublicKey) -> dict[str, str]:
    numbers = public_key.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _base64url_encode(numbers.x.to_bytes(32, "big")),
        "y": _base64url_encode(numbers.y.to_bytes(32, "big")),
    }


def _load_public_key(payload: dict[str, str]) -> ec.EllipticCurvePublicKey:
    return ec.EllipticCurvePublicNumbers(
        x=int.from_bytes(_base64url_decode(payload["x"]), "big"),
        y=int.from_bytes(_base64url_decode(payload["y"]), "big"),
        curve=ec.SECP256R1(),
    ).public_key()


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")
