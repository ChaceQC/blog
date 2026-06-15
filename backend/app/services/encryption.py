from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from os import urandom

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_der_public_key,
)

from app.core.config import Settings
from app.core.encryption import (
    EncryptionError,
    EncryptionProfile,
    encrypt_json_payload_with_key_material,
)
from app.schemas.encryption import (
    BrowserPublicKey,
    CreateEncryptionSessionResponse,
    EncryptedApiResponse,
    JsonObject,
)


@dataclass(frozen=True)
class EncryptionSession:
    id: str
    key_material: bytes
    expires_at: datetime


class EncryptionSessionError(Exception):
    pass


class EncryptionSessionManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_session(
        self,
        *,
        client_public_key: BrowserPublicKey,
    ) -> CreateEncryptionSessionResponse:
        self._remove_expired_sessions()
        server_private_key = ec.generate_private_key(ec.SECP256R1())
        shared_key = server_private_key.exchange(
            ec.ECDH(),
            _load_browser_public_key(client_public_key),
        )
        session_id = _random_token()
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.encryption_session_expire_seconds,
        )
        _SESSIONS[session_id] = EncryptionSession(
            id=session_id,
            key_material=shared_key,
            expires_at=expires_at,
        )

        return CreateEncryptionSessionResponse(
            session_id=session_id,
            server_public_key=_export_browser_public_key(
                server_private_key.public_key(),
            ),
            profiles=[EncryptionProfile.SENSITIVE, EncryptionProfile.CONTENT],
            expires_at=expires_at,
        )

    def encrypt_response(
        self,
        *,
        session_id: str,
        profile: EncryptionProfile,
        payload: JsonObject,
    ) -> EncryptedApiResponse:
        session = self._get_session(session_id)
        try:
            envelope = encrypt_json_payload_with_key_material(
                payload,
                key_material=session.key_material,
                profile=profile,
            )
        except EncryptionError as exc:
            raise EncryptionSessionError("failed to encrypt response") from exc

        return EncryptedApiResponse(
            session_id=session.id,
            profile=envelope.profile,
            algorithm=envelope.algorithm,
            nonce=envelope.nonce,
            ciphertext=envelope.ciphertext,
        )

    def _get_session(self, session_id: str) -> EncryptionSession:
        session = _SESSIONS.get(session_id)
        if session is None or session.expires_at <= datetime.now(UTC):
            _SESSIONS.pop(session_id, None)
            raise EncryptionSessionError("encryption session is invalid or expired")
        return session

    def _remove_expired_sessions(self) -> None:
        now = datetime.now(UTC)
        expired_ids = [
            session_id
            for session_id, session in _SESSIONS.items()
            if session.expires_at <= now
        ]
        for session_id in expired_ids:
            _SESSIONS.pop(session_id, None)


_SESSIONS: dict[str, EncryptionSession] = {}


def _load_browser_public_key(client_key: BrowserPublicKey) -> ec.EllipticCurvePublicKey:
    x = _base64url_decode(client_key.x)
    y = _base64url_decode(client_key.y)
    if len(x) != 32 or len(y) != 32:
        raise EncryptionSessionError("invalid P-256 public key coordinates")

    public_bytes = b"\x04" + x + y
    try:
        public_key = load_der_public_key(
            ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(),
                public_bytes,
            ).public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo),
        )
    except (ValueError, InvalidKey) as exc:
        raise EncryptionSessionError("invalid client public key") from exc

    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise EncryptionSessionError("client public key must be EC")
    return public_key


def _export_browser_public_key(
    public_key: ec.EllipticCurvePublicKey,
) -> BrowserPublicKey:
    numbers = public_key.public_numbers()
    return BrowserPublicKey(
        kty="EC",
        crv="P-256",
        x=_base64url_encode(numbers.x.to_bytes(32, "big")),
        y=_base64url_encode(numbers.y.to_bytes(32, "big")),
    )


def _random_token() -> str:
    return _base64url_encode(urandom(32))


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")
