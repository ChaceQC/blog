from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.link import FriendLinkGroup
from app.models.site import SiteNavGroup


class LinkGroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_friend_link_groups(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[FriendLinkGroup]:
        result = await self.session.execute(
            select(FriendLinkGroup)
            .order_by(FriendLinkGroup.sort_order.asc(), FriendLinkGroup.id.asc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

    async def get_friend_link_group(
        self,
        group_id: int,
    ) -> FriendLinkGroup | None:
        result = await self.session.execute(
            select(FriendLinkGroup).where(FriendLinkGroup.id == group_id),
        )
        return result.scalar_one_or_none()

    async def get_friend_link_group_by_slug(
        self,
        slug: str,
    ) -> FriendLinkGroup | None:
        result = await self.session.execute(
            select(FriendLinkGroup).where(FriendLinkGroup.slug == slug),
        )
        return result.scalar_one_or_none()

    async def create_friend_link_group(
        self,
        *,
        name: str,
        slug: str,
        sort_order: int,
    ) -> FriendLinkGroup:
        group = FriendLinkGroup(name=name, slug=slug, sort_order=sort_order)
        self.session.add(group)
        await self.session.flush()
        return group

    async def list_site_nav_groups(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SiteNavGroup]:
        result = await self.session.execute(
            select(SiteNavGroup)
            .order_by(SiteNavGroup.sort_order.asc(), SiteNavGroup.id.asc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

    async def get_site_nav_group(self, group_id: int) -> SiteNavGroup | None:
        result = await self.session.execute(
            select(SiteNavGroup).where(SiteNavGroup.id == group_id),
        )
        return result.scalar_one_or_none()

    async def get_site_nav_group_by_slug(self, slug: str) -> SiteNavGroup | None:
        result = await self.session.execute(
            select(SiteNavGroup).where(SiteNavGroup.slug == slug),
        )
        return result.scalar_one_or_none()

    async def create_site_nav_group(
        self,
        *,
        name: str,
        slug: str,
        description: str | None,
        visibility: str,
        sort_order: int,
    ) -> SiteNavGroup:
        group = SiteNavGroup(
            name=name,
            slug=slug,
            description=description,
            visibility=visibility,
            sort_order=sort_order,
        )
        self.session.add(group)
        await self.session.flush()
        return group

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)
