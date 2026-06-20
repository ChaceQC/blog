from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.core.url_validation import validate_public_href, validate_public_image_src
from app.models.setting import Setting

SITE_PROFILE_KEY = "site_profile"
SITE_PROFILE_GROUP = "site"
SITE_PROFILE_TEXT_LIMITS = {
    "title": 80,
    "owner": 80,
    "avatar_url": 1000,
    "description": 500,
    "quote": 500,
}
SITE_PROFILE_MUSING_CONTENT_MAX_LENGTH = 500
SITE_PROFILE_MUSING_DATE_MAX_LENGTH = 80
SITE_PROFILE_SOCIAL_LABEL_MAX_LENGTH = 80
SITE_PROFILE_SOCIAL_URL_MAX_LENGTH = 1000
SITE_PROFILE_MUSING_LIMIT = 3
SITE_PROFILE_SOCIAL_LINK_LIMIT = 12
DEFAULT_SITE_PROFILE = {
    "title": "静默书房",
    "owner": "ChaceQC",
    "avatar_url": "https://github.com/ChaceQC.png",
    "description": "把长期写作、素材管理和自建服务收束到一处安静的发布空间。",
    "quote": "「把想法放慢一点，让每一次发布都留下可以回看的纹理。」",
    "musings": [
        {
            "content": "「先把字句放稳，页面自然会慢慢有自己的呼吸。」",
            "date": "2026年6月15日星期一",
        },
        {
            "content": "「UI 的留白不是空，是让内容有地方沉下来。」",
            "date": "2026年6月15日星期一",
        },
    ],
    "social_links": [
        {"label": "GitHub", "url": "https://github.com/ChaceQC"},
        {"label": "RSS", "url": "/rss.xml"},
        {"label": "Email", "url": "mailto:ChaceQC@users.noreply.github.com"},
    ],
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


@dataclass(frozen=True)
class AdminSettingRead:
    id: int | None
    key_name: str
    value_json: dict[str, Any]
    group_name: str
    is_public: bool
    updated_by: int | None
    updated_at: datetime | None


@dataclass(frozen=True)
class PublicSiteProfileRead:
    title: str
    owner: str
    avatar_url: str
    description: str
    quote: str
    musings: list[dict[str, str]]
    social_links: list[dict[str, str]]

    def with_avatar_url(self, avatar_url: str | None) -> "PublicSiteProfileRead":
        return PublicSiteProfileRead(
            title=self.title,
            owner=self.owner,
            avatar_url=avatar_url or self.avatar_url,
            description=self.description,
            quote=self.quote,
            musings=self.musings,
            social_links=self.social_links,
        )


class SettingService:
    def __init__(self, repository: SettingRepositoryProtocol) -> None:
        self.repository = repository

    async def list_settings(self) -> list[AdminSettingRead]:
        settings = list(await self.repository.list_settings())
        if not any(setting.key_name == SITE_PROFILE_KEY for setting in settings):
            settings.insert(0, self.default_site_profile())
        return [self.admin_setting_response(setting) for setting in settings]

    async def get_site_profile(self) -> Setting | VirtualSetting:
        setting = await self.repository.get_setting(SITE_PROFILE_KEY)
        if setting is None or not setting.is_public:
            return self.default_site_profile()
        return setting

    async def get_public_site_profile(self) -> PublicSiteProfileRead:
        setting = await self.get_site_profile()
        return self.public_site_profile_response(setting)

    async def update_setting(
        self,
        *,
        key_name: str,
        value_json: dict[str, Any],
        group_name: str,
        is_public: bool,
        updated_by: int | None,
    ) -> Setting:
        if key_name == SITE_PROFILE_KEY:
            value_json = normalize_site_profile(value_json)
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

    def admin_setting_response(
        self,
        setting: Setting | VirtualSetting,
    ) -> AdminSettingRead:
        return AdminSettingRead(
            id=setting.id,
            key_name=setting.key_name,
            value_json=dict(setting.value_json),
            group_name=setting.group_name,
            is_public=setting.is_public,
            updated_by=setting.updated_by,
            updated_at=setting.updated_at,
        )

    def public_site_profile_response(
        self,
        setting: Setting | VirtualSetting,
    ) -> PublicSiteProfileRead:
        value = setting.value_json
        avatar_url = _site_profile_string(
            value.get("avatar_url"),
            DEFAULT_SITE_PROFILE["avatar_url"],
            max_length=SITE_PROFILE_TEXT_LIMITS["avatar_url"],
        )
        try:
            avatar_url = validate_public_image_src(avatar_url)
        except ValueError:
            avatar_url = str(DEFAULT_SITE_PROFILE["avatar_url"])

        return PublicSiteProfileRead(
            title=_site_profile_string(
                value.get("title"),
                DEFAULT_SITE_PROFILE["title"],
                max_length=SITE_PROFILE_TEXT_LIMITS["title"],
            ),
            owner=_site_profile_string(
                value.get("owner"),
                DEFAULT_SITE_PROFILE["owner"],
                max_length=SITE_PROFILE_TEXT_LIMITS["owner"],
            ),
            avatar_url=avatar_url,
            description=_site_profile_string(
                value.get("description"),
                DEFAULT_SITE_PROFILE["description"],
                max_length=SITE_PROFILE_TEXT_LIMITS["description"],
            ),
            quote=_site_profile_string(
                value.get("quote"),
                DEFAULT_SITE_PROFILE["quote"],
                max_length=SITE_PROFILE_TEXT_LIMITS["quote"],
            ),
            musings=_site_profile_musings(value.get("musings")),
            social_links=_site_profile_social_links(value.get("social_links")),
        )

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


def normalize_site_profile(value_json: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(value_json)

    for key, max_length in SITE_PROFILE_TEXT_LIMITS.items():
        normalized[key] = _normalized_text(
            normalized.get(key),
            fallback=DEFAULT_SITE_PROFILE[key],
            max_length=max_length,
        )

    avatar_url = normalized["avatar_url"]
    if isinstance(avatar_url, str) and avatar_url.strip():
        normalized["avatar_url"] = validate_public_image_src(avatar_url)

    musings = normalized.get("musings")
    if isinstance(musings, list):
        normalized["musings"] = _normalize_musings(musings)

    social_links = normalized.get("social_links")
    if isinstance(social_links, list):
        normalized["social_links"] = _normalize_social_links(social_links)
    return normalized


def _normalized_text(value: object, *, fallback: object, max_length: int) -> str:
    if not isinstance(value, str):
        value = fallback
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _site_profile_string(
    value: object,
    fallback: object,
    *,
    max_length: int,
) -> str:
    selected = value if isinstance(value, str) and value else fallback
    if not isinstance(selected, str):
        return ""
    return selected.strip()[:max_length]


def _normalize_musings(value: list[object]) -> list[dict[str, str]]:
    musings: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        content = _normalized_text(
            item.get("content"),
            fallback="",
            max_length=SITE_PROFILE_MUSING_CONTENT_MAX_LENGTH,
        )
        if not content:
            continue
        date = _normalized_text(
            item.get("date"),
            fallback="",
            max_length=SITE_PROFILE_MUSING_DATE_MAX_LENGTH,
        )
        musings.append({"content": content, "date": date})
        if len(musings) >= SITE_PROFILE_MUSING_LIMIT:
            break
    return musings


def _site_profile_musings(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return _normalize_musings(value)


def _normalize_social_links(value: list[object]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = _normalized_text(
            item.get("label"),
            fallback="",
            max_length=SITE_PROFILE_SOCIAL_LABEL_MAX_LENGTH,
        )
        raw_url = _normalized_text(
            item.get("url"),
            fallback="",
            max_length=SITE_PROFILE_SOCIAL_URL_MAX_LENGTH,
        )
        if not label or not raw_url:
            continue
        try:
            safe_url = validate_public_href(raw_url)
        except ValueError:
            continue
        links.append({"label": label, "url": safe_url})
        if len(links) >= SITE_PROFILE_SOCIAL_LINK_LIMIT:
            break
    return links


def _site_profile_social_links(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return _normalize_social_links(value)
