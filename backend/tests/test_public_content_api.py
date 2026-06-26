from tests.public_content_api_helpers import (
    ExplodingPublicContentService,
    FakeEncryptionSessionManager,
    FakeLogService,
    FakePostInteractionService,
    FakePublicContentService,
    TestClient,
    app,
    get_content_service,
    get_encryption_session_manager,
    get_log_service,
    get_post_interaction_service,
)


def fingerprint_payload() -> dict[str, object]:
    return {
        "fingerprint": {
            "version": "web-v1",
            "visitor_id": "local-visitor-id-0123456789",
            "browser_hash": "a" * 64,
            "device_hash": "b" * 64,
            "composite_hash": "c" * 64,
            "timezone": "Asia/Shanghai",
            "language": "zh-CN",
            "platform": "Win32",
            "screen": "1536x864x24",
            "created_at_ms": 1782460800000,
        },
    }


def test_public_posts_returns_published_post_list() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/posts?limit=1",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["slug"] == "public-post"
    assert "content_html" not in manager.payload["items"][0]
    assert manager.payload["items"][0]["word_count"] == 8
    assert manager.payload["items"][0]["view_count"] == 649
    assert manager.payload["items"][0]["like_count"] == 11
    assert manager.payload["items"][0]["seo_keywords"] == "博客,验证"
    assert manager.payload["items"][0]["category_names"] == ["技术"]
    assert manager.payload["items"][0]["tag_names"] == ["FastAPI", "React"]
    assert (
        "/api/public/posts/public-post/files/1/thumbnail?expires="
        in str(manager.payload["items"][0]["cover_image_url"])
    )
    assert logs.items[0]["access_type"] == "public_posts_list"
    assert logs.items[0]["path"] == "/api/public/posts"

def test_public_posts_validate_session_before_query() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_content_service] = (
        lambda: ExplodingPublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.get("/api/public/posts?limit=1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "missing encryption session"

def test_public_posts_rejects_oversized_offset() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/public/posts?limit=1&offset=10001",
        headers={
            "X-Encryption-Session": "public-session",
            "X-Encryption-Response-Salt": "test-response-salt",
        },
    )

    assert response.status_code == 422

def test_public_posts_accept_category_and_tag_filters() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/posts?limit=2&category=category-a&tag=fastapi",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["slug"] == "public-post"
    assert logs.items[0]["access_type"] == "public_posts_list"
    assert logs.items[0]["path"] == "/api/public/posts"

def test_public_categories_return_encrypted_list() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/categories?limit=2",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0] == {
        "id": 1,
        "name": "技术",
        "slug": "category-a",
        "post_count": 3,
    }
    assert logs.items[0]["access_type"] == "public_categories_list"
    assert logs.items[0]["path"] == "/api/public/categories"

def test_public_category_detail_returns_encrypted_item() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/categories/category-a",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload == {
        "id": 1,
        "name": "技术",
        "slug": "category-a",
        "post_count": 3,
    }
    assert logs.items[0]["access_type"] == "public_category_detail"
    assert logs.items[0]["path"] == "/api/public/categories/category-a"

def test_public_category_detail_returns_404_for_missing_category() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/categories/missing-category",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "category not found"
    assert logs.items[0]["status_code"] == 404

def test_public_tags_return_encrypted_list() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/tags?limit=2",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0] == {
        "id": 1,
        "name": "FastAPI",
        "slug": "fastapi",
        "post_count": 2,
    }
    assert logs.items[0]["access_type"] == "public_tags_list"
    assert logs.items[0]["path"] == "/api/public/tags"

def test_public_tag_detail_returns_encrypted_item() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/tags/fastapi",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload == {
        "id": 1,
        "name": "FastAPI",
        "slug": "fastapi",
        "post_count": 2,
    }
    assert logs.items[0]["access_type"] == "public_tag_detail"
    assert logs.items[0]["path"] == "/api/public/tags/fastapi"

def test_public_tag_detail_returns_404_for_missing_tag() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/tags/missing-tag",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "tag not found"
    assert logs.items[0]["status_code"] == 404

