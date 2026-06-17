from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.link import FriendLink, FriendLinkGroup
from app.models.site import SiteNavGroup, SiteNavItem


class LinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_friend_links(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[FriendLink, str | None]]:
        result = await self.session.execute(
            select(FriendLink, FriendLinkGroup.name)
            .outerjoin(FriendLinkGroup, FriendLinkGroup.id == FriendLink.group_id)
            .order_by(FriendLink.sort_order.asc(), FriendLink.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.all()

    async def list_public_friend_links(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[FriendLink, str | None]]:
        result = await self.session.execute(
            select(FriendLink, FriendLinkGroup.name)
            .outerjoin(FriendLinkGroup, FriendLinkGroup.id == FriendLink.group_id)
            .where(FriendLink.status == "healthy")
            .order_by(FriendLink.sort_order.asc(), FriendLink.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.all()

    async def count_public_friend_links(self) -> int:
        result = await self.session.execute(
            select(func.count(FriendLink.id)).where(FriendLink.status == "healthy"),
        )
        return int(result.scalar_one())

    async def list_healthy_friend_links_for_check(
        self,
        *,
        limit: int,
    ) -> Sequence[FriendLink]:
        result = await self.session.execute(
            select(FriendLink)
            .where(FriendLink.status == "healthy")
            .order_by(
                FriendLink.last_checked_at.is_not(None),
                FriendLink.last_checked_at.asc(),
                FriendLink.id.asc(),
            )
            .limit(limit),
        )
        return result.scalars().all()

    async def get_friend_link(self, link_id: int) -> FriendLink | None:
        result = await self.session.execute(
            select(FriendLink).where(FriendLink.id == link_id),
        )
        return result.scalar_one_or_none()

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
    ) -> FriendLink:
        link = FriendLink(
            group_id=group_id,
            name=name,
            url=url,
            avatar_url=avatar_url,
            description=description,
            rss_url=rss_url,
            status=status,
            sort_order=sort_order,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def list_site_nav_items(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[SiteNavItem, str | None, str | None]]:
        result = await self.session.execute(
            select(SiteNavItem, SiteNavGroup.name, SiteNavGroup.slug)
            .outerjoin(SiteNavGroup, SiteNavGroup.id == SiteNavItem.group_id)
            .order_by(SiteNavItem.sort_order.asc(), SiteNavItem.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.all()

    async def list_public_site_nav_items(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[SiteNavItem, str | None, str | None]]:
        result = await self.session.execute(
            select(SiteNavItem, SiteNavGroup.name, SiteNavGroup.slug)
            .outerjoin(SiteNavGroup, SiteNavGroup.id == SiteNavItem.group_id)
            .where(SiteNavItem.visibility == "public")
            .order_by(SiteNavItem.sort_order.asc(), SiteNavItem.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.all()

    async def count_public_site_nav_items(self) -> int:
        result = await self.session.execute(
            select(func.count(SiteNavItem.id)).where(
                SiteNavItem.visibility == "public",
            ),
        )
        return int(result.scalar_one())

    async def get_site_nav_item(self, item_id: int) -> SiteNavItem | None:
        result = await self.session.execute(
            select(SiteNavItem).where(SiteNavItem.id == item_id),
        )
        return result.scalar_one_or_none()

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
    ) -> SiteNavItem:
        item = SiteNavItem(
            group_id=group_id,
            title=title,
            url=url,
            icon_url=icon_url,
            description=description,
            tags_json=tags_json,
            open_target=open_target,
            visibility=visibility,
            sort_order=sort_order,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)
