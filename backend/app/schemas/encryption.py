from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.encryption import EncryptionProfile


class BrowserPublicKey(BaseModel):
    kty: Literal["EC"]
    crv: Literal["P-256"]
    x: str = Field(min_length=1)
    y: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class CreateEncryptionSessionRequest(BaseModel):
    client_public_key: BrowserPublicKey

    model_config = ConfigDict(extra="forbid")


class CreateEncryptionSessionResponse(BaseModel):
    session_id: str
    server_public_key: BrowserPublicKey
    profiles: list[EncryptionProfile]
    expires_at: datetime

    model_config = ConfigDict(extra="forbid")


class EncryptedApiResponse(BaseModel):
    encrypted: Literal[True] = True
    session_id: str
    profile: EncryptionProfile
    algorithm: str
    nonce: str
    ciphertext: str

    model_config = ConfigDict(extra="forbid")


JsonObject = dict[str, Any]
