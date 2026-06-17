from starlette.requests import Request

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


def test_client_ip_prefers_first_forwarded_for_address() -> None:
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


def test_client_ip_falls_back_to_real_ip_then_connection_ip() -> None:
    assert client_ip(make_request([(b"x-real-ip", b"198.51.100.7")])) == (
        "198.51.100.7"
    )
    assert client_ip(make_request([])) == "172.23.0.1"
