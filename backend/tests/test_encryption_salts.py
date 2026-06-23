from datetime import UTC, datetime, timedelta

import pytest
from redis.exceptions import RedisError

from app.core.encryption import EncryptionProfile
from app.services.encryption_salts import (
    EncryptionSaltReplay,
    InMemorySaltLeaseStore,
    RedisSaltLeaseStore,
    SaltLeaseService,
)


def test_in_memory_salt_lease_is_single_use() -> None:
    service = SaltLeaseService(store=InMemorySaltLeaseStore())
    lease = service.issue(
        session_id="session-1",
        scope="admin",
        purpose="response",
        profile=EncryptionProfile.SENSITIVE,
    )

    consumed = service.consume(
        lease_id=lease.lease_id,
        session_id="session-1",
        scope="admin",
        purpose="response",
        profile=EncryptionProfile.SENSITIVE,
    )

    assert consumed.salt == lease.salt
    with pytest.raises(EncryptionSaltReplay):
        service.consume(
            lease_id=lease.lease_id,
            session_id="session-1",
            scope="admin",
            purpose="response",
            profile=EncryptionProfile.SENSITIVE,
        )


def test_in_memory_salt_lease_rejects_wrong_purpose() -> None:
    service = SaltLeaseService(store=InMemorySaltLeaseStore())
    lease = service.issue(
        session_id="session-1",
        scope="admin",
        purpose="request",
        profile=EncryptionProfile.CONTENT,
    )

    with pytest.raises(EncryptionSaltReplay):
        service.consume(
            lease_id=lease.lease_id,
            session_id="session-1",
            scope="admin",
            purpose="response",
            profile=EncryptionProfile.CONTENT,
        )


def test_in_memory_salt_lease_rejects_expired() -> None:
    store = InMemorySaltLeaseStore()
    lease = store.issue(
        session_id="session-1",
        scope="public",
        purpose="esid",
        profile=None,
        now=datetime(2026, 6, 24, tzinfo=UTC),
    )

    with pytest.raises(EncryptionSaltReplay):
        store.consume(
            lease_id=lease.lease_id,
            session_id="session-1",
            scope="public",
            purpose="esid",
            profile=None,
            now=datetime(2026, 6, 24, tzinfo=UTC) + timedelta(seconds=60),
        )


def test_salt_lease_wss_frames_are_encrypted() -> None:
    service = SaltLeaseService(store=InMemorySaltLeaseStore())
    lease = service.issue(
        session_id="session-1",
        scope="admin",
        purpose="login_capsule",
        profile=EncryptionProfile.SENSITIVE,
    )
    frame = service.wrap(lease=lease, key_material=b"k" * 32)

    assert lease.lease_id not in frame.ciphertext
    assert "login_capsule" not in frame.ciphertext
    unwrapped = service.unwrap_request(frame, key_material=b"k" * 32)

    assert unwrapped["lease_id"] == lease.lease_id
    assert unwrapped["purpose"] == "login_capsule"
    assert unwrapped["salt"]


def test_salt_lease_wss_ping_pong_frames_are_encrypted() -> None:
    service = SaltLeaseService(store=InMemorySaltLeaseStore())
    key_material = b"k" * 32
    ping = service.wrap_payload(
        session_id="session-1",
        payload={"kind": "ping", "seq": 7, "ts": 1782220000},
        key_material=key_material,
    )

    assert "ping" not in ping.ciphertext
    unwrapped_ping = service.unwrap_request(ping, key_material=key_material)
    assert unwrapped_ping == {"kind": "ping", "seq": 7, "ts": 1782220000}

    pong = service.wrap_payload(
        session_id="session-1",
        payload={
            "kind": "pong",
            "seq": unwrapped_ping["seq"],
            "ts": unwrapped_ping["ts"],
        },
        key_material=key_material,
    )

    assert "pong" not in pong.ciphertext
    assert service.unwrap_request(pong, key_material=key_material) == {
        "kind": "pong",
        "seq": 7,
        "ts": 1782220000,
    }


def test_redis_salt_lease_uses_get_and_delete_atomically() -> None:
    redis = FakeRedis()
    service = SaltLeaseService(
        store=RedisSaltLeaseStore(redis_client=redis, key_prefix="blog:test"),
    )
    lease = service.issue(
        session_id="session-1",
        scope="admin",
        purpose="response",
        profile=EncryptionProfile.SENSITIVE,
    )

    consumed = service.consume(
        lease_id=lease.lease_id,
        session_id="session-1",
        scope="admin",
        purpose="response",
        profile=EncryptionProfile.SENSITIVE,
    )

    assert consumed.lease_id == lease.lease_id
    assert redis.deleted_keys == [f"blog:test:salt-lease:{lease.lease_id}"]
    with pytest.raises(EncryptionSaltReplay):
        service.consume(
            lease_id=lease.lease_id,
            session_id="session-1",
            scope="admin",
            purpose="response",
            profile=EncryptionProfile.SENSITIVE,
        )


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.deleted_keys: list[str] = []

    def set(self, key: str, value: str, *, ex: int) -> None:
        assert ex > 0
        self.values[key] = value

    def eval(self, _: str, __: int, key: str) -> str | None:
        if key not in self.values:
            return None
        self.deleted_keys.append(key)
        return self.values.pop(key)


class FailingRedis:
    def set(self, *_: object, **__: object) -> None:
        raise RedisError("redis is unavailable")
