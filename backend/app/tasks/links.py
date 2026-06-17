import asyncio
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.repositories.links import LinkRepository
from app.services.link_health import (
    FriendLinkHealthCheckResult,
    FriendLinkHealthService,
)


@dataclass(frozen=True)
class FriendLinkHealthCheckCommand:
    limit: int
    timeout_seconds: float = 5.0


class UrlFriendLinkHealthChecker:
    def __init__(self, *, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    async def check_url(self, url: str) -> int | None:
        return await asyncio.to_thread(
            _check_url,
            url,
            timeout_seconds=self.timeout_seconds,
        )


async def check_friend_links(
    command: FriendLinkHealthCheckCommand,
    *,
    settings: Settings | None = None,
) -> FriendLinkHealthCheckResult:
    """检查已通过友链的 HTTP 状态，供 CLI 或定时任务调用。"""
    _ = settings or get_settings()
    async with AsyncSessionLocal() as session:
        service = FriendLinkHealthService(
            repository=LinkRepository(session),
            checker=UrlFriendLinkHealthChecker(
                timeout_seconds=command.timeout_seconds,
            ),
        )
        return await service.check_healthy_friend_links(limit=command.limit)


def _check_url(url: str, *, timeout_seconds: float) -> int | None:
    status_code = _request_status(url, method="HEAD", timeout_seconds=timeout_seconds)
    if status_code == 405:
        return _request_status(url, method="GET", timeout_seconds=timeout_seconds)
    return status_code


def _request_status(
    url: str,
    *,
    method: str,
    timeout_seconds: float,
) -> int | None:
    request = Request(
        url,
        method=method,
        headers={"User-Agent": "blog-friend-link-checker/0.1"},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except (OSError, URLError, ValueError):
        return None
