from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.encryption import EncryptionProfile

EncryptionSessionScope = Literal["admin", "public"]
ENCRYPTION_SESSION_ID_MAX_LENGTH = 128
ENCRYPTION_NONCE_MAX_LENGTH = 64
ENCRYPTION_CIPHERTEXT_MAX_LENGTH = 2_000_000


class BrowserPublicKey(BaseModel):
    kty: Literal["EC"]
    crv: Literal["P-256"]
    x: str = Field(min_length=1, max_length=64)
    y: str = Field(min_length=1, max_length=64)

    model_config = ConfigDict(extra="forbid")


class CreateEncryptionSessionRequest(BaseModel):
    client_public_key: BrowserPublicKey

    model_config = ConfigDict(extra="forbid")


class CreateEncryptionSessionResponse(BaseModel):
    session_id: str
    scope: EncryptionSessionScope
    server_public_key: BrowserPublicKey
    profiles: list[EncryptionProfile]
    expires_at: datetime

    model_config = ConfigDict(extra="forbid")


class EncryptedApiResponse(BaseModel):
    session_id: str = Field(min_length=1, max_length=ENCRYPTION_SESSION_ID_MAX_LENGTH)
    profile: EncryptionProfile
    nonce: str = Field(min_length=1, max_length=ENCRYPTION_NONCE_MAX_LENGTH)
    ciphertext: str = Field(min_length=1, max_length=ENCRYPTION_CIPHERTEXT_MAX_LENGTH)

    model_config = ConfigDict(extra="forbid")


class EncryptedApiRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=ENCRYPTION_SESSION_ID_MAX_LENGTH)
    profile: EncryptionProfile
    nonce: str = Field(min_length=1, max_length=ENCRYPTION_NONCE_MAX_LENGTH)
    ciphertext: str = Field(min_length=1, max_length=ENCRYPTION_CIPHERTEXT_MAX_LENGTH)

    model_config = ConfigDict(extra="forbid")


JsonObject = dict[str, Any]
