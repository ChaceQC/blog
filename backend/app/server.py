from copy import deepcopy
from typing import Any

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from app.core.config import Settings, get_settings

UVICORN_LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def forwarded_allow_ips_from_settings(settings: Settings) -> list[str]:
    return [host.strip() for host in settings.trusted_proxy_hosts if host.strip()]


def build_uvicorn_log_config() -> dict[str, Any]:
    log_config = deepcopy(LOGGING_CONFIG)
    default_formatter = log_config["formatters"]["default"]
    access_formatter = log_config["formatters"]["access"]

    default_formatter["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    default_formatter["datefmt"] = UVICORN_LOG_DATE_FORMAT
    access_formatter["fmt"] = (
        '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" '
        "%(status_code)s"
    )
    access_formatter["datefmt"] = UVICORN_LOG_DATE_FORMAT
    return log_config


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        forwarded_allow_ips=forwarded_allow_ips_from_settings(settings),
        log_config=build_uvicorn_log_config(),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
