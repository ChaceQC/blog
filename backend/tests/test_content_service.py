from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.services.content import (
    ContentService,
    ContentSlugExistsError,
    CreatePageCommand,
    CreatePostCommand,
    UpdatePageCommand,
    UpdatePostCommand,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class FakePost:
    id: int
    title: str
    slug: str
    summary: str | None
    content_md: str
    content_html: str
    author_id: int
    status: str
    visibility: str
    cover_file_id: int | None
    word_count: int
    seo_title: str | None
    seo_description: str | None
    seo_keywords: str | None = None
    category_names: list[str] = field(default_factory=list)
    tag_names: list[str] = field(default_factory=list)
    published_at: object | None = None
    updated_at: object | None = None


@dataclass
class FakePage:
    id: int
    title: str
    slug: str
    content_md: str
    content_html: str
    status: str
    show_in_nav: bool
    sort_order: int
    seo_title: str | None
    seo_description: str | None


class FakeContentRepository:
    def __init__(self) -> None:
        self.posts: list[FakePost] = []
        self.pages: list[FakePage] = []
        self.file_ids: set[int] = set()
        self.file_usages: dict[tuple[str, int], list[tuple[int, str]]] = {}
        self.post_categories: dict[int, list[str]] = {}
        self.post_tags: dict[int, list[str]] = {}
        self.commit_count = 0

    async def list_posts(self, *, limit: int, offset: int) -> list[FakePost]:
        return self.posts[offset : offset + limit]

    async def list_public_posts(
        self,
        *,
        limit: int,
        offset: int,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> list[FakePost]:
        assert category_slug is None
        assert tag_slug is None
        return [
            post
            for post in self.posts
            if post.status == "published" and post.visibility == "public"
        ][offset : offset + limit]

    async def get_post(self, post_id: int) -> FakePost | None:
        return next((post for post in self.posts if post.id == post_id), None)

    async def get_post_by_slug(self, slug: str) -> FakePost | None:
        return next((post for post in self.posts if post.slug == slug), None)

    async def get_public_post_by_slug(self, slug: str) -> FakePost | None:
        return next(
            (
                post
                for post in self.posts
                if post.slug == slug
                and post.status == "published"
                and post.visibility == "public"
            ),
            None,
        )

    async def create_post(self, **payload: object) -> FakePost:
        post = FakePost(id=len(self.posts) + 1, **payload)
        self.posts.append(post)
        return post

    async def file_exists(self, file_id: int) -> bool:
        return file_id in self.file_ids

    async def replace_file_usages(
        self,
        *,
        entity_type: str,
        entity_id: int,
        usages: list[tuple[int, str]],
    ) -> None:
        self.file_usages[(entity_type, entity_id)] = list(usages)

    async def replace_post_categories(
        self,
        *,
        post_id: int,
        category_names: list[str],
    ) -> None:
        self.post_categories[post_id] = list(category_names)
        post = await self.get_post(post_id)
        if post is not None:
            post.category_names = list(category_names)

    async def replace_post_tags(
        self,
        *,
        post_id: int,
        tag_names: list[str],
    ) -> None:
        self.post_tags[post_id] = list(tag_names)
        post = await self.get_post(post_id)
        if post is not None:
            post.tag_names = list(tag_names)

    async def list_pages(self, *, limit: int, offset: int) -> list[FakePage]:
        return self.pages[offset : offset + limit]

    async def get_page(self, page_id: int) -> FakePage | None:
        return next((page for page in self.pages if page.id == page_id), None)

    async def get_page_by_slug(self, slug: str) -> FakePage | None:
        return next((page for page in self.pages if page.slug == slug), None)

    async def create_page(self, **payload: object) -> FakePage:
        page = FakePage(id=len(self.pages) + 1, **payload)
        self.pages.append(page)
        return page

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, instance: object) -> None:
        return None


@pytest.mark.anyio
async def test_create_post_renders_safe_html_and_counts_words() -> None:
    repository = FakeContentRepository()
    service = ContentService(repository=repository)

    post = await service.create_post(
        CreatePostCommand(
            title="第一篇文章",
            slug="first-post",
            summary="摘要",
            content_md="hello <script>\n\nworld",
            author_id=1,
            status="draft",
            visibility="public",
            cover_file_id=None,
            seo_title=None,
            seo_description=None,
        ),
    )

    assert post.content_html == "<p>hello &lt;script&gt;</p>\n<p>world</p>"
    assert post.word_count == 3
    assert repository.commit_count == 1


@pytest.mark.anyio
async def test_create_post_rejects_duplicate_slug() -> None:
    repository = FakeContentRepository()
    service = ContentService(repository=repository)
    command = CreatePostCommand(
        title="第一篇文章",
        slug="first-post",
        summary=None,
        content_md="正文",
        author_id=1,
        status="draft",
        visibility="public",
        cover_file_id=None,
        seo_title=None,
        seo_description=None,
    )
    await service.create_post(command)

    with pytest.raises(ContentSlugExistsError):
        await service.create_post(command)


@pytest.mark.anyio
async def test_update_page_rerenders_content() -> None:
    repository = FakeContentRepository()
    service = ContentService(repository=repository)
    page = await service.create_page(
        CreatePageCommand(
            title="关于",
            slug="about",
            content_md="旧内容",
            status="draft",
            show_in_nav=True,
            sort_order=0,
            seo_title=None,
            seo_description=None,
        ),
    )

    updated = await service.update_page(
        page_id=page.id,
        command=UpdatePageCommand(content_md="新内容 <b>"),
    )

    assert updated.content_html == "<p>新内容 &lt;b&gt;</p>"
    assert repository.commit_count == 2


@pytest.mark.anyio
async def test_list_public_posts_only_returns_published_public_posts() -> None:
    repository = FakeContentRepository()
    service = ContentService(repository=repository)
    await service.create_post(
        CreatePostCommand(
            title="公开文章",
            slug="public-post",
            summary=None,
            content_md="正文",
            author_id=1,
            status="published",
            visibility="public",
            cover_file_id=None,
            seo_title=None,
            seo_description=None,
        ),
    )
    await service.create_post(
        CreatePostCommand(
            title="隐藏文章",
            slug="hidden-post",
            summary=None,
            content_md="正文",
            author_id=1,
            status="published",
            visibility="hidden",
            cover_file_id=None,
            seo_title=None,
            seo_description=None,
        ),
    )

    posts = await service.list_public_posts(limit=10, offset=0)
    post = await service.get_public_post_by_slug("public-post")

    assert [item.slug for item in posts] == ["public-post"]
    assert post.title == "公开文章"


@pytest.mark.anyio
async def test_create_post_records_cover_and_body_file_usages() -> None:
    repository = FakeContentRepository()
    repository.file_ids.update({3, 5})
    service = ContentService(repository=repository)

    post = await service.create_post(
        CreatePostCommand(
            title="带图文章",
            slug="image-post",
            summary=None,
            content_md="![配图](/api/public/posts/image-post/files/5/render)",
            author_id=1,
            status="draft",
            visibility="public",
            cover_file_id=3,
            seo_title=None,
            seo_description=None,
        ),
    )

    assert repository.file_usages[("post", post.id)] == [
        (3, "cover"),
        (5, "post_body"),
    ]


@pytest.mark.anyio
async def test_create_post_records_taxonomy_and_scheduled_time() -> None:
    repository = FakeContentRepository()
    service = ContentService(repository=repository)
    scheduled_at = datetime.now(UTC) + timedelta(days=1)

    post = await service.create_post(
        CreatePostCommand(
            title="定时文章",
            slug="scheduled-post",
            summary=None,
            content_md="正文",
            author_id=1,
            status="scheduled",
            visibility="public",
            cover_file_id=None,
            seo_title="SEO 标题",
            seo_description="SEO 描述",
            seo_keywords="博客,定时",
            category_names=["技术", "技术", " 随笔 "],
            tag_names=["FastAPI", "React"],
            published_at=scheduled_at,
        ),
    )

    assert post.published_at == scheduled_at
    assert post.seo_keywords == "博客,定时"
    assert post.category_names == ["技术", "随笔"]
    assert post.tag_names == ["FastAPI", "React"]
    assert repository.post_categories[post.id] == ["技术", "随笔"]
    assert repository.post_tags[post.id] == ["FastAPI", "React"]


@pytest.mark.anyio
async def test_update_post_replaces_file_usages() -> None:
    repository = FakeContentRepository()
    repository.file_ids.update({1, 2, 8})
    service = ContentService(repository=repository)
    post = await service.create_post(
        CreatePostCommand(
            title="旧文章",
            slug="old-post",
            summary=None,
            content_md="![旧图](/api/public/posts/old-post/files/1/render)",
            author_id=1,
            status="draft",
            visibility="public",
            cover_file_id=2,
            seo_title=None,
            seo_description=None,
        ),
    )

    await service.update_post(
        post_id=post.id,
        command=UpdatePostCommand(
            cover_file_id=None,
            content_md="![新图](/api/public/posts/old-post/files/8/render)",
        ),
    )

    assert repository.file_usages[("post", post.id)] == [(8, "post_body")]
