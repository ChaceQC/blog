import re
from pathlib import Path
from types import UnionType
from typing import Any, get_args, get_origin

import pytest
from pydantic import BaseModel

from app.schemas.auth import AuthSessionResponse, AuthUserResponse
from app.schemas.content import (
    AdminPageItem,
    AdminPostItem,
    PublicPageDetail,
    PublicPostDetail,
    PublicPostItem,
    PublicTaxonomyItem,
)
from app.schemas.files import AdminFileItem, PublicFileItem
from app.schemas.links import (
    AdminFriendLinkGroupItem,
    AdminFriendLinkItem,
    AdminSiteNavGroupItem,
    AdminSiteNavItem,
    PublicFriendLinkApplicationResponse,
    PublicFriendLinkItem,
    PublicSiteNavItem,
)
from app.schemas.logs import (
    AccessLogItem,
    AuditLogItem,
    LoginLogItem,
    SecurityEventItem,
)
from app.schemas.settings import AdminSettingItem, PublicSiteProfileResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
TYPE_BLOCK_PATTERN = re.compile(
    r"export type (?P<name>\w+) = \{(?P<body>.*?)\n\}",
    re.DOTALL,
)
FIELD_PATTERN = re.compile(r"^\s*(?P<name>\w+)(?P<optional>\?)?: (?P<type>.+)$")

CONTRACT_TYPES = [
    ("features/content/types.ts", "AdminPostItem", AdminPostItem),
    ("features/content/types.ts", "AdminPageItem", AdminPageItem),
    ("features/files/types.ts", "AdminFileItem", AdminFileItem),
    ("features/files/types.ts", "PublicFileItem", PublicFileItem),
    ("features/links/types.ts", "AdminFriendLinkGroup", AdminFriendLinkGroupItem),
    ("features/links/types.ts", "AdminSiteNavGroup", AdminSiteNavGroupItem),
    ("features/links/types.ts", "AdminFriendLink", AdminFriendLinkItem),
    ("features/links/types.ts", "AdminSiteNavItem", AdminSiteNavItem),
    ("features/links/types.ts", "FriendLink", PublicFriendLinkItem),
    (
        "features/links/types.ts",
        "PublicFriendLinkApplicationResponse",
        PublicFriendLinkApplicationResponse,
    ),
    ("features/settings/types.ts", "AdminSettingItem", AdminSettingItem),
    ("features/settings/types.ts", "PublicSiteProfile", PublicSiteProfileResponse),
    ("features/logs/types.ts", "AuditLogItem", AuditLogItem),
    ("features/logs/types.ts", "AccessLogItem", AccessLogItem),
    ("features/logs/types.ts", "LoginLogItem", LoginLogItem),
    ("features/logs/types.ts", "SecurityEventItem", SecurityEventItem),
    ("features/posts/types.ts", "PublicPostItem", PublicPostItem),
    ("features/posts/types.ts", "PublicPostDetail", PublicPostDetail),
    ("features/posts/types.ts", "PublicPageDetail", PublicPageDetail),
    ("features/posts/types.ts", "PublicTaxonomyItem", PublicTaxonomyItem),
    ("features/sites/types.ts", "SiteItem", PublicSiteNavItem),
    ("features/auth/types.ts", "AuthUser", AuthUserResponse),
    ("features/auth/types.ts", "AuthSessionResponse", AuthSessionResponse),
]

TYPE_ALIAS_NORMALIZATION = {
    "AdminFriendLinkStatus": "string",
    "AdminSiteNavOpenTarget": "string",
    "AdminSiteNavVisibility": "string",
    "AuthUser": "record",
    "ContentStatus": "string",
    "FileVisibility": "string",
    "PostVisibility": "string",
}


