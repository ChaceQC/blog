from tests.public_content_api_helpers import (
    FakeEncryptionSessionManager,
    FakeLogService,
    FakeSettingService,
    SimpleNamespace,
    TestClient,
    _site_profile_response,
    app,
    get_encryption_session_manager,
    get_log_service,
    get_setting_service,
)


def test_public_site_profile_returns_encrypted_setting() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/settings/site-profile",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["title"] == "恬妡的小屋"
    assert manager.payload["owner"] == "恬妡"
    assert manager.payload["musings"][0]["content"] == "后台碎念"
    assert manager.payload["social_links"][0]["label"] == "GitHub"
    assert logs.items[0]["access_type"] == "public_site_profile"
    assert logs.items[0]["path"] == "/api/public/settings/site-profile"

def test_public_site_profile_filters_unsafe_social_href() -> None:
    class UnsafeSettingService:
        async def get_site_profile(self) -> object:
            return SimpleNamespace(
                key_name="site_profile",
                value_json={
                    "title": "静默书房",
                    "owner": "ChaceQC",
                    "avatar_url": "mailto:avatar@example.com",
                    "description": "描述",
                    "quote": "引文",
                    "social_links": [
                        {"label": "RSS", "url": "/rss.xml"},
                        {"label": "坏链接", "url": "javascript:alert(1)"},
                    ],
                },
            )

        async def get_public_site_profile(self) -> object:
            setting = await self.get_site_profile()
            return _site_profile_response(setting)

    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_setting_service] = lambda: UnsafeSettingService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/settings/site-profile",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.payload is not None
    assert manager.payload["avatar_url"] == "https://github.com/ChaceQC.png"
    assert manager.payload["social_links"] == [{"label": "RSS", "url": "/rss.xml"}]

def test_public_site_profile_bounds_legacy_oversized_values() -> None:
    class OversizedSettingService:
        async def get_site_profile(self) -> object:
            return SimpleNamespace(
                key_name="site_profile",
                value_json={
                    "title": "站" * 100,
                    "owner": "主人" * 100,
                    "avatar_url": "https://example.com/" + "a" * 1200,
                    "description": "描述" * 400,
                    "quote": "引文" * 400,
                    "musings": [
                        {"content": "碎念" * 400, "date": "日期" * 80},
                        {"content": "第二条", "date": "2026"},
                        {"content": "第三条", "date": "2026"},
                        {"content": "第四条", "date": "2026"},
                    ],
                    "social_links": [
                        {"label": f"链接{i}", "url": f"https://example.com/{i}"}
                        for i in range(20)
                    ],
                },
            )

        async def get_public_site_profile(self) -> object:
            setting = await self.get_site_profile()
            return _site_profile_response(setting)

    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_setting_service] = lambda: OversizedSettingService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/settings/site-profile",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.payload is not None
    assert len(manager.payload["title"]) == 80
    assert len(manager.payload["owner"]) == 80
    assert len(manager.payload["description"]) == 500
    assert len(manager.payload["quote"]) == 500
    assert len(manager.payload["musings"]) == 3
    assert len(manager.payload["musings"][0]["content"]) == 500
    assert len(manager.payload["musings"][0]["date"]) == 80
    assert len(manager.payload["social_links"]) == 12
