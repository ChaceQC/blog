from app.core.config import get_settings
from app.services.avatar_cache_tokens import verify_avatar_cache_token
from tests.public_content_api_helpers import (
    FakeEncryptionSessionManager,
    FakeLogService,
    FakePublicLinkService,
    InMemoryAccessLogDedupeBackend,
    RateLimitService,
    TestClient,
    app,
    get_access_log_dedupe_backend,
    get_encryption_session_manager,
    get_link_service,
    get_log_service,
    get_rate_limit_service,
)


def test_public_friend_links_return_encrypted_list() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/friend-links?limit=1",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["name"] == "ChaceQC"
    avatar_url = manager.payload["items"][0]["avatar_url"]
    assert isinstance(avatar_url, str)
    assert avatar_url.startswith("http://testserver/api/public/avatar-cache/")
    token = avatar_url.rsplit("/", 1)[1]
    assert (
        verify_avatar_cache_token(token, secret_key=get_settings().secret_key)
        == "https://example.com/friend-avatar.png"
    )
    assert logs.items[0]["access_type"] == "public_friend_links_list"
    assert logs.items[0]["path"] == "/api/public/friend-links"

def test_public_friend_link_application_decrypts_content_request() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新朋友",
            "url": "https://friend.example.test",
            "avatar_url": "",
            "description": "新的个人站点",
        },
    )
    logs = FakeLogService()
    app.dependency_overrides[get_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        response = client.post(
            "/api/public/friend-links/applications",
            headers={"X-Encryption-Session": "public-session"},
            json={
                "session_id": "public-session",
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
    assert manager.payload["status"] == "pending"
    assert logs.items[0]["access_type"] == "public_friend_link_application"
    assert logs.items[0]["entity_id"] == 2
    assert logs.items[0]["detail_json"] is None

def test_public_friend_link_application_rejects_duplicate_url() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新朋友",
            "url": "https://friend.example.test",
        },
    )
    app.dependency_overrides[get_link_service] = lambda: FakePublicLinkService(
        duplicate_application=True,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        response = client.post(
            "/api/public/friend-links/applications",
            headers={"X-Encryption-Session": "public-session"},
            json={
                "session_id": "public-session",
                "profile": "content-v1",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "friend link application already exists"

def test_public_friend_link_application_rejects_pending_overflow() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新朋友",
            "url": "https://friend.example.test",
        },
    )
    app.dependency_overrides[get_link_service] = lambda: FakePublicLinkService(
        application_limit_exceeded=True,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        response = client.post(
            "/api/public/friend-links/applications",
            headers={"X-Encryption-Session": "public-session"},
            json={
                "session_id": "public-session",
                "profile": "content-v1",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == "too many pending friend link applications"

def test_public_site_items_return_encrypted_list() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/site-items?limit=1",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["title"] == "GitHub 仓库"
    assert logs.items[0]["access_type"] == "public_site_items_list"
    assert logs.items[0]["path"] == "/api/public/site-items"

def test_public_site_item_visit_records_click_and_redirects() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    link_service = FakePublicLinkService()
    app.dependency_overrides[get_link_service] = lambda: link_service
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_access_log_dedupe_backend] = (
        lambda: InMemoryAccessLogDedupeBackend()
    )

    try:
        response = client.get("/api/public/site-items/1/visit", follow_redirects=False)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 302
    assert response.headers["location"] == "https://github.com/ChaceQC/blog"
    assert link_service.site_nav_click_count == 1
    assert logs.items[0]["access_type"] == "public_site_item_visit"
    assert logs.items[0]["entity_id"] == 1
    assert logs.items[0]["detail_json"] is None

def test_public_site_item_visit_dedupes_repeated_click_and_log() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    link_service = FakePublicLinkService()
    dedupe_backend = InMemoryAccessLogDedupeBackend()
    app.dependency_overrides[get_link_service] = lambda: link_service
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_access_log_dedupe_backend] = lambda: dedupe_backend

    try:
        first = client.get("/api/public/site-items/1/visit", follow_redirects=False)
        second = client.get("/api/public/site-items/1/visit", follow_redirects=False)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 302
    assert second.status_code == 302
    assert first.headers["location"] == "https://github.com/ChaceQC/blog"
    assert second.headers["location"] == "https://github.com/ChaceQC/blog"
    assert link_service.site_nav_click_count == 1
    assert len(logs.items) == 1

def test_public_site_item_visit_returns_404_for_missing_item() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/api/public/site-items/404/visit")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "site nav item not found"
    assert logs.items[0]["access_type"] == "public_site_item_visit"
    assert logs.items[0]["status_code"] == 404
