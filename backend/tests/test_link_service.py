import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.services.links import (
    CreateFriendLinkCommand,
    DuplicateFriendLinkApplicationError,
    FriendLinkApplicationLimitExceededError,
    LinkService,
    friend_link_domain,
    normalize_friend_link_url,
)


@dataclass
class FakeFriendLink:
    id: int
    group_id: int | None
    name: str
    url: str
    avatar_url: str | None
    description: str | None
    rss_url: str | None
    status: str
    sort_order: int
    last_checked_at: datetime | None = None
    last_status_code: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FakeLinkRepository:
    def __init__(
        self,
        *,
        existing_links: list[FakeFriendLink] | None = None,
        pending_count: int | None = None,
    ) -> None:
        self.existing_links = existing_links or []
        self.pending_count = (
            pending_count
            if pending_count is not None
            else sum(1 for link in self.existing_links if link.status == "pending")
        )
        self.created_links: list[FakeFriendLink] = []
        self.commit_count = 0

    async def count_friend_links_by_status(self, *, status: str) -> int:
        assert status == "pending"
        return self.pending_count

    async def list_friend_links_by_statuses(
        self,
        *,
        statuses: set[str],
        limit: int,
    ) -> list[FakeFriendLink]:
        assert statuses == {"pending", "healthy"}
        assert limit == 5000
        return [
            link for link in self.existing_links if link.status in statuses
        ][:limit]

    async def create_friend_link(self, **payload: object) -> FakeFriendLink:
        link = FakeFriendLink(
            id=len(self.existing_links) + len(self.created_links) + 1,
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
            updated_at=datetime(2026, 6, 19, tzinfo=UTC),
            **payload,
        )
        self.created_links.append(link)
        return link

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, instance: object) -> None:
        return None


def make_command(url: str = "HTTPS://Friend.Example.TEST:443/path?b=2&a=1#top"):
    return CreateFriendLinkCommand(
        group_id=None,
        name="新朋友",
        url=url,
        avatar_url=None,
        description="新的个人站点",
        rss_url=None,
        status="pending",
        sort_order=1000,
    )


def test_normalize_friend_link_url_removes_fragment_and_default_port() -> None:
    assert (
        normalize_friend_link_url("HTTPS://Friend.Example.TEST:443/path?b=2&a=1#top")
        == "https://friend.example.test/path?a=1&b=2"
    )
    assert normalize_friend_link_url("http://example.test:80") == (
        "http://example.test/"
    )


def test_friend_link_domain_returns_lowercase_host() -> None:
    assert friend_link_domain("https://Friend.Example.TEST/path") == (
        "friend.example.test"
    )


def test_public_friend_link_application_creates_normalized_pending_link() -> None:
    repository = FakeLinkRepository()
    service = LinkService(repository=repository)

    result = asyncio.run(service.create_public_friend_link_application(make_command()))

    assert result.url == "https://friend.example.test/path?a=1&b=2"
    assert repository.created_links[0].url == result.url
    assert repository.commit_count == 1


def test_public_friend_link_application_rejects_duplicate_url() -> None:
    repository = FakeLinkRepository(
        existing_links=[
            FakeFriendLink(
                id=1,
                group_id=None,
                name="旧朋友",
                url="https://friend.example.test/path?a=1&b=2",
                avatar_url=None,
                description=None,
                rss_url=None,
                status="healthy",
                sort_order=0,
            ),
        ],
    )
    service = LinkService(repository=repository)

    with pytest.raises(DuplicateFriendLinkApplicationError):
        asyncio.run(service.create_public_friend_link_application(make_command()))

    assert repository.created_links == []
    assert repository.commit_count == 0


def test_public_friend_link_application_rejects_domain_pending_overflow() -> None:
    repository = FakeLinkRepository(
        existing_links=[
            FakeFriendLink(
                id=index,
                group_id=None,
                name=f"待审{index}",
                url=f"https://friend.example.test/{index}",
                avatar_url=None,
                description=None,
                rss_url=None,
                status="pending",
                sort_order=0,
            )
            for index in range(5)
        ],
    )
    service = LinkService(repository=repository)

    with pytest.raises(FriendLinkApplicationLimitExceededError):
        asyncio.run(
            service.create_public_friend_link_application(
                make_command("https://friend.example.test/new"),
            ),
        )

    assert repository.created_links == []
    assert repository.commit_count == 0


def test_public_friend_link_application_rejects_global_pending_overflow() -> None:
    repository = FakeLinkRepository(pending_count=100)
    service = LinkService(repository=repository)

    with pytest.raises(FriendLinkApplicationLimitExceededError):
        asyncio.run(service.create_public_friend_link_application(make_command()))

    assert repository.created_links == []
    assert repository.commit_count == 0
