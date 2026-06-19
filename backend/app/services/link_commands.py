from dataclasses import dataclass
from typing import Any

from app.services.update_commands import UNSET, UnsetType


@dataclass(frozen=True)
class CreateFriendLinkCommand:
    group_id: int | None
    name: str
    url: str
    avatar_url: str | None
    description: str | None
    rss_url: str | None
    status: str
    sort_order: int


@dataclass(frozen=True)
class CreateSiteNavItemCommand:
    group_id: int | None
    title: str
    url: str
    icon_url: str | None
    description: str | None
    tags_json: dict[str, Any] | None
    open_target: str
    visibility: str
    sort_order: int


@dataclass(frozen=True)
class UpdateFriendLinkCommand:
    group_id: int | None | UnsetType = UNSET
    name: str | UnsetType = UNSET
    url: str | UnsetType = UNSET
    avatar_url: str | None | UnsetType = UNSET
    description: str | None | UnsetType = UNSET
    rss_url: str | None | UnsetType = UNSET
    status: str | UnsetType = UNSET
    sort_order: int | UnsetType = UNSET


@dataclass(frozen=True)
class UpdateSiteNavItemCommand:
    group_id: int | None | UnsetType = UNSET
    title: str | UnsetType = UNSET
    url: str | UnsetType = UNSET
    icon_url: str | None | UnsetType = UNSET
    description: str | None | UnsetType = UNSET
    tags_json: dict[str, Any] | None | UnsetType = UNSET
    open_target: str | UnsetType = UNSET
    visibility: str | UnsetType = UNSET
    sort_order: int | UnsetType = UNSET
