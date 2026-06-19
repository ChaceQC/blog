from starlette.requests import Request

import app.core.request as request_module
from app.core.request import client_ip


def make_request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": ("172.23.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        },
    )


class FakeSettings:
    trusted_proxy_hosts = ["172.23.0.1"]


class FakeCidrSettings:
    trusted_proxy_hosts = ["172.23.0.0/24"]


def test_client_ip_uses_forwarded_for_address_for_trusted_proxy(
    monkeypatch,
) -> None:
    monkeypatch.setattr(request_module, "get_settings", lambda: FakeSettings())
    request = make_request(
        [
            (
                b"x-forwarded-for",
                b"203.0.113.9, 172.23.0.1",
            ),
            (b"x-real-ip", b"198.51.100.7"),
        ],
    )

    assert client_ip(request) == "203.0.113.9"


def test_client_ip_ignores_untrusted_leftmost_forwarded_for_spoof(
    monkeypatch,
) -> None:
    monkeypatch.setattr(request_module, "get_settings", lambda: FakeSettings())
    request = make_request(
        [
            (
                b"x-forwarded-for",
                b"198.51.100.99, 203.0.113.9, 172.23.0.1",
            ),
        ],
    )

    assert client_ip(request) == "203.0.113.9"


def test_client_ip_uses_docker_gateway_forwarded_for_when_gateway_is_trusted(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        request_module,
        "get_settings",
        lambda: type("Settings", (), {"trusted_proxy_hosts": ["172.16.0.0/12"]})(),
    )
    request = make_request([(b"x-forwarded-for", b"203.0.113.9")])

    assert client_ip(request) == "203.0.113.9"


def test_client_ip_falls_back_to_real_ip_then_connection_ip_for_trusted_proxy(
    monkeypatch,
) -> None:
    monkeypatch.setattr(request_module, "get_settings", lambda: FakeSettings())
    assert client_ip(make_request([(b"x-real-ip", b"198.51.100.7")])) == (
        "198.51.100.7"
    )
    assert client_ip(make_request([])) == "172.23.0.1"


def test_client_ip_allows_trusted_proxy_cidr(monkeypatch) -> None:
    monkeypatch.setattr(request_module, "get_settings", lambda: FakeCidrSettings())
    request = make_request([(b"x-forwarded-for", b"203.0.113.9")])

    assert client_ip(request) == "203.0.113.9"


def test_client_ip_ignores_forwarded_headers_for_untrusted_connection(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        request_module,
        "get_settings",
        lambda: type("Settings", (), {"trusted_proxy_hosts": []})(),
    )
    request = make_request(
        [
            (b"x-forwarded-for", b"203.0.113.9"),
            (b"x-real-ip", b"198.51.100.7"),
        ],
    )

    assert client_ip(request) == "172.23.0.1"
