from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FileVisibility = Literal["public", "private"]


class AdminFileItem(BaseModel):
    id: int
    storage: str
    bucket: str | None
    object_key: str
    original_name: str
    mime_type: str
    extension: str
    size_bytes: int = Field(ge=0)
    sha256: str
    width: int | None
    height: int | None
    alt_text: str | None
    uploader_id: int | None
    visibility: str
    public_listed: bool
    status: str
    usage_count: int = Field(ge=0)
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AdminFileListResponse(BaseModel):
    items: list[AdminFileItem]

    model_config = ConfigDict(extra="forbid")


class AdminFileTemporaryUrlResponse(BaseModel):
    url: str
    expires_at: datetime

    model_config = ConfigDict(extra="forbid")


class PublicFileItem(BaseModel):
    id: int
    original_name: str
    mime_type: str
    extension: str
    size_bytes: int = Field(ge=0)
    width: int | None
    height: int | None
    alt_text: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicFileListResponse(BaseModel):
    items: list[PublicFileItem]

    model_config = ConfigDict(extra="forbid")
