from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import utc_now
from app.models.setting import Setting


class SettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_settings(self) -> Sequence[Setting]:
        result = await self.session.execute(
            select(Setting).order_by(Setting.group_name.asc(), Setting.key_name.asc()),
        )
        return result.scalars().all()

    async def get_setting(self, key_name: str) -> Setting | None:
        result = await self.session.execute(
            select(Setting).where(Setting.key_name == key_name),
        )
        return result.scalar_one_or_none()

    async def upsert_setting(
        self,
        *,
        key_name: str,
        value_json: dict[str, Any],
        group_name: str,
        is_public: bool,
        updated_by: int | None,
    ) -> Setting:
        setting = await self.get_setting(key_name)
        now = utc_now()
        if setting is None:
            setting = Setting(
                key_name=key_name,
                value_json=value_json,
                group_name=group_name,
                is_public=is_public,
                updated_by=updated_by,
                updated_at=now,
            )
            self.session.add(setting)
            await self.session.flush()
            return setting

        setting.value_json = value_json
        setting.group_name = group_name
        setting.is_public = is_public
        setting.updated_by = updated_by
        setting.updated_at = now
        await self.session.flush()
        return setting

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)
