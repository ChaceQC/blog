import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from os import urandom
from threading import Lock
from typing import Literal, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.crypto_context import ContextOpcode, binary_context
from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptionSessionScope

SaltPurpose = Literal["esid", "login_capsule", "request", "response"]

_LEASE_ID_BYTES = 24
_SALT_BYTES = 32
_WRAP_SALT_BYTES = 32
_WRAP_NONCE_BYTES = 12
_LEASE_TTL_SECONDS = 45


class EncryptionSaltError(Exception):
    pass


class EncryptionSaltUnavailable(EncryptionSaltError):
    pass


class EncryptionSaltReplay(EncryptionSaltError):
    pass


@dataclass(frozen=True)
class SaltLease:
    lease_id: str
    session_id: str
    scope: EncryptionSessionScope
    purpose: SaltPurpose
    profile: EncryptionProfile | None
    salt: bytes
    expires_at: datetime


@dataclass(frozen=True)
class WrappedSaltFrame:
    session_id: str
    wrap_salt: str
    nonce: str
    ciphertext: str


class SaltLeaseStore(Protocol):
    def issue(
        self,
        *,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
        now: datetime | None = None,
    ) -> SaltLease: ...

    def consume(
        self,
        *,
        lease_id: str,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
        now: datetime | None = None,
    ) -> SaltLease: ...


class InMemorySaltLeaseStore:
    def __init__(self, *, max_leases: int = 20_000) -> None:
        self._leases: dict[str, SaltLease] = {}
        self._lock = Lock()
        self._max_leases = max(1, max_leases)

    def issue(
        self,
        *,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
        now: datetime | None = None,
    ) -> SaltLease:
        current_time = now or datetime.now(UTC)
        lease = _new_lease(
            session_id=session_id,
            scope=scope,
            purpose=purpose,
            profile=profile,
            now=current_time,
        )
        with self._lock:
            self._cleanup_expired(current_time)
            if len(self._leases) >= self._max_leases:
                self._evict_oldest()
            self._leases[lease.lease_id] = lease
        return lease

    def consume(
        self,
        *,
        lease_id: str,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
        now: datetime | None = None,
    ) -> SaltLease:
        current_time = now or datetime.now(UTC)
        with self._lock:
            lease = self._leases.pop(lease_id, None)
            if lease is None:
                raise EncryptionSaltReplay("salt lease is missing or already used")
            if _is_expired(lease, current_time) or not _matches(
                lease,
                session_id=session_id,
                scope=scope,
                purpose=purpose,
                profile=profile,
            ):
                raise EncryptionSaltReplay("salt lease is invalid")
        return lease

    def _cleanup_expired(self, now: datetime) -> None:
        expired_ids = [
            lease_id
            for lease_id, lease in self._leases.items()
            if _is_expired(lease, now)
        ]
        for lease_id in expired_ids:
            self._leases.pop(lease_id, None)

    def _evict_oldest(self) -> None:
        oldest_id = min(
            self._leases,
            key=lambda item: self._leases[item].expires_at,
        )
        self._leases.pop(oldest_id, None)


class RedisSaltLeaseStore:
    _CONSUME_SCRIPT = """
local key = KEYS[1]
local value = redis.call("GET", key)
if not value then
  return nil
end
redis.call("DEL", key)
return value
"""

    def __init__(self, *, redis_client: Redis, key_prefix: str) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix.rstrip(":")

    def issue(
        self,
        *,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
        now: datetime | None = None,
    ) -> SaltLease:
        current_time = now or datetime.now(UTC)
        lease = _new_lease(
            session_id=session_id,
            scope=scope,
            purpose=purpose,
            profile=profile,
            now=current_time,
        )
        try:
            self._redis.set(
                self._redis_key(lease.lease_id),
                _serialize_lease(lease),
                ex=_LEASE_TTL_SECONDS,
            )
        except RedisError as exc:
            raise EncryptionSaltUnavailable("redis salt lease issue failed") from exc
        return lease

    def consume(
        self,
        *,
        lease_id: str,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
        now: datetime | None = None,
    ) -> SaltLease:
        current_time = now or datetime.now(UTC)
        try:
            raw = self._redis.eval(
                self._CONSUME_SCRIPT,
                1,
                self._redis_key(lease_id),
            )
        except RedisError as exc:
            raise EncryptionSaltUnavailable("redis salt lease consume failed") from exc
        if raw is None:
            raise EncryptionSaltReplay("salt lease is missing or already used")

        lease = _deserialize_lease(str(raw))
        if _is_expired(lease, current_time) or not _matches(
            lease,
            session_id=session_id,
            scope=scope,
            purpose=purpose,
            profile=profile,
        ):
            raise EncryptionSaltReplay("salt lease is invalid")
        return lease

    def _redis_key(self, lease_id: str) -> str:
        return f"{self._key_prefix}:salt-lease:{lease_id}"


