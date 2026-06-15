from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.models.setting import Setting

SITE_PROFILE_KEY = "site_profile"
SITE_PROFILE_GROUP = "site"
DEFAULT_SITE_PROFILE = {
    "title": "静默书房",
    "owner": "ChaceQC",
    "avatar_url": "https://github.com/ChaceQC.png",
    "description": "把长期写作、素材管理和自建服务收束到一处安静的发布空间。",
    "quote": "「把想法放慢一点，让每一次发布都留下可以回看的纹理。」",
}


class SettingRepositoryProtocol(Protocol):
    async def list_settings(self) -> Sequence[Setting]: ...

    async def get_setting(self, key_name: str) -> Setting | None: ...

    async def upsert_setting(
        self,
        *,
        key_name: str,
        value_json: dict[str, Any],
        group_name: str,
        is_public: bool,
        updated_by: int | None,
    ) -> Setting: ...

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...


@dataclass(frozen=True)
class VirtualSetting:
    id: int | None
    key_name: str
    value_json: dict[str, Any]
    group_name: str
    is_public: bool
    updated_by: int | None
    updated_at: datetime | None


class SettingService:
    def __init__(self, repository: SettingRepositoryProtocol) -> None:
        self.repository = repository

    async def list_settings(self) -> list[Setting | VirtualSetting]:
        settings = list(await self.repository.list_settings())
        if not any(setting.key_name == SITE_PROFILE_KEY for setting in settings):
            settings.insert(0, self.default_site_profile())
        return settings

    async def update_setting(
        self,
        *,
        key_name: str,
        value_json: dict[str, Any],
        group_name: str,
        is_public: bool,
        updated_by: int | None,
    ) -> Setting:
        setting = await self.repository.upsert_setting(
            key_name=key_name,
            value_json=value_json,
            group_name=group_name,
            is_public=is_public,
            updated_by=updated_by,
        )
        await self.repository.commit()
        await self.repository.refresh(setting)
        return setting

    def default_site_profile(self) -> VirtualSetting:
        return VirtualSetting(
            id=None,
            key_name=SITE_PROFILE_KEY,
            value_json=dict(DEFAULT_SITE_PROFILE),
            group_name=SITE_PROFILE_GROUP,
            is_public=True,
            updated_by=None,
            updated_at=None,
        )
