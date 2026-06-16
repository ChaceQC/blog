from collections.abc import Sequence

from sqlalchemy import select
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

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)
