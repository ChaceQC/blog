from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from os import urandom
from typing import Protocol

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_der_public_key,
)

from app.core.config import Settings
from app.core.encryption import (
    EncryptedEnvelope,
    EncryptionError,
    EncryptionProfile,
    decrypt_json_payload_with_key_material,
    encrypt_json_payload_with_key_material,
)
from app.core.encryption_sid import (
    EncryptionSidError,
    validate_encryption_sid,
)
from app.core.login_capsule import (
    LoginCapsuleError,
    decrypt_login_capsule_payload,
    derive_login_capsule_keys,
    verify_login_capsule_tag,
)
from app.models.auth import EncryptionSession
from app.schemas.auth import LoginCapsuleRequest, LoginRequest
from app.schemas.encryption import (
    BrowserPublicKey,
    CreateEncryptionSessionResponse,
    EncryptedApiRequest,
    EncryptedApiResponse,
    EncryptionSessionScope,
    JsonObject,
    LoginChallengeResponse,
)
from app.services.encryption_salts import (
    EncryptionSaltError,
    InMemorySaltLeaseStore,
    SaltLeaseService,
    SaltPurpose,
)


class EncryptionSessionRepositoryProtocol(Protocol):
    async def create_session(
        self,
        *,
        session_id: str,
        scope: str,
        client_ip: str | None,
        key_material: bytes,
        expires_at: datetime,
        login_challenge_id: str | None = None,
        login_challenge_salt: bytes | None = None,
        login_challenge_expires_at: datetime | None = None,
    ) -> EncryptionSession: ...

    async def count_active_sessions_by_client(
        self,
        *,
        scope: str,
        client_ip: str,
        now: datetime,
    ) -> int: ...

    async def get_active_session(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> EncryptionSession | None: ...

    async def consume_login_challenge(
        self,
        *,
        session_id: str,
        challenge_id: str,
        now: datetime,
    ) -> bool: ...

    async def delete_expired_sessions(self, *, now: datetime) -> int: ...

    async def commit(self) -> None: ...


class EncryptionSessionError(Exception):
    pass


class ActiveEncryptionSessionLimitExceeded(EncryptionSessionError):
    pass


_LOGIN_CHALLENGE_EXPIRE_SECONDS = 180
_LOGIN_CAPSULE_CLOCK_SKEW_SECONDS = 30


class EncryptionSessionManager:
    def __init__(
        self,
        *,
        repository: EncryptionSessionRepositoryProtocol,
        settings: Settings,
        salt_leases: SaltLeaseService | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._salt_leases = salt_leases or SaltLeaseService(
            store=InMemorySaltLeaseStore(),
        )

    async def create_session(
        self,
        *,
        client_public_key: BrowserPublicKey,
        scope: EncryptionSessionScope = "admin",
        client_ip: str | None = None,
        active_session_limit: int | None = None,
    ) -> CreateEncryptionSessionResponse:
        now = _utc_now()
        await self._repository.delete_expired_sessions(now=now)
        if (
            active_session_limit is not None
            and client_ip is not None
            and active_session_limit >= 0
        ):
            active_count = await self._repository.count_active_sessions_by_client(
                scope=scope,
                client_ip=client_ip,
                now=now,
            )
            if active_count >= active_session_limit:
                raise ActiveEncryptionSessionLimitExceeded(
                    "too many active encryption sessions",
                )

        server_private_key = ec.generate_private_key(ec.SECP256R1())
        shared_key = server_private_key.exchange(
            ec.ECDH(),
            _load_browser_public_key(client_public_key),
        )
        session_id = _random_token()
        expires_at = now + timedelta(
            seconds=self._settings.encryption_session_expire_seconds,
        )
        login_challenge_id: str | None = None
        login_challenge_salt: bytes | None = None
        login_challenge_expires_at: datetime | None = None
        if scope == "admin":
            login_challenge_id = _random_token()
            login_challenge_salt = urandom(32)
            login_challenge_expires_at = min(
                expires_at,
                now + timedelta(seconds=_LOGIN_CHALLENGE_EXPIRE_SECONDS),
            )
        await self._repository.create_session(
            session_id=session_id,
            scope=scope,
            client_ip=client_ip,
            key_material=shared_key,
            expires_at=expires_at,
            login_challenge_id=login_challenge_id,
            login_challenge_salt=login_challenge_salt,
            login_challenge_expires_at=login_challenge_expires_at,
        )
        await self._repository.commit()

        return CreateEncryptionSessionResponse(
            session_id=session_id,
            scope=scope,
            server_public_key=_export_browser_public_key(
                server_private_key.public_key(),
            ),
            profiles=_profiles_for_scope(scope),
            expires_at=_as_utc_aware(expires_at),
            login_challenge=(
                LoginChallengeResponse(
                    challenge_id=login_challenge_id,
                    challenge_salt=_base64url_encode(login_challenge_salt),
                    expires_at=_as_utc_aware(login_challenge_expires_at),
                )
                if login_challenge_id
                and login_challenge_salt
                and login_challenge_expires_at
                else None
            ),
        )

    async def cleanup_expired_sessions(self, *, now: datetime | None = None) -> int:
        now = _as_utc_naive(now or datetime.now(UTC))
        deleted_count = await self._repository.delete_expired_sessions(now=now)
        if deleted_count > 0:
            await self._repository.commit()
        return deleted_count

    async def validate_session(
        self,
        *,
        session_id: str,
        esid: str | None,
        esid_salt_id: str | None,
        scope: EncryptionSessionScope,
        profile: EncryptionProfile,
    ) -> None:
        await self._get_session(
            session_id=session_id,
            esid=esid,
            esid_salt_id=esid_salt_id,
            expected_scope=scope,
            expected_profile=profile,
        )

    async def get_session_for_salt_stream(
        self,
        *,
        session_id: str,
        scope: EncryptionSessionScope,
    ) -> EncryptionSession:
        session = await self._repository.get_active_session(
            session_id=session_id,
            now=_utc_now(),
        )
        if session is None:
            raise EncryptionSessionError("encryption session is invalid or expired")
        if session.scope != scope:
            raise EncryptionSessionError("encryption session scope mismatch")
        return session

    async def encrypt_response(
        self,
        *,
        session_id: str,
        esid: str | None,
        esid_salt_id: str | None,
        scope: EncryptionSessionScope,
        profile: EncryptionProfile,
        payload: JsonObject,
        response_salt_id: str,
    ) -> EncryptedApiResponse:
        session = await self._get_session(
            session_id=session_id,
            esid=esid,
            esid_salt_id=esid_salt_id,
            expected_scope=scope,
            expected_profile=profile,
        )
        response_salt = self._consume_salt(
            lease_id=response_salt_id,
            session_id=session.session_id,
            scope=scope,
            purpose="response",
            profile=profile,
        )
        try:
            envelope = encrypt_json_payload_with_key_material(
                payload,
                key_material=session.key_material,
                profile=profile,
                salt=response_salt,
            )
        except EncryptionError as exc:
            raise EncryptionSessionError("failed to encrypt response") from exc

        return EncryptedApiResponse(
            session_id=session.session_id,
            profile=envelope.profile,
            salt_id=response_salt_id,
            nonce=envelope.nonce,
            ciphertext=envelope.ciphertext,
        )

    async def encrypt_response_for_validated_session(
        self,
        *,
        session_id: str,
        scope: EncryptionSessionScope,
        profile: EncryptionProfile,
        payload: JsonObject,
        response_salt_id: str,
    ) -> EncryptedApiResponse:
        session = await self._repository.get_active_session(
            session_id=session_id,
            now=_utc_now(),
        )
        if session is None or session.scope != scope:
            raise EncryptionSessionError("encryption session is invalid or expired")
        response_salt = self._consume_salt(
            lease_id=response_salt_id,
            session_id=session.session_id,
            scope=scope,
            purpose="response",
            profile=profile,
        )
        try:
            envelope = encrypt_json_payload_with_key_material(
                payload,
                key_material=session.key_material,
                profile=profile,
                salt=response_salt,
            )
        except EncryptionError as exc:
            raise EncryptionSessionError("failed to encrypt response") from exc
        return EncryptedApiResponse(
            session_id=session.session_id,
            profile=envelope.profile,
            salt_id=response_salt_id,
            nonce=envelope.nonce,
            ciphertext=envelope.ciphertext,
        )

    async def decrypt_request(
        self,
        *,
        session_id: str,
        esid: str | None,
        esid_salt_id: str | None,
        scope: EncryptionSessionScope,
        profile: EncryptionProfile,
        payload: EncryptedApiRequest,
    ) -> JsonObject:
        if payload.session_id != session_id:
            raise EncryptionSessionError("encrypted request session mismatch")
        session = await self._get_session(
            session_id=session_id,
            esid=esid,
            esid_salt_id=esid_salt_id,
            expected_scope=scope,
            expected_profile=profile,
        )
        request_salt = self._consume_salt(
            lease_id=payload.salt_id,
            session_id=session.session_id,
            scope=scope,
            purpose="request",
            profile=profile,
        )
        try:
            return decrypt_json_payload_with_key_material(
                EncryptedEnvelope(
                    profile=payload.profile,
                    nonce=payload.nonce,
                    ciphertext=payload.ciphertext,
                ),
                key_material=session.key_material,
                expected_profile=profile,
                salt=request_salt,
            )
        except EncryptionError as exc:
            raise EncryptionSessionError("failed to decrypt request") from exc

    async def decrypt_login_capsule(
        self,
        *,
        session_id: str,
        esid: str | None,
        esid_salt_id: str | None,
        payload: LoginCapsuleRequest,
        method: str,
        path: str,
    ) -> LoginRequest:
        if payload.session_id != session_id:
            raise EncryptionSessionError("login capsule session mismatch")

        now = datetime.now(UTC)
        if abs(float(payload.issued_at) - now.timestamp()) > (
            _LOGIN_CAPSULE_CLOCK_SKEW_SECONDS
        ):
            raise EncryptionSessionError("login capsule timestamp is invalid")
        db_now = _as_utc_naive(now)

        session = await self._get_session(
            session_id=session_id,
            esid=esid,
            esid_salt_id=esid_salt_id,
            expected_scope="admin",
            expected_profile=EncryptionProfile.SENSITIVE,
            now=db_now,
        )
        challenge_expires_at = (
            _as_utc_naive(session.login_challenge_expires_at)
            if session.login_challenge_expires_at is not None
            else None
        )
        if (
            session.login_challenge_id is None
            or session.login_challenge_salt is None
            or challenge_expires_at is None
            or session.login_challenge_used_at is not None
            or session.login_challenge_id != payload.challenge_id
            or challenge_expires_at <= db_now
        ):
            raise EncryptionSessionError("login challenge is invalid or expired")

        keys = derive_login_capsule_keys(
            key_material=session.key_material,
            challenge_salt=session.login_challenge_salt,
            transport_salt=self._consume_salt(
                lease_id=payload.salt_id,
                session_id=session.session_id,
                scope="admin",
                purpose="login_capsule",
                profile=EncryptionProfile.SENSITIVE,
            ),
            session_id=session.session_id,
            challenge_id=session.login_challenge_id,
        )
        try:
            verify_login_capsule_tag(
                payload,
                keys=keys,
                method=method,
                path=path,
            )
            login_payload = decrypt_login_capsule_payload(payload, keys=keys)
        except LoginCapsuleError as exc:
            raise EncryptionSessionError("invalid login capsule") from exc

        consumed = await self._repository.consume_login_challenge(
            session_id=session.session_id,
            challenge_id=session.login_challenge_id,
            now=db_now,
        )
        if not consumed:
            raise EncryptionSessionError("login challenge is already used")
        await self._repository.commit()
        return login_payload

    async def _get_session(
        self,
        *,
        session_id: str,
        esid: str | None,
        esid_salt_id: str | None,
        expected_scope: EncryptionSessionScope,
        expected_profile: EncryptionProfile,
        now: datetime | None = None,
    ) -> EncryptionSession:
        session = await self._repository.get_active_session(
            session_id=session_id,
            now=_as_utc_naive(now or datetime.now(UTC)),
        )
        if session is None:
            raise EncryptionSessionError("encryption session is invalid or expired")
        if session.scope != expected_scope:
            raise EncryptionSessionError("encryption session scope mismatch")
        if expected_profile not in _profiles_for_scope(expected_scope):
            raise EncryptionSessionError("encryption profile is not allowed")
        try:
            if esid_salt_id is None:
                raise EncryptionSidError("missing esid salt")
            esid_salt = self._consume_salt(
                lease_id=esid_salt_id,
                session_id=session.session_id,
                scope=expected_scope,
                purpose="esid",
                profile=None,
            )
            validate_encryption_sid(
                esid,
                session_id=session.session_id,
                scope=expected_scope,
                key_material=session.key_material,
                salt=esid_salt,
            )
        except (EncryptionSidError, EncryptionSaltError) as exc:
            raise EncryptionSessionError("invalid encryption session sid") from exc
        return session

    def _consume_salt(
        self,
        *,
        lease_id: str,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
    ) -> bytes:
        try:
            lease = self._salt_leases.consume(
                lease_id=lease_id,
                session_id=session_id,
                scope=scope,
                purpose=purpose,
                profile=profile,
            )
        except EncryptionSaltError as exc:
            raise EncryptionSessionError("invalid encryption salt") from exc
        return lease.salt


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


def _profiles_for_scope(scope: EncryptionSessionScope) -> list[EncryptionProfile]:
    if scope == "public":
        return [EncryptionProfile.CONTENT]
    return [EncryptionProfile.SENSITIVE, EncryptionProfile.CONTENT]


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")
