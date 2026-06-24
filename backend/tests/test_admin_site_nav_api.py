from tests.admin_links_api_helpers import (
    FakeEncryptionSessionManager,
    FakeLinkService,
    FakeLogService,
    TestClient,
    app,
    get_current_admin_user,
    get_encryption_session_manager,
    get_link_service,
    get_log_service,
    override_admin_user,
)


def test_admin_site_items_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/site-items?limit=1",
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
    assert manager.payload["items"][0]["title"] == "博客源码"

def test_create_admin_site_item_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "新导航",
            "url": "https://nav.example.test",
            "icon_url": "https://nav.example.test/icon.svg",
            "description": "新的导航入口",
            "tags_json": {"items": [" 工具 ", "博客", "工具"]},
            "open_target": "self",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/site-items",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
                "salt_id": "test-request-salt",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.request_payload is not None
    assert manager.payload is not None
    assert manager.payload["title"] == "新导航"
    assert manager.payload["icon_url"] == "https://nav.example.test/icon.svg"
    assert manager.payload["tags_json"] == {"items": ["工具", "博客"]}
    assert manager.payload["open_target"] == "self"
    assert logs.audit_items[0]["action"] == "site_nav.create"
    assert logs.audit_items[0]["after_json"] == {"visibility": "public"}
    assert "title" not in logs.audit_items[0]["after_json"]
    assert "url" not in logs.audit_items[0]["after_json"]
    assert "tags_json" not in logs.audit_items[0]["after_json"]

def test_update_admin_site_item_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "更新后的导航",
            "description": "更新后的导航描述",
            "tags_json": {"tags": ["项目", "Demo"]},
            "visibility": "hidden",
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/site-items/1",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
                "salt_id": "test-request-salt",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.request_payload is not None
    assert manager.payload is not None
    assert manager.payload["title"] == "更新后的导航"
    assert manager.payload["tags_json"] == {"items": ["项目", "Demo"]}
    assert logs.audit_items[0]["action"] == "site_nav.update"
    assert "tags_json" in logs.audit_items[0]["after_json"]["changed_fields"]

def test_delete_admin_site_item_requires_csrf_and_records_audit() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.delete(
            "/api/admin/site-items/1",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["title"] == "博客源码"
    assert logs.audit_items[0]["action"] == "site_nav.delete"
    assert logs.audit_items[0]["entity_type"] == "site_nav_item"
    assert logs.audit_items[0]["entity_id"] == 1
    assert logs.audit_items[0]["after_json"]["deleted"] is True

def test_create_admin_site_item_rejects_invalid_tags() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "新导航",
            "url": "https://nav.example.test",
            "tags_json": {"items": ["x" * 25]},
            "open_target": "blank",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.post(
            "/api/admin/site-items",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
                "salt_id": "test-request-salt",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid encrypted request payload"
