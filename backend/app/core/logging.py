import logging

import structlog

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
