from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from redis.exceptions import RedisError

from app.api.encryption_salts import salt_websocket
from app.core.config import get_settings
from app.core.encryption import EncryptionProfile
from app.services.encryption import EncryptionSessionManager
from app.services.encryption_salts import (
    EncryptionSaltReplay,
    InMemorySaltLeaseStore,
    RedisSaltLeaseStore,
    SaltLeaseService,
)

TEST_CONTEXT_SEED = b"c" * 32


class FakeTelemetry:
    environment = "test"
    version = "1.0.0"

    def __init__(self) -> None:
        self.metrics: list[dict[str, object]] = []

    def record_metric(self, **kwargs: object) -> None:
        self.metrics.append(dict(kwargs))


class FakeEncryptionSessionRepository:
    def __init__(self, session: SimpleNamespace) -> None:
        self.session = session

    async def get_active_session(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> SimpleNamespace | None:
        if session_id == self.session.session_id:
            return self.session
        return None


class FakeWebSocket:
    def __init__(self, payload: dict[str, object], telemetry: FakeTelemetry) -> None:
        self._payload = payload
        self.app = SimpleNamespace(
            state=SimpleNamespace(telemetry_service=telemetry),
        )
        self.client = SimpleNamespace(host="203.0.113.9")
        self.headers: dict[str, str] = {}
        self.closed_code: int | None = None
        self.sent: list[dict[str, object]] = []

    async def accept(self) -> None:
        return None

    async def receive_json(self) -> dict[str, object]:
        return self._payload

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    async def close(self, code: int) -> None:
        self.closed_code = code


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
    frame = service.wrap(
        lease=lease,
        key_material=b"k" * 32,
        context_seed=TEST_CONTEXT_SEED,
    )

    assert lease.lease_id not in frame.ciphertext
    assert "login_capsule" not in frame.ciphertext
    unwrapped = service.unwrap_request(
        frame,
        key_material=b"k" * 32,
        context_seed=TEST_CONTEXT_SEED,
        scope="admin",
    )

    assert unwrapped["lease_id"] == lease.lease_id
    assert unwrapped["purpose"] == "login_capsule"
    assert unwrapped["salt"]


def test_salt_lease_wss_ping_pong_frames_are_encrypted() -> None:
    service = SaltLeaseService(store=InMemorySaltLeaseStore())
    key_material = b"k" * 32
    ping = service.wrap_payload(
        session_id="session-1",
        scope="admin",
        payload={"kind": "ping", "seq": 7, "ts": 1782220000},
        key_material=key_material,
        context_seed=TEST_CONTEXT_SEED,
    )

    assert "ping" not in ping.ciphertext
    unwrapped_ping = service.unwrap_request(
        ping,
        key_material=key_material,
        context_seed=TEST_CONTEXT_SEED,
        scope="admin",
    )
    assert unwrapped_ping == {"kind": "ping", "seq": 7, "ts": 1782220000}

    pong = service.wrap_payload(
        session_id="session-1",
        scope="admin",
        payload={
            "kind": "pong",
            "seq": unwrapped_ping["seq"],
            "ts": unwrapped_ping["ts"],
        },
        key_material=key_material,
        context_seed=TEST_CONTEXT_SEED,
    )

    assert "pong" not in pong.ciphertext
    assert service.unwrap_request(
        pong,
        key_material=key_material,
        context_seed=TEST_CONTEXT_SEED,
        scope="admin",
    ) == {
        "kind": "pong",
        "seq": 7,
        "ts": 1782220000,
    }


def test_salt_websocket_records_rejected_lease_validation() -> None:
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    key_material = b"k" * 32
    session = SimpleNamespace(
        session_id="session-1",
        scope="public",
        key_material=key_material,
        context_seed=TEST_CONTEXT_SEED,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    manager = EncryptionSessionManager(
        repository=FakeEncryptionSessionRepository(session),
        settings=get_settings(),
        salt_leases=salt_leases,
    )
    request_frame = salt_leases.wrap_payload(
        session_id=session.session_id,
        scope="public",
        payload={
            "kind": "salt_request",
            "purpose": "login_capsule",
            "profile": "sensitive-v1",
            "count": 2,
        },
        key_material=key_material,
        context_seed=TEST_CONTEXT_SEED,
    )
    telemetry = FakeTelemetry()
    websocket = FakeWebSocket(request_frame.__dict__, telemetry)

    import asyncio

    asyncio.run(
        salt_websocket(
            websocket,  # type: ignore[arg-type]
            scope="public",
            manager=manager,
            salt_leases=salt_leases,
        ),
    )

    rejected_metric = next(
        metric
        for metric in telemetry.metrics
        if metric["name"] == "blog.encryption.salt.lease.count"
        and metric["tags"]["stage"] == "rejected"
    )
    assert rejected_metric["value"] == 2
    assert rejected_metric["tags"]["purpose"] == "login_capsule"
    assert websocket.closed_code == 1008


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
