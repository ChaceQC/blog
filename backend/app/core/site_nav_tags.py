SITE_NAV_TAGS_KEY = "items"
SITE_NAV_LEGACY_TAGS_KEY = "tags"
SITE_NAV_MAX_TAGS = 8
SITE_NAV_MAX_TAG_LENGTH = 24


def normalize_site_nav_tags_json(value: object) -> dict[str, list[str]] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("site nav tags must be an object")

    raw_items = value.get(SITE_NAV_TAGS_KEY)
    if raw_items is None and SITE_NAV_LEGACY_TAGS_KEY in value:
        raw_items = value[SITE_NAV_LEGACY_TAGS_KEY]
    if raw_items is None:
        if len(value) == 0:
            return None
        raise ValueError("site nav tags must include items")
    if not isinstance(raw_items, list):
        raise ValueError("site nav tags items must be a list")

    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw_items:
        if not isinstance(raw_tag, str):
            raise ValueError("site nav tag must be text")
        tag = raw_tag.strip()
        if tag == "":
            continue
        if len(tag) > SITE_NAV_MAX_TAG_LENGTH:
            raise ValueError("site nav tag is too long")
        tag_key = tag.casefold()
        if tag_key in seen:
            continue
        tags.append(tag)
        seen.add(tag_key)

    if len(tags) > SITE_NAV_MAX_TAGS:
        raise ValueError("too many site nav tags")
    return {SITE_NAV_TAGS_KEY: tags} if tags else None
