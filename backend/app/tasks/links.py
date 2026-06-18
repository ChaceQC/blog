import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    OpenerDirector,
    Request,
    build_opener,
)

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.core.url_validation import validate_http_url
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


class UnsafeFriendLinkUrlError(ValueError):
    pass


class _NoRedirectHandler(HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)

    http_error_302 = http_error_301
    http_error_303 = http_error_301
    http_error_307 = http_error_301
    http_error_308 = http_error_301


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
    status_code = _request_status(
        url,
        method="HEAD",
        timeout_seconds=timeout_seconds,
        opener=build_opener(_NoRedirectHandler),
    )
    if status_code == 405:
        return _request_status(
            url,
            method="GET",
            timeout_seconds=timeout_seconds,
            opener=build_opener(_NoRedirectHandler),
        )
    return status_code


def _request_status(
    url: str,
    *,
    method: str,
    timeout_seconds: float,
    opener: OpenerDirector,
    remaining_redirects: int = 3,
) -> int | None:
    try:
        _ensure_safe_http_url(url)
    except UnsafeFriendLinkUrlError:
        return None

    request = Request(
        url,
        method=method,
        headers={"User-Agent": "blog-friend-link-checker/0.1"},
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            return response.status
    except HTTPError as exc:
        if exc.code in {301, 302, 303, 307, 308} and remaining_redirects > 0:
            redirect_url = exc.headers.get("Location")
            if not redirect_url:
                return exc.code
            return _request_status(
                urljoin(url, redirect_url),
                method="GET" if exc.code == 303 else method,
                timeout_seconds=timeout_seconds,
                opener=opener,
                remaining_redirects=remaining_redirects - 1,
            )
        return exc.code
    except (OSError, URLError, ValueError):
        return None


def _ensure_safe_http_url(url: str) -> str:
    safe_url = validate_http_url(url)
    parsed = urlparse(safe_url)
    hostname = parsed.hostname
    if hostname is None:
        raise UnsafeFriendLinkUrlError("url host is required")
    try:
        infos = socket.getaddrinfo(hostname, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeFriendLinkUrlError("url host cannot be resolved") from exc
    if not infos:
        raise UnsafeFriendLinkUrlError("url host cannot be resolved")

    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeFriendLinkUrlError("resolved address is invalid") from exc
        if _is_private_target(ip):
            raise UnsafeFriendLinkUrlError("url resolves to private network")
    return safe_url


def _is_private_target(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        ),
    )
