import re
from collections.abc import Sequence
from hashlib import sha1

from sqlalchemy import or_

from app.models.content import Post


def normalize_labels(labels: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for label in labels:
        value = label.strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        normalized.append(value[:64])
    return normalized


def slug_from_label(label: str, *, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    if slug:
        return slug[:80]
    digest = sha1(label.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def public_post_filters(now) -> tuple[object, ...]:
    return (
        Post.deleted_at.is_(None),
        or_(
            Post.status == "published",
            Post.status == "scheduled",
        ),
        Post.visibility == "public",
        Post.published_at.is_not(None),
        Post.published_at <= now,
    )


def rows_to_map(rows: Sequence[tuple[int, str]]) -> dict[int, list[str]]:
    mapped: dict[int, list[str]] = {}
    for post_id, name in rows:
        mapped.setdefault(post_id, []).append(name)
    return mapped
