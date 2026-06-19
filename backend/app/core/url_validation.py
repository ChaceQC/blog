from collections.abc import Container
from urllib.parse import unquote, urlparse

HTTP_URL_SCHEMES = frozenset({"http", "https"})
PUBLIC_HREF_SCHEMES = frozenset({"http", "https", "mailto"})
PUBLIC_IMAGE_SOURCE_SCHEMES = frozenset({"http", "https"})
PUBLIC_SITE_PATH_DENYLIST = ("/admin", "/api/admin")


def validate_http_url(value: str) -> str:
    return validate_url(value, allowed_schemes=HTTP_URL_SCHEMES, allow_site_path=False)


def validate_public_href(value: str) -> str:
    return validate_url(
        value,
        allowed_schemes=PUBLIC_HREF_SCHEMES,
        allow_site_path=True,
    )


def validate_public_image_src(value: str) -> str:
    return validate_url(
        value,
        allowed_schemes=PUBLIC_IMAGE_SOURCE_SCHEMES,
        allow_site_path=True,
    )


def validate_url(
    value: str,
    *,
    allowed_schemes: Container[str],
    allow_site_path: bool,
) -> str:
    url = value.strip()
    if not url:
        raise ValueError("url is required")
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        raise ValueError("url must not contain control characters")

    if allow_site_path and url.startswith("/") and not url.startswith("//"):
        ensure_public_site_path(url)
        return url

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in allowed_schemes:
        raise ValueError("url scheme is not allowed")
    if scheme in HTTP_URL_SCHEMES and not parsed.netloc:
        raise ValueError("http url must include host")
    if scheme in HTTP_URL_SCHEMES:
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("http url port is invalid") from exc
    if scheme == "mailto" and not parsed.path:
        raise ValueError("mailto url must include address")
    return url


def ensure_public_site_path(url: str) -> None:
    parsed = urlparse(url)
    path = parsed.path.lower()
    for _ in range(3):
        decoded_path = unquote(path).lower()
        if decoded_path == path:
            break
        path = decoded_path
    if "\\" in path or path.startswith("//"):
        raise ValueError("site path is not public")
    for denied_prefix in PUBLIC_SITE_PATH_DENYLIST:
        if path == denied_prefix or path.startswith(f"{denied_prefix}/"):
            raise ValueError("site path is not public")
