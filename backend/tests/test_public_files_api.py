from tests.admin_files_api_helpers import (
    FILE_ACCESS_TOKEN_MAX_LENGTH,
    FailIfDownloadCalledFileService,
    FakeDeniedDownloadFileService,
    FakeDownloadFileService,
    FakeEncryptionSessionManager,
    FakeLogService,
    TestClient,
    _png_bytes,
    app,
    get_encryption_session_manager,
    get_file_service,
    get_log_service,
    override_file_service,
)


def test_public_file_list_uses_public_encryption_session() -> None:
    manager = FakeEncryptionSessionManager(session_id="public-session")
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files?limit=1",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["original_name"] == "cover.png"
    assert "object_key" not in manager.payload["items"][0]
    assert logs.items[0]["access_type"] == "public_files_list"
    assert logs.items[0]["path"] == "/api/public/files"

def test_public_file_temporary_url_requires_public_session() -> None:
    manager = FakeEncryptionSessionManager(session_id="public-session")
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files/1/temporary-url",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert (
        manager.payload["url"]
        == "/api/public/files/1/download?token=public-signed-token"
    )
    assert logs.items[0]["access_type"] == "public_file_temporary_url"

def test_public_file_download_uses_temporary_token(tmp_path) -> None:
    file_path = tmp_path / "cover.png"
    file_path.write_bytes(_png_bytes())
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files/1/download?token=signed-token-value",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == _png_bytes()
    assert logs.items[0]["access_type"] == "public_file_download"
    assert logs.items[0]["path"] == "/api/public/files/1/download"

def test_public_file_download_rejects_invalid_token() -> None:
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = lambda: FakeDeniedDownloadFileService()
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files/1/download?token=signed-token-value",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid file access"
    assert logs.items[0]["status_code"] == 403

def test_public_file_download_rejects_oversized_token_before_service() -> None:
    app.dependency_overrides[get_file_service] = (
        lambda: FailIfDownloadCalledFileService()
    )
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files/1/download",
            params={"token": "x" * (FILE_ACCESS_TOKEN_MAX_LENGTH + 1)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
