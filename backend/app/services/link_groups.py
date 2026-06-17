from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.link import FriendLinkGroup
from app.models.site import SiteNavGroup
from app.services.links import ALLOWED_SITE_NAV_VISIBILITIES


class LinkGroupNotFoundError(Exception):
    pass


class LinkGroupSlugExistsError(Exception):
    pass


class InvalidLinkGroupValueError(Exception):
    pass


class LinkGroupRepositoryProtocol(Protocol):
    async def list_friend_link_groups(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[FriendLinkGroup]: ...

    async def get_friend_link_group(
        self,
        group_id: int,
    ) -> FriendLinkGroup | None: ...

    async def get_friend_link_group_by_slug(
        self,
        slug: str,
    ) -> FriendLinkGroup | None: ...

    async def create_friend_link_group(
        self,
        *,
        name: str,
        slug: str,
        sort_order: int,
    ) -> FriendLinkGroup: ...

    async def list_site_nav_groups(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SiteNavGroup]: ...

    async def get_site_nav_group(self, group_id: int) -> SiteNavGroup | None: ...

    async def get_site_nav_group_by_slug(self, slug: str) -> SiteNavGroup | None: ...

    async def create_site_nav_group(
        self,
        *,
        name: str,
        slug: str,
        description: str | None,
        visibility: str,
        sort_order: int,
    ) -> SiteNavGroup: ...

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...


@dataclass(frozen=True)
class AdminFriendLinkGroupRecord:
    id: int
    name: str
    slug: str
    sort_order: int
    created_at: datetime | None


@dataclass(frozen=True)
class AdminSiteNavGroupRecord:
    id: int
    name: str
    slug: str
    description: str | None
    visibility: str
    sort_order: int
    created_at: datetime | None


@dataclass(frozen=True)
class CreateFriendLinkGroupCommand:
    name: str
    slug: str
    sort_order: int


@dataclass(frozen=True)
class CreateSiteNavGroupCommand:
    name: str
    slug: str
    description: str | None
    visibility: str
    sort_order: int


class LinkGroupService:
    def __init__(self, *, repository: LinkGroupRepositoryProtocol) -> None:
        self.repository = repository

    async def list_friend_link_groups(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[AdminFriendLinkGroupRecord]:
        groups = await self.repository.list_friend_link_groups(
            limit=limit,
            offset=offset,
        )
        return [self._friend_link_group_record(group) for group in groups]

    async def create_friend_link_group(
        self,
        command: CreateFriendLinkGroupCommand,
    ) -> AdminFriendLinkGroupRecord:
        await self._ensure_friend_group_slug_available(command.slug)
        group = await self.repository.create_friend_link_group(
            name=command.name,
            slug=command.slug,
            sort_order=command.sort_order,
        )
        await self.repository.commit()
        await self.repository.refresh(group)
        return self._friend_link_group_record(group)

    async def update_friend_link_group(
        self,
        *,
        group_id: int,
        changes: dict[str, object],
    ) -> AdminFriendLinkGroupRecord:
        group = await self.repository.get_friend_link_group(group_id)
        if group is None:
            raise LinkGroupNotFoundError("friend link group not found")

        slug = changes.get("slug")
        if isinstance(slug, str):
            await self._ensure_friend_group_slug_available(slug, current_id=group.id)

        for field in ("name", "slug", "sort_order"):
            if field in changes:
                setattr(group, field, changes[field])

        await self.repository.commit()
        await self.repository.refresh(group)
        return self._friend_link_group_record(group)

    async def list_site_nav_groups(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[AdminSiteNavGroupRecord]:
        groups = await self.repository.list_site_nav_groups(
            limit=limit,
            offset=offset,
        )
        return [self._site_nav_group_record(group) for group in groups]

    async def create_site_nav_group(
        self,
        command: CreateSiteNavGroupCommand,
    ) -> AdminSiteNavGroupRecord:
        self._ensure_site_nav_group_visibility(command.visibility)
        await self._ensure_site_group_slug_available(command.slug)
        group = await self.repository.create_site_nav_group(
            name=command.name,
            slug=command.slug,
            description=command.description,
            visibility=command.visibility,
            sort_order=command.sort_order,
        )
        await self.repository.commit()
        await self.repository.refresh(group)
        return self._site_nav_group_record(group)

    async def update_site_nav_group(
        self,
        *,
        group_id: int,
        changes: dict[str, object],
    ) -> AdminSiteNavGroupRecord:
        group = await self.repository.get_site_nav_group(group_id)
        if group is None:
            raise LinkGroupNotFoundError("site nav group not found")

        slug = changes.get("slug")
        if isinstance(slug, str):
            await self._ensure_site_group_slug_available(slug, current_id=group.id)
        visibility = changes.get("visibility")
        if isinstance(visibility, str):
            self._ensure_site_nav_group_visibility(visibility)

        for field in ("name", "slug", "description", "visibility", "sort_order"):
            if field in changes:
                setattr(group, field, changes[field])

        await self.repository.commit()
        await self.repository.refresh(group)
        return self._site_nav_group_record(group)

    async def _ensure_friend_group_slug_available(
        self,
        slug: str,
        *,
        current_id: int | None = None,
    ) -> None:
        group = await self.repository.get_friend_link_group_by_slug(slug)
        if group is not None and group.id != current_id:
            raise LinkGroupSlugExistsError("friend link group slug exists")

    async def _ensure_site_group_slug_available(
        self,
        slug: str,
        *,
        current_id: int | None = None,
    ) -> None:
        group = await self.repository.get_site_nav_group_by_slug(slug)
        if group is not None and group.id != current_id:
            raise LinkGroupSlugExistsError("site nav group slug exists")

    def _ensure_site_nav_group_visibility(self, visibility: str) -> None:
        if visibility not in ALLOWED_SITE_NAV_VISIBILITIES:
            raise InvalidLinkGroupValueError("invalid site nav group visibility")

    def _friend_link_group_record(
        self,
        group: FriendLinkGroup,
    ) -> AdminFriendLinkGroupRecord:
        return AdminFriendLinkGroupRecord(
            id=group.id,
            name=group.name,
            slug=group.slug,
            sort_order=group.sort_order,
            created_at=group.created_at,
        )

    def _site_nav_group_record(self, group: SiteNavGroup) -> AdminSiteNavGroupRecord:
        return AdminSiteNavGroupRecord(
            id=group.id,
            name=group.name,
            slug=group.slug,
            description=group.description,
            visibility=group.visibility,
            sort_order=group.sort_order,
            created_at=group.created_at,
        )
