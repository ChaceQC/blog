from dataclasses import dataclass

import pytest

from app.services.content import (
    ContentService,
    ContentSlugExistsError,
    CreatePageCommand,
    CreatePostCommand,
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
    word_count: int
    seo_title: str | None
    seo_description: str | None
    published_at: object | None = None


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
        self.commit_count = 0

    async def list_posts(self, *, limit: int, offset: int) -> list[FakePost]:
        return self.posts[offset : offset + limit]

    async def get_post(self, post_id: int) -> FakePost | None:
        return next((post for post in self.posts if post.id == post_id), None)

    async def get_post_by_slug(self, slug: str) -> FakePost | None:
        return next((post for post in self.posts if post.slug == slug), None)

    async def create_post(self, **payload: object) -> FakePost:
        post = FakePost(id=len(self.posts) + 1, **payload)
        self.posts.append(post)
        return post

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
        changes={"content_md": "新内容 <b>"},
    )

    assert updated.content_html == "<p>新内容 &lt;b&gt;</p>"
    assert repository.commit_count == 2
