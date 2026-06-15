from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminSettingItem(BaseModel):
    id: int | None
    key_name: str
    value_json: dict[str, Any]
    group_name: str
    is_public: bool
    updated_by: int | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AdminSettingListResponse(BaseModel):
    items: list[AdminSettingItem]

    model_config = ConfigDict(extra="forbid")


class SettingUpdateRequest(BaseModel):
    value_json: dict[str, Any]
    group_name: str = Field(min_length=1, max_length=64)
    is_public: bool

    model_config = ConfigDict(extra="forbid")
