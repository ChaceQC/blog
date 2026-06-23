from tests.admin_files_api_helpers import (
    FailIfUploadCalledFileService,
    FakeEncryptionSessionManager,
    FakeLogService,
    SmallUploadSettings,
    TestClient,
    _png_bytes,
    app,
    get_current_admin_user,
    get_encryption_session_manager,
    get_file_service,
    get_log_service,
    get_settings,
    override_admin_user,
    override_file_service,
)


def test_admin_files_use_content_encryption_profile() -> None:
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    client = TestClient(app)

    try:
        response = client.get(
            "/api/admin/files?limit=1&offset=0",
            headers={
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["original_name"] == "cover.png"

def test_admin_file_upload_accepts_multipart_and_csrf() -> None:
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/files",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
            cookies={"blog_admin_csrf": "csrf-token"},
            data={
                "visibility": "public",
                "alt_text": "封面图",
                "public_listed": "true",
            },
            files={"file": ("cover.png", _png_bytes(), "image/png")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["object_key"] == "public/2026/06/cover.png"
    assert logs.audit_items[0]["action"] == "file.upload"
    assert logs.audit_items[0]["entity_type"] == "file"
    assert logs.audit_items[0]["after_json"] == {
        "visibility": "public",
        "public_listed": True,
        "status": "active",
    }
    assert "original_name" not in logs.audit_items[0]["after_json"]
    assert "mime_type" not in logs.audit_items[0]["after_json"]

def test_admin_file_upload_rejects_oversized_body_before_service() -> None:
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = lambda: FailIfUploadCalledFileService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_settings] = lambda: SmallUploadSettings()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/files",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
            cookies={"blog_admin_csrf": "csrf-token"},
            data={
                "visibility": "public",
                "alt_text": "封面图",
                "public_listed": "true",
            },
            files={"file": ("cover.png", b"012345678", "image/png")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"] == "file is too large"
    assert manager.payload is None

def test_admin_file_delete_requires_csrf() -> None:
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.delete(
            "/api/admin/files/1",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
            cookies={"blog_admin_csrf": "csrf-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["status"] == "deleted"
    assert logs.audit_items[0]["action"] == "file.delete"
    assert logs.audit_items[0]["entity_id"] == 1
    assert logs.audit_items[0]["after_json"]["status"] == "deleted"

def test_admin_file_temporary_url_uses_encrypted_response() -> None:
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/admin/files/1/temporary-url",
            headers={
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert (
        manager.payload["url"]
        == "/api/public/files/1/download?token=signed-token-value"
    )
    assert manager.payload["expires_at"] == "2026-06-16T00:00:00Z"
    assert logs.items[0]["access_type"] == "admin_file_temporary_url"
