import pytest

from app.schemas.content import VisitorFingerprint
from app.services.logs import InMemoryAccessLogDedupeBackend
from app.services.post_interactions import (
    PostInteractionRiskLimited,
    PostInteractionService,
)


class FakePostInteractionRepository:
    def __init__(self) -> None:
        self.post_id = 1
        self.slug = "public-post"
        self.view_count = 10
        self.like_count = 2
        self.likes: dict[tuple[int, str], bool] = {}
        self.commit_count = 0

    async def get_public_post_counts_by_slug(
        self,
        slug: str,
    ) -> tuple[int, int, int] | None:
        if slug != self.slug:
            return None
        return self.post_id, self.view_count, self.like_count

    async def get_post_like_active(
        self,
        *,
        post_id: int,
        visitor_hash: str,
    ) -> bool | None:
        return self.likes.get((post_id, visitor_hash))

    async def increment_post_view_count(self, *, post_id: int) -> None:
        assert post_id == self.post_id
        self.view_count += 1

    async def set_post_like_state(
        self,
        *,
        post_id: int,
        visitor_hash: str,
        fingerprint_hash: str,
        risk_hash: str,
        liked: bool,
    ) -> bool:
        assert post_id == self.post_id
        assert len(fingerprint_hash) == 64
        assert len(risk_hash) == 64
        key = (post_id, visitor_hash)
        previous = self.likes.get(key)
        if previous is None:
            if not liked:
                return False
            self.likes[key] = True
            self.like_count += 1
            return True
        if previous != liked:
            self.like_count = (
                self.like_count + 1 if liked else max(0, self.like_count - 1)
            )
        self.likes[key] = liked
        return liked

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_record_view_dedupes_incognito_visitor_id_rotation() -> None:
    repository = FakePostInteractionRepository()
    service = create_service(repository, view_dedupe_seconds=600)
    fingerprint = visitor_fingerprint(composite_hash="c" * 64)

    first = await service.record_view(
        slug="public-post",
        fingerprint=fingerprint,
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    second = await service.record_view(
        slug="public-post",
        fingerprint=visitor_fingerprint(composite_hash="d" * 64),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    assert first.view_count == 11
    assert second.view_count == 11
    assert repository.view_count == 11
    assert repository.commit_count == 1


@pytest.mark.anyio
async def test_like_is_idempotent_target_state() -> None:
    repository = FakePostInteractionRepository()
    service = create_service(repository)
    fingerprint = visitor_fingerprint(composite_hash="c" * 64)

    first = await service.set_like(
        slug="public-post",
        fingerprint=fingerprint,
        liked=True,
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    second = await service.set_like(
        slug="public-post",
        fingerprint=fingerprint,
        liked=True,
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    removed = await service.set_like(
        slug="public-post",
        fingerprint=fingerprint,
        liked=False,
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    assert first.like_count == 3
    assert second.like_count == 3
    assert removed.like_count == 2
    assert removed.liked is False


@pytest.mark.anyio
async def test_like_risk_window_blocks_incognito_visitor_id_rotation() -> None:
    repository = FakePostInteractionRepository()
    service = create_service(repository, like_risk_window_seconds=86400)

    await service.set_like(
        slug="public-post",
        fingerprint=visitor_fingerprint(composite_hash="c" * 64),
        liked=True,
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    with pytest.raises(PostInteractionRiskLimited):
        await service.set_like(
            slug="public-post",
            fingerprint=visitor_fingerprint(composite_hash="d" * 64),
            liked=True,
            client_ip="203.0.113.8",
            user_agent="pytest-browser",
            accept_language="zh-CN",
        )

    assert repository.like_count == 3
    assert len(repository.likes) == 1


def create_service(
    repository: FakePostInteractionRepository,
    *,
    view_dedupe_seconds: int = 600,
    like_risk_window_seconds: int = 86400,
) -> PostInteractionService:
    return PostInteractionService(
        repository=repository,
        dedupe_backend=InMemoryAccessLogDedupeBackend(),
        secret_key="test-secret-key-with-at-least-32-chars",
        view_dedupe_seconds=view_dedupe_seconds,
        like_risk_window_seconds=like_risk_window_seconds,
    )


def visitor_fingerprint(*, composite_hash: str) -> VisitorFingerprint:
    return VisitorFingerprint(
        version="web-v1",
        visitor_id="local-visitor-id-0123456789",
        browser_hash="a" * 64,
        device_hash="b" * 64,
        composite_hash=composite_hash,
        timezone="Asia/Shanghai",
        language="zh-CN",
        platform="Win32",
        screen="1536x864x24",
        created_at_ms=1782460800000,
    )
