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
