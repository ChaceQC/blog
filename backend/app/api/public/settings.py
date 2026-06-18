from fastapi import APIRouter, Request, status

from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    SettingServiceDependency,
)
from app.api.encrypted_response import encrypted_response
from app.api.public.common import (
    record_public_access,
    validate_public_content_session,
)
from app.core.encryption import EncryptionProfile
from app.core.url_validation import validate_public_href, validate_public_image_src
from app.schemas.settings import PublicSiteProfileResponse

router = APIRouter(tags=["public-settings"])
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


@router.get("/settings/site-profile")
async def get_public_site_profile(
    request: Request,
    service: SettingServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
):
    await validate_public_content_session(request, encryption_manager)
    setting = await service.get_site_profile()
    profile = _site_profile_response(setting.value_json)
    response = await encrypted_response(
        profile,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_site_profile",
        status_code=status.HTTP_200_OK,
        entity_type="setting",
        detail_json={"key_name": setting.key_name},
    )
    return response


def _site_profile_response(value: dict[str, object]) -> PublicSiteProfileResponse:
    avatar_url = _string_value(
        value.get("avatar_url"),
        "https://github.com/ChaceQC.png",
        max_length=SITE_PROFILE_TEXT_LIMITS["avatar_url"],
    )
    try:
        avatar_url = validate_public_image_src(avatar_url)
    except ValueError:
        avatar_url = "https://github.com/ChaceQC.png"

    return PublicSiteProfileResponse(
        title=_string_value(
            value.get("title"),
            "静默书房",
            max_length=SITE_PROFILE_TEXT_LIMITS["title"],
        ),
        owner=_string_value(
            value.get("owner"),
            "ChaceQC",
            max_length=SITE_PROFILE_TEXT_LIMITS["owner"],
        ),
        avatar_url=avatar_url,
        description=_string_value(
            value.get("description"),
            "把长期写作、素材管理和自建服务收束到一处安静的发布空间。",
            max_length=SITE_PROFILE_TEXT_LIMITS["description"],
        ),
        quote=_string_value(
            value.get("quote"),
            "「把想法放慢一点，让每一次发布都留下可以回看的纹理。」",
            max_length=SITE_PROFILE_TEXT_LIMITS["quote"],
        ),
        musings=_musings_value(value.get("musings")),
        social_links=_social_links_value(value.get("social_links")),
    )


def _string_value(value: object, fallback: str, *, max_length: int) -> str:
    selected = value if isinstance(value, str) and value else fallback
    return selected.strip()[:max_length]


def _musings_value(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    musings: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        date = item.get("date")
        if isinstance(content, str) and content.strip():
            musings.append(
                {
                    "content": content.strip()[
                        :SITE_PROFILE_MUSING_CONTENT_MAX_LENGTH
                    ],
                    "date": (
                        date.strip()[:SITE_PROFILE_MUSING_DATE_MAX_LENGTH]
                        if isinstance(date, str)
                        else ""
                    ),
                },
            )
    return musings[:3]


def _social_links_value(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    links: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        url = item.get("url")
        if (
            isinstance(label, str)
            and label.strip()
            and isinstance(url, str)
            and url.strip()
        ):
            try:
                safe_url = validate_public_href(
                    url.strip()[:SITE_PROFILE_SOCIAL_URL_MAX_LENGTH],
                )
            except ValueError:
                continue
            links.append(
                {
                    "label": label.strip()[:SITE_PROFILE_SOCIAL_LABEL_MAX_LENGTH],
                    "url": safe_url,
                },
            )
    return links[:12]
