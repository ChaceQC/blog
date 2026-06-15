from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Blog CMS API"
    version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    public_base_url: str = "http://localhost:5173"
    database_url: str = (
        "mysql+asyncmy://blog_app:blog_dev_password@127.0.0.1:3306/"
        "blog?charset=utf8mb4"
    )
    secret_key: str = "dev-only-change-me"

    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    docs_enabled: bool = True
    readiness_check_database: bool = False
    upload_root: Path = Path("var/uploads")

    model_config = SettingsConfigDict(
        env_file=".env",
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
