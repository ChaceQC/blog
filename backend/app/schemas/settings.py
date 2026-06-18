import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

SETTING_VALUE_JSON_MAX_BYTES = 32_768


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

    @model_validator(mode="after")
    def validate_value_json_size(self) -> "SettingUpdateRequest":
        encoded = json.dumps(
            self.value_json,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > SETTING_VALUE_JSON_MAX_BYTES:
            raise ValueError("value_json is too large")
        return self


class PublicSiteProfileResponse(BaseModel):
    title: str
    owner: str
    avatar_url: str
    description: str
    quote: str
    musings: list[dict[str, str]]
    social_links: list[dict[str, str]]

    model_config = ConfigDict(extra="forbid", from_attributes=True)
