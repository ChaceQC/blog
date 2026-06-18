import asyncio

import pytest

import app.services.logs as logs_module
from app.services.logs import LogService


class FakeSettings:
    access_log_skip_types = ["public_posts_list"]


class FakeLogRepository:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []
        self.commit_count = 0

    async def record_access_log(self, **kwargs: object) -> None:
        self.items.append(dict(kwargs))

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.parametrize("status_code", [200, 302])
def test_record_access_log_skips_configured_success_types(
    monkeypatch,
    status_code: int,
) -> None:
    monkeypatch.setattr(logs_module, "get_settings", lambda: FakeSettings())
    repository = FakeLogRepository()
    service = LogService(repository=repository)

    asyncio.run(
        service.record_access_log(
            access_type="public_posts_list",
            method="GET",
            path="/api/public/posts",
            status_code=status_code,
            ip="127.0.0.1",
            user_agent="pytest",
        ),
    )

    assert repository.items == []
    assert repository.commit_count == 0


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
