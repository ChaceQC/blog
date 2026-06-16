from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FriendLinkStatus = Literal["pending", "healthy", "rejected"]


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
