from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Role, User, UserRole


class AdminBootstrapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username),
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email),
        )
        return result.scalar_one_or_none()

    async def get_role_by_code(self, code: str) -> Role | None:
        result = await self.session.execute(
            select(Role).where(Role.code == code),
        )
        return result.scalar_one_or_none()

    async def create_role(
        self,
        *,
        code: str,
        name: str,
        description: str,
    ) -> Role:
        role = Role(code=code, name=name, description=description)
        self.session.add(role)
        await self.session.flush()
        return role

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        display_name: str | None,
        status: int,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            status=status,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def assign_role(self, *, user_id: int, role_id: int) -> None:
        self.session.add(UserRole(user_id=user_id, role_id=role_id))

    async def commit(self) -> None:
        await self.session.commit()