def test_public_post_detail_returns_html_content() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/posts/public-post",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert (
        'src="/api/public/posts/public-post/files/1/render?expires='
        in str(manager.payload["content_html"])
    )
    assert manager.payload["word_count"] == 8
    assert manager.payload["view_count"] == 649
    assert manager.payload["like_count"] == 11
    assert (
        "/api/public/posts/public-post/files/1/thumbnail?expires="
        in str(manager.payload["cover_image_url"])
    )
    assert manager.payload["seo_keywords"] == "博客,验证"
    assert manager.payload["category_names"] == ["技术"]
    assert manager.payload["tag_names"] == ["FastAPI", "React"]
    assert "token=" in str(manager.payload["content_html"])
    assert logs.items[0]["access_type"] == "public_post_detail"
    assert logs.items[0]["path"] == "/api/public/posts/public-post"

def test_public_post_view_records_with_fingerprint() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager(fingerprint_payload())
    interactions = FakePostInteractionService()
    logs = FakeLogService()
    app.dependency_overrides[get_post_interaction_service] = lambda: interactions
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/public/posts/public-post/view",
            json={
                "session_id": "public-session",
                "profile": "content-v1",
                "salt_id": "request-salt",
                "nonce": "nonce",
                "ciphertext": "ciphertext",
            },
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.payload == {
        "view_count": 650,
        "like_count": 11,
        "liked": False,
    }
    assert interactions.views[0]["slug"] == "public-post"
    assert interactions.views[0]["fingerprint"].version == "web-v1"
    assert logs.items[0]["access_type"] == "public_post_view"

def test_public_post_like_sets_target_state() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager(
        {**fingerprint_payload(), "liked": True},
    )
    interactions = FakePostInteractionService()
    app.dependency_overrides[get_post_interaction_service] = lambda: interactions
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.post(
            "/api/public/posts/public-post/like",
            json={
                "session_id": "public-session",
                "profile": "content-v1",
                "salt_id": "request-salt",
                "nonce": "nonce",
                "ciphertext": "ciphertext",
            },
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.payload == {
        "view_count": 650,
        "like_count": 12,
        "liked": True,
    }
    assert interactions.likes[0]["liked"] is True

def test_public_post_like_rejects_delta_payload() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager(
        {**fingerprint_payload(), "liked": True, "delta": 99},
    )
    interactions = FakePostInteractionService()
    app.dependency_overrides[get_post_interaction_service] = lambda: interactions
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.post(
            "/api/public/posts/public-post/like",
            json={
                "session_id": "public-session",
                "profile": "content-v1",
                "salt_id": "request-salt",
                "nonce": "nonce",
                "ciphertext": "ciphertext",
            },
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert interactions.likes == []

def test_public_post_like_risk_limit_returns_429() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager(
        {**fingerprint_payload(), "liked": True},
    )
    interactions = FakePostInteractionService(risk_limited=True)
    app.dependency_overrides[get_post_interaction_service] = lambda: interactions
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.post(
            "/api/public/posts/public-post/like",
            json={
                "session_id": "public-session",
                "profile": "content-v1",
                "salt_id": "request-salt",
                "nonce": "nonce",
                "ciphertext": "ciphertext",
            },
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == "post interaction risk limited"

def test_public_post_detail_returns_404_for_missing_post() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/posts/missing-post",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "post not found"
    assert logs.items[0]["status_code"] == 404

def test_public_page_detail_returns_html_content() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/pages/about",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload == {
        "id": 3,
        "title": "关于",
        "slug": "about",
        "content_html": "<p>这里是关于页面。</p>",
        "seo_title": "关于静默书房",
        "seo_description": "关于这个长期写作空间",
        "updated_at": "2026-06-17T00:00:00Z",
    }
    assert logs.items[0]["access_type"] == "public_page_detail"
    assert logs.items[0]["path"] == "/api/public/pages/about"

def test_public_page_detail_returns_404_for_missing_page() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/pages/missing-page",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "page not found"
    assert logs.items[0]["access_type"] == "public_page_detail"
    assert logs.items[0]["status_code"] == 404
