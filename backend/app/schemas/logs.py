from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogItem(BaseModel):
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    ip: str | None
    user_agent: str | None
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AccessLogItem(BaseModel):
    id: int
    access_type: str
    method: str
    path: str
    status_code: int
    entity_type: str | None
    entity_id: int | None
    ip: str | None
    user_agent: str | None
    detail_json: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class LoginLogItem(BaseModel):
    id: int
    user_id: int | None
    username: str
    success: bool
    ip: str | None
    user_agent: str | None
    reason: str | None
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class SecurityEventItem(BaseModel):
    id: int
    event_type: str
    severity: str
    actor_id: int | None
    ip: str | None
    user_agent: str | None
    path: str | None
    detail_json: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int

    model_config = ConfigDict(extra="forbid")


class AccessLogListResponse(BaseModel):
    items: list[AccessLogItem]
    total: int

    model_config = ConfigDict(extra="forbid")


class LoginLogListResponse(BaseModel):
    items: list[LoginLogItem]
    total: int

    model_config = ConfigDict(extra="forbid")


class SecurityEventListResponse(BaseModel):
    items: list[SecurityEventItem]
    total: int

    model_config = ConfigDict(extra="forbid")
