from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import (
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.log import LoginLog


@dataclass(frozen=True)
class Authorization:
    roles: set[str]
    permissions: set[str]


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username),
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id),
        )
        return result.scalar_one_or_none()

    async def get_authorization(self, user_id: int) -> Authorization:
        roles_result = await self.session.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id),
        )
        permissions_result = await self.session.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id),
        )
        return Authorization(
            roles=set(roles_result.scalars().all()),
            permissions=set(permissions_result.scalars().all()),
        )

    async def create_refresh_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        note: str | None,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            note=note,
        )
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def get_active_refresh_token(
        self,
        *,
        token_hash: str,
        now: datetime,
    ) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            ),
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(
        self,
        *,
        token_hash: str,
        revoked_at: datetime,
    ) -> bool:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash),
        )
        refresh_token = result.scalar_one_or_none()
        if refresh_token is None or refresh_token.revoked_at is not None:
            return False

        refresh_token.revoked_at = revoked_at
        await self.session.flush()
        return True

    async def touch_last_login(self, *, user_id: int, logged_in_at: datetime) -> None:
        user = await self.get_user_by_id(user_id)
        if user is not None:
            user.last_login_at = logged_in_at

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
        self.session.add(
            LoginLog(
                username=username,
                success=success,
                user_id=user_id,
                ip=ip,
                user_agent=user_agent,
                reason=reason,
            ),
        )

    async def commit(self) -> None:
        await self.session.commit()
