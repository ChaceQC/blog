import re
from collections.abc import Sequence
from datetime import datetime

from app.core.auth import utc_now


def build_post_file_usages(
    *,
    content_md: str,
    cover_file_id: int | None,
) -> list[tuple[int, str]]:
    usages: list[tuple[int, str]] = []
    if cover_file_id is not None:
        usages.append((cover_file_id, "cover"))

    for file_id in extract_post_body_file_ids(content_md):
        usages.append((file_id, "post_body"))

    seen: set[tuple[int, str]] = set()
    deduped: list[tuple[int, str]] = []
    for usage in usages:
        if usage not in seen:
            seen.add(usage)
            deduped.append(usage)
    return deduped


def extract_post_body_file_ids(content_md: str) -> list[int]:
    pattern = re.compile(
        r"/?api/public/posts/[a-z0-9][a-z0-9_-]*/files/(?P<file_id>\d+)/render",
    )
    return [int(match.group("file_id")) for match in pattern.finditer(content_md)]


def published_at_for_status(
    *,
    status: str,
    requested_at: datetime | None,
) -> datetime | None:
    if status == "published":
        return requested_at or utc_now()
    if status == "scheduled":
        return requested_at
    return None


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
