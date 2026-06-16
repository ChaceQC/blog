from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

FriendLinkStatus = Literal["pending", "healthy", "rejected"]
SiteNavOpenTarget = Literal["blank", "self"]
SiteNavVisibility = Literal["public", "hidden", "private"]


class AdminFriendLinkItem(BaseModel):
    id: int
    group_id: int | None
    group_name: str | None
    name: str
    url: str
    avatar_url: str | None
    description: str | None
    rss_url: str | None
    status: str
    sort_order: int
    last_checked_at: datetime | None
    last_status_code: int | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AdminFriendLinkListResponse(BaseModel):
    items: list[AdminFriendLinkItem]

    model_config = ConfigDict(extra="forbid")


class PublicFriendLinkItem(BaseModel):
    id: int
    group_name: str | None
    name: str
    url: str
    avatar_url: str | None
    description: str | None
    sort_order: int

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicFriendLinkListResponse(BaseModel):
    items: list[PublicFriendLinkItem]

    model_config = ConfigDict(extra="forbid")


class PublicFriendLinkApplicationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=255)
    rss_url: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "url", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("avatar_url", "description", "rss_url", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("url", "avatar_url", "rss_url")
    @classmethod
    def _validate_http_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must use http or https")
        return value


class PublicFriendLinkApplicationResponse(BaseModel):
    id: int
    status: FriendLinkStatus

    model_config = ConfigDict(extra="forbid")


class FriendLinkReviewRequest(BaseModel):
    status: FriendLinkStatus

    model_config = ConfigDict(extra="forbid")


class FriendLinkCreateRequest(BaseModel):
    group_id: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=255)
    rss_url: str | None = Field(default=None, max_length=1000)
    status: FriendLinkStatus = "pending"
    sort_order: int = Field(default=0, ge=0, le=10000)

    model_config = ConfigDict(extra="forbid")


class FriendLinkUpdateRequest(BaseModel):
    group_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = Field(default=None, min_length=1, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=255)
    rss_url: str | None = Field(default=None, max_length=1000)
    status: FriendLinkStatus | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)

    model_config = ConfigDict(extra="forbid")


class AdminSiteNavItem(BaseModel):
    id: int
    group_id: int | None
    group_name: str | None
    group_slug: str | None
    title: str
    url: str
    icon_url: str | None
    description: str | None
    tags_json: dict[str, Any] | None
    open_target: str
    visibility: str
    click_count: int = Field(ge=0)
    sort_order: int
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AdminSiteNavItemListResponse(BaseModel):
    items: list[AdminSiteNavItem]

    model_config = ConfigDict(extra="forbid")


class PublicSiteNavItem(BaseModel):
    id: int
    group_name: str | None
    group_slug: str | None
    title: str
    url: str
    icon_url: str | None
    description: str | None
    tags_json: dict[str, Any] | None
    open_target: str
    sort_order: int

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicSiteNavItemListResponse(BaseModel):
    items: list[PublicSiteNavItem]

    model_config = ConfigDict(extra="forbid")


class SiteNavItemCreateRequest(BaseModel):
    group_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=1000)
    icon_url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=255)
    tags_json: dict[str, Any] | None = None
    open_target: SiteNavOpenTarget = "blank"
    visibility: SiteNavVisibility = "public"
    sort_order: int = Field(default=0, ge=0, le=10000)

    model_config = ConfigDict(extra="forbid")


class SiteNavItemUpdateRequest(BaseModel):
    group_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = Field(default=None, min_length=1, max_length=1000)
    icon_url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=255)
    tags_json: dict[str, Any] | None = None
    open_target: SiteNavOpenTarget | None = None
    visibility: SiteNavVisibility | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)

    model_config = ConfigDict(extra="forbid")
