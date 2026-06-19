import pytest

from app.core.url_validation import (
    validate_http_url,
    validate_public_href,
    validate_public_image_src,
)
from app.schemas.content import CONTENT_MD_MAX_LENGTH, PostCreateRequest
from app.schemas.encryption import ENCRYPTION_CIPHERTEXT_MAX_LENGTH, EncryptedApiRequest
from app.schemas.links import (
    FriendLinkCreateRequest,
    PublicFriendLinkApplicationRequest,
    SiteNavItemCreateRequest,
)


def test_friend_link_url_allows_only_http_urls() -> None:
    payload = FriendLinkCreateRequest(
        name="友链",
        url="https://example.com",
        avatar_url="https://example.com/avatar.png",
    )

    assert payload.url == "https://example.com"
    with pytest.raises(ValueError):
        FriendLinkCreateRequest(name="坏链接", url="javascript:alert(1)")


def test_public_friend_application_rejects_private_protocol() -> None:
    with pytest.raises(ValueError):
        PublicFriendLinkApplicationRequest(name="坏链接", url="file:///etc/passwd")


def test_public_friend_application_rejects_invalid_http_port() -> None:
    with pytest.raises(ValueError):
        PublicFriendLinkApplicationRequest(
            name="坏端口",
            url="https://example.test:bad",
        )


def test_site_nav_item_allows_site_path_and_mailto_but_rejects_script() -> None:
    item = SiteNavItemCreateRequest(
        title="站内入口",
        url="/posts",
        icon_url="mailto:admin@example.com",
    )

    assert item.url == "/posts"
    assert item.icon_url == "mailto:admin@example.com"
    with pytest.raises(ValueError):
        SiteNavItemCreateRequest(title="坏入口", url="javascript:alert(1)")


@pytest.mark.parametrize(
    "url",
    [
        "/admin",
        "/admin/users",
        "/admin?next=/posts",
        "/api/admin",
        "/api/admin/content",
        "/API/Admin/content",
        "/%61dmin",
        "/%2561dmin",
        "/%2fadmin",
        "/%5cadmin",
    ],
)
def test_public_href_rejects_admin_site_paths(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_href(url)


def test_shared_url_validator_rejects_control_characters() -> None:
    with pytest.raises(ValueError):
        validate_public_href("https://example.com/\nnext")
    with pytest.raises(ValueError):
        validate_http_url("//example.com/path")


def test_public_image_src_allows_site_path_but_rejects_mailto() -> None:
    assert validate_public_image_src("/avatar.png") == "/avatar.png"
    with pytest.raises(ValueError):
        validate_public_image_src("mailto:admin@example.com")


def test_encrypted_request_rejects_oversized_ciphertext() -> None:
    with pytest.raises(ValueError):
        EncryptedApiRequest(
            session_id="session",
            profile="content-v1",
            nonce="nonce",
            ciphertext="a" * (ENCRYPTION_CIPHERTEXT_MAX_LENGTH + 1),
        )


def test_markdown_content_rejects_oversized_body() -> None:
    with pytest.raises(ValueError):
        PostCreateRequest(
            title="长文",
            slug="long-post",
            content_md="字" * (CONTENT_MD_MAX_LENGTH + 1),
        )
