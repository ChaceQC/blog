from tests.admin_files_api_helpers import (
    UTC,
    FakeDownloadFileService,
    FakeLogService,
    FakePublicFileContentService,
    TestClient,
    _assert_signed_cache_headers,
    _png_bytes,
    app,
    create_article_render_token,
    datetime,
    get_content_service,
    get_file_service,
    get_log_service,
    get_settings,
)


def test_post_file_render_uses_article_image_endpoint(tmp_path) -> None:
    file_path = tmp_path / "cover.png"
    file_path.write_bytes(_png_bytes())
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicFileContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)
    settings = get_settings()
    access = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    try:
        response = client.get(
            "/api/public/posts/public-post/files/1/render",
            params={"expires": access.expires, "token": access.token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == _png_bytes()
    _assert_signed_cache_headers(response)
    assert logs.items[0]["access_type"] == "post_image_render"
    assert logs.items[0]["path"] == "/api/public/posts/public-post/files/1/render"

def test_post_file_thumbnail_uses_article_image_endpoint(tmp_path) -> None:
    file_path = tmp_path / "cover.jpg"
    file_path.write_bytes(_png_bytes())
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicFileContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)
    settings = get_settings()
    access = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    try:
        response = client.get(
            "/api/public/posts/public-post/files/1/thumbnail",
            params={"expires": access.expires, "token": access.token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == _png_bytes()
    _assert_signed_cache_headers(response)
    assert logs.items[0]["access_type"] == "post_image_thumbnail"
    assert logs.items[0]["path"] == "/api/public/posts/public-post/files/1/thumbnail"

def test_article_render_token_is_stable_inside_cache_window(monkeypatch) -> None:
    settings = get_settings()
    first_now = datetime.fromtimestamp(1_800_000_010, UTC)
    monkeypatch.setattr(
        "app.services.file_tokens.utc_now",
        lambda: first_now,
    )
    first = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    monkeypatch.setattr(
        "app.services.file_tokens.utc_now",
        lambda: datetime.fromtimestamp(1_800_000_040, UTC),
    )
    second = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    monkeypatch.setattr(
        "app.services.file_tokens.utc_now",
        lambda: datetime.fromtimestamp(1_800_000_170, UTC),
    )
    third = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    assert second == first
    assert third.expires > first.expires
    assert third.token != first.token

def test_post_file_render_rejects_missing_image_token(tmp_path) -> None:
    file_path = tmp_path / "cover.png"
    file_path.write_bytes(_png_bytes())
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicFileContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get("/api/public/posts/public-post/files/1/render")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid image access"
    assert logs.items[0]["access_type"] == "post_image_render"
    assert logs.items[0]["status_code"] == 403
