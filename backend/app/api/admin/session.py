from hmac import compare_digest
from secrets import token_urlsafe

from fastapi import HTTPException, Request, Response, status

from app.core.config import Settings
from app.schemas.auth import AuthSessionResponse, AuthUserResponse
from app.services.auth import AuthenticatedUser, TokenPair

ACCESS_COOKIE_NAME = "blog_admin_access"
REFRESH_COOKIE_NAME = "blog_admin_refresh"
CSRF_COOKIE_NAME = "blog_admin_csrf"
ADMIN_COOKIE_PATH = "/api/admin"


def create_csrf_token() -> str:
    return token_urlsafe(32)


def set_admin_session_cookies(
    response: Response,
    *,
    tokens: TokenPair,
    csrf_token: str,
    settings: Settings,
) -> None:
    _set_cookie(
        response,
        name=ACCESS_COOKIE_NAME,
        value=tokens.access_token,
        max_age=tokens.expires_in,
        http_only=True,
        settings=settings,
    )
    _set_cookie(
        response,
        name=REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        http_only=True,
        settings=settings,
    )
    _set_cookie(
        response,
        name=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        http_only=False,
        settings=settings,
    )


def ensure_csrf_cookie(
    request: Request,
    response: Response,
    *,
    settings: Settings,
) -> str:
    csrf_token = request.cookies.get(CSRF_COOKIE_NAME)
    if csrf_token:
        return csrf_token

    csrf_token = create_csrf_token()
    _set_cookie(
        response,
        name=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        http_only=False,
        settings=settings,
    )
    return csrf_token


def clear_admin_session_cookies(response: Response, *, settings: Settings) -> None:
    for name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(
            key=name,
            path=ADMIN_COOKIE_PATH,
            secure=settings.admin_cookie_secure,
            samesite=settings.admin_cookie_samesite,
        )


def refresh_token_from_request(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE_NAME)


def access_token_from_request(request: Request) -> str | None:
    return request.cookies.get(ACCESS_COOKIE_NAME)


def csrf_token_from_request(request: Request) -> str | None:
    return request.cookies.get(CSRF_COOKIE_NAME)


def verify_csrf_tokens(header_token: str | None, cookie_token: str | None) -> None:
    if (
        not header_token
        or not cookie_token
        or not compare_digest(header_token, cookie_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid csrf token",
        )


def session_response(
    *,
    user: AuthenticatedUser,
    csrf_token: str,
    expires_in: int,
) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=AuthUserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            roles=user.roles,
            permissions=user.permissions,
        ),
        csrf_token=csrf_token,
        expires_in=expires_in,
    )


def _set_cookie(
    response: Response,
    *,
    name: str,
    value: str,
    max_age: int,
    http_only: bool,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=http_only,
        secure=settings.admin_cookie_secure,
        samesite=settings.admin_cookie_samesite,
        path=ADMIN_COOKIE_PATH,
    )
