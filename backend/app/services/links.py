from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.core.site_nav_tags import normalize_site_nav_tags_json
from app.models.link import FriendLink
from app.models.site import SiteNavItem
from app.services.update_commands import UNSET, UnsetType, is_set

FriendLinkStatus = str
ALLOWED_FRIEND_LINK_STATUSES = {"pending", "healthy", "rejected"}
ALLOWED_SITE_NAV_OPEN_TARGETS = {"blank", "self"}
ALLOWED_SITE_NAV_VISIBILITIES = {"public", "hidden", "private"}


class LinkNotFoundError(Exception):
    pass


class InvalidFriendLinkStatusError(Exception):
    pass


class SiteNavItemNotFoundError(Exception):
    pass


class InvalidSiteNavItemValueError(Exception):
    pass


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

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...


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


class LinkService:
    def __init__(self, *, repository: LinkRepositoryProtocol) -> None:
        self.repository = repository

    async def list_friend_links(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[AdminFriendLinkRecord]:
        rows = await self.repository.list_friend_links(limit=limit, offset=offset)
        return [
            self._friend_link_record(link=link, group_name=group_name)
            for link, group_name in rows
        ]

    async def list_public_friend_links(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[AdminFriendLinkRecord]:
        rows = await self.repository.list_public_friend_links(
            limit=limit,
            offset=offset,
        )
        return [
            self._friend_link_record(link=link, group_name=group_name)
            for link, group_name in rows
        ]

    async def count_public_friend_links(self) -> int:
        return await self.repository.count_public_friend_links()

    async def review_friend_link(
        self,
        *,
        link_id: int,
        status: FriendLinkStatus,
    ) -> AdminFriendLinkRecord:
        if status not in ALLOWED_FRIEND_LINK_STATUSES:
            raise InvalidFriendLinkStatusError("invalid friend link status")

        link = await self.repository.get_friend_link(link_id)
        if link is None:
            raise LinkNotFoundError("friend link not found")

        link.status = status
        await self.repository.commit()
        await self.repository.refresh(link)
        return self._friend_link_record(link=link, group_name=None)

    async def create_friend_link(
        self,
        command: CreateFriendLinkCommand,
    ) -> AdminFriendLinkRecord:
        self._ensure_valid_status(command.status)
        link = await self.repository.create_friend_link(
            group_id=command.group_id,
            name=command.name,
            url=command.url,
            avatar_url=command.avatar_url,
            description=command.description,
            rss_url=command.rss_url,
            status=command.status,
            sort_order=command.sort_order,
        )
        await self.repository.commit()
        await self.repository.refresh(link)
        return self._friend_link_record(link=link, group_name=None)

    async def update_friend_link(
        self,
        *,
        link_id: int,
        command: UpdateFriendLinkCommand,
    ) -> AdminFriendLinkRecord:
        if is_set(command.status):
            self._ensure_valid_status(command.status)

        link = await self.repository.get_friend_link(link_id)
        if link is None:
            raise LinkNotFoundError("friend link not found")

        if is_set(command.group_id):
            link.group_id = command.group_id
        if is_set(command.name):
            link.name = command.name
        if is_set(command.url):
            link.url = command.url
        if is_set(command.avatar_url):
            link.avatar_url = command.avatar_url
        if is_set(command.description):
            link.description = command.description
        if is_set(command.rss_url):
            link.rss_url = command.rss_url
        if is_set(command.status):
            link.status = command.status
        if is_set(command.sort_order):
            link.sort_order = command.sort_order

        await self.repository.commit()
        await self.repository.refresh(link)
        return self._friend_link_record(link=link, group_name=None)

    async def list_site_nav_items(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[AdminSiteNavItemRecord]:
        rows = await self.repository.list_site_nav_items(limit=limit, offset=offset)
        return [
            self._site_nav_item_record(
                item=item,
                group_name=group_name,
                group_slug=group_slug,
            )
            for item, group_name, group_slug in rows
        ]

    async def list_public_site_nav_items(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[AdminSiteNavItemRecord]:
        rows = await self.repository.list_public_site_nav_items(
            limit=limit,
            offset=offset,
        )
        return [
            self._site_nav_item_record(
                item=item,
                group_name=group_name,
                group_slug=group_slug,
            )
            for item, group_name, group_slug in rows
        ]

    async def count_public_site_nav_items(self) -> int:
        return await self.repository.count_public_site_nav_items()

    async def get_public_site_nav_item(
        self,
        *,
        item_id: int,
    ) -> AdminSiteNavItemRecord:
        item = await self.repository.get_public_site_nav_item(item_id)
        if item is None:
            raise SiteNavItemNotFoundError("site nav item not found")
        return self._site_nav_item_record(item=item, group_name=None, group_slug=None)

    async def record_public_site_nav_click(
        self,
        *,
        item_id: int,
    ) -> AdminSiteNavItemRecord:
        item = await self.repository.increment_public_site_nav_click(item_id)
        if item is None:
            raise SiteNavItemNotFoundError("site nav item not found")

        await self.repository.commit()
        await self.repository.refresh(item)
        return self._site_nav_item_record(item=item, group_name=None, group_slug=None)

    async def create_site_nav_item(
        self,
        command: CreateSiteNavItemCommand,
    ) -> AdminSiteNavItemRecord:
        self._ensure_valid_site_nav_values(
            open_target=command.open_target,
            visibility=command.visibility,
        )
        tags_json = self._normalize_site_nav_tags(command.tags_json)
        item = await self.repository.create_site_nav_item(
            group_id=command.group_id,
            title=command.title,
            url=command.url,
            icon_url=command.icon_url,
            description=command.description,
            tags_json=tags_json,
            open_target=command.open_target,
            visibility=command.visibility,
            sort_order=command.sort_order,
        )
        await self.repository.commit()
        await self.repository.refresh(item)
        return self._site_nav_item_record(item=item, group_name=None, group_slug=None)

    async def update_site_nav_item(
        self,
        *,
        item_id: int,
        command: UpdateSiteNavItemCommand,
    ) -> AdminSiteNavItemRecord:
        self._ensure_valid_site_nav_values(
            open_target=command.open_target if is_set(command.open_target) else None,
            visibility=command.visibility if is_set(command.visibility) else None,
        )

        item = await self.repository.get_site_nav_item(item_id)
        if item is None:
            raise SiteNavItemNotFoundError("site nav item not found")

        if is_set(command.group_id):
            item.group_id = command.group_id
        if is_set(command.title):
            item.title = command.title
        if is_set(command.url):
            item.url = command.url
        if is_set(command.icon_url):
            item.icon_url = command.icon_url
        if is_set(command.description):
            item.description = command.description
        if is_set(command.tags_json):
            item.tags_json = self._normalize_site_nav_tags(command.tags_json)
        if is_set(command.open_target):
            item.open_target = command.open_target
        if is_set(command.visibility):
            item.visibility = command.visibility
        if is_set(command.sort_order):
            item.sort_order = command.sort_order

        await self.repository.commit()
        await self.repository.refresh(item)
        return self._site_nav_item_record(item=item, group_name=None, group_slug=None)

    def _friend_link_record(
        self,
        *,
        link: FriendLink,
        group_name: str | None,
    ) -> AdminFriendLinkRecord:
        return AdminFriendLinkRecord(
            id=link.id,
            group_id=link.group_id,
            group_name=group_name,
            name=link.name,
            url=link.url,
            avatar_url=link.avatar_url,
            description=link.description,
            rss_url=link.rss_url,
            status=link.status,
            sort_order=link.sort_order,
            last_checked_at=link.last_checked_at,
            last_status_code=link.last_status_code,
            created_at=link.created_at,
            updated_at=link.updated_at,
        )

    def _ensure_valid_status(self, status: str) -> None:
        if status not in ALLOWED_FRIEND_LINK_STATUSES:
            raise InvalidFriendLinkStatusError("invalid friend link status")

    def _ensure_valid_site_nav_values(
        self,
        *,
        open_target: str | None,
        visibility: str | None,
    ) -> None:
        if open_target is not None and open_target not in ALLOWED_SITE_NAV_OPEN_TARGETS:
            raise InvalidSiteNavItemValueError("invalid site nav open target")
        if visibility is not None and visibility not in ALLOWED_SITE_NAV_VISIBILITIES:
            raise InvalidSiteNavItemValueError("invalid site nav visibility")

    def _normalize_site_nav_tags(
        self,
        tags_json: object,
    ) -> dict[str, list[str]] | None:
        try:
            return normalize_site_nav_tags_json(tags_json)
        except ValueError as exc:
            raise InvalidSiteNavItemValueError("invalid site nav tags") from exc

    def _site_nav_item_record(
        self,
        *,
        item: SiteNavItem,
        group_name: str | None,
        group_slug: str | None,
    ) -> AdminSiteNavItemRecord:
        return AdminSiteNavItemRecord(
            id=item.id,
            group_id=item.group_id,
            group_name=group_name,
            group_slug=group_slug,
            title=item.title,
            url=item.url,
            icon_url=item.icon_url,
            description=item.description,
            tags_json=item.tags_json,
            open_target=item.open_target,
            visibility=item.visibility,
            click_count=item.click_count,
            sort_order=item.sort_order,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
