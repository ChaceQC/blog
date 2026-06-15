from dataclasses import dataclass

import pytest

from app.core.auth import verify_password
from app.policies.auth import ACTIVE_USER_STATUS, SUPER_ADMIN_ROLE
from app.services.admin_bootstrap import (
    AdminBootstrapService,
    InitialAdminCommand,
    InitialAdminExistsError,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class FakeUser:
    id: int
    username: str
    email: str
    password_hash: str
    display_name: str | None
    status: int


@dataclass
class FakeRole:
    id: int
    code: str
    name: str
    description: str


class FakeAdminBootstrapRepository:
    def __init__(self) -> None:
        self.users: list[FakeUser] = []
        self.roles: list[FakeRole] = []
        self.assignments: list[tuple[int, int]] = []
        self.commit_count = 0

    async def get_user_by_username(self, username: str) -> FakeUser | None:
        return next((user for user in self.users if user.username == username), None)

    async def get_user_by_email(self, email: str) -> FakeUser | None:
        return next((user for user in self.users if user.email == email), None)

    async def get_role_by_code(self, code: str) -> FakeRole | None:
        return next((role for role in self.roles if role.code == code), None)

    async def create_role(
        self,
        *,
        code: str,
        name: str,
        description: str,
    ) -> FakeRole:
        role = FakeRole(
            id=len(self.roles) + 1,
            code=code,
            name=name,
            description=description,
        )
        self.roles.append(role)
        return role

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        display_name: str | None,
        status: int,
    ) -> FakeUser:
        user = FakeUser(
            id=len(self.users) + 1,
            username=username,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            status=status,
        )
        self.users.append(user)
        return user

    async def assign_role(self, *, user_id: int, role_id: int) -> None:
        self.assignments.append((user_id, role_id))

    async def commit(self) -> None:
        self.commit_count += 1


def make_command() -> InitialAdminCommand:
    return InitialAdminCommand(
        username="admin",
        email="admin@example.com",
        password="strong-password",
        display_name="管理员",
    )


@pytest.mark.anyio
async def test_create_initial_admin_creates_user_role_and_assignment() -> None:
    repository = FakeAdminBootstrapRepository()
    service = AdminBootstrapService(repository)

    user = await service.create_initial_admin(make_command())

    assert user.username == "admin"
    assert user.email == "admin@example.com"
    assert user.display_name == "管理员"
    assert user.status == ACTIVE_USER_STATUS
    assert verify_password("strong-password", user.password_hash)
    assert repository.roles[0].code == SUPER_ADMIN_ROLE
    assert repository.assignments == [(user.id, repository.roles[0].id)]
    assert repository.commit_count == 1


@pytest.mark.anyio
async def test_create_initial_admin_rejects_duplicate_username() -> None:
    repository = FakeAdminBootstrapRepository()
    service = AdminBootstrapService(repository)
    await service.create_initial_admin(make_command())

    with pytest.raises(InitialAdminExistsError):
        await service.create_initial_admin(make_command())

    assert repository.commit_count == 1
