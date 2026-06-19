import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import app.services.logs as logs_module
from app.services.log_retention import LogRetentionService
from app.services.logs import (
    AccessLogDedupeRule,
    InMemoryAccessLogDedupeBackend,
    LogService,
    RedisAccessLogDedupeBackend,
    build_access_log_dedupe_key,
)


class FakeSettings:
    access_log_dedupe_seconds = 60


class FakeLogRepository:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []
        self.commit_count = 0

    async def record_access_log(self, **kwargs: object) -> None:
        self.items.append(dict(kwargs))

    async def commit(self) -> None:
        self.commit_count += 1


class FakeReadableLogRepository(FakeLogRepository):
    async def list_audit_logs(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 10
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                actor_id=1,
                action="post.update",
                entity_type="post",
                entity_id=2,
                before_json={"title": "旧标题", "status": "draft"},
                after_json={
                    "title": "新标题",
                    "slug": "new-post",
                    "status": "published",
                    "changed_fields": ["title", "slug", "status"],
                },
                ip="127.0.0.1",
                user_agent="pytest",
                created_at=datetime(2026, 6, 19, tzinfo=UTC),
            ),
        ]

    async def list_access_logs(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 10
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                access_type="post_image_render",
                method="GET",
                path="/api/public/posts/new-post/files/1/render",
                status_code=200,
                entity_type="file",
                entity_id=1,
                ip="127.0.0.1",
                user_agent="pytest",
                detail_json={"slug": "new-post", "filename": "cover.png"},
                created_at=datetime(2026, 6, 19, tzinfo=UTC),
            ),
        ]

    async def list_security_events(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[object]:
        assert limit == 10
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                event_type="rate_limit.admin_login",
                severity="medium",
                actor_id=None,
                ip="127.0.0.1",
                user_agent="pytest",
                path="/api/admin/auth/login",
                detail_json={"username": "admin", "credential": "username"},
                created_at=datetime(2026, 6, 19, tzinfo=UTC),
            ),
        ]


