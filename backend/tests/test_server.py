from types import SimpleNamespace

from uvicorn.config import LOGGING_CONFIG

from app.server import build_uvicorn_log_config, forwarded_allow_ips_from_settings


def test_forwarded_allow_ips_uses_trusted_proxy_hosts() -> None:
    settings = SimpleNamespace(
        trusted_proxy_hosts=[" 172.16.0.0/12 ", "", "127.0.0.1"],
    )

    assert forwarded_allow_ips_from_settings(settings) == [
        "172.16.0.0/12",
        "127.0.0.1",
    ]


def test_forwarded_allow_ips_disables_implicit_proxy_trust_when_empty() -> None:
    settings = SimpleNamespace(trusted_proxy_hosts=[])

    assert forwarded_allow_ips_from_settings(settings) == []


def test_uvicorn_access_log_format_includes_timestamp() -> None:
    log_config = build_uvicorn_log_config()
    access_formatter = log_config["formatters"]["access"]

    assert "%(asctime)s" in access_formatter["fmt"]
    assert "%(client_addr)s" in access_formatter["fmt"]
    assert "%(request_line)s" in access_formatter["fmt"]
    assert access_formatter["datefmt"] == "%Y-%m-%dT%H:%M:%S%z"


def test_uvicorn_log_config_does_not_mutate_default_config() -> None:
    build_uvicorn_log_config()

    assert "%(asctime)s" not in LOGGING_CONFIG["formatters"]["access"]["fmt"]
