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


def test_admin_friend_links_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/friend-links?limit=1",
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
    assert manager.payload["items"][0]["name"] == "静默书房"

def test_review_admin_friend_link_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(decrypted_payload={"status": "healthy"})
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/friend-links/1/review",
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
    assert manager.payload["status"] == "healthy"
    assert logs.audit_items[0]["action"] == "friend_link.review"
    assert logs.audit_items[0]["entity_type"] == "friend_link"
    assert logs.audit_items[0]["after_json"]["review_status"] == "healthy"

def test_create_admin_friend_link_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新友链",
            "url": "https://new-link.example.test",
            "description": "新的长期入口",
            "status": "pending",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/friend-links",
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
    assert manager.payload["name"] == "新友链"
    assert logs.audit_items[0]["action"] == "friend_link.create"

def test_update_admin_friend_link_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "更新后的友链",
            "description": "更新后的描述",
            "status": "healthy",
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/friend-links/1",
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
    assert manager.payload["name"] == "更新后的友链"
    assert logs.audit_items[0]["action"] == "friend_link.update"

def test_delete_admin_friend_link_requires_csrf_and_records_audit() -> None:
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
            "/api/admin/friend-links/1",
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
    assert manager.payload["name"] == "静默书房"
    assert logs.audit_items[0]["action"] == "friend_link.delete"
    assert logs.audit_items[0]["entity_type"] == "friend_link"
    assert logs.audit_items[0]["entity_id"] == 1
    assert logs.audit_items[0]["after_json"]["deleted"] is True
