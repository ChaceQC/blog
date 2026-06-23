from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.encryption import (
    ENCRYPTION_CIPHERTEXT_MAX_LENGTH,
    ENCRYPTION_NONCE_MAX_LENGTH,
    ENCRYPTION_SALT_ID_MAX_LENGTH,
    ENCRYPTION_SESSION_ID_MAX_LENGTH,
    ENCRYPTION_TAG_MAX_LENGTH,
)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")


class LoginCapsuleRequest(BaseModel):
    scheme: Literal["login-capsule-v2"]
    session_id: str = Field(min_length=1, max_length=ENCRYPTION_SESSION_ID_MAX_LENGTH)
    challenge_id: str = Field(min_length=1, max_length=128)
    salt_id: str = Field(min_length=1, max_length=ENCRYPTION_SALT_ID_MAX_LENGTH)
    nonce: str = Field(min_length=1, max_length=ENCRYPTION_NONCE_MAX_LENGTH)
    issued_at: int = Field(ge=0)
    ciphertext: str = Field(min_length=1, max_length=ENCRYPTION_CIPHERTEXT_MAX_LENGTH)
    tag: str = Field(min_length=1, max_length=ENCRYPTION_TAG_MAX_LENGTH)

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
