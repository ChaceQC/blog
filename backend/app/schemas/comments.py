import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.content import SLUG_PATTERN, VisitorFingerprint

COMMENT_BODY_MAX_LENGTH = 2_000
COMMENT_BODY_MAX_LINES = 30
COMMENT_BODY_MAX_LINE_LENGTH = 300
COMMENT_DISPLAY_NAME_MAX_LENGTH = 32
COMMENT_DELETE_TOKEN_MAX_LENGTH = 256
COMMENT_RECEIPT_MAX_COUNT = 50
AUTHOR_SECRET_PROOF_PATTERN = re.compile(r"^[a-f0-9]{64}$")
DELETE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
COMMENT_STATUS_PENDING = "pending"
COMMENT_STATUS_PUBLISHED = "published"
COMMENT_STATUS_REJECTED = "rejected"
COMMENT_STATUS_DELETED_BY_AUTHOR = "deleted_by_author"
COMMENT_STATUS_DELETED_BY_ADMIN = "deleted_by_admin"
COMMENT_STATUS_SPAM = "spam"
COMMENT_PUBLIC_OWNED_STATUSES = {
    COMMENT_STATUS_PENDING,
    COMMENT_STATUS_PUBLISHED,
    COMMENT_STATUS_DELETED_BY_AUTHOR,
    COMMENT_STATUS_DELETED_BY_ADMIN,
}
COMMENT_PUBLIC_LIST_STATUSES = {
    COMMENT_STATUS_PUBLISHED,
    COMMENT_STATUS_DELETED_BY_AUTHOR,
    COMMENT_STATUS_DELETED_BY_ADMIN,
}
RESERVED_DISPLAY_NAMES = {
    "admin",
    "administrator",
    "chace",
    "chaceqc",
    "root",
    "system",
    "管理员",
    "站长",
    "博主",
    "系统",
}

CommentStatus = Literal[
    "pending",
    "published",
    "rejected",
    "deleted_by_author",
    "deleted_by_admin",
    "spam",
]
AdminCommentStatusFilter = Literal[
    "all",
    "pending",
    "published",
    "rejected",
    "deleted_by_author",
    "deleted_by_admin",
    "spam",
]
AdminCommentReviewAction = Literal["approve", "reject", "spam", "delete"]


class PublicCommentItem(BaseModel):
    id: int
    parent_id: int | None = None
    status: CommentStatus
    display_name: str
    author_public_id: str
    body_text: str
    reply_count: int = Field(ge=0)
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicCommentListResponse(BaseModel):
    items: list[PublicCommentItem]
    total: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class PublicCommentCreateRequest(BaseModel):
    parent_id: int | None = Field(default=None, ge=1)
    display_name: str | None = Field(default=None, max_length=64)
    body_text: str = Field(min_length=1, max_length=COMMENT_BODY_MAX_LENGTH)
    author_secret_proof: str = Field(min_length=32, max_length=128)
    fingerprint: VisitorFingerprint

    model_config = ConfigDict(extra="forbid")

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        return normalize_display_name(value)

    @field_validator("body_text")
    @classmethod
    def normalize_body_text(cls, value: str) -> str:
        return normalize_comment_body(value)

    @field_validator("author_secret_proof")
    @classmethod
    def normalize_author_secret_proof(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not AUTHOR_SECRET_PROOF_PATTERN.fullmatch(cleaned):
            raise ValueError("author secret proof must be a sha256 hex digest")
        return cleaned


class PublicCommentCreateResponse(BaseModel):
    comment: PublicCommentItem
    delete_token: str = Field(min_length=32, max_length=COMMENT_DELETE_TOKEN_MAX_LENGTH)
    message: str

    model_config = ConfigDict(extra="forbid")


class PublicCommentDeleteRequest(BaseModel):
    delete_token: str = Field(min_length=32, max_length=COMMENT_DELETE_TOKEN_MAX_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @field_validator("delete_token")
    @classmethod
    def normalize_delete_token(cls, value: str) -> str:
        return normalize_delete_token(value)


class PublicCommentDeleteResponse(BaseModel):
    id: int
    status: CommentStatus

    model_config = ConfigDict(extra="forbid")


class PublicOwnedCommentReceipt(BaseModel):
    comment_id: int = Field(ge=1)
    post_slug: Annotated[str | None, Field(pattern=SLUG_PATTERN)] = None
    delete_token: str = Field(min_length=32, max_length=COMMENT_DELETE_TOKEN_MAX_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @field_validator("delete_token")
    @classmethod
    def normalize_delete_token(cls, value: str) -> str:
        return normalize_delete_token(value)


class PublicOwnedCommentsRequest(BaseModel):
    receipts: list[PublicOwnedCommentReceipt] = Field(
        default_factory=list,
        max_length=COMMENT_RECEIPT_MAX_COUNT,
    )

    model_config = ConfigDict(extra="forbid")


class PublicOwnedCommentsResponse(BaseModel):
    items: list[PublicCommentItem]

    model_config = ConfigDict(extra="forbid")


class AdminCommentItem(BaseModel):
    id: int
    post_id: int
    post_title: str
    post_slug: str
    parent_id: int | None = None
    status: CommentStatus
    display_name: str
    author_public_id: str
    body_text: str
    reply_count: int = Field(ge=0)
    risk_hash_prefix: str
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: int | None = None
    deleted_at: datetime | None = None
    deleted_reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class AdminCommentListResponse(BaseModel):
    items: list[AdminCommentItem]
    total: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class AdminCommentReviewRequest(BaseModel):
    action: AdminCommentReviewAction
    reason_class: str | None = Field(default=None, max_length=64)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason_class")
    @classmethod
    def normalize_reason_class(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        if not all(char.isalnum() or char in {"_", "-"} for char in cleaned):
            raise ValueError("invalid reason class")
        return cleaned


def normalize_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    if len(cleaned) > COMMENT_DISPLAY_NAME_MAX_LENGTH:
        raise ValueError("display name is too long")
    if _has_control_characters(cleaned):
        raise ValueError("display name cannot contain control characters")
    if cleaned.casefold() in RESERVED_DISPLAY_NAMES:
        raise ValueError("display name is reserved")
    return cleaned


def normalize_comment_body(value: str) -> str:
    cleaned = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        raise ValueError("comment body cannot be empty")
    if len(cleaned) > COMMENT_BODY_MAX_LENGTH:
        raise ValueError("comment body is too long")
    if _has_control_characters(cleaned, allow_newline=True, allow_tab=True):
        raise ValueError("comment body cannot contain control characters")
    lines = cleaned.split("\n")
    if len(lines) > COMMENT_BODY_MAX_LINES:
        raise ValueError("comment body has too many lines")
    if any(len(line) > COMMENT_BODY_MAX_LINE_LENGTH for line in lines):
        raise ValueError("comment body line is too long")
    return cleaned


def normalize_delete_token(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) < 32:
        raise ValueError("delete token is too short")
    if len(cleaned) > COMMENT_DELETE_TOKEN_MAX_LENGTH:
        raise ValueError("delete token is too long")
    if _has_control_characters(cleaned):
        raise ValueError("delete token cannot contain control characters")
    if not DELETE_TOKEN_PATTERN.fullmatch(cleaned):
        raise ValueError("delete token must be base64url text")
    return cleaned


def _has_control_characters(
    value: str,
    *,
    allow_newline: bool = False,
    allow_tab: bool = False,
) -> bool:
    for char in value:
        code = ord(char)
        if allow_newline and char == "\n":
            continue
        if allow_tab and char == "\t":
            continue
        if code < 32 or code == 127:
            return True
    return False
