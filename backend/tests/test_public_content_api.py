from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.public.router import get_public_content_service
from app.main import app
from app.services.content import ContentNotFoundError


class FakePublicContentService:
    async def list_public_posts(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                title="公开文章",
                slug="public-post",
                summary="摘要",
                word_count=3,
                seo_title=None,
                seo_description="SEO 摘要",
                published_at=datetime(2026, 6, 16, tzinfo=UTC),
                updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def get_public_post_by_slug(self, slug: str) -> object:
        if slug != "public-post":
            raise ContentNotFoundError("post not found")
        return SimpleNamespace(
            id=1,
            title="公开文章",
            slug="public-post",
            summary="摘要",
            content_html="<p>正文</p>",
            word_count=3,
            seo_title=None,
            seo_description="SEO 摘要",
            published_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )


def test_public_posts_returns_published_post_list() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )

    try:
        response = client.get("/api/public/posts?limit=1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["slug"] == "public-post"
    assert "content_html" not in response.json()["items"][0]


def test_public_post_detail_returns_html_content() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )

    try:
        response = client.get("/api/public/posts/public-post")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["content_html"] == "<p>正文</p>"


def test_public_post_detail_returns_404_for_missing_post() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )

    try:
        response = client.get("/api/public/posts/missing-post")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "post not found"
