import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.link_health import FAILED_STATUS_CODE, FriendLinkHealthService
from app.tasks import links as link_tasks


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


def test_url_checker_rejects_loopback_target(monkeypatch) -> None:
    requested_addresses: list[str] = []

    def fake_request_status_once(*args, address: str, **kwargs) -> tuple[int, None]:
        requested_addresses.append(address)
        return 204, None

    monkeypatch.setattr(
        link_tasks.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                link_tasks.socket.AF_INET,
                link_tasks.socket.SOCK_STREAM,
                6,
                "",
                ("127.0.0.1", 80),
            ),
        ],
    )
    monkeypatch.setattr(
        link_tasks,
        "_request_status_once",
        fake_request_status_once,
    )

    assert link_tasks._request_status(
        "https://example.test",
        method="HEAD",
        timeout_seconds=1,
    ) is None
    assert requested_addresses == []


def test_url_checker_allows_public_target(monkeypatch) -> None:
    requested_addresses: list[str] = []

    def fake_request_status_once(*args, address: str, **kwargs) -> tuple[int, None]:
        requested_addresses.append(address)
        return 204, None

    monkeypatch.setattr(
        link_tasks.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                link_tasks.socket.AF_INET,
                link_tasks.socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 443),
            ),
        ],
    )
    monkeypatch.setattr(
        link_tasks,
        "_request_status_once",
        fake_request_status_once,
    )

    assert link_tasks._request_status(
        "https://example.test",
        method="HEAD",
        timeout_seconds=1,
    ) == 204
    assert requested_addresses == ["93.184.216.34"]


def test_url_checker_revalidates_redirect_target(monkeypatch) -> None:
    def fake_getaddrinfo(host: str, *args, **kwargs):
        address = "93.184.216.34" if host == "example.test" else "127.0.0.1"
        return [
            (
                link_tasks.socket.AF_INET,
                link_tasks.socket.SOCK_STREAM,
                6,
                "",
                (address, 80),
            ),
        ]

    monkeypatch.setattr(link_tasks.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(
        link_tasks,
        "_request_status_once",
        lambda *args, **kwargs: (302, "http://private.example.test/"),
    )

    assert link_tasks._request_status(
        "http://example.test",
        method="HEAD",
        timeout_seconds=1,
    ) is None


def _link_item(link_id: int, url: str) -> object:
    return SimpleNamespace(
        id=link_id,
        url=url,
        last_checked_at=None,
        last_status_code=None,
    )
