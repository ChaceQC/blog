from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    version: str
    environment: Literal["development", "test", "production"]
    debug: bool

    public_base_url: str
    database_url: str
    secret_key: str
    access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=14, ge=1, le=90)
    encryption_session_expire_seconds: int = Field(default=300, ge=60, le=3600)
    admin_login_rate_limit_max_attempts: int = Field(default=5, ge=1, le=100)
    admin_login_rate_limit_window_seconds: int = Field(default=60, ge=10, le=3600)
    encryption_session_rate_limit_max_attempts: int = Field(default=20, ge=1, le=300)
    encryption_session_rate_limit_window_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
    )
    public_encryption_session_active_limit_per_ip: int = Field(
        default=10,
        ge=1,
        le=100,
    )
    admin_encryption_session_active_limit_per_ip: int = Field(
        default=10,
        ge=1,
        le=100,
    )
    friend_link_application_rate_limit_max_attempts: int = Field(
        default=5,
        ge=1,
        le=100,
    )
    friend_link_application_rate_limit_window_seconds: int = Field(
        default=600,
        ge=10,
        le=3600,
    )
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    redis_url: str | None = None
    redis_key_prefix: str = "blog:rate-limit"
    trusted_proxy_hosts: list[str] = Field(default_factory=list)
    admin_cookie_secure: bool = False
    admin_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    allowed_hosts: list[str]
    cors_origins: list[str]
    docs_enabled: bool
    readiness_check_database: bool
    access_log_dedupe_seconds: int = Field(default=60, ge=0, le=3600)
    upload_root: Path
    upload_max_size_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    file_temporary_url_expire_seconds: int = Field(default=300, ge=30, le=3600)
    avatar_cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    avatar_cache_max_size_bytes: int = Field(
        default=2 * 1024 * 1024,
        ge=1024,
        le=10 * 1024 * 1024,
    )
    avatar_cache_request_timeout_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
    )
    avatar_cache_retry_attempts: int = Field(default=2, ge=0, le=5)

    dev_server_host: str
    dev_server_port: int = Field(ge=1024, le=65535)

    model_config = SettingsConfigDict(
        env_file=(".env.example", ".env"),
        env_file_encoding="utf-8",
        env_prefix="BLOG_",
        case_sensitive=False,
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("mysql+asyncmy://"):
            return value.replace("mysql+asyncmy://", "mysql+aiomysql://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.environment != "production":
            return self

        if self.debug:
            raise ValueError("BLOG_DEBUG must be false in production")
        if self.docs_enabled:
            raise ValueError("BLOG_DOCS_ENABLED must be false in production")
        if self.secret_key == "dev-only-change-me" or len(self.secret_key) < 32:
            raise ValueError("BLOG_SECRET_KEY must be strong in production")
        if not self.admin_cookie_secure:
            raise ValueError("BLOG_ADMIN_COOKIE_SECURE must be true in production")
        if self.admin_cookie_samesite == "none" and not self.admin_cookie_secure:
            raise ValueError("BLOG_ADMIN_COOKIE_SAMESITE=none requires secure cookies")
        if "*" in self.allowed_hosts:
            raise ValueError("BLOG_ALLOWED_HOSTS cannot contain '*' in production")
        if "*" in self.cors_origins:
            raise ValueError("BLOG_CORS_ORIGINS cannot contain '*' in production")
        parsed_public_base_url = urlparse(self.public_base_url)
        if (
            parsed_public_base_url.scheme != "https"
            or not parsed_public_base_url.netloc
        ):
            raise ValueError(
                "BLOG_PUBLIC_BASE_URL must be an absolute https URL "
                "in production",
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
