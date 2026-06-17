from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.auth import RefreshToken, User, UserRole  # noqa: E402
from app.models.file import BlogFile, FileUsage  # noqa: E402
from app.models.link import FriendLink, FriendLinkGroup  # noqa: E402
from app.models.site import SiteNavGroup, SiteNavItem  # noqa: E402


class PublicPageVerifyError(Exception):
    pass


@dataclass(frozen=True)
class RouteCheck:
    route: str
    label: str


@dataclass(frozen=True)
class ViewportCheck:
    name: str
    width: int
    height: int


ROUTES = (
    RouteCheck(route="/links?page=2", label="友链第二页"),
    RouteCheck(route="/sites?page=2", label="站点目录第二页"),
    RouteCheck(route="/files?page=2", label="公开文件第二页"),
)
VIEWPORTS = (
    ViewportCheck(name="desktop", width=1280, height=900),
    ViewportCheck(name="mobile", width=390, height=844),
)


async def verify_public_page_pagination(args: argparse.Namespace) -> dict[str, Any]:
    run_prefix = f"{args.seed_prefix}_{secrets.token_hex(4)}"
    try:
        await _seed_public_data(run_prefix)
        checks = await _check_frontend_pages(
            frontend_url=args.frontend_url,
            browser_channel=args.browser_channel,
            timeout_ms=int(args.timeout * 1000),
        )
        return {
            "ok": True,
            "prefix": run_prefix,
            "checks": checks,
        }
    finally:
        await _cleanup_public_data(run_prefix)


async def _seed_public_data(prefix: str) -> None:
    async with AsyncSessionLocal() as session:
        user = User(
            username=f"{prefix}_user",
            email=f"{prefix}@example.test",
            password_hash="disabled",
            display_name="公开分页验证",
            status=0,
        )
        friend_group = FriendLinkGroup(
            name="公开分页验证友链",
            slug=f"{prefix}_friends",
            sort_order=999_000,
        )
        site_group = SiteNavGroup(
            name="公开分页验证导航",
            slug=f"{prefix}_sites",
            description="临时公开分页验证数据",
            sort_order=999_000,
            visibility="public",
        )
        session.add_all([user, friend_group, site_group])
        await session.flush()

        for index in range(18):
            session.add(
                FriendLink(
                    group_id=friend_group.id,
                    name=f"公开分页验证友链 {index + 1:02d}",
                    url=f"https://{prefix}.friends.example.test/{index + 1:02d}",
                    avatar_url=None,
                    description="临时公开分页验证友链",
                    rss_url=None,
                    status="healthy",
                    sort_order=999_000 + index,
                ),
            )
        for index in range(12):
            session.add(
                SiteNavItem(
                    group_id=site_group.id,
                    title=f"公开分页验证导航 {index + 1:02d}",
                    url=f"https://{prefix}.sites.example.test/{index + 1:02d}",
                    icon_url=None,
                    description="临时公开分页验证入口",
                    tags_json={"tags": ["verify"]},
                    open_target="blank",
                    visibility="public",
                    click_count=0,
                    sort_order=999_000 + index,
                ),
            )
        for index in range(12):
            digest = hashlib.sha256(f"{prefix}:{index}".encode()).hexdigest()
            session.add(
                BlogFile(
                    storage="local",
                    bucket=None,
                    object_key=f"public/{prefix}/{index + 1:02d}.txt",
                    public_url=None,
                    original_name=f"public-pagination-{index + 1:02d}.txt",
                    mime_type="text/plain",
                    extension=".txt",
                    size_bytes=128 + index,
                    sha256=digest,
                    width=None,
                    height=None,
                    alt_text=None,
                    uploader_id=user.id,
                    visibility="public",
                    public_listed=True,
                    status="active",
                ),
            )
        await session.commit()


async def _check_frontend_pages(
    *,
    frontend_url: str,
    browser_channel: str,
    timeout_ms: int,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel=browser_channel,
            headless=True,
        )
        try:
            for viewport in VIEWPORTS:
                page = await browser.new_page(
                    viewport={"width": viewport.width, "height": viewport.height},
                )
                page.set_default_timeout(timeout_ms)
                try:
                    for route in ROUTES:
                        checks.append(
                            await _check_route(
                                page=page,
                                frontend_url=frontend_url,
                                route=route,
                                viewport=viewport,
                            ),
                        )
                finally:
                    await page.close()
        finally:
            await browser.close()
    return checks


async def _check_route(
    *,
    page: Any,
    frontend_url: str,
    route: RouteCheck,
    viewport: ViewportCheck,
) -> dict[str, Any]:
    url = f"{frontend_url.rstrip('/')}{route.route}"
    response = await page.goto(url, wait_until="networkidle")
    if response is None or not response.ok:
        status = response.status if response is not None else "no response"
        raise PublicPageVerifyError(f"{route.label}访问失败：{status}")

    await page.wait_for_selector(".pagination-bar")
    pager_text = await page.locator(".pagination-bar span").first.text_content()
    pager_text = (pager_text or "").strip()
    _assert_second_page_pager(route.label, pager_text)

    overflow = await _collect_overflow(page)
    if overflow["has_overflow"]:
        raise PublicPageVerifyError(
            f"{route.label}在 {viewport.name} 视口横向溢出："
            f"{json.dumps(overflow, ensure_ascii=False)}",
        )

    return {
        "route": route.route,
        "label": route.label,
        "viewport": viewport.name,
        "pager": pager_text,
        "scroll_width": overflow["document_scroll_width"],
        "client_width": overflow["document_client_width"],
    }


