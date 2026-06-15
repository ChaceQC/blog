from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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

    allowed_hosts: list[str]
    cors_origins: list[str]
    docs_enabled: bool
    readiness_check_database: bool
    upload_root: Path

    dev_server_host: str
    dev_server_port: int = Field(ge=1024, le=65535)

    model_config = SettingsConfigDict(
        env_file=(".env.example", ".env"),
        env_file_encoding="utf-8",
        env_prefix="BLOG_",
        case_sensitive=False,
    )

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
        if "*" in self.allowed_hosts:
            raise ValueError("BLOG_ALLOWED_HOSTS cannot contain '*' in production")
        if "*" in self.cors_origins:
            raise ValueError("BLOG_CORS_ORIGINS cannot contain '*' in production")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
