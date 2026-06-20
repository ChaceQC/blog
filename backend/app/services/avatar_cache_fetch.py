import http.client
import ipaddress
import socket
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse

from PIL import Image, UnidentifiedImageError

from app.core.url_validation import validate_http_url

AVATAR_CACHE_USER_AGENT = "blog-avatar-cache/0.1"
AVATAR_CACHE_MAX_PIXELS = 16_000_000
ALLOWED_AVATAR_CONTENT_TYPES = {
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}
IMAGE_FORMAT_CONTENT_TYPES = {
    "AVIF": "image/avif",
    "GIF": "image/gif",
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


class AvatarCacheFetchError(RuntimeError):
    pass


class UnsafeAvatarSourceError(ValueError):
    pass


@dataclass(frozen=True)
class FetchedAvatar:
    content: bytes
    media_type: str


@dataclass(frozen=True)
class _SafeHttpTarget:
    url: str
    addresses: tuple[str, ...]


def fetch_avatar(
    url: str,
    *,
    timeout_seconds: float,
    max_size_bytes: int,
    remaining_redirects: int = 3,
) -> FetchedAvatar:
    try:
        target = safe_http_target(url)
    except UnsafeAvatarSourceError as exc:
        raise AvatarCacheFetchError("avatar source is unsafe") from exc

    for address in target.addresses:
        try:
            fetched, redirect_url = _fetch_avatar_once(
                target.url,
                address=address,
                timeout_seconds=timeout_seconds,
                max_size_bytes=max_size_bytes,
            )
        except (OSError, ValueError, http.client.HTTPException):
            continue
        if redirect_url and remaining_redirects > 0:
            return fetch_avatar(
                urljoin(target.url, redirect_url),
                timeout_seconds=timeout_seconds,
                max_size_bytes=max_size_bytes,
                remaining_redirects=remaining_redirects - 1,
            )
        return fetched
    raise AvatarCacheFetchError("avatar source cannot be fetched")


def safe_http_target(url: str) -> _SafeHttpTarget:
    safe_url = validate_http_url(url)
    parsed = urlparse(safe_url)
    hostname = parsed.hostname
    if hostname is None:
        raise UnsafeAvatarSourceError("url host is required")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeAvatarSourceError("url host cannot be resolved") from exc
    if not infos:
        raise UnsafeAvatarSourceError("url host cannot be resolved")

    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeAvatarSourceError("resolved address is invalid") from exc
        if _is_private_target(ip):
            raise UnsafeAvatarSourceError("url resolves to private network")
        if address not in addresses:
            addresses.append(address)
    return _SafeHttpTarget(url=safe_url, addresses=tuple(addresses))


def _fetch_avatar_once(
    url: str,
    *,
    address: str,
    timeout_seconds: float,
    max_size_bytes: int,
) -> tuple[FetchedAvatar, str | None]:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("url host is required")
    connection = _avatar_http_connection(
        parsed,
        address=address,
        timeout_seconds=timeout_seconds,
    )
    try:
        connection.request(
            "GET",
            _request_target(parsed),
            headers={
                "Accept": _avatar_accept_header(),
                "Host": _host_header(parsed),
                "User-Agent": AVATAR_CACHE_USER_AGENT,
            },
        )
        response = connection.getresponse()
        try:
            if response.status in {301, 302, 303, 307, 308}:
                return FetchedAvatar(b"", "image/png"), response.getheader("Location")
            if response.status != 200:
                raise AvatarCacheFetchError("avatar source returned non-200 status")
            content_length = response.getheader("Content-Length")
            if content_length is not None and int(content_length) > max_size_bytes:
                raise AvatarCacheFetchError("avatar source is too large")
            media_type = _response_media_type(response.getheader("Content-Type"))
            content = response.read(max_size_bytes + 1)
            if len(content) > max_size_bytes:
                raise AvatarCacheFetchError("avatar source is too large")
            media_type = _validate_avatar_content(content, media_type)
            return FetchedAvatar(content=content, media_type=media_type), None
        finally:
            response.close()
    finally:
        connection.close()


def _avatar_http_connection(
    parsed: ParseResult,
    *,
    address: str,
    timeout_seconds: float,
) -> http.client.HTTPConnection:
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if parsed.scheme == "https":
        return _PinnedHTTPSConnection(
            hostname,
            port=port,
            connect_host=address,
            timeout=timeout_seconds,
        )
    return _PinnedHTTPConnection(
        hostname,
        port=port,
        connect_host=address,
        timeout=timeout_seconds,
    )


def _avatar_accept_header() -> str:
    return "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.8"


def _response_media_type(value: str | None) -> str | None:
    if value is None:
        return None
    return value.split(";", 1)[0].strip().lower() or None


def _validate_avatar_content(content: bytes, media_type: str | None) -> str:
    if media_type is not None and media_type not in ALLOWED_AVATAR_CONTENT_TYPES:
        raise AvatarCacheFetchError("avatar source content type is not allowed")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.width * image.height > AVATAR_CACHE_MAX_PIXELS:
                raise AvatarCacheFetchError("avatar image is too large")
            image.verify()
            inferred_type = IMAGE_FORMAT_CONTENT_TYPES.get(str(image.format).upper())
    except (UnidentifiedImageError, OSError) as exc:
        raise AvatarCacheFetchError("avatar source is not a valid image") from exc
    if inferred_type is None:
        raise AvatarCacheFetchError("avatar image format is not allowed")
    if media_type is not None and media_type != inferred_type:
        raise AvatarCacheFetchError("avatar source content type is invalid")
    return inferred_type


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
