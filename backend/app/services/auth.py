from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

import jwt

from app.core.auth import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    utc_now,
    verify_password,
)
from app.core.config import Settings
from app.models.auth import RefreshToken, User
from app.policies.auth import AuthPolicy
from app.repositories.auth import Authorization
from app.services.log_sanitizers import sanitize_log_ip, sanitize_log_user_agent


class AuthenticationError(Exception):
    pass


DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$rIlOXSgomTbRCi+eNR3zVw"
    "$Dw2Fs2E3Xfyt5phCoDWV6VALbztfkFDR+HPgzJgeA7s"
)


class AuthRepositoryProtocol(Protocol):
    async def get_user_by_username(self, username: str) -> User | None: ...

    async def get_user_by_id(self, user_id: int) -> User | None: ...

    async def get_authorization(self, user_id: int) -> Authorization: ...

    async def create_refresh_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        note: str | None,
    ) -> RefreshToken: ...

    async def get_active_refresh_token(
        self,
        *,
        token_hash: str,
        now: datetime,
    ) -> RefreshToken | None: ...

    async def revoke_refresh_token(
        self,
        *,
        token_hash: str,
        revoked_at: datetime,
    ) -> bool: ...

    async def touch_last_login(self, *, user_id: int, logged_in_at: datetime) -> None:
        ...

    async def record_login_log(
        self,
        *,
        username: str,
        success: bool,
        user_id: int | None,
        ip: str | None,
        user_agent: str | None,
        reason: str | None,
    ) -> None: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    display_name: str | None
    roles: list[str]
    permissions: list[str]


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    user: AuthenticatedUser


class AuthService:
    def __init__(
        self,
        *,
        repository: AuthRepositoryProtocol,
        settings: Settings,
        policy: AuthPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.policy = policy or AuthPolicy()

    async def login(
        self,
        *,
        username: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        logged_in_at = utc_now()
        user = await self.repository.get_user_by_username(username)
        password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        password_matches = verify_password(password, password_hash)
        if user is None or not password_matches:
            await self._record_login_failure(
                username=username,
                user_id=user.id if user else None,
                ip=ip,
                user_agent=user_agent,
                reason="invalid_credentials",
            )
            raise AuthenticationError("invalid credentials")

        if not self.policy.can_login(user):
            await self._record_login_failure(
                username=username,
                user_id=user.id,
                ip=ip,
                user_agent=user_agent,
                reason="inactive_user",
            )
            raise AuthenticationError("invalid credentials")

        tokens = await self._issue_tokens(user=user, now=logged_in_at)
        await self.repository.touch_last_login(
            user_id=user.id,
            logged_in_at=logged_in_at,
        )
        await self.repository.record_login_log(
            username=user.username,
            success=True,
            user_id=user.id,
            ip=sanitize_log_ip(ip),
            user_agent=sanitize_log_user_agent(user_agent),
            reason=None,
        )
        await self.repository.commit()
        return tokens

    async def refresh(self, *, refresh_token: str) -> TokenPair:
        now = utc_now()
        token_hash = hash_refresh_token(refresh_token)
        stored_token = await self.repository.get_active_refresh_token(
            token_hash=token_hash,
            now=now,
        )
        if stored_token is None:
            raise AuthenticationError("invalid refresh token")

        user = await self.repository.get_user_by_id(stored_token.user_id)
        if user is None or not self.policy.can_login(user):
            await self.repository.revoke_refresh_token(
                token_hash=token_hash,
                revoked_at=now,
            )
            await self.repository.commit()
            raise AuthenticationError("invalid refresh token")

        await self.repository.revoke_refresh_token(
            token_hash=token_hash,
            revoked_at=now,
        )
        tokens = await self._issue_tokens(user=user, now=now)
        await self.repository.commit()
        return tokens

    async def logout(self, *, refresh_token: str) -> None:
        await self.repository.revoke_refresh_token(
            token_hash=hash_refresh_token(refresh_token),
            revoked_at=utc_now(),
        )
        await self.repository.commit()

    async def authenticate_access_token(
        self,
        *,
        access_token: str,
    ) -> AuthenticatedUser:
        try:
            payload = decode_access_token(access_token, self.settings.secret_key)
            user_id = _user_id_from_access_token_payload(payload)
        except (ValueError, jwt.InvalidTokenError) as exc:
            raise AuthenticationError("invalid access token") from exc

        user = await self.repository.get_user_by_id(user_id)
        if user is None or not self.policy.can_login(user):
            raise AuthenticationError("invalid access token")

        return await self._authenticated_user(user)

    async def _issue_tokens(self, *, user: User, now: datetime) -> TokenPair:
        authenticated_user = await self._authenticated_user(user)
        expires_delta = timedelta(minutes=self.settings.access_token_expire_minutes)
        refresh_token = generate_refresh_token()
        refresh_expires_at = now + timedelta(
            days=self.settings.refresh_token_expire_days,
        )

        await self.repository.create_refresh_token(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=refresh_expires_at,
            note="admin-session",
        )

        return TokenPair(
            access_token=create_access_token(
                user_id=user.id,
                roles=authenticated_user.roles,
                permissions=authenticated_user.permissions,
                secret_key=self.settings.secret_key,
                expires_delta=expires_delta,
                now=now,
            ),
            refresh_token=refresh_token,
            expires_in=int(expires_delta.total_seconds()),
            user=authenticated_user,
        )

    async def _authenticated_user(self, user: User) -> AuthenticatedUser:
        authorization = await self.repository.get_authorization(user.id)
        roles = sorted(authorization.roles)
        permissions = sorted(
            self.policy.token_permissions(
                roles=authorization.roles,
                permissions=authorization.permissions,
            ),
        )
        return AuthenticatedUser(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            roles=roles,
            permissions=permissions,
        )

    async def _record_login_failure(
        self,
        *,
        username: str,
        user_id: int | None,
        ip: str | None,
        user_agent: str | None,
        reason: str,
    ) -> None:
        await self.repository.record_login_log(
            username=username,
            success=False,
            user_id=user_id,
            ip=sanitize_log_ip(ip),
            user_agent=sanitize_log_user_agent(user_agent),
            reason=reason,
        )
        await self.repository.commit()


def _user_id_from_access_token_payload(payload: dict[str, object]) -> int:
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise ValueError("missing subject")

    user_id = int(subject)
    if user_id <= 0:
        raise ValueError("invalid subject")

    return user_id
