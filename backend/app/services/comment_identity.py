from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new
from ipaddress import ip_address, ip_network
from json import dumps
from secrets import token_urlsafe

from app.schemas.content import VisitorFingerprint


@dataclass(frozen=True)
class CommentIdentity:
    author_key_hash: str
    author_public_id: str
    fingerprint_hash: str
    risk_hash: str


class CommentIdentityService:
    def __init__(self, *, secret_key: str) -> None:
        self._secret_key = secret_key

    def create_delete_token(self) -> str:
        return token_urlsafe(32)

    def delete_token_hash(self, delete_token: str) -> str:
        return self._hmac_text("comment:delete", delete_token)

    def body_hash(self, body_text: str) -> str:
        return self._hmac_text("comment:body", body_text)

    def verify_delete_token(
        self,
        *,
        stored_hash: str | None,
        delete_token: str,
    ) -> bool:
        if stored_hash is None:
            return False
        return compare_digest(stored_hash, self.delete_token_hash(delete_token))

    def identity(
        self,
        *,
        post_id: int,
        author_secret_proof: str,
        fingerprint: VisitorFingerprint,
        client_ip: str | None,
        user_agent: str | None,
        accept_language: str | None,
    ) -> CommentIdentity:
        author_key_hash = self._hmac_text(
            "comment:author",
            author_secret_proof,
        )
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
        fingerprint_hash = self._hmac_json(
            "comment:fingerprint",
            fingerprint_payload,
        )
        risk_fingerprint_hash = self._hmac_json(
            "comment:risk-fingerprint",
            risk_fingerprint_payload,
        )
        risk_hash = self._hmac_json(
            "comment:risk",
            {
                "accept_language": _short_text(accept_language, 96),
                "ip_prefix": _ip_prefix(client_ip),
                "risk_fingerprint_hash": risk_fingerprint_hash,
                "user_agent": _short_text(user_agent, 256),
            },
        )
        author_public_id = self._hmac_text(
            "comment:public",
            f"{post_id}:{author_key_hash}",
        )[:6].upper()
        return CommentIdentity(
            author_key_hash=author_key_hash,
            author_public_id=author_public_id,
            fingerprint_hash=fingerprint_hash,
            risk_hash=risk_hash,
        )

    def _hmac_text(self, namespace: str, value: str) -> str:
        return hmac_new(
            self._secret_key.encode(),
            f"{namespace}:{value}".encode(),
            sha256,
        ).hexdigest()

    def _hmac_json(self, namespace: str, payload: dict[str, object]) -> str:
        canonical = dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return self._hmac_text(namespace, canonical)


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
