from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi import Request

from app.providers.telemetry import TelemetryService


def telemetry_context(request: Request) -> dict[str, str]:
    context = getattr(request.state, "telemetry_context", None)
    if isinstance(context, dict):
        return context

    context = {
        "request_id": uuid4().hex,
        "trace_id": uuid4().hex,
        "span_id": uuid4().hex[:16],
    }
    request.state.telemetry_context = context
    return context


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return _with_api_prefix(
            template=template,
            path=str(request.scope.get("path") or "/"),
        )

    path = str(request.scope.get("path") or "/")
    if path == "/":
        return "/"
    if path.startswith("/api/admin"):
        return "/api/admin/{unmatched}"
    if path.startswith("/api/public"):
        return "/api/public/{unmatched}"
    return "/{unmatched}"


def request_scope_component(request: Request) -> tuple[str, str]:
    route = route_template(request)
    if route.startswith("/api/admin/encryption") or route.startswith(
        "/api/public/encryption",
    ):
        return scope_from_route(route), "encryption"
    if "/files" in route:
        return scope_from_route(route), "files"
    if route.startswith("/api/admin/auth"):
        return "admin", "auth"
    if route.startswith("/api/admin"):
        return "admin", "admin-api"
    if route.startswith("/api/public"):
        return "public", "public-api"
    if route in {"/rss.xml", "/sitemap.xml", "/robots.txt"}:
        return "public", "feeds"
    return "system", "system"


def request_tags(
    telemetry: TelemetryService,
    request: Request,
    *,
    status_code: int,
    outcome: str,
) -> dict[str, str]:
    scope, component = request_scope_component(request)
    return telemetry.request_tags(
        component=component,
        scope=scope,
        route=route_template(request),
        method=request.method,
        status_code=status_code,
        outcome=outcome,
    )


def scope_from_route(route: str) -> str:
    if route.startswith("/api/admin"):
        return "admin"
    if route.startswith("/api/public"):
        return "public"
    return "system"


def outcome_from_status(status_code: int) -> str:
    if status_code == 429:
        return "limited"
    if status_code in {401, 403}:
        return "denied"
    if status_code >= 400:
        return "error"
    return "ok"


def safe_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:128]


def reason_class(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"_", "-", "."} else "_"
        for char in value.lower()
    ).strip("_")
    return cleaned[:64] or "unknown"


def error_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def deterministic_sample(seed: str, percent: int) -> bool:
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return digest[0] < int(256 * percent / 100)


def _with_api_prefix(*, template: str, path: str) -> str:
    if template.startswith("/api/"):
        return template
    for prefix in ("/api/admin", "/api/public"):
        if path == prefix or path.startswith(f"{prefix}/"):
            return f"{prefix}{template}"
    return template
