from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=256)

    model_config = ConfigDict(extra="forbid")


class AuthUserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None
    roles: list[str]
    permissions: list[str]

    model_config = ConfigDict(extra="forbid")


class AuthSessionResponse(BaseModel):
    user: AuthUserResponse
    csrf_token: str
    expires_in: int

    model_config = ConfigDict(extra="forbid")


class LogoutResponse(BaseModel):
    status: Literal["ok"] = "ok"

    model_config = ConfigDict(extra="forbid")