@pytest.mark.parametrize(("type_path", "type_name", "schema"), CONTRACT_TYPES)
def test_frontend_response_type_matches_backend_schema(
    type_path: str,
    type_name: str,
    schema: type[BaseModel],
) -> None:
    frontend_fields = _frontend_type_fields(type_path, type_name)
    backend_fields = {
        name: _python_type_to_typescript(field.annotation)
        for name, field in schema.model_fields.items()
    }
    assert frontend_fields == backend_fields


def _frontend_type_fields(type_path: str, type_name: str) -> dict[str, str]:
    source = (REPO_ROOT / "frontend" / "src" / type_path).read_text(
        encoding="utf-8",
    )
    fields = _parse_type_block(source, type_name)
    if fields is not None:
        return fields

    intersection = _parse_intersection_extension(source, type_name)
    if intersection is not None:
        base_name, extra_fields = intersection
        base_fields = _frontend_type_fields(type_path, base_name)
        return {**base_fields, **extra_fields}

    raise AssertionError(f"frontend type {type_name} not found in {type_path}")


def _parse_type_block(source: str, type_name: str) -> dict[str, str] | None:
    for match in TYPE_BLOCK_PATTERN.finditer(source):
        if match.group("name") != type_name:
            continue
        fields: dict[str, str] = {}
        for raw_line in match.group("body").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            field_match = FIELD_PATTERN.match(line)
            if field_match is None:
                continue
            name = field_match.group("name")
            field_type = field_match.group("type").rstrip(",")
            fields[name] = _normalize_typescript_type(field_type)
        return fields
    return None


def _parse_intersection_extension(
    source: str,
    type_name: str,
) -> tuple[str, dict[str, str]] | None:
    pattern = re.compile(
        rf"export type {re.escape(type_name)} = (?P<base>\w+) & \{{(?P<body>.*?)\n\}}",
        re.DOTALL,
    )
    match = pattern.search(source)
    if match is None:
        return None
    fields: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        field_match = FIELD_PATTERN.match(raw_line.strip())
        if field_match is not None:
            fields[field_match.group("name")] = _normalize_typescript_type(
                field_match.group("type").rstrip(","),
            )
    return match.group("base"), fields


def _normalize_typescript_type(value: str) -> str:
    normalized = value.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace(" | ", "|")
    normalized = normalized.replace("Record<string, unknown>[]", "record[]")
    normalized = normalized.replace("Record<string, unknown>", "record")
    normalized = normalized.replace("SiteMusing[]", "record[]")
    normalized = normalized.replace("SiteSocialLink[]", "record[]")
    if normalized in TYPE_ALIAS_NORMALIZATION:
        return TYPE_ALIAS_NORMALIZATION[normalized]
    literal_union = re.fullmatch(r"(?:'[^']+'(?:\|'[^']+')*)", normalized)
    if literal_union is not None:
        return "string"
    if normalized.endswith("[]"):
        item_type = normalized.removesuffix("[]")
        return f"{_normalize_typescript_type(item_type)}[]"
    return normalized


def _python_type_to_typescript(annotation: Any) -> str:
    optional, inner = _strip_optional(annotation)
    value = _python_inner_type_to_typescript(inner)
    return f"{value}|null" if optional else value


def _strip_optional(annotation: Any) -> tuple[bool, Any]:
    origin = get_origin(annotation)
    if origin is UnionType or (origin is not None and str(origin) == "typing.Union"):
        args = get_args(annotation)
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) != len(args):
            return True, non_none[0] if len(non_none) == 1 else non_none
    return False, annotation


def _python_inner_type_to_typescript(annotation: Any) -> str:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is list:
        return f"{_python_inner_type_to_typescript(args[0])}[]"
    if origin is dict:
        return "record"
    if origin is not None and str(origin) == "typing.Literal":
        return "string"
    if annotation is int or annotation is float:
        return "number"
    if annotation is str:
        return "string"
    if annotation is bool:
        return "boolean"
    if getattr(annotation, "__name__", "") == "datetime":
        return "string"
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return "record"
    return "record"
