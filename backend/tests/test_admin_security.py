import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_auth_service, require_admin_permission
from app.api.admin.session import session_response, verify_csrf_tokens
from app.core.config import Settings, get_settings
from app.main import create_app
from app.services.auth import AuthenticatedUser


class FakeLogoutAuthService:
    def __init__(self) -> None:
        self.refresh_tokens: list[str] = []

    async def logout(self, *, refresh_token: str) -> None:
        self.refresh_tokens.append(refresh_token)


def make_user(*, permissions: list[str]) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["editor"],
        permissions=permissions,
    )


def test_verify_csrf_tokens_accepts_matching_token() -> None:
    verify_csrf_tokens(header_token="csrf-token", cookie_token="csrf-token")


def test_verify_csrf_tokens_rejects_missing_or_mismatched_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        verify_csrf_tokens(header_token="csrf-token", cookie_token="other-token")

    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_require_admin_permission_allows_explicit_permission() -> None:
    checker = require_admin_permission("post:write")
    user = make_user(permissions=["post:write"])

    current_user = await checker(user)

    assert current_user is user


@pytest.mark.anyio
async def test_require_admin_permission_allows_wildcard_permission() -> None:
    checker = require_admin_permission("setting:write")
    user = make_user(permissions=["*"])

    current_user = await checker(user)

    assert current_user is user


@pytest.mark.anyio
async def test_require_admin_permission_rejects_missing_permission() -> None:
    checker = require_admin_permission("setting:write")

    with pytest.raises(HTTPException) as exc_info:
        await checker(make_user(permissions=["post:read"]))

    assert exc_info.value.status_code == 403


def test_session_response_keeps_tokens_out_of_response_body() -> None:
    response = session_response(
        user=make_user(permissions=["post:read"]),
        csrf_token="csrf-token",
        expires_in=900,
    )

    assert response.model_dump() == {
        "user": {
            "id": 1,
            "username": "admin",
            "display_name": "管理员",
            "roles": ["editor"],
            "permissions": ["post:read"],
        },
        "csrf_token": "csrf-token",
        "expires_in": 900,
    }


def test_logout_uses_refresh_cookie_and_ignores_body_token() -> None:
    app = create_app(settings=get_settings())
    client = TestClient(app)
    service = FakeLogoutAuthService()
    app.dependency_overrides[get_auth_service] = lambda: service
    client.cookies.set("blog_admin_csrf", "csrf-token", path="/api/admin")
    client.cookies.set("blog_admin_refresh", "cookie-refresh", path="/api/admin")

    try:
        response = client.post(
            "/api/admin/auth/logout",
            headers={"X-CSRF-Token": "csrf-token"},
            json={"refresh_token": "body-refresh-token-that-must-be-ignored"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert service.refresh_tokens == ["cookie-refresh"]


def test_logout_ignores_body_token_without_refresh_cookie() -> None:
    app = create_app(settings=get_settings())
    client = TestClient(app)
    service = FakeLogoutAuthService()
    app.dependency_overrides[get_auth_service] = lambda: service
    client.cookies.set("blog_admin_csrf", "csrf-token", path="/api/admin")

    try:
        response = client.post(
            "/api/admin/auth/logout",
            headers={"X-CSRF-Token": "csrf-token"},
            json={"refresh_token": "body-refresh-token-that-must-be-ignored"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert service.refresh_tokens == []


def test_development_response_uses_basic_security_headers_without_csp() -> None:
    client = TestClient(create_app(settings=get_settings()))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
    assert "content-security-policy" not in response.headers
    assert "strict-transport-security" not in response.headers


def test_production_response_uses_hsts_and_content_security_policy() -> None:
    settings_data = get_settings().model_dump()
    settings_data.update(
        {
            "environment": "production",
            "debug": False,
            "docs_enabled": False,
            "secret_key": "production-secret-key-with-at-least-32-chars",
            "admin_cookie_secure": True,
            "public_base_url": "https://example.com",
            "allowed_hosts": ["testserver"],
            "cors_origins": ["https://example.com"],
        },
    )
    settings = Settings(**settings_data)
    client = TestClient(create_app(settings=settings))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/docs").status_code == 404


def test_production_rejects_invalid_public_base_url() -> None:
    settings_data = get_settings().model_dump()
    settings_data.update(
        {
            "environment": "production",
            "debug": False,
            "docs_enabled": False,
            "secret_key": "production-secret-key-with-at-least-32-chars",
            "admin_cookie_secure": True,
            "public_base_url": "javascript:alert(1)",
            "allowed_hosts": ["example.com"],
            "cors_origins": ["https://example.com"],
        },
    )

    with pytest.raises(ValueError, match="BLOG_PUBLIC_BASE_URL"):
        Settings(**settings_data)
