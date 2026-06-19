from tests.admin_files_api_helpers import (
    FakeDeniedAdminDownloadFileService,
    FakeDownloadFileService,
    FakeLogService,
    TestClient,
    _assert_signed_cache_headers,
    _png_bytes,
    app,
    create_admin_file_preview_token,
    get_current_admin_user,
    get_file_service,
    get_log_service,
    get_settings,
    override_admin_user,
)


def test_admin_file_download_allows_private_file_with_admin_auth(tmp_path) -> None:
    file_path = tmp_path / "private-note.pdf"
    file_path.write_bytes(b"%PDF-1.7\n")
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get("/api/admin/files/1/download")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.7\n"
    assert logs.items[0]["access_type"] == "admin_file_download"
    assert logs.items[0]["entity_id"] == 1
    assert logs.items[0]["detail_json"] is None

def test_admin_file_download_records_denied_access() -> None:
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDeniedAdminDownloadFileService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get("/api/admin/files/1/download")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "file is not downloadable"
    assert logs.items[0]["access_type"] == "admin_file_download"
    assert logs.items[0]["status_code"] == 403

def test_admin_file_thumbnail_returns_small_preview(tmp_path) -> None:
    file_path = tmp_path / "cover.jpg"
    file_path.write_bytes(_png_bytes())
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    client = TestClient(app)

    try:
        response = client.get("/api/admin/files/1/thumbnail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == _png_bytes()

def test_admin_file_preview_uses_signed_cache_headers(tmp_path) -> None:
    file_path = tmp_path / "cover.png"
    file_path.write_bytes(_png_bytes())
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    client = TestClient(app)
    settings = get_settings()
    access = create_admin_file_preview_token(
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    try:
        response = client.get(
            "/api/admin/files/1/preview",
            params={"expires": access.expires, "token": access.token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == _png_bytes()
    _assert_signed_cache_headers(response)
