from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AdminFriendLinkRecord:
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

    def with_avatar_url(self, avatar_url: str | None) -> "AdminFriendLinkRecord":
        return AdminFriendLinkRecord(
            id=self.id,
            group_id=self.group_id,
            group_name=self.group_name,
            name=self.name,
            url=self.url,
            avatar_url=avatar_url,
            description=self.description,
            rss_url=self.rss_url,
            status=self.status,
            sort_order=self.sort_order,
            last_checked_at=self.last_checked_at,
            last_status_code=self.last_status_code,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class AdminSiteNavItemRecord:
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
    click_count: int
    sort_order: int
    created_at: datetime | None
    updated_at: datetime | None
