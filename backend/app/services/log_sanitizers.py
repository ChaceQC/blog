from typing import Any

LOG_IP_MAX_LENGTH = 64
LOG_PATH_MAX_LENGTH = 500
LOG_USER_AGENT_MAX_LENGTH = 500

AUDIT_PAYLOAD_ALLOWED_KEYS = frozenset(
    {
        "changed_fields",
        "status",
        "visibility",
        "public_listed",
        "show_in_nav",
        "published",
        "published_at_set",
        "review_status",
        "reason_class",
        "previous_status",
        "deleted",
        "is_public",
    },
)
SECURITY_EVENT_DETAIL_ALLOWED_KEYS = frozenset({"scope", "profile", "credential"})


def sanitize_log_ip(value: str | None) -> str | None:
    return _truncate_text(value, LOG_IP_MAX_LENGTH)


def sanitize_log_path(value: str | None) -> str | None:
    return _truncate_text(value, LOG_PATH_MAX_LENGTH)


def sanitize_log_user_agent(value: str | None) -> str | None:
    return _truncate_text(value, LOG_USER_AGENT_MAX_LENGTH)


def sanitize_audit_log_payload(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _sanitize_json_payload(payload, AUDIT_PAYLOAD_ALLOWED_KEYS)


def sanitize_access_log_detail(_: dict[str, Any] | None) -> None:
    return None


def sanitize_security_event_detail(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _sanitize_json_payload(payload, SECURITY_EVENT_DETAIL_ALLOWED_KEYS)


def _sanitize_json_payload(
    payload: dict[str, Any] | None,
    allowed_keys: frozenset[str],
) -> dict[str, Any] | None:
    if payload is None:
        return None

    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in allowed_keys:
            continue
        safe_value = _safe_json_value(key=key, value=value)
        if safe_value is not None:
            sanitized[key] = safe_value
    return sanitized or None


def _safe_json_value(*, key: str, value: Any) -> Any:
    if key == "changed_fields":
        if not isinstance(value, (list, tuple, set)):
            return None
        fields = sorted(
            str(item)
            for item in value
            if isinstance(item, str) and item.strip()
        )
        return fields[:64] if fields else None
    if isinstance(value, (str, bool, int, float)):
        return value
    return None


def _truncate_text(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]