class SaltLeaseService:
    def __init__(self, *, store: SaltLeaseStore) -> None:
        self._store = store

    def issue(
        self,
        *,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None = None,
    ) -> SaltLease:
        return self._store.issue(
            session_id=session_id,
            scope=scope,
            purpose=purpose,
            profile=profile,
        )

    def consume(
        self,
        *,
        lease_id: str,
        session_id: str,
        scope: EncryptionSessionScope,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None = None,
    ) -> SaltLease:
        return self._store.consume(
            lease_id=lease_id,
            session_id=session_id,
            scope=scope,
            purpose=purpose,
            profile=profile,
        )

    def wrap(
        self,
        *,
        lease: SaltLease,
        key_material: bytes,
        context_seed: bytes,
    ) -> WrappedSaltFrame:
        return self.wrap_payload(
            session_id=lease.session_id,
            scope=lease.scope,
            payload={
                "lease_id": lease.lease_id,
                "purpose": lease.purpose,
                "scope": lease.scope,
                "profile": lease.profile.value if lease.profile is not None else None,
                "salt": _base64url_encode(lease.salt),
                "expires_at": int(lease.expires_at.timestamp()),
            },
            key_material=key_material,
            context_seed=context_seed,
        )

    def wrap_payload(
        self,
        *,
        session_id: str,
        scope: EncryptionSessionScope,
        payload: dict[str, object],
        key_material: bytes,
        context_seed: bytes,
    ) -> WrappedSaltFrame:
        plaintext = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        wrap_salt = urandom(_WRAP_SALT_BYTES)
        nonce = urandom(_WRAP_NONCE_BYTES)
        ciphertext = AESGCM(
            _derive_wrap_key(
                key_material,
                context_seed=context_seed,
                wrap_salt=wrap_salt,
                session_id=session_id,
                scope=scope,
            ),
        ).encrypt(
            nonce,
            plaintext,
            _wrap_associated_data(
                context_seed=context_seed,
                session_id=session_id,
                scope=scope,
            ),
        )
        return WrappedSaltFrame(
            session_id=session_id,
            wrap_salt=_base64url_encode(wrap_salt),
            nonce=_base64url_encode(nonce),
            ciphertext=_base64url_encode(ciphertext),
        )

    def unwrap_request(
        self,
        frame: WrappedSaltFrame,
        *,
        key_material: bytes,
        context_seed: bytes,
        scope: EncryptionSessionScope,
    ) -> dict[str, object]:
        try:
            plaintext = AESGCM(
                _derive_wrap_key(
                    key_material,
                    context_seed=context_seed,
                    wrap_salt=_base64url_decode(frame.wrap_salt),
                    session_id=frame.session_id,
                    scope=scope,
                ),
            ).decrypt(
                _base64url_decode(frame.nonce),
                _base64url_decode(frame.ciphertext),
                _wrap_associated_data(
                    context_seed=context_seed,
                    session_id=frame.session_id,
                    scope=scope,
                ),
            )
            payload = json.loads(plaintext.decode("utf-8"))
        except (InvalidTag, ValueError, UnicodeDecodeError, TypeError) as exc:
            raise EncryptionSaltError("invalid encrypted salt frame") from exc
        if not isinstance(payload, dict):
            raise EncryptionSaltError("salt frame payload must be an object")
        return payload


