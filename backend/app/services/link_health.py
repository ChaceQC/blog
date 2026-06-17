from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.models.link import FriendLink

FAILED_STATUS_CODE = 0


class LinkHealthRepositoryProtocol(Protocol):
    async def list_healthy_friend_links_for_check(
        self,
        *,
        limit: int,
    ) -> Sequence[FriendLink]: ...

    async def commit(self) -> None: ...


class FriendLinkHealthCheckerProtocol(Protocol):
    async def check_url(self, url: str) -> int | None: ...


@dataclass(frozen=True)
class FriendLinkHealthCheckResult:
    scanned_links: int
    healthy_links: int
    unhealthy_links: int
    failed_links: int
    checked_link_ids: tuple[int, ...]


class FriendLinkHealthService:
    def __init__(
        self,
        *,
        repository: LinkHealthRepositoryProtocol,
        checker: FriendLinkHealthCheckerProtocol,
    ) -> None:
        self.repository = repository
        self.checker = checker

    async def check_healthy_friend_links(
        self,
        *,
        limit: int,
        checked_at: datetime | None = None,
    ) -> FriendLinkHealthCheckResult:
        links = await self.repository.list_healthy_friend_links_for_check(limit=limit)
        check_time = checked_at or datetime.now(UTC)
        healthy_count = 0
        unhealthy_count = 0
        failed_count = 0
        checked_ids: list[int] = []

        for link in links:
            status_code = await self._safe_check(link.url)
            link.last_checked_at = check_time
            link.last_status_code = status_code
            checked_ids.append(link.id)

            if status_code == FAILED_STATUS_CODE:
                failed_count += 1
                unhealthy_count += 1
            elif 200 <= status_code < 400:
                healthy_count += 1
            else:
                unhealthy_count += 1

        if links:
            await self.repository.commit()

        return FriendLinkHealthCheckResult(
            scanned_links=len(links),
            healthy_links=healthy_count,
            unhealthy_links=unhealthy_count,
            failed_links=failed_count,
            checked_link_ids=tuple(checked_ids),
        )

    async def _safe_check(self, url: str) -> int:
        try:
            status_code = await self.checker.check_url(url)
        except Exception:
            return FAILED_STATUS_CODE
        return status_code or FAILED_STATUS_CODE
