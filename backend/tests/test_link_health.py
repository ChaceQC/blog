import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.link_health import FAILED_STATUS_CODE, FriendLinkHealthService


class FakeLinkHealthRepository:
    def __init__(self, links: list[object]) -> None:
        self.links = links
        self.commit_count = 0

    async def list_healthy_friend_links_for_check(self, *, limit: int) -> list[object]:
        return self.links[:limit]

    async def commit(self) -> None:
        self.commit_count += 1


class FakeLinkHealthChecker:
    def __init__(self, status_codes: dict[str, int | Exception]) -> None:
        self.status_codes = status_codes
        self.checked_urls: list[str] = []

    async def check_url(self, url: str) -> int | None:
        self.checked_urls.append(url)
        result = self.status_codes[url]
        if isinstance(result, Exception):
            raise result
        return result


def test_check_healthy_friend_links_updates_status_fields() -> None:
    checked_at = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    links = [
        _link_item(1, "https://ok.example.test"),
        _link_item(2, "https://redirect.example.test"),
        _link_item(3, "https://missing.example.test"),
        _link_item(4, "https://timeout.example.test"),
    ]
    repository = FakeLinkHealthRepository(links)
    checker = FakeLinkHealthChecker(
        {
            "https://ok.example.test": 200,
            "https://redirect.example.test": 302,
            "https://missing.example.test": 404,
            "https://timeout.example.test": TimeoutError("timeout"),
        },
    )
    service = FriendLinkHealthService(repository=repository, checker=checker)

    result = asyncio.run(
        service.check_healthy_friend_links(limit=10, checked_at=checked_at),
    )

    assert result.scanned_links == 4
    assert result.healthy_links == 2
    assert result.unhealthy_links == 2
    assert result.failed_links == 1
    assert result.checked_link_ids == (1, 2, 3, 4)
    assert [link.last_checked_at for link in links] == [checked_at] * 4
    assert [link.last_status_code for link in links] == [
        200,
        302,
        404,
        FAILED_STATUS_CODE,
    ]
    assert repository.commit_count == 1


def test_check_healthy_friend_links_skips_empty_commit() -> None:
    repository = FakeLinkHealthRepository([])
    checker = FakeLinkHealthChecker({})
    service = FriendLinkHealthService(repository=repository, checker=checker)

    result = asyncio.run(service.check_healthy_friend_links(limit=10))

    assert result.scanned_links == 0
    assert result.checked_link_ids == ()
    assert repository.commit_count == 0


def _link_item(link_id: int, url: str) -> object:
    return SimpleNamespace(
        id=link_id,
        url=url,
        last_checked_at=None,
        last_status_code=None,
    )
