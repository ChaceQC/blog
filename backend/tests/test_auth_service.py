from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.core.auth import decode_access_token, hash_password, hash_refresh_token
from app.repositories.auth import Authorization
from app.services.auth import AuthenticationError, AuthService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class FakeRefreshToken:
    user_id: int
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None
    note: str | None = None


class FakeAuthRepository:
    def __init__(self, user: SimpleNamespace | None) -> None:
        self.user = user
        self.authorization = Authorization(
            roles={"editor"},
            permissions={"post:read", "post:write"},
        )
        self.refresh_tokens: list[FakeRefreshToken] = []
        self.login_logs: list[dict[str, object]] = []
        self.commit_count = 0

    async def get_user_by_username(self, username: str) -> SimpleNamespace | None:
        if self.user is not None and self.user.username == username:
            return self.user
        return None

    async def get_user_by_id(self, user_id: int) -> SimpleNamespace | None:
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None

    async def get_authorization(self, user_id: int) -> Authorization:
        return self.authorization

    async def create_refresh_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        note: str | None,
    ) -> FakeRefreshToken:
        refresh_token = FakeRefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            note=note,
        )
        self.refresh_tokens.append(refresh_token)
        return refresh_token

    async def get_active_refresh_token(
        self,
        *,
        token_hash: str,
        now: datetime,
    ) -> FakeRefreshToken | None:
        for refresh_token in self.refresh_tokens:
            if (
                refresh_token.token_hash == token_hash
                and refresh_token.revoked_at is None
                and refresh_token.expires_at > now
            ):
                return refresh_token
        return None

    async def revoke_refresh_token(
        self,
        *,
        token_hash: str,
        revoked_at: datetime,
    ) -> bool:
        for refresh_token in self.refresh_tokens:
            if refresh_token.token_hash == token_hash:
                if refresh_token.revoked_at is not None:
                    return False
                refresh_token.revoked_at = revoked_at
                return True
        return False

    async def touch_last_login(self, *, user_id: int, logged_in_at: datetime) -> None:
        if self.user is not None and self.user.id == user_id:
            self.user.last_login_at = logged_in_at

    async def record_login_log(
        self,
        *,
        username: str,
        success: bool,
        user_id: int | None,
        ip: str | None,
        user_agent: str | None,
        reason: str | None,
    ) -> None:
        self.login_logs.append(
            {
                "username": username,
                "success": success,
                "user_id": user_id,
                "ip": ip,
                "user_agent": user_agent,
                "reason": reason,
            },
        )

    async def commit(self) -> None:
        self.commit_count += 1


def make_settings() -> SimpleNamespace:
    return SimpleNamespace(
        secret_key="test-secret-key-with-at-least-32-characters",
        access_token_expire_minutes=15,
        refresh_token_expire_days=14,
    )


def make_user(
    *,
    password: str = "correct-password",
    status: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        username="admin",
        password_hash=hash_password(password),
        display_name="管理员",
        status=status,
        last_login_at=None,
    )


@pytest.mark.anyio
async def test_login_issues_token_pair_and_records_success() -> None:
    settings = make_settings()
    repository = FakeAuthRepository(make_user())
    service = AuthService(repository=repository, settings=settings)

    tokens = await service.login(
        username="admin",
        password="correct-password",
        ip="127.0.0.1",
        user_agent="pytest",
    )

    payload = decode_access_token(tokens.access_token, settings.secret_key)
    assert payload["sub"] == "1"
    assert payload["roles"] == ["editor"]
    assert payload["permissions"] == ["post:read", "post:write"]
    assert tokens.user.username == "admin"
    assert tokens.refresh_token
    assert repository.refresh_tokens[0].token_hash == hash_refresh_token(
        tokens.refresh_token,
    )
    assert repository.user.last_login_at is not None
    assert repository.login_logs == [
        {
            "username": "admin",
            "success": True,
            "user_id": 1,
            "ip": "127.0.0.1",
            "user_agent": "pytest",
            "reason": None,
        },
    ]
    assert repository.commit_count == 1


@pytest.mark.anyio
async def test_login_rejects_wrong_password_and_records_failure() -> None:
    repository = FakeAuthRepository(make_user())
    service = AuthService(repository=repository, settings=make_settings())

    with pytest.raises(AuthenticationError):
        await service.login(
            username="admin",
            password="wrong-password",
            ip=None,
            user_agent=None,
        )

    assert repository.refresh_tokens == []
    assert repository.login_logs[0]["success"] is False
    assert repository.login_logs[0]["reason"] == "invalid_credentials"
    assert repository.commit_count == 1


@pytest.mark.anyio
async def test_login_truncates_log_ip_and_user_agent() -> None:
    settings = make_settings()
    repository = FakeAuthRepository(make_user())
    service = AuthService(repository=repository, settings=settings)

    await service.login(
        username="admin",
        password="correct-password",
        ip="3" * 120,
        user_agent="ua" * 400,
    )

    assert len(repository.login_logs[0]["ip"]) == 64
    assert len(repository.login_logs[0]["user_agent"]) == 500


@pytest.mark.anyio
async def test_refresh_rotates_refresh_token() -> None:
    repository = FakeAuthRepository(make_user())
    service = AuthService(repository=repository, settings=make_settings())
    first_tokens = await service.login(
        username="admin",
        password="correct-password",
        ip=None,
        user_agent=None,
    )

    second_tokens = await service.refresh(refresh_token=first_tokens.refresh_token)

    assert second_tokens.refresh_token != first_tokens.refresh_token
    assert repository.refresh_tokens[0].revoked_at is not None
    assert repository.refresh_tokens[1].token_hash == hash_refresh_token(
        second_tokens.refresh_token,
    )
    assert repository.commit_count == 2


@pytest.mark.anyio
async def test_logout_revokes_refresh_token() -> None:
    repository = FakeAuthRepository(make_user())
    service = AuthService(repository=repository, settings=make_settings())
    tokens = await service.login(
        username="admin",
        password="correct-password",
        ip=None,
        user_agent=None,
    )

    await service.logout(refresh_token=tokens.refresh_token)

    assert repository.refresh_tokens[0].revoked_at is not None
    assert repository.commit_count == 2


@pytest.mark.anyio
async def test_authenticate_access_token_returns_current_user() -> None:
    repository = FakeAuthRepository(make_user())
    service = AuthService(repository=repository, settings=make_settings())
    tokens = await service.login(
        username="admin",
        password="correct-password",
        ip=None,
        user_agent=None,
    )

    current_user = await service.authenticate_access_token(
        access_token=tokens.access_token,
    )

    assert current_user.id == 1
    assert current_user.username == "admin"
    assert current_user.roles == ["editor"]
    assert current_user.permissions == ["post:read", "post:write"]


@pytest.mark.anyio
async def test_authenticate_access_token_rejects_invalid_token() -> None:
    service = AuthService(
        repository=FakeAuthRepository(make_user()),
        settings=make_settings(),
    )

    with pytest.raises(AuthenticationError):
        await service.authenticate_access_token(access_token="not-a-jwt")
