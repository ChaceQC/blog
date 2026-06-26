from dataclasses import dataclass
from hashlib import sha256
from hmac import new as hmac_new
from ipaddress import ip_address, ip_network
from json import dumps
from typing import Protocol

from app.schemas.content import PublicPostInteractionState, VisitorFingerprint
from app.services.content_errors import ContentNotFoundError
from app.services.logs import AccessLogDedupeBackend, AccessLogDedupeRule


class PostInteractionRiskLimited(Exception):
    pass


class PostInteractionRepositoryProtocol(Protocol):
    async def get_public_post_counts_by_slug(
        self,
        slug: str,
    ) -> tuple[int, int, int] | None: ...

    async def get_post_like_active(
        self,
        *,
        post_id: int,
        visitor_hash: str,
    ) -> bool | None: ...

    async def increment_post_view_count(self, *, post_id: int) -> None: ...

    async def set_post_like_state(
        self,
        *,
        post_id: int,
        visitor_hash: str,
        fingerprint_hash: str,
        risk_hash: str,
        liked: bool,
    ) -> bool: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True)
class PostInteractionIdentity:
    visitor_hash: str
    fingerprint_hash: str
    risk_hash: str


class PostInteractionService:
    def __init__(
        self,
        *,
        repository: PostInteractionRepositoryProtocol,
        dedupe_backend: AccessLogDedupeBackend,
        secret_key: str,
        view_dedupe_seconds: int,
        like_risk_window_seconds: int,
    ) -> None:
        self.repository = repository
        self._dedupe_backend = dedupe_backend
        self._secret_key = secret_key
        self._view_dedupe_seconds = view_dedupe_seconds
        self._like_risk_window_seconds = like_risk_window_seconds

    async def record_view(
        self,
        *,
        slug: str,
        fingerprint: VisitorFingerprint,
        client_ip: str | None,
        user_agent: str | None,
        accept_language: str | None,
    ) -> PublicPostInteractionState:
        counts = await self._require_counts(slug)
        post_id, _, _ = counts
        identity = self._identity(
            fingerprint=fingerprint,
            client_ip=client_ip,
            user_agent=user_agent,
            accept_language=accept_language,
        )
        if self._should_record_view(post_id=post_id, identity=identity):
            await self.repository.increment_post_view_count(post_id=post_id)
            await self.repository.commit()
        return await self._state(slug=slug, identity=identity)

    async def set_like(
        self,
        *,
        slug: str,
        fingerprint: VisitorFingerprint,
        liked: bool,
        client_ip: str | None,
        user_agent: str | None,
        accept_language: str | None,
    ) -> PublicPostInteractionState:
        counts = await self._require_counts(slug)
        post_id, _, _ = counts
        identity = self._identity(
            fingerprint=fingerprint,
            client_ip=client_ip,
            user_agent=user_agent,
            accept_language=accept_language,
        )
        current = await self.repository.get_post_like_active(
            post_id=post_id,
            visitor_hash=identity.visitor_hash,
        )
        if liked and current is None and not self._reserve_like_risk(
            post_id=post_id,
            identity=identity,
        ):
            raise PostInteractionRiskLimited("post like risk limited")
        await self.repository.set_post_like_state(
            post_id=post_id,
            visitor_hash=identity.visitor_hash,
            fingerprint_hash=identity.fingerprint_hash,
            risk_hash=identity.risk_hash,
            liked=liked,
        )
        await self.repository.commit()
        return await self._state(slug=slug, identity=identity)

    async def _state(
        self,
        *,
        slug: str,
        identity: PostInteractionIdentity,
    ) -> PublicPostInteractionState:
        post_id, view_count, like_count = await self._require_counts(slug)
        liked = await self.repository.get_post_like_active(
            post_id=post_id,
            visitor_hash=identity.visitor_hash,
        )
        return PublicPostInteractionState(
            view_count=view_count,
            like_count=like_count,
            liked=bool(liked),
        )

    async def _require_counts(self, slug: str) -> tuple[int, int, int]:
        counts = await self.repository.get_public_post_counts_by_slug(slug)
        if counts is None:
            raise ContentNotFoundError("post not found")
        return counts

    def _should_record_view(
        self,
        *,
        post_id: int,
        identity: PostInteractionIdentity,
    ) -> bool:
        if self._view_dedupe_seconds <= 0:
            return True
        return self._dedupe_backend.should_record(
            key=f"post-view:{post_id}:{identity.risk_hash}",
            rule=AccessLogDedupeRule(window_seconds=self._view_dedupe_seconds),
        )

    def _reserve_like_risk(
        self,
        *,
        post_id: int,
        identity: PostInteractionIdentity,
    ) -> bool:
        if self._like_risk_window_seconds <= 0:
            return True
        return self._dedupe_backend.should_record(
            key=f"post-like-risk:{post_id}:{identity.risk_hash}",
            rule=AccessLogDedupeRule(window_seconds=self._like_risk_window_seconds),
        )

    def _identity(
        self,
        *,
        fingerprint: VisitorFingerprint,
        client_ip: str | None,
        user_agent: str | None,
        accept_language: str | None,
    ) -> PostInteractionIdentity:
        fingerprint_payload = {
            "browser_hash": fingerprint.browser_hash,
            "composite_hash": fingerprint.composite_hash,
            "device_hash": fingerprint.device_hash,
            "language": fingerprint.language,
            "platform": fingerprint.platform,
            "screen": fingerprint.screen,
            "timezone": fingerprint.timezone,
            "version": fingerprint.version,
        }
        risk_fingerprint_payload = {
            "browser_hash": fingerprint.browser_hash,
            "device_hash": fingerprint.device_hash,
            "language": fingerprint.language,
            "platform": fingerprint.platform,
            "screen": fingerprint.screen,
            "timezone": fingerprint.timezone,
            "version": fingerprint.version,
        }
        fingerprint_hash = self._hmac("post:fingerprint", fingerprint_payload)
        risk_fingerprint_hash = self._hmac(
            "post:risk-fingerprint",
            risk_fingerprint_payload,
        )
        visitor_hash = self._hmac("post:visitor", fingerprint_payload)
        risk_hash = self._hmac(
            "post:risk",
            {
                "accept_language": _short_text(accept_language, 96),
                "ip_prefix": _ip_prefix(client_ip),
                "risk_fingerprint_hash": risk_fingerprint_hash,
                "user_agent": _short_text(user_agent, 256),
            },
        )
        return PostInteractionIdentity(
            visitor_hash=visitor_hash,
            fingerprint_hash=fingerprint_hash,
            risk_hash=risk_hash,
        )

    def _hmac(self, namespace: str, payload: dict[str, object]) -> str:
        canonical = dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hmac_new(
            self._secret_key.encode(),
            f"{namespace}:{canonical}".encode(),
            sha256,
        ).hexdigest()


def _ip_prefix(value: str | None) -> str:
    if not value:
        return "unknown"
    try:
        parsed = ip_address(value)
    except ValueError:
        return "invalid"
    if parsed.version == 4:
        return str(ip_network(f"{parsed}/24", strict=False).network_address)
    return str(ip_network(f"{parsed}/48", strict=False).network_address)


def _short_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]
