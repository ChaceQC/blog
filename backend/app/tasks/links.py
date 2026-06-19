import asyncio
import http.client
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse

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


@dataclass(frozen=True)
class _SafeHttpTarget:
    url: str
    addresses: tuple[str, ...]


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
    )
    if status_code == 405:
        return _request_status(
            url,
            method="GET",
            timeout_seconds=timeout_seconds,
        )
    return status_code


def _request_status(
    url: str,
    *,
    method: str,
    timeout_seconds: float,
    remaining_redirects: int = 3,
) -> int | None:
    try:
        target = _safe_http_target(url)
    except UnsafeFriendLinkUrlError:
        return None

    for address in target.addresses:
        try:
            status_code, redirect_url = _request_status_once(
                target.url,
                address=address,
                method=method,
                timeout_seconds=timeout_seconds,
            )
        except (OSError, ValueError, http.client.HTTPException):
            continue

        if (
            status_code in {301, 302, 303, 307, 308}
            and redirect_url
            and remaining_redirects > 0
        ):
            return _request_status(
                urljoin(target.url, redirect_url),
                method="GET" if status_code == 303 else method,
                timeout_seconds=timeout_seconds,
                remaining_redirects=remaining_redirects - 1,
            )
        return status_code

    return None


def _request_status_once(
    url: str,
    *,
    address: str,
    method: str,
    timeout_seconds: float,
) -> tuple[int, str | None]:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("url host is required")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    connection: http.client.HTTPConnection
    if parsed.scheme == "https":
        connection = _PinnedHTTPSConnection(
            hostname,
            port=port,
            connect_host=address,
            timeout=timeout_seconds,
        )
    else:
        connection = _PinnedHTTPConnection(
            hostname,
            port=port,
            connect_host=address,
            timeout=timeout_seconds,
        )
    try:
        connection.request(
            method,
            _request_target(parsed),
            headers={
                "Host": _host_header(parsed),
                "User-Agent": "blog-friend-link-checker/0.1",
            },
        )
        response = connection.getresponse()
        try:
            return response.status, response.getheader("Location")
        finally:
            response.close()
    finally:
        connection.close()


def _safe_http_target(url: str) -> _SafeHttpTarget:
    safe_url = validate_http_url(url)
    parsed = urlparse(safe_url)
    hostname = parsed.hostname
    if hostname is None:
        raise UnsafeFriendLinkUrlError("url host is required")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeFriendLinkUrlError("url host cannot be resolved") from exc
    if not infos:
        raise UnsafeFriendLinkUrlError("url host cannot be resolved")

    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeFriendLinkUrlError("resolved address is invalid") from exc
        if _is_private_target(ip):
            raise UnsafeFriendLinkUrlError("url resolves to private network")
        if address not in addresses:
            addresses.append(address)
    return _SafeHttpTarget(url=safe_url, addresses=tuple(addresses))


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


def _request_target(parsed: ParseResult) -> str:
    return urlunparse(("", "", parsed.path or "/", parsed.params, parsed.query, ""))


def _host_header(parsed: ParseResult) -> str:
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    default_port = 443 if parsed.scheme == "https" else 80
    if parsed.port is not None and parsed.port != default_port:
        return f"{hostname}:{parsed.port}"
    return hostname


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(
        self,
        host: str,
        *,
        port: int,
        connect_host: str,
        timeout: float,
    ) -> None:
        super().__init__(host, port=port, timeout=timeout)
        self._connect_host = connect_host

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._connect_host, self.port),
            self.timeout,
            self.source_address,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        *,
        port: int,
        connect_host: str,
        timeout: float,
    ) -> None:
        super().__init__(host, port=port, timeout=timeout)
        self._connect_host = connect_host

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._connect_host, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
