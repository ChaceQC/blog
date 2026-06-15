from dataclasses import dataclass
from typing import Protocol

from app.core.auth import hash_password
from app.models.auth import Role, User
from app.policies.auth import ACTIVE_USER_STATUS, SUPER_ADMIN_ROLE


class InitialAdminExistsError(Exception):
    pass


class AdminBootstrapRepositoryProtocol(Protocol):
    async def get_user_by_username(self, username: str) -> User | None: ...

    async def get_user_by_email(self, email: str) -> User | None: ...

    async def get_role_by_code(self, code: str) -> Role | None: ...

    async def create_role(
        self,
        *,
        code: str,
        name: str,
        description: str,
    ) -> Role: ...

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        display_name: str | None,
        status: int,
    ) -> User: ...

    async def assign_role(self, *, user_id: int, role_id: int) -> None: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True)
class InitialAdminCommand:
    username: str
    email: str
    password: str
    display_name: str | None


class AdminBootstrapService:
    def __init__(self, repository: AdminBootstrapRepositoryProtocol) -> None:
        self.repository = repository

    async def create_initial_admin(self, command: InitialAdminCommand) -> User:
        if await self.repository.get_user_by_username(command.username) is not None:
            raise InitialAdminExistsError("username already exists")
        if await self.repository.get_user_by_email(command.email) is not None:
            raise InitialAdminExistsError("email already exists")

        role = await self.repository.get_role_by_code(SUPER_ADMIN_ROLE)
        if role is None:
            role = await self.repository.create_role(
                code=SUPER_ADMIN_ROLE,
                name="超级管理员",
                description="拥有后台全部权限",
            )

        user = await self.repository.create_user(
            username=command.username,
            email=command.email,
            password_hash=hash_password(command.password),
            display_name=command.display_name,
            status=ACTIVE_USER_STATUS,
        )
        await self.repository.assign_role(user_id=user.id, role_id=role.id)
        await self.repository.commit()
        return user