async def _collect_overflow(page: Any) -> dict[str, Any]:
    return await page.evaluate(
        """
        () => {
          const clientWidth = document.documentElement.clientWidth;
          const scrollWidth = Math.max(
            document.documentElement.scrollWidth,
            document.body.scrollWidth
          );
          const offenders = Array.from(document.body.querySelectorAll('*'))
            .filter((element) => {
              const style = window.getComputedStyle(element);
              if (style.display === 'none' || style.visibility === 'hidden') {
                return false;
              }
              const rect = element.getBoundingClientRect();
              return rect.width > 0 && rect.right > clientWidth + 1;
            })
            .slice(0, 5)
            .map((element) => ({
              tag: element.tagName.toLowerCase(),
              className: String(element.className || ''),
              right: Math.round(element.getBoundingClientRect().right),
              width: Math.round(element.getBoundingClientRect().width),
            }));
          return {
            has_overflow: scrollWidth > clientWidth + 1 || offenders.length > 0,
            document_scroll_width: scrollWidth,
            document_client_width: clientWidth,
            offenders,
          };
        }
        """,
    )


def _assert_second_page_pager(label: str, pager_text: str) -> None:
    if not pager_text.startswith("第 2 / "):
        raise PublicPageVerifyError(f"{label}分页条不是第二页：{pager_text!r}")
    total_text = pager_text.removeprefix("第 2 / ").removesuffix(" 页")
    try:
        total_pages = int(total_text)
    except ValueError as exc:
        raise PublicPageVerifyError(f"{label}分页总页数格式异常：{pager_text}") from exc
    if total_pages < 2:
        raise PublicPageVerifyError(f"{label}分页总页数小于 2：{pager_text}")


async def _cleanup_public_data(prefix: str) -> None:
    async with AsyncSessionLocal() as session:
        await _delete_seeded_data(session, prefix)
        await session.commit()


async def _delete_seeded_data(session: AsyncSession, prefix: str) -> None:
    postless_file_ids = await _ids_for(
        session,
        BlogFile,
        BlogFile.object_key.like(f"public/{prefix}/%"),
    )
    user_ids = await _ids_for(session, User, User.username.like(f"{prefix}%"))
    friend_group_ids = await _ids_for(
        session,
        FriendLinkGroup,
        FriendLinkGroup.slug.like(f"{prefix}%"),
    )
    site_group_ids = await _ids_for(
        session,
        SiteNavGroup,
        SiteNavGroup.slug.like(f"{prefix}%"),
    )

    if postless_file_ids:
        await session.execute(
            delete(FileUsage).where(FileUsage.file_id.in_(postless_file_ids)),
        )
    if user_ids:
        await session.execute(
            delete(RefreshToken).where(RefreshToken.user_id.in_(user_ids)),
        )
        await session.execute(delete(UserRole).where(UserRole.user_id.in_(user_ids)))
    await session.execute(
        delete(FriendLink).where(
            FriendLink.url.like(f"https://{prefix}.friends.example.test/%"),
        ),
    )
    if friend_group_ids:
        await session.execute(
            delete(FriendLink).where(FriendLink.group_id.in_(friend_group_ids)),
        )
    await session.execute(
        delete(SiteNavItem).where(
            SiteNavItem.url.like(f"https://{prefix}.sites.example.test/%"),
        ),
    )
    if site_group_ids:
        await session.execute(
            delete(SiteNavItem).where(SiteNavItem.group_id.in_(site_group_ids)),
        )
    await session.execute(
        delete(BlogFile).where(BlogFile.object_key.like(f"public/{prefix}/%")),
    )
    await session.execute(
        delete(FriendLinkGroup).where(FriendLinkGroup.slug.like(f"{prefix}%")),
    )
    await session.execute(
        delete(SiteNavGroup).where(SiteNavGroup.slug.like(f"{prefix}%")),
    )
    await session.execute(delete(User).where(User.username.like(f"{prefix}%")))


async def _ids_for(
    session: AsyncSession,
    model: Any,
    criterion: Any,
) -> list[int]:
    result = await session.execute(select(model.id).where(criterion))
    return list(result.scalars())


async def _count_seeded_rows(prefix: str) -> int:
    checks = (
        (FriendLink, FriendLink.url.like(f"https://{prefix}.friends.example.test/%")),
        (FriendLinkGroup, FriendLinkGroup.slug.like(f"{prefix}%")),
        (SiteNavItem, SiteNavItem.url.like(f"https://{prefix}.sites.example.test/%")),
        (SiteNavGroup, SiteNavGroup.slug.like(f"{prefix}%")),
        (BlogFile, BlogFile.object_key.like(f"public/{prefix}/%")),
        (User, User.username.like(f"{prefix}%")),
    )
    total = 0
    async with AsyncSessionLocal() as session:
        for model, criterion in checks:
            result = await session.execute(
                select(func.count()).select_from(model).where(criterion),
            )
            total += int(result.scalar_one())
    return total


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="验证公开友链、站点目录和文件页第二页分页与横向溢出",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("BLOG_VERIFY_FRONTEND_URL", "http://127.0.0.1:15173"),
        help="前端站点地址，默认读取 BLOG_VERIFY_FRONTEND_URL 或本地 15173",
    )
    parser.add_argument(
        "--browser-channel",
        default=os.getenv("BLOG_VERIFY_BROWSER_CHANNEL", "msedge"),
        help="Playwright Chromium 通道，默认 msedge",
    )
    parser.add_argument(
        "--seed-prefix",
        default=os.getenv("BLOG_VERIFY_PUBLIC_PAGE_PREFIX", "codex_public_pages"),
        help="临时数据前缀，脚本会自动追加随机后缀",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="页面超时秒数")
    return parser


async def main_async() -> None:
    args = build_parser().parse_args()
    result = await verify_public_page_pagination(args)
    remaining = await _count_seeded_rows(str(result["prefix"]))
    result["remaining_seed_rows"] = remaining
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