def create_salt_lease_service(settings: Settings) -> SaltLeaseService:
    if settings.rate_limit_backend == "redis" and settings.redis_url:
        redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            protocol=2,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        return SaltLeaseService(
            store=RedisSaltLeaseStore(
                redis_client=redis_client,
                key_prefix=settings.redis_key_prefix,
            ),
        )
    if settings.environment == "production":
        raise EncryptionSaltUnavailable(
            "production encryption salts require redis backend",
        )
    return SaltLeaseService(store=InMemorySaltLeaseStore())


def _new_lease(
    *,
    session_id: str,
    scope: EncryptionSessionScope,
    purpose: SaltPurpose,
    profile: EncryptionProfile | None,
    now: datetime,
) -> SaltLease:
    return SaltLease(
        lease_id=_base64url_encode(urandom(_LEASE_ID_BYTES)),
        session_id=session_id,
        scope=scope,
        purpose=purpose,
        profile=profile,
        salt=urandom(_SALT_BYTES),
        expires_at=now + timedelta(seconds=_LEASE_TTL_SECONDS),
    )


def _matches(
    lease: SaltLease,
    *,
    session_id: str,
    scope: EncryptionSessionScope,
    purpose: SaltPurpose,
    profile: EncryptionProfile | None,
) -> bool:
    return (
        compare_digest(lease.session_id, session_id)
        and lease.scope == scope
        and lease.purpose == purpose
        and lease.profile == profile
    )


def _is_expired(lease: SaltLease, now: datetime) -> bool:
    current_time = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    expires_at = (
        lease.expires_at
        if lease.expires_at.tzinfo is not None
        else lease.expires_at.replace(tzinfo=UTC)
    )
    return expires_at <= current_time


def _serialize_lease(lease: SaltLease) -> str:
    return json.dumps(
        {
            "lease_id": lease.lease_id,
            "session_id": lease.session_id,
            "scope": lease.scope,
            "purpose": lease.purpose,
            "profile": lease.profile.value if lease.profile is not None else None,
            "salt": _base64url_encode(lease.salt),
            "expires_at": int(lease.expires_at.timestamp()),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _deserialize_lease(value: str) -> SaltLease:
    try:
        payload = json.loads(value)
        profile_value = payload.get("profile")
        return SaltLease(
            lease_id=str(payload["lease_id"]),
            session_id=str(payload["session_id"]),
            scope=_scope(str(payload["scope"])),
            purpose=_purpose(str(payload["purpose"])),
            profile=(
                EncryptionProfile(str(profile_value))
                if profile_value is not None
                else None
            ),
            salt=_base64url_decode(str(payload["salt"])),
            expires_at=datetime.fromtimestamp(int(payload["expires_at"]), UTC),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EncryptionSaltReplay("salt lease is malformed") from exc


def _scope(value: str) -> EncryptionSessionScope:
    if value not in {"admin", "public"}:
        raise ValueError("invalid salt scope")
    return value  # type: ignore[return-value]


def _purpose(value: str) -> SaltPurpose:
    if value not in {"esid", "login_capsule", "request", "response"}:
        raise ValueError("invalid salt purpose")
    return value  # type: ignore[return-value]


def _derive_wrap_key(
    key_material: bytes,
    *,
    context_seed: bytes,
    wrap_salt: bytes,
    session_id: str,
    scope: EncryptionSessionScope,
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=wrap_salt,
        info=binary_context(
            seed=context_seed,
            opcode=ContextOpcode.WSS_WRAP_KEY,
            scope=scope,
            session_id=session_id,
        ),
    ).derive(key_material)


def _wrap_associated_data(
    *,
    context_seed: bytes,
    session_id: str,
    scope: EncryptionSessionScope,
) -> bytes:
    return binary_context(
        seed=context_seed,
        opcode=ContextOpcode.WSS_WRAP_AAD,
        scope=scope,
        session_id=session_id,
    )


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")
