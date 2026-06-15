import pytest
from fastapi import HTTPException

from app.api.admin.dependencies import require_admin_permission
from app.api.admin.session import session_response, verify_csrf_tokens
from app.services.auth import AuthenticatedUser


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
