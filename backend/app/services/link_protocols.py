from collections.abc import Sequence
from typing import Any, Protocol

from app.models.link import FriendLink
from app.models.site import SiteNavItem


class LinkRepositoryProtocol(Protocol):
    async def list_friend_links(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[FriendLink, str | None]]: ...

    async def list_public_friend_links(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[FriendLink, str | None]]: ...

    async def count_public_friend_links(self) -> int: ...

    async def list_friend_links_by_statuses(
        self,
        *,
        statuses: set[str],
        limit: int,
    ) -> Sequence[FriendLink]: ...

    async def count_friend_links_by_status(self, *, status: str) -> int: ...

    async def get_friend_link(self, link_id: int) -> FriendLink | None: ...

    async def create_friend_link(
        self,
        *,
        group_id: int | None,
        name: str,
        url: str,
        avatar_url: str | None,
        description: str | None,
        rss_url: str | None,
        status: str,
        sort_order: int,
    ) -> FriendLink: ...

    async def delete_friend_link(self, link_id: int) -> None: ...

    async def list_site_nav_items(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[SiteNavItem, str | None, str | None]]: ...

    async def list_public_site_nav_items(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[SiteNavItem, str | None, str | None]]: ...

    async def count_public_site_nav_items(self) -> int: ...

    async def get_site_nav_item(self, item_id: int) -> SiteNavItem | None: ...

    async def get_public_site_nav_item(
        self,
        item_id: int,
    ) -> SiteNavItem | None: ...

    async def increment_public_site_nav_click(
        self,
        item_id: int,
    ) -> SiteNavItem | None: ...

    async def create_site_nav_item(
        self,
        *,
        group_id: int | None,
        title: str,
        url: str,
        icon_url: str | None,
        description: str | None,
        tags_json: dict[str, Any] | None,
        open_target: str,
        visibility: str,
        sort_order: int,
    ) -> SiteNavItem: ...

    async def delete_site_nav_item(self, item_id: int) -> None: ...

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...
