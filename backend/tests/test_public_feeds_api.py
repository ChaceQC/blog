from tests.public_content_api_helpers import (
    ExplodingFeedContentService,
    FakeLogService,
    FakePublicContentService,
    FakeSettingService,
    TestClient,
    _clear_feed_response_cache,
    app,
    get_content_service,
    get_log_service,
    get_setting_service,
)


def test_rss_feed_returns_public_posts_xml() -> None:
    _clear_feed_response_cache()
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/rss.xml")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")
    assert response.headers["cache-control"] == (
        "public, max-age=300, stale-while-revalidate=60"
    )
    assert response.headers["etag"]
    assert "<title>恬妡的小屋</title>" in response.text
    assert "<title>SEO 标题</title>" in response.text
    assert "http://127.0.0.1:15173/posts/public-post" in response.text
    assert "SEO &lt;摘要&gt;" in response.text
    assert "<category>FastAPI</category>" in response.text
    assert logs.items[0]["access_type"] == "public_rss"
    assert logs.items[0]["detail_json"] is None

def test_rss_feed_returns_304_without_access_log_for_matching_etag() -> None:
    _clear_feed_response_cache()
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        first = client.get("/rss.xml")
        logs.items.clear()
        second = client.get(
            "/rss.xml",
            headers={"If-None-Match": first.headers["etag"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["etag"] == first.headers["etag"]
    assert logs.items == []

def test_rss_feed_cached_etag_short_circuits_before_queries() -> None:
    _clear_feed_response_cache()
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        first = client.get("/rss.xml")
        logs.items.clear()
        app.dependency_overrides[get_content_service] = (
            lambda: ExplodingFeedContentService()
        )
        second = client.get(
            "/rss.xml",
            headers={"If-None-Match": first.headers["etag"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 304
    assert logs.items == []

def test_sitemap_returns_public_post_urls_xml() -> None:
    _clear_feed_response_cache()
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/sitemap.xml")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert response.headers["etag"]
    assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in (
        response.text
    )
    assert "<loc>http://127.0.0.1:15173/</loc>" in response.text
    assert "<loc>http://127.0.0.1:15173/posts</loc>" in response.text
    assert (
        "<loc>http://127.0.0.1:15173/posts/public-post</loc>" in response.text
    )
    assert (
        "<loc>http://127.0.0.1:15173/categories/category-a</loc>" in response.text
    )
    assert "<loc>http://127.0.0.1:15173/tags/fastapi</loc>" in response.text
    assert "<lastmod>2026-06-17</lastmod>" in response.text
    assert logs.items[0]["access_type"] == "public_sitemap"
    assert logs.items[0]["detail_json"] is None

def test_sitemap_cached_etag_short_circuits_before_queries() -> None:
    _clear_feed_response_cache()
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        first = client.get("/sitemap.xml")
        logs.items.clear()
        app.dependency_overrides[get_content_service] = (
            lambda: ExplodingFeedContentService()
        )
        second = client.get(
            "/sitemap.xml",
            headers={"If-None-Match": first.headers["etag"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 304
    assert logs.items == []

def test_robots_txt_points_to_sitemap_and_hides_admin_paths() -> None:
    _clear_feed_response_cache()
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/robots.txt")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in response.text
    assert "Allow: /" in response.text
    assert "Disallow: /admin" in response.text
    assert "Disallow: /api/admin/" in response.text
    assert "Sitemap: http://127.0.0.1:15173/sitemap.xml" in response.text
    assert logs.items[0]["access_type"] == "public_robots"
