from tests.admin_links_api_helpers import (
    FakeEncryptionSessionManager,
    FakeLinkGroupService,
    FakeLogService,
    TestClient,
    app,
    get_current_admin_user,
    get_encryption_session_manager,
    get_link_group_service,
    get_log_service,
    override_admin_user,
)


def test_admin_friend_link_groups_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/friend-link-groups?limit=1",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["slug"] == "friends"

def test_create_admin_friend_link_group_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新友链分组",
            "slug": "new-friends",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/friend-link-groups",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
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
    assert manager.payload["name"] == "新友链分组"
    assert logs.audit_items[0]["action"] == "friend_link_group.create"

def test_update_admin_friend_link_group_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "更新后的友链分组",
            "slug": "friends-updated",
            "sort_order": 1,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/friend-link-groups/1",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
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
    assert manager.payload["name"] == "更新后的友链分组"
    assert logs.audit_items[0]["action"] == "friend_link_group.update"

def test_admin_site_nav_groups_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/site-groups?limit=1",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["slug"] == "projects"

def test_create_admin_site_nav_group_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新导航分组",
            "slug": "new-sites",
            "description": "新的导航入口集合",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/site-groups",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
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
    assert manager.payload["name"] == "新导航分组"
    assert logs.audit_items[0]["action"] == "site_nav_group.create"

def test_update_admin_site_nav_group_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "更新后的导航分组",
            "description": "更新后的入口集合",
            "visibility": "hidden",
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/site-groups/1",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
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
    assert manager.payload["name"] == "更新后的导航分组"
    assert logs.audit_items[0]["action"] == "site_nav_group.update"
