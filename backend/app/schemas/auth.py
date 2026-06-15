from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=256)

    model_config = ConfigDict(extra="forbid")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=256)

    model_config = ConfigDict(extra="forbid")


class AuthUserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None
    roles: list[str]
    permissions: list[str]

    model_config = ConfigDict(extra="forbid")


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthUserResponse

    model_config = ConfigDict(extra="forbid")


class LogoutResponse(BaseModel):
    status: Literal["ok"] = "ok"

    model_config = ConfigDict(extra="forbid")