class FakeLogRetentionRepository:
    def __init__(
        self,
        *,
        access_logs: int = 0,
        audit_logs: int = 0,
        login_logs: int = 0,
        security_events: int = 0,
    ) -> None:
        self.deleted = {
            "access": access_logs,
            "audit": audit_logs,
            "login": login_logs,
            "security": security_events,
        }
        self.cutoffs: dict[str, datetime] = {}
        self.limits: list[int] = []
        self.commit_count = 0

    async def delete_access_logs_before(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int:
        self.cutoffs["access"] = created_before
        self.limits.append(limit)
        return self.deleted["access"]

    async def delete_audit_logs_before(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int:
        self.cutoffs["audit"] = created_before
        self.limits.append(limit)
        return self.deleted["audit"]

    async def delete_login_logs_before(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int:
        self.cutoffs["login"] = created_before
        self.limits.append(limit)
        return self.deleted["login"]

    async def delete_security_events_before(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int:
        self.cutoffs["security"] = created_before
        self.limits.append(limit)
        return self.deleted["security"]

    async def commit(self) -> None:
        self.commit_count += 1


def test_record_access_log_dedupes_same_ip_method_and_path(monkeypatch) -> None:
    monkeypatch.setattr(logs_module, "get_settings", lambda: FakeSettings())
    repository = FakeLogRepository()
    service = LogService(repository=repository)

    async def run() -> None:
        await service.record_access_log(
            access_type="public_posts_list",
            method="GET",
            path="/api/public/posts",
            status_code=200,
            ip="127.0.0.1",
            user_agent="pytest",
        )
        await service.record_access_log(
            access_type="public_posts_list",
            method="GET",
            path="/api/public/posts",
            status_code=200,
            ip="127.0.0.1",
            user_agent="pytest",
        )

    asyncio.run(run())

    assert len(repository.items) == 1
    assert repository.items[0]["path"] == "/api/public/posts"
    assert repository.commit_count == 1


def test_record_access_log_keeps_different_paths(monkeypatch) -> None:
    monkeypatch.setattr(logs_module, "get_settings", lambda: FakeSettings())
    repository = FakeLogRepository()
    service = LogService(repository=repository)

    async def run() -> None:
        await service.record_access_log(
            access_type="public_posts_list",
            method="GET",
            path="/api/public/posts",
            status_code=200,
            ip="127.0.0.1",
            user_agent="pytest",
        )
        await service.record_access_log(
            access_type="public_post_detail",
            method="GET",
            path="/api/public/posts/example",
            status_code=200,
            ip="127.0.0.1",
            user_agent="pytest",
        )

    asyncio.run(run())

    assert [item["path"] for item in repository.items] == [
        "/api/public/posts",
        "/api/public/posts/example",
    ]
    assert repository.commit_count == 2


def test_record_access_log_keeps_configured_error_types(monkeypatch) -> None:
    monkeypatch.setattr(logs_module, "get_settings", lambda: FakeSettings())
    repository = FakeLogRepository()
    service = LogService(repository=repository)

    asyncio.run(
        service.record_access_log(
            access_type="public_posts_list",
            method="GET",
            path="/api/public/posts/missing",
            status_code=404,
            ip="127.0.0.1",
            user_agent="pytest",
        ),
    )

    assert repository.items[0]["status_code"] == 404
    assert repository.commit_count == 1


def test_record_access_log_keeps_post_operations(monkeypatch) -> None:
    monkeypatch.setattr(logs_module, "get_settings", lambda: FakeSettings())
    repository = FakeLogRepository()
    service = LogService(repository=repository)

    async def run() -> None:
        await service.record_access_log(
            access_type="public_friend_link_application",
            method="POST",
            path="/api/public/friend-links/applications",
            status_code=200,
            ip="127.0.0.1",
            user_agent="pytest",
        )
        await service.record_access_log(
            access_type="public_friend_link_application",
            method="POST",
            path="/api/public/friend-links/applications",
            status_code=200,
            ip="127.0.0.1",
            user_agent="pytest",
        )

    asyncio.run(run())

    assert len(repository.items) == 2
    assert repository.commit_count == 2


def test_list_logs_sanitizes_historical_json_payloads() -> None:
    service = LogService(repository=FakeReadableLogRepository())

    async def run() -> tuple[object, object, object]:
        audit_log = (await service.list_audit_logs(limit=10, offset=0))[0]
        access_log = (await service.list_access_logs(limit=10, offset=0))[0]
        security_event = (await service.list_security_events(limit=10, offset=0))[0]
        return audit_log, access_log, security_event

    audit_log, access_log, security_event = asyncio.run(run())

    assert audit_log.before_json == {"status": "draft"}
    assert audit_log.after_json == {
        "changed_fields": ["slug", "status", "title"],
        "status": "published",
    }
    assert access_log.detail_json is None
    assert security_event.detail_json == {"credential": "username"}


def test_in_memory_access_log_dedupe_allows_after_window() -> None:
    backend = InMemoryAccessLogDedupeBackend()
    rule = AccessLogDedupeRule(window_seconds=60)
    now = datetime(2026, 6, 19, 12, 0, tzinfo=UTC)

    assert backend.should_record(
        key="127.0.0.1:GET:/api/public/posts",
        rule=rule,
        now=now,
    )
    assert not backend.should_record(
        key="127.0.0.1:GET:/api/public/posts",
        rule=rule,
        now=now + timedelta(seconds=30),
    )
    assert backend.should_record(
        key="127.0.0.1:GET:/api/public/posts",
        rule=rule,
        now=now + timedelta(seconds=60),
    )


def test_redis_access_log_dedupe_uses_set_nx_ex() -> None:
    backend = RedisAccessLogDedupeBackend(
        redis_client=FakeRedis(),
        key_prefix="blog:test",
    )
    rule = AccessLogDedupeRule(window_seconds=60)

    assert backend.should_record(key="127.0.0.1:GET:/api/public/posts", rule=rule)
    assert not backend.should_record(key="127.0.0.1:GET:/api/public/posts", rule=rule)


def test_build_access_log_dedupe_key_ignores_query_values() -> None:
    assert build_access_log_dedupe_key(
        ip="127.0.0.1",
        method="get",
        path="/api/public/posts",
    ) == "127.0.0.1:GET:/api/public/posts"


def test_log_retention_cleans_each_log_table_and_commits_once() -> None:
    now = datetime(2026, 6, 19, 12, 0, tzinfo=UTC)
    repository = FakeLogRetentionRepository(
        access_logs=3,
        audit_logs=2,
        login_logs=1,
        security_events=4,
    )
    service = LogRetentionService(repository)

    result = asyncio.run(
        service.cleanup_old_logs(
            now=now,
            access_days=30,
            audit_days=180,
            login_days=90,
            security_days=365,
            limit=5000,
        ),
    )

    assert result.access_logs == 3
    assert result.audit_logs == 2
    assert result.login_logs == 1
    assert result.security_events == 4
    assert result.total_deleted == 10
    assert repository.commit_count == 1
    assert repository.cutoffs == {
        "access": now - timedelta(days=30),
        "audit": now - timedelta(days=180),
        "login": now - timedelta(days=90),
        "security": now - timedelta(days=365),
    }
    assert repository.limits == [5000, 5000, 5000, 5000]


def test_log_retention_skips_zero_day_policy_and_empty_commit() -> None:
    now = datetime(2026, 6, 19, 12, 0, tzinfo=UTC)
    repository = FakeLogRetentionRepository()
    service = LogRetentionService(repository)

    result = asyncio.run(
        service.cleanup_old_logs(
            now=now,
            access_days=0,
            audit_days=0,
            login_days=0,
            security_days=0,
            limit=5000,
        ),
    )

    assert result.total_deleted == 0
    assert repository.cutoffs == {}
    assert repository.commit_count == 0


class FakeRedis:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    def set(self, key: str, value: str, *, ex: int, nx: bool) -> bool:
        assert value == "1"
        assert ex == 60
        assert nx is True
        if key in self.keys:
            return False
        self.keys.add(key)
        return True
