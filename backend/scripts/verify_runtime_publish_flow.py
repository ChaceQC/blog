from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any, Literal

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
from websockets.sync.client import connect as ws_connect

from app.core.encryption_sid import ESID_COOKIE_NAME, create_encryption_sid
from app.core.login_capsule import LOGIN_CAPSULE_SCHEME, derive_login_capsule_keys

EncryptionProfile = Literal["sensitive-v1", "content-v1"]
EncryptionScope = Literal["admin", "public"]
SaltPurpose = Literal["esid", "login_capsule", "request", "response"]

SALT_WRAP_INFO = b"blog-cms:wss-salt-wrap:v1"


@dataclass(frozen=True)
class EncryptionSession:
    id: str
    scope: EncryptionScope
    shared_key: bytes
    profiles: list[str]
    expires_at: datetime
    login_challenge: dict[str, Any] | None = None


@dataclass(frozen=True)
class SaltLease:
    lease_id: str
    purpose: SaltPurpose
    scope: EncryptionScope
    profile: EncryptionProfile | None
    salt: bytes
    expires_at: datetime


@dataclass(frozen=True)
class RuntimeVerifyResult:
    post_id: int
    post_slug: str
    page_id: int
    page_slug: str
    file_id: int
    private_file_id: int
    approved_friend_link_id: int
    rejected_friend_link_id: int
    site_item_id: int
    category_slug: str
    tag_slug: str
    checked_public_routes: list[str]
    checked_admin_routes: list[str]
    checked_access_types: list[str]


class RuntimeVerifyError(Exception):
    pass


@dataclass(frozen=True)
class M4RuntimeVerifyResult:
    approved_friend_link_id: int
    rejected_friend_link_id: int
    friend_link_group_id: int
    site_group_id: int
    site_item_id: int
    checked_public_routes: list[str]


class RuntimeApiClient:
    def __init__(self, *, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=False,
        )
        self._response_salts: dict[str, SaltLease] = {}

    def close(self) -> None:
        self.client.close()

    def create_session(self, scope: EncryptionScope) -> EncryptionSession:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_numbers = private_key.public_key().public_numbers()
        response = self.client.post(
            f"/api/{scope}/encryption/sessions",
            json={
                "client_public_key": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": _b64url(
                        public_numbers.x.to_bytes(32, byteorder="big"),
                    ),
                    "y": _b64url(
                        public_numbers.y.to_bytes(32, byteorder="big"),
                    ),
                },
            },
        )
        _raise_for_status(response, "加密会话协商失败")
        payload = response.json()
        server_key = payload["server_public_key"]
        server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(),
            b"\x04" + _b64url_decode(server_key["x"]) + _b64url_decode(server_key["y"]),
        )
        shared_key = private_key.exchange(ec.ECDH(), server_public_key)
        return EncryptionSession(
            id=payload["session_id"],
            scope=payload["scope"],
            shared_key=shared_key,
            profiles=list(payload["profiles"]),
            expires_at=datetime.fromisoformat(
                str(payload["expires_at"]).replace("Z", "+00:00"),
            ),
            login_challenge=payload.get("login_challenge"),
        )

    def decrypt(
        self,
        envelope: dict[str, Any],
        *,
        session: EncryptionSession,
        profile: EncryptionProfile,
    ) -> dict[str, Any]:
        if envelope.get("session_id") != session.id:
            raise RuntimeVerifyError("加密响应 session_id 不匹配")
        if envelope.get("profile") != profile:
            raise RuntimeVerifyError("加密响应 profile 不匹配")
        salt_id = str(envelope.get("salt_id") or "")
        if not salt_id:
            raise RuntimeVerifyError("加密响应缺少 salt_id")
        response_salt = self._consume_salt(
            session=session,
            lease_id=salt_id,
            purpose="response",
            profile=profile,
        )
        aesgcm = AESGCM(_derive_key(session.shared_key, profile, response_salt.salt))
        plaintext = aesgcm.decrypt(
            _b64url_decode(str(envelope["nonce"])),
            _b64url_decode(str(envelope["ciphertext"])),
            _associated_data(profile),
        )
        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise RuntimeVerifyError("加密响应解密结果不是对象")
        return decoded

    def encrypt(
        self,
        payload: dict[str, Any],
        *,
        session: EncryptionSession,
        profile: EncryptionProfile,
    ) -> dict[str, str]:
        request_salt = self._issue_salt(
            session=session,
            purpose="request",
            profile=profile,
        )
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        ciphertext = AESGCM(
            _derive_key(session.shared_key, profile, request_salt.salt),
        ).encrypt(
            nonce,
            plaintext,
            _associated_data(profile),
        )
        return {
            "session_id": session.id,
            "profile": profile,
            "salt_id": request_salt.lease_id,
            "nonce": _b64url(nonce),
            "ciphertext": _b64url(ciphertext),
        }

    def login(
        self,
        *,
        username: str,
        password: str,
        session: EncryptionSession,
    ) -> dict[str, Any]:
        capsule = self._login_capsule(
            username=username,
            password=password,
            session=session,
            path="/api/admin/auth/login",
        )
        response = self.client.post(
            "/api/admin/auth/login",
            headers=self._encrypted_headers(session=session, profile="sensitive-v1"),
            json=capsule,
        )
        _raise_for_status(response, "后台登录失败")
        return self.decrypt(
            response.json(),
            session=session,
            profile="sensitive-v1",
        )

    def upload_image(
        self,
        *,
        session: EncryptionSession,
        csrf_token: str,
        filename: str,
        data: bytes,
        visibility: Literal["public", "private"],
        public_listed: bool,
        alt_text: str,
    ) -> dict[str, Any]:
        response = self.client.post(
            "/api/admin/files",
            headers={
                "X-CSRF-Token": csrf_token,
                **self._encrypted_headers(session=session, profile="content-v1"),
            },
            data={
                "visibility": visibility,
                "alt_text": alt_text,
                "public_listed": "true" if public_listed else "false",
            },
            files={
                "file": (
                    filename,
                    data,
                    "image/png",
                ),
            },
        )
        _raise_for_status(response, "上传验证图片失败")
        return self.decrypt(
            response.json(),
            session=session,
            profile="content-v1",
        )

    def upload_public_image(
        self,
        *,
        session: EncryptionSession,
        csrf_token: str,
        run_token: str,
    ) -> dict[str, Any]:
        return self.upload_image(
            session=session,
            csrf_token=csrf_token,
            filename=f"runtime-flow-cover-{run_token}.png",
            data=_runtime_png(run_token=run_token, variant="public"),
            visibility="public",
            public_listed=True,
            alt_text="运行库闭环验证图",
        )

    def upload_private_image(
        self,
        *,
        session: EncryptionSession,
        csrf_token: str,
        run_token: str,
    ) -> dict[str, Any]:
        return self.upload_image(
            session=session,
            csrf_token=csrf_token,
            filename=f"runtime-flow-private-{run_token}.png",
            data=_runtime_png(run_token=run_token, variant="private"),
            visibility="private",
            public_listed=False,
            alt_text="运行库私有文件验证图",
        )

    def encrypted_post(
        self,
        path: str,
        *,
        session: EncryptionSession,
        csrf_token: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.client.post(
            path,
            headers={
                "X-CSRF-Token": csrf_token,
                **self._encrypted_headers(session=session, profile="content-v1"),
            },
            json=(
                self.encrypt(payload, session=session, profile="content-v1")
                if payload is not None
                else None
            ),
        )
        _raise_for_status(response, f"POST {path} 失败")
        return self.decrypt(
            response.json(),
            session=session,
            profile="content-v1",
        )

    def public_encrypted_post(
        self,
        path: str,
        *,
        session: EncryptionSession,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.client.post(
            path,
            headers=self._encrypted_headers(session=session, profile="content-v1"),
            json=self.encrypt(payload, session=session, profile="content-v1"),
        )
        _raise_for_status(response, f"POST {path} 失败")
        return self.decrypt(
            response.json(),
            session=session,
            profile="content-v1",
        )

    def encrypted_patch(
        self,
        path: str,
        *,
        session: EncryptionSession,
        csrf_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.client.patch(
            path,
            headers={
                "X-CSRF-Token": csrf_token,
                **self._encrypted_headers(session=session, profile="content-v1"),
            },
            json=self.encrypt(payload, session=session, profile="content-v1"),
        )
        _raise_for_status(response, f"PATCH {path} 失败")
        return self.decrypt(
            response.json(),
            session=session,
            profile="content-v1",
        )

    def encrypted_delete(
        self,
        path: str,
        *,
        session: EncryptionSession,
        csrf_token: str,
    ) -> dict[str, Any]:
        response = self.client.delete(
            path,
            headers={
                "X-CSRF-Token": csrf_token,
                **self._encrypted_headers(session=session, profile="content-v1"),
            },
        )
        _raise_for_status(response, f"DELETE {path} 失败")
        return self.decrypt(
            response.json(),
            session=session,
            profile="content-v1",
        )

    def encrypted_get(
        self,
        path: str,
        *,
        session: EncryptionSession,
        profile: EncryptionProfile,
    ) -> dict[str, Any]:
        response = self.client.get(
            path,
            headers=self._encrypted_headers(session=session, profile=profile),
        )
        _raise_for_status(response, f"GET {path} 失败")
        return self.decrypt(response.json(), session=session, profile=profile)

    def encrypted_get_response(
        self,
        path: str,
        *,
        session: EncryptionSession,
        profile: EncryptionProfile,
    ) -> httpx.Response:
        return self.client.get(
            path,
            headers=self._encrypted_headers(session=session, profile=profile),
        )

    def get_binary(self, url: str) -> httpx.Response:
        response = self.client.get(url)
        _raise_for_status(response, f"请求文件 {url} 失败")
        return response

    def get_text(self, path: str) -> str:
        response = self.client.get(path)
        _raise_for_status(response, f"GET {path} 失败")
        return response.text

    def _encrypted_headers(
        self,
        *,
        session: EncryptionSession,
        profile: EncryptionProfile,
    ) -> dict[str, str]:
        esid_salt = self._issue_salt(session=session, purpose="esid", profile=None)
        esid = create_encryption_sid(
            session_id=session.id,
            scope=session.scope,
            key_material=session.shared_key,
            expires_at=session.expires_at,
            salt=esid_salt.salt,
        )
        cookie_path = f"/api/{session.scope}"
        self.client.cookies.set(
            ESID_COOKIE_NAME,
            esid,
            domain=httpx.URL(self.base_url).host,
            path=cookie_path,
        )
        response_salt = self._issue_salt(
            session=session,
            purpose="response",
            profile=profile,
        )
        self._response_salts[response_salt.lease_id] = response_salt
        return {
            "X-Encryption-Session": session.id,
            "X-Encryption-Esid-Salt": esid_salt.lease_id,
            "X-Encryption-Response-Salt": response_salt.lease_id,
        }

    def _login_capsule(
        self,
        *,
        username: str,
        password: str,
        session: EncryptionSession,
        path: str,
    ) -> dict[str, Any]:
        challenge = session.login_challenge
        if not challenge:
            raise RuntimeVerifyError("后台登录缺少 login_challenge")
        challenge_id = str(challenge["challenge_id"])
        login_salt = self._issue_salt(
            session=session,
            purpose="login_capsule",
            profile="sensitive-v1",
        )
        keys = derive_login_capsule_keys(
            key_material=session.shared_key,
            challenge_salt=_b64url_decode(str(challenge["challenge_salt"])),
            transport_salt=login_salt.salt,
            session_id=session.id,
            challenge_id=challenge_id,
        )
        payload = json.dumps(
            {"username": username, "password": password},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        bucket_size = next(
            size for size in (256, 512, 1024, 2048) if size >= len(payload) + 2
        )
        padded = bytearray(secrets.token_bytes(bucket_size))
        padded[0:2] = len(payload).to_bytes(2, "big")
        padded[2 : 2 + len(payload)] = payload
        nonce = secrets.token_bytes(16)
        encryptor = Cipher(
            algorithms.AES(keys.encryption_key),
            modes.CTR(nonce),
        ).encryptor()
        ciphertext = encryptor.update(bytes(padded)) + encryptor.finalize()
        capsule: dict[str, Any] = {
            "scheme": LOGIN_CAPSULE_SCHEME,
            "session_id": session.id,
            "challenge_id": challenge_id,
            "salt_id": login_salt.lease_id,
            "nonce": _b64url(nonce),
            "issued_at": int(datetime.now(UTC).timestamp()),
            "ciphertext": _b64url(ciphertext),
        }
        capsule["tag"] = _b64url(
            hmac.digest(
                keys.mac_key,
                _login_capsule_signing_input(capsule, path),
                "sha256",
            ),
        )
        return capsule

    def _issue_salt(
        self,
        *,
        session: EncryptionSession,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
    ) -> SaltLease:
        request_payload = {
            "purpose": purpose,
            "profile": profile,
            "count": 1,
        }
        with ws_connect(
            _salt_ws_url(self.base_url, session.scope),
            open_timeout=self.timeout,
            close_timeout=self.timeout,
        ) as websocket:
            websocket.send(
                json.dumps(
                    _wrap_salt_payload(
                        request_payload,
                        session_id=session.id,
                        key_material=session.shared_key,
                    ),
                    separators=(",", ":"),
                ),
            )
            response = json.loads(websocket.recv(timeout=self.timeout))
        frames = response.get("frames")
        if response.get("type") != "salt_leases" or not isinstance(frames, list):
            raise RuntimeVerifyError("salt WSS 返回格式异常")
        if not frames:
            raise RuntimeVerifyError("salt WSS 未返回 lease")
        lease = _unwrap_salt_frame(
            frames[0],
            session_id=session.id,
            key_material=session.shared_key,
        )
        if (
            lease.purpose != purpose
            or lease.scope != session.scope
            or lease.profile != profile
        ):
            raise RuntimeVerifyError("salt lease 用途不匹配")
        return lease

    def _consume_salt(
        self,
        *,
        session: EncryptionSession,
        lease_id: str,
        purpose: SaltPurpose,
        profile: EncryptionProfile | None,
    ) -> SaltLease:
        lease = self._response_salts.pop(lease_id, None)
        if lease is None:
            raise RuntimeVerifyError("响应 salt_id 不匹配")
        if (
            lease.purpose != purpose
            or lease.scope != session.scope
            or lease.profile != profile
        ):
            raise RuntimeVerifyError("响应 salt lease 用途不匹配")
        return lease


def verify_runtime_flow(args: argparse.Namespace) -> RuntimeVerifyResult:
    api = RuntimeApiClient(base_url=args.base_url, timeout=args.timeout)
    try:
        admin_session = api.create_session("admin")
        login_payload = api.login(
            username=args.username,
            password=args.password,
            session=admin_session,
        )
        csrf_token = str(login_payload["csrf_token"])

        run_token = secrets.token_hex(4)
        uploaded = api.upload_public_image(
            session=admin_session,
            csrf_token=csrf_token,
            run_token=run_token,
        )
        file_id = int(uploaded["id"])
        private_uploaded = api.upload_private_image(
            session=admin_session,
            csrf_token=csrf_token,
            run_token=run_token,
        )
        private_file_id = int(private_uploaded["id"])
        slug = f"{args.slug_prefix}-{secrets.token_hex(4)}"
        page_slug = f"{args.slug_prefix}-page-{secrets.token_hex(4)}"
        content_md = "\n\n".join(
            [
                "这是一篇由运行库闭环验证脚本创建的短文。",
                "公式验证：$a^2 + b^2 = c^2$。",
                f"![运行库正文图](/api/public/posts/{slug}/files/{file_id}/render)",
            ],
        )

        preview = api.encrypted_post(
            "/api/admin/posts/preview",
            session=admin_session,
            csrf_token=csrf_token,
            payload={"slug": slug, "content_md": content_md},
        )
        _assert_contains(
            preview["content_html"],
            f"/api/admin/files/{file_id}/preview?expires=",
            "后台实时预览没有签名后台图片地址",
        )

        post = api.encrypted_post(
            "/api/admin/posts",
            session=admin_session,
            csrf_token=csrf_token,
            payload={
                "title": "运行库闭环验证文章",
                "slug": slug,
                "summary": "用于验证上传、封面、发布、公开渲染和日志链路。",
                "content_md": content_md,
                "status": "draft",
                "visibility": "public",
                "cover_file_id": file_id,
                "seo_title": "运行库闭环验证 SEO 标题",
                "seo_description": "验证文章发布链路中的 SEO 描述。",
                "seo_keywords": "运行库,文章发布,闭环验证",
                "category_names": ["验证"],
                "tag_names": ["发布", "图片", "SEO"],
            },
        )
        post_id = int(post["id"])
        page = api.encrypted_post(
            "/api/admin/pages",
            session=admin_session,
            csrf_token=csrf_token,
            payload={
                "title": "运行库闭环验证页面",
                "slug": page_slug,
                "content_md": "\n\n".join(
                    [
                        "## 页面内容验证",
                        "这是由真实运行库脚本创建并公开访问的独立页面。",
                        "页面公式：$E=mc^2$。",
                    ],
                ),
                "status": "published",
                "show_in_nav": True,
                "sort_order": 9999,
                "seo_title": "运行库页面 SEO 标题",
                "seo_description": "验证公开页面详情和前端 SEO 元信息。",
            },
        )
        page_id = int(page["id"])
        published = api.encrypted_post(
            f"/api/admin/posts/{post_id}/publish",
            session=admin_session,
            csrf_token=csrf_token,
        )
        if published["status"] != "published":
            raise RuntimeVerifyError("文章发布后状态不是 published")

        scheduled_slug = f"{args.slug_prefix}-scheduled-{secrets.token_hex(4)}"
        scheduled = api.encrypted_post(
            "/api/admin/posts",
            session=admin_session,
            csrf_token=csrf_token,
            payload={
                "title": "运行库定时发布验证文章",
                "slug": scheduled_slug,
                "summary": "用于验证未来发布时间不会提前公开。",
                "content_md": "这篇文章应该等到未来时间才公开。",
                "status": "scheduled",
                "visibility": "public",
                "published_at": (
                    datetime.now(UTC) + timedelta(days=1)
                ).isoformat(),
                "seo_title": "运行库定时发布 SEO 标题",
                "seo_description": "验证定时发布不会提前公开。",
                "seo_keywords": "定时发布,验证",
                "category_names": ["验证"],
                "tag_names": ["定时发布"],
            },
        )
        scheduled_post_id = int(scheduled["id"])
        extra_post_ids, extra_file_ids = _seed_admin_pagination_data(
            api=api,
            session=admin_session,
            csrf_token=csrf_token,
            slug_prefix=args.slug_prefix,
            run_token=run_token,
        )

        public_session = api.create_session("public")
        m4_result = _verify_m4_links_and_sites(
            api=api,
            admin_session=admin_session,
            public_session=public_session,
            csrf_token=csrf_token,
            slug_prefix=args.slug_prefix,
            run_token=run_token,
            frontend_url=args.frontend_url,
            browser_channel=args.browser_channel,
            timeout_seconds=args.timeout,
        )
        public_list = api.encrypted_get(
            "/api/public/posts?limit=5&offset=0",
            session=public_session,
            profile="content-v1",
        )
        matching_posts = [
            item for item in public_list["items"] if item.get("slug") == slug
        ]
        if not matching_posts:
            raise RuntimeVerifyError("公开文章列表没有返回刚发布的验证文章")
        if any(item.get("slug") == scheduled_slug for item in public_list["items"]):
            raise RuntimeVerifyError("未来定时文章提前出现在公开文章列表")
        scheduled_response = api.encrypted_get_response(
            f"/api/public/posts/{scheduled_slug}",
            session=public_session,
            profile="content-v1",
        )
        if scheduled_response.status_code != 404:
            raise RuntimeVerifyError("未来定时文章详情提前公开")
        cover_url = str(matching_posts[0].get("cover_image_url") or "")
        _assert_contains(cover_url, "/thumbnail?expires=", "公开列表缺少封面缩略图")
        cover_response = api.get_binary(cover_url)
        _assert_media_type(cover_response, "image/jpeg", "公开封面缩略图")

        detail = api.encrypted_get(
            f"/api/public/posts/{slug}",
            session=public_session,
            profile="content-v1",
        )
        if detail.get("seo_keywords") != "运行库,文章发布,闭环验证":
            raise RuntimeVerifyError("公开文章详情没有返回 SEO 关键词")
        if detail.get("category_names") != ["验证"]:
            raise RuntimeVerifyError("公开文章详情没有返回分类")
        if set(detail.get("tag_names", [])) != {"发布", "图片", "SEO"}:
            raise RuntimeVerifyError("公开文章详情没有返回标签")
        _assert_contains(
            detail["content_html"],
            "/render?expires=",
            "公开文章详情正文图没有签名渲染地址",
        )
        render_url = _extract_image_src(detail["content_html"], file_id=file_id)
        render_response = api.get_binary(render_url)
        _assert_media_type(render_response, "image/png", "公开正文图片")

        public_page = api.encrypted_get(
            f"/api/public/pages/{page_slug}",
            session=public_session,
            profile="content-v1",
        )
        if public_page.get("seo_title") != "运行库页面 SEO 标题":
            raise RuntimeVerifyError("公开页面详情没有返回 SEO 标题")
        if public_page.get("seo_description") != "验证公开页面详情和前端 SEO 元信息。":
            raise RuntimeVerifyError("公开页面详情没有返回 SEO 描述")
        _assert_contains(
            public_page["content_html"],
            "页面内容验证",
            "公开页面详情没有返回渲染后的正文",
        )

        category_slug = _find_taxonomy_slug(
            api.encrypted_get(
                "/api/public/categories?limit=100&offset=0",
                session=public_session,
                profile="content-v1",
            ),
            name="验证",
            label="公开分类列表",
        )
        tag_slug = _find_taxonomy_slug(
            api.encrypted_get(
                "/api/public/tags?limit=100&offset=0",
                session=public_session,
                profile="content-v1",
            ),
            name="SEO",
            label="公开标签列表",
        )
        category_detail = api.encrypted_get(
            f"/api/public/categories/{category_slug}",
            session=public_session,
            profile="content-v1",
        )
        _assert_taxonomy_detail(category_detail, name="验证", label="公开分类详情")
        tag_detail = api.encrypted_get(
            f"/api/public/tags/{tag_slug}",
            session=public_session,
            profile="content-v1",
        )
        _assert_taxonomy_detail(tag_detail, name="SEO", label="公开标签详情")
        _assert_public_posts_include_slug(
            api.encrypted_get(
                f"/api/public/posts?limit=5&offset=0&category={category_slug}",
                session=public_session,
                profile="content-v1",
            ),
            slug=slug,
            label="公开分类文章列表",
        )
        _assert_public_posts_include_slug(
            api.encrypted_get(
                f"/api/public/posts?limit=5&offset=0&tag={tag_slug}",
                session=public_session,
                profile="content-v1",
            ),
            slug=slug,
            label="公开标签文章列表",
        )
        rss_xml = api.get_text("/rss.xml")
        _assert_contains(rss_xml, f"/posts/{slug}", "RSS 没有包含验证文章 URL")
        _assert_contains(
            rss_xml,
            "运行库闭环验证 SEO 标题",
            "RSS 没有使用文章 SEO 标题",
        )
        sitemap_xml = api.get_text("/sitemap.xml")
        _assert_contains(sitemap_xml, f"/posts/{slug}", "sitemap 没有包含验证文章 URL")
        _assert_contains(
            sitemap_xml,
            f"/categories/{category_slug}",
            "sitemap 没有包含分类稳定 URL",
        )
        _assert_contains(
            sitemap_xml,
            f"/tags/{tag_slug}",
            "sitemap 没有包含标签稳定 URL",
        )
        robots_txt = api.get_text("/robots.txt")
        _assert_contains(robots_txt, "Disallow: /admin", "robots.txt 没有屏蔽后台入口")
        _assert_contains(robots_txt, "/sitemap.xml", "robots.txt 没有声明 sitemap")
        _assert_frontend_route(args.frontend_url, f"/categories/{category_slug}")
        _assert_frontend_route(args.frontend_url, f"/tags/{tag_slug}")
        _assert_frontend_seo(
            frontend_url=args.frontend_url,
            browser_channel=args.browser_channel,
            timeout_seconds=args.timeout,
            checks=[
                FrontendSeoCheck(
                    path=f"/posts/{slug}",
                    title="运行库闭环验证 SEO 标题",
                    description="验证文章发布链路中的 SEO 描述。",
                    keywords="运行库,文章发布,闭环验证",
                    og_type="article",
                ),
                FrontendSeoCheck(
                    path=f"/{page_slug}",
                    title="运行库页面 SEO 标题",
                    description="验证公开页面详情和前端 SEO 元信息。",
                    keywords=None,
                    og_type="article",
                ),
            ],
        )

        public_files = api.encrypted_get(
            "/api/public/files?limit=20&offset=0",
            session=public_session,
            profile="content-v1",
        )
        if not any(item.get("id") == file_id for item in public_files["items"]):
            raise RuntimeVerifyError("公开文件栏没有返回刚上传的公开文件")
        if any(item.get("id") == private_file_id for item in public_files["items"]):
            raise RuntimeVerifyError("公开文件栏暴露了私有文件")
        temporary_url = api.encrypted_get(
            f"/api/public/files/{file_id}/temporary-url",
            session=public_session,
            profile="content-v1",
        )
        download_response = api.get_binary(str(temporary_url["url"]))
        _assert_media_type(download_response, "image/png", "公开文件下载")

        private_public_response = api.encrypted_get_response(
            f"/api/public/files/{private_file_id}/temporary-url",
            session=public_session,
            profile="content-v1",
        )
        if private_public_response.status_code != 403:
            raise RuntimeVerifyError("私有文件公开短时访问入口没有返回 403")

        admin_download = api.get_binary(f"/api/admin/files/{file_id}/download")
        _assert_media_type(admin_download, "image/png", "后台鉴权文件下载")
        private_admin_download = api.get_binary(
            f"/api/admin/files/{private_file_id}/download",
        )
        _assert_media_type(private_admin_download, "image/png", "后台私有文件下载")

        admin_files = api.encrypted_get(
            "/api/admin/files?limit=100&offset=0",
            session=admin_session,
            profile="content-v1",
        )
        tracked_file = _find_file(admin_files, file_id=file_id, label="后台文件列表")
        if int(tracked_file.get("usage_count") or 0) < 1:
            raise RuntimeVerifyError("后台文件列表没有体现文章文件引用")
        admin_route_checks = _assert_admin_pagination(
            api=api,
            frontend_url=args.frontend_url,
            backend_url=args.base_url,
            browser_channel=args.browser_channel,
            timeout_seconds=args.timeout,
        )

        logs = api.encrypted_get(
            "/api/admin/access-logs?limit=100&offset=0",
            session=admin_session,
            profile="sensitive-v1",
        )
        access_types = {str(item["access_type"]) for item in logs["items"]}
        expected = {
            "public_posts_list",
            "public_post_detail",
            "post_image_thumbnail",
            "post_image_render",
            "public_page_detail",
            "public_rss",
            "public_sitemap",
            "public_robots",
            "public_files_list",
            "public_file_temporary_url",
            "public_file_download",
            "admin_file_download",
            "public_categories_list",
            "public_category_detail",
            "public_tags_list",
            "public_tag_detail",
            "public_friend_link_application",
            "public_friend_links_list",
            "public_site_items_list",
            "public_site_item_visit",
        }
        missing = sorted(expected - access_types)
        if missing:
            raise RuntimeVerifyError(f"后台访问日志缺少记录：{', '.join(missing)}")

        if args.archive_after_verify:
            api.encrypted_patch(
                f"/api/admin/posts/{post_id}",
                session=admin_session,
                csrf_token=csrf_token,
                payload={"status": "archived"},
            )
            api.encrypted_patch(
                f"/api/admin/posts/{scheduled_post_id}",
                session=admin_session,
                csrf_token=csrf_token,
                payload={"status": "archived"},
            )
            api.encrypted_patch(
                f"/api/admin/pages/{page_id}",
                session=admin_session,
                csrf_token=csrf_token,
                payload={"status": "archived", "show_in_nav": False},
            )
            for extra_post_id in extra_post_ids:
                api.encrypted_patch(
                    f"/api/admin/posts/{extra_post_id}",
                    session=admin_session,
                    csrf_token=csrf_token,
                    payload={"status": "archived"},
                )
            api.encrypted_patch(
                f"/api/admin/friend-links/{m4_result.approved_friend_link_id}",
                session=admin_session,
                csrf_token=csrf_token,
                payload={"status": "rejected"},
            )
            api.encrypted_patch(
                f"/api/admin/friend-links/{m4_result.rejected_friend_link_id}",
                session=admin_session,
                csrf_token=csrf_token,
                payload={"status": "rejected"},
            )
            api.encrypted_patch(
                f"/api/admin/site-items/{m4_result.site_item_id}",
                session=admin_session,
                csrf_token=csrf_token,
                payload={"visibility": "hidden"},
            )
            api.encrypted_patch(
                f"/api/admin/site-groups/{m4_result.site_group_id}",
                session=admin_session,
                csrf_token=csrf_token,
                payload={"visibility": "hidden"},
            )
        for extra_file_id in extra_file_ids:
            api.encrypted_delete(
                f"/api/admin/files/{extra_file_id}",
                session=admin_session,
                csrf_token=csrf_token,
            )
        api.encrypted_delete(
            f"/api/admin/files/{private_file_id}",
            session=admin_session,
            csrf_token=csrf_token,
        )

        return RuntimeVerifyResult(
            post_id=post_id,
            post_slug=slug,
            page_id=page_id,
            page_slug=page_slug,
            file_id=file_id,
            private_file_id=private_file_id,
            approved_friend_link_id=m4_result.approved_friend_link_id,
            rejected_friend_link_id=m4_result.rejected_friend_link_id,
            site_item_id=m4_result.site_item_id,
            category_slug=category_slug,
            tag_slug=tag_slug,
            checked_public_routes=m4_result.checked_public_routes,
            checked_admin_routes=admin_route_checks,
            checked_access_types=sorted(expected),
        )
    finally:
        api.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="验证真实运行库的内容发布、文件、友链、导航和日志闭环",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BLOG_VERIFY_BASE_URL", "http://127.0.0.1:18080"),
        help="后端 API 地址，默认读取 BLOG_VERIFY_BASE_URL 或本地 18080",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("BLOG_VERIFY_ADMIN_USERNAME"),
        help="后台管理员用户名，也可通过 BLOG_VERIFY_ADMIN_USERNAME 设置",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("BLOG_VERIFY_ADMIN_PASSWORD"),
        help="后台管理员密码，也可通过 BLOG_VERIFY_ADMIN_PASSWORD 设置",
    )
    parser.add_argument(
        "--slug-prefix",
        default=os.getenv("BLOG_VERIFY_SLUG_PREFIX", "runtime-flow-verify"),
        help="验证文章 slug 前缀，脚本会自动追加随机后缀",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("BLOG_VERIFY_FRONTEND_URL", "http://127.0.0.1:15173"),
        help="前端站点地址，用于验证稳定路由和 SEO 元信息",
    )
    parser.add_argument(
        "--browser-channel",
        default=os.getenv("BLOG_VERIFY_BROWSER_CHANNEL", "msedge"),
        help="Playwright Chromium 通道，默认 msedge",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="请求超时秒数")
    parser.add_argument(
        "--keep-published",
        dest="archive_after_verify",
        action="store_false",
        help="验证完成后保留文章和页面 published 状态，默认归档验证文章和页面",
    )
    parser.set_defaults(archive_after_verify=True)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.username or not args.password:
        raise SystemExit(
            "请通过参数或环境变量提供 BLOG_VERIFY_ADMIN_USERNAME "
            "和 BLOG_VERIFY_ADMIN_PASSWORD",
        )
    result = verify_runtime_flow(args)
    print(
        json.dumps(
            {
                "ok": True,
                "post_id": result.post_id,
                "post_slug": result.post_slug,
                "page_id": result.page_id,
                "page_slug": result.page_slug,
                "file_id": result.file_id,
                "private_file_id": result.private_file_id,
                "approved_friend_link_id": result.approved_friend_link_id,
                "rejected_friend_link_id": result.rejected_friend_link_id,
                "site_item_id": result.site_item_id,
                "category_slug": result.category_slug,
                "tag_slug": result.tag_slug,
                "checked_public_routes": result.checked_public_routes,
                "checked_admin_routes": result.checked_admin_routes,
                "checked_access_types": result.checked_access_types,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


@dataclass(frozen=True)
class FrontendSeoCheck:
    path: str
    title: str
    description: str
    keywords: str | None
    og_type: str


@dataclass(frozen=True)
class AdminRouteCheck:
    path: str
    label: str


@dataclass(frozen=True)
class ViewportCheck:
    name: str
    width: int
    height: int


ADMIN_ROUTES = (
    AdminRouteCheck(path="/admin/posts", label="后台文章列表"),
    AdminRouteCheck(path="/admin/files", label="后台文件列表"),
)
VIEWPORTS = (
    ViewportCheck(name="desktop", width=1280, height=900),
    ViewportCheck(name="mobile", width=390, height=844),
)


def _seed_admin_pagination_data(
    *,
    api: RuntimeApiClient,
    session: EncryptionSession,
    csrf_token: str,
    slug_prefix: str,
    run_token: str,
) -> tuple[list[int], list[int]]:
    post_ids: list[int] = []
    file_ids: list[int] = []
    for index in range(7):
        slug = f"{slug_prefix}-admin-page-{run_token}-{index}"
        post = api.encrypted_post(
            "/api/admin/posts",
            session=session,
            csrf_token=csrf_token,
            payload={
                "title": f"后台分页验证文章 {index + 1:02d}",
                "slug": slug,
                "summary": "用于验证后台文章列表大数量分页。",
                "content_md": "这篇文章只用于后台分页验证。",
                "status": "draft",
                "visibility": "public",
                "category_names": ["后台分页"],
                "tag_names": ["分页"],
            },
        )
        post_ids.append(int(post["id"]))
        uploaded = api.upload_image(
            session=session,
            csrf_token=csrf_token,
            filename=f"runtime-flow-admin-file-{run_token}-{index}.png",
            data=_runtime_png(
                run_token=f"{run_token}-{index}",
                variant="private",
            ),
            visibility="private",
            public_listed=False,
            alt_text="后台分页验证文件",
        )
        file_ids.append(int(uploaded["id"]))
    return post_ids, file_ids


def _verify_m4_links_and_sites(
    *,
    api: RuntimeApiClient,
    admin_session: EncryptionSession,
    public_session: EncryptionSession,
    csrf_token: str,
    slug_prefix: str,
    run_token: str,
    frontend_url: str,
    browser_channel: str,
    timeout_seconds: float,
) -> M4RuntimeVerifyResult:
    friend_group_slug = f"{slug_prefix}-friends-{run_token}"
    site_group_slug = f"{slug_prefix}-sites-{run_token}"
    approved_name = f"运行库验收友链通过 {run_token}"
    rejected_name = f"运行库验收友链拒绝 {run_token}"
    site_title = f"运行库验收导航 {run_token}"
    site_url = f"https://{run_token}.sites.example.test/tools"
    site_icon_url = f"{frontend_url.rstrip('/')}/default-cover.svg"

    friend_group = api.encrypted_post(
        "/api/admin/friend-link-groups",
        session=admin_session,
        csrf_token=csrf_token,
        payload={
            "name": "运行库验收友链分组",
            "slug": friend_group_slug,
            "sort_order": 0,
        },
    )
    friend_group_id = int(friend_group["id"])
    approved_application = api.public_encrypted_post(
        "/api/public/friend-links/applications",
        session=public_session,
        payload={
            "name": approved_name,
            "url": f"https://{run_token}.approved-friend.example.test",
            "avatar_url": None,
            "description": "M4 真实运行库验收通过友链",
            "rss_url": f"https://{run_token}.approved-friend.example.test/rss.xml",
        },
    )
    rejected_application = api.public_encrypted_post(
        "/api/public/friend-links/applications",
        session=public_session,
        payload={
            "name": rejected_name,
            "url": f"https://{run_token}.rejected-friend.example.test",
            "avatar_url": None,
            "description": "M4 真实运行库验收拒绝友链",
            "rss_url": None,
        },
    )
    approved_friend_link_id = int(approved_application["id"])
    rejected_friend_link_id = int(rejected_application["id"])
    if approved_application.get("status") != "pending":
        raise RuntimeVerifyError("公开友链申请没有创建 pending 状态")
    if rejected_application.get("status") != "pending":
        raise RuntimeVerifyError("公开拒绝友链申请没有创建 pending 状态")

    api.encrypted_patch(
        f"/api/admin/friend-links/{approved_friend_link_id}",
        session=admin_session,
        csrf_token=csrf_token,
        payload={"group_id": friend_group_id, "sort_order": 0},
    )
    approved_link = api.encrypted_patch(
        f"/api/admin/friend-links/{approved_friend_link_id}/review",
        session=admin_session,
        csrf_token=csrf_token,
        payload={"status": "healthy"},
    )
    rejected_link = api.encrypted_patch(
        f"/api/admin/friend-links/{rejected_friend_link_id}/review",
        session=admin_session,
        csrf_token=csrf_token,
        payload={"status": "rejected"},
    )
    if approved_link.get("status") != "healthy":
        raise RuntimeVerifyError("后台友链审核通过后状态不正确")
    if rejected_link.get("status") != "rejected":
        raise RuntimeVerifyError("后台友链审核拒绝后状态不正确")

    admin_links = api.encrypted_get(
        "/api/admin/friend-links?limit=100&offset=0",
        session=admin_session,
        profile="content-v1",
    )
    admin_approved = _find_item_by_id(
        admin_links,
        item_id=approved_friend_link_id,
        label="后台友链列表",
    )
    if admin_approved.get("group_id") != friend_group_id:
        raise RuntimeVerifyError("后台友链列表没有保留审核分组")

    public_links = api.encrypted_get(
        "/api/public/friend-links?limit=100&offset=0",
        session=public_session,
        profile="content-v1",
    )
    public_approved = _find_item_by_id(
        public_links,
        item_id=approved_friend_link_id,
        label="公开友链列表",
    )
    if public_approved.get("group_name") != "运行库验收友链分组":
        raise RuntimeVerifyError("公开友链列表没有展示后台分组")
    if any(
        item.get("id") == rejected_friend_link_id
        for item in public_links.get("items", [])
        if isinstance(item, dict)
    ):
        raise RuntimeVerifyError("公开友链列表展示了已拒绝友链")

    site_group = api.encrypted_post(
        "/api/admin/site-groups",
        session=admin_session,
        csrf_token=csrf_token,
        payload={
            "name": "运行库验收导航分组",
            "slug": site_group_slug,
            "description": "M4 真实运行库验收导航分组",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    site_group_id = int(site_group["id"])
    site_item = api.encrypted_post(
        "/api/admin/site-items",
        session=admin_session,
        csrf_token=csrf_token,
        payload={
            "group_id": site_group_id,
            "title": site_title,
            "url": site_url,
            "icon_url": site_icon_url,
            "description": "M4 真实运行库验收导航入口",
            "tags_json": {"items": ["验收", "导航"]},
            "open_target": "self",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    site_item_id = int(site_item["id"])
    if site_item.get("tags_json") != {"items": ["验收", "导航"]}:
        raise RuntimeVerifyError("后台导航条目没有返回规范化标签")

    public_sites = api.encrypted_get(
        "/api/public/site-items?limit=100&offset=0",
        session=public_session,
        profile="content-v1",
    )
    public_site = _find_item_by_id(
        public_sites,
        item_id=site_item_id,
        label="公开站点目录",
    )
    if public_site.get("icon_url") != site_icon_url:
        raise RuntimeVerifyError("公开站点目录没有返回图标 URL")
    if public_site.get("tags_json") != {"items": ["验收", "导航"]}:
        raise RuntimeVerifyError("公开站点目录没有返回标签")
    if public_site.get("open_target") != "self":
        raise RuntimeVerifyError("公开站点目录没有返回打开方式")

    visit_response = api.client.get(f"/api/public/site-items/{site_item_id}/visit")
    if visit_response.status_code != 302:
        raise RuntimeVerifyError(
            f"公开站点跳转没有返回 302：{visit_response.status_code}",
        )
    if visit_response.headers.get("location") != site_url:
        raise RuntimeVerifyError("公开站点跳转 location 不正确")

    admin_sites = api.encrypted_get(
        "/api/admin/site-items?limit=100&offset=0",
        session=admin_session,
        profile="content-v1",
    )
    admin_site = _find_item_by_id(
        admin_sites,
        item_id=site_item_id,
        label="后台站点目录",
    )
    if int(admin_site.get("click_count") or 0) < 1:
        raise RuntimeVerifyError("后台站点目录没有体现点击统计")

    checked_public_routes = _assert_m4_public_frontend(
        frontend_url=frontend_url,
        browser_channel=browser_channel,
        timeout_seconds=timeout_seconds,
        friend_name=approved_name,
        rejected_friend_name=rejected_name,
        site_title=site_title,
    )
    return M4RuntimeVerifyResult(
        approved_friend_link_id=approved_friend_link_id,
        rejected_friend_link_id=rejected_friend_link_id,
        friend_link_group_id=friend_group_id,
        site_group_id=site_group_id,
        site_item_id=site_item_id,
        checked_public_routes=checked_public_routes,
    )


def _runtime_png(*, run_token: str, variant: Literal["public", "private"]) -> bytes:
    background = (247, 245, 239) if variant == "public" else (238, 241, 246)
    accent = (171, 90, 112) if variant == "public" else (70, 105, 145)
    image = Image.new("RGB", (960, 540), color=background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 36, 924, 504), outline=(118, 76, 91), width=6)
    draw.line((92, 380, 868, 160), fill=accent, width=10)
    draw.ellipse((390, 170, 570, 350), fill=(230, 214, 202), outline=(60, 56, 54))
    draw.text((76, 74), f"{variant}:{run_token}", fill=(60, 56, 54))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _extract_image_src(content_html: str, *, file_id: int) -> str:
    pattern = rf'src="([^"]*/files/{file_id}/render\?[^"]+)"'
    match = re.search(pattern, content_html)
    if match is None:
        raise RuntimeVerifyError("公开文章详情中没有找到正文图片渲染地址")
    return match.group(1).replace("&amp;", "&")


def _find_taxonomy_slug(
    payload: dict[str, Any],
    *,
    name: str,
    label: str,
) -> str:
    for item in payload.get("items", []):
        if isinstance(item, dict) and item.get("name") == name:
            slug = item.get("slug")
            if isinstance(slug, str) and slug:
                return slug
    raise RuntimeVerifyError(f"{label}没有返回 {name} 的 slug")


def _assert_taxonomy_detail(
    payload: dict[str, Any],
    *,
    name: str,
    label: str,
) -> None:
    if payload.get("name") != name:
        raise RuntimeVerifyError(f"{label}名称不匹配")
    post_count = payload.get("post_count")
    if not isinstance(post_count, int) or post_count < 1:
        raise RuntimeVerifyError(f"{label}公开文章数量不正确")


def _assert_public_posts_include_slug(
    payload: dict[str, Any],
    *,
    slug: str,
    label: str,
) -> None:
    if not any(item.get("slug") == slug for item in payload.get("items", [])):
        raise RuntimeVerifyError(f"{label}没有返回验证文章")


def _find_file(
    payload: dict[str, Any],
    *,
    file_id: int,
    label: str,
) -> dict[str, Any]:
    for item in payload.get("items", []):
        if isinstance(item, dict) and item.get("id") == file_id:
            return item
    raise RuntimeVerifyError(f"{label}没有返回文件 {file_id}")


def _find_item_by_id(
    payload: dict[str, Any],
    *,
    item_id: int,
    label: str,
) -> dict[str, Any]:
    for item in payload.get("items", []):
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    raise RuntimeVerifyError(f"{label}没有返回记录 {item_id}")


def _assert_frontend_route(frontend_url: str, path: str) -> None:
    url = frontend_url.rstrip("/") + path
    response = httpx.get(url, timeout=10.0, follow_redirects=True)
    _raise_for_status(response, f"前端路由 {path} 不可访问")
    _assert_contains(
        response.text,
        '<div id="root">',
        f"前端路由 {path} 未返回应用入口",
    )


def _assert_frontend_seo(
    *,
    frontend_url: str,
    browser_channel: str,
    timeout_seconds: float,
    checks: list[FrontendSeoCheck],
) -> None:
    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel=browser_channel,
            headless=True,
        )
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            for check in checks:
                url = frontend_url.rstrip("/") + check.path
                response = page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                if response is None or not response.ok:
                    status = response.status if response is not None else "no response"
                    raise RuntimeVerifyError(
                        f"前端页面 {check.path} 访问失败：{status}",
                    )
                page.wait_for_function(
                    "(expected) => document.title.includes(expected)",
                    arg=check.title,
                    timeout=timeout_ms,
                )
                seo = page.evaluate(
                    """
                    () => ({
                      title: document.title,
                      description: metaContent('meta[name="description"]'),
                      keywords: metaContent('meta[name="keywords"]'),
                      canonical:
                        document.querySelector('link[rel="canonical"]')?.href || '',
                      ogTitle: metaContent('meta[property="og:title"]'),
                      ogDescription:
                        metaContent('meta[property="og:description"]'),
                      ogType: metaContent('meta[property="og:type"]'),
                      ogUrl: metaContent('meta[property="og:url"]'),
                    })

                    function metaContent(selector) {
                      return document.querySelector(selector)?.content || '';
                    }
                    """,
                )
                if check.title not in seo["title"]:
                    raise RuntimeVerifyError(
                        f"前端页面 {check.path} 标题未写入 SEO 标题",
                    )
                if seo["description"] != check.description:
                    raise RuntimeVerifyError(
                        f"前端页面 {check.path} description 不匹配",
                    )
                if check.keywords is not None and seo["keywords"] != check.keywords:
                    raise RuntimeVerifyError(f"前端页面 {check.path} keywords 不匹配")
                if not str(seo["canonical"]).endswith(check.path):
                    raise RuntimeVerifyError(f"前端页面 {check.path} canonical 不匹配")
                if seo["ogTitle"] != check.title:
                    raise RuntimeVerifyError(f"前端页面 {check.path} og:title 不匹配")
                if seo["ogDescription"] != check.description:
                    raise RuntimeVerifyError(
                        f"前端页面 {check.path} og:description 不匹配",
                    )
                if seo["ogType"] != check.og_type:
                    raise RuntimeVerifyError(f"前端页面 {check.path} og:type 不匹配")
                if not str(seo["ogUrl"]).endswith(check.path):
                    raise RuntimeVerifyError(f"前端页面 {check.path} og:url 不匹配")
        finally:
            browser.close()


def _assert_m4_public_frontend(
    *,
    frontend_url: str,
    browser_channel: str,
    timeout_seconds: float,
    friend_name: str,
    rejected_friend_name: str,
    site_title: str,
) -> list[str]:
    checked: list[str] = []
    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel=browser_channel,
            headless=True,
        )
        try:
            for viewport in VIEWPORTS:
                page = browser.new_page(
                    viewport={"width": viewport.width, "height": viewport.height},
                )
                page.set_default_timeout(timeout_ms)
                try:
                    _check_m4_public_route(
                        page=page,
                        frontend_url=frontend_url,
                        path="/links",
                        label="公开友链页",
                        viewport=viewport,
                        expected_texts=[friend_name, "运行库验收友链分组"],
                        rejected_texts=[rejected_friend_name],
                        timeout_ms=timeout_ms,
                    )
                    checked.append(f"/links:{viewport.name}")
                    _check_m4_public_route(
                        page=page,
                        frontend_url=frontend_url,
                        path="/sites",
                        label="公开站点目录页",
                        viewport=viewport,
                        expected_texts=[site_title, "#验收", "#导航"],
                        rejected_texts=[],
                        timeout_ms=timeout_ms,
                    )
                    site_tile = page.locator(".site-tile", has_text=site_title).first
                    if site_tile.locator(".site-tile__icon").count() < 1:
                        raise RuntimeVerifyError("公开站点目录页没有展示导航图标")
                    checked.append(f"/sites:{viewport.name}")
                finally:
                    page.close()
        finally:
            browser.close()
    return checked


def _check_m4_public_route(
    *,
    page: Any,
    frontend_url: str,
    path: str,
    label: str,
    viewport: ViewportCheck,
    expected_texts: list[str],
    rejected_texts: list[str],
    timeout_ms: int,
) -> None:
    response = page.goto(
        frontend_url.rstrip("/") + path,
        wait_until="networkidle",
        timeout=timeout_ms,
    )
    if response is None or not response.ok:
        status = response.status if response is not None else "no response"
        raise RuntimeVerifyError(f"{label}访问失败：{status}")
    for expected_text in expected_texts:
        page.get_by_text(expected_text, exact=False).first.wait_for(
            timeout=timeout_ms,
        )
    body_text = page.locator("body").inner_text(timeout=timeout_ms)
    for rejected_text in rejected_texts:
        if rejected_text in body_text:
            raise RuntimeVerifyError(f"{label}展示了不应公开的内容：{rejected_text}")
    overflow = _collect_overflow(page)
    if overflow["has_overflow"]:
        raise RuntimeVerifyError(
            f"{label}在 {viewport.name} 视口横向溢出："
            f"{json.dumps(overflow, ensure_ascii=False)}",
        )


def _assert_admin_pagination(
    *,
    api: RuntimeApiClient,
    frontend_url: str,
    backend_url: str,
    browser_channel: str,
    timeout_seconds: float,
) -> list[str]:
    checked: list[str] = []
    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel=browser_channel,
            headless=True,
        )
        try:
            for viewport in VIEWPORTS:
                context = browser.new_context(
                    viewport={"width": viewport.width, "height": viewport.height},
                )
                context.add_cookies(_playwright_cookies(api, backend_url=backend_url))
                page = context.new_page()
                page.set_default_timeout(timeout_ms)
                try:
                    for route in ADMIN_ROUTES:
                        _check_admin_route(
                            page=page,
                            frontend_url=frontend_url,
                            route=route,
                            viewport=viewport,
                            timeout_ms=timeout_ms,
                        )
                        checked.append(f"{route.path}:{viewport.name}")
                finally:
                    context.close()
        finally:
            browser.close()
    return checked


def _check_admin_route(
    *,
    page: Any,
    frontend_url: str,
    route: AdminRouteCheck,
    viewport: ViewportCheck,
    timeout_ms: int,
) -> None:
    response = page.goto(
        frontend_url.rstrip("/") + route.path,
        wait_until="networkidle",
        timeout=timeout_ms,
    )
    if response is None or not response.ok:
        status = response.status if response is not None else "no response"
        raise RuntimeVerifyError(f"{route.label}访问失败：{status}")

    page.wait_for_selector(".pagination-bar", timeout=timeout_ms)
    pager = (page.locator(".pagination-bar span").first.text_content() or "").strip()
    _assert_first_page_pager(route.label, pager)
    overflow = _collect_overflow(page)
    if overflow["has_overflow"]:
        raise RuntimeVerifyError(
            f"{route.label}在 {viewport.name} 视口横向溢出："
            f"{json.dumps(overflow, ensure_ascii=False)}",
        )


def _assert_first_page_pager(label: str, pager_text: str) -> None:
    if not pager_text.startswith("第 1 / "):
        raise RuntimeVerifyError(f"{label}分页条不是第一页：{pager_text!r}")
    total_text = pager_text.removeprefix("第 1 / ").removesuffix(" 页")
    try:
        total_pages = int(total_text)
    except ValueError as exc:
        raise RuntimeVerifyError(f"{label}分页总页数格式异常：{pager_text}") from exc
    if total_pages < 2:
        raise RuntimeVerifyError(f"{label}分页总页数小于 2：{pager_text}")


def _collect_overflow(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const clientWidth = document.documentElement.clientWidth;
          const scrollWidth = Math.max(
            document.documentElement.scrollWidth,
            document.body.scrollWidth
          );
          const offenders = Array.from(document.body.querySelectorAll('*'))
            .filter((element) => {
              const style = window.getComputedStyle(element);
              if (style.display === 'none' || style.visibility === 'hidden') {
                return false;
              }
              const rect = element.getBoundingClientRect();
              return rect.width > 0 && rect.right > clientWidth + 1;
            })
            .slice(0, 5)
            .map((element) => ({
              tag: element.tagName.toLowerCase(),
              className: String(element.className || ''),
              right: Math.round(element.getBoundingClientRect().right),
              width: Math.round(element.getBoundingClientRect().width),
            }));
          return {
            has_overflow: scrollWidth > clientWidth + 1 || offenders.length > 0,
            document_scroll_width: scrollWidth,
            document_client_width: clientWidth,
            offenders,
          };
        }
        """,
    )


def _playwright_cookies(
    api: RuntimeApiClient,
    *,
    backend_url: str,
) -> list[dict[str, object]]:
    cookies: list[dict[str, object]] = []
    for cookie in api.client.cookies.jar:
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "url": backend_url.rstrip("/"),
            },
        )
    if not cookies:
        raise RuntimeVerifyError("后台浏览器检查缺少登录 Cookie")
    return cookies


def _raise_for_status(response: httpx.Response, message: str) -> None:
    if response.is_success:
        return
    raise RuntimeVerifyError(
        f"{message}：HTTP {response.status_code} {response.text[:500]}",
    )


def _assert_contains(value: object, expected: str, message: str) -> None:
    if expected not in str(value):
        raise RuntimeVerifyError(message)


def _assert_media_type(
    response: httpx.Response,
    expected: str,
    label: str,
) -> None:
    content_type = response.headers.get("content-type", "")
    if expected not in content_type:
        raise RuntimeVerifyError(f"{label}响应类型不是 {expected}：{content_type}")


def _wrap_salt_payload(
    payload: dict[str, object],
    *,
    session_id: str,
    key_material: bytes,
) -> dict[str, str]:
    wrap_salt = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_derive_salt_wrap_key(key_material, wrap_salt)).encrypt(
        nonce,
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
        _salt_wrap_associated_data(session_id),
    )
    return {
        "session_id": session_id,
        "wrap_salt": _b64url(wrap_salt),
        "nonce": _b64url(nonce),
        "ciphertext": _b64url(ciphertext),
    }


def _unwrap_salt_frame(
    frame: dict[str, Any],
    *,
    session_id: str,
    key_material: bytes,
) -> SaltLease:
    if frame.get("session_id") != session_id:
        raise RuntimeVerifyError("salt frame session_id 不匹配")
    plaintext = AESGCM(
        _derive_salt_wrap_key(
            key_material,
            _b64url_decode(str(frame["wrap_salt"])),
        ),
    ).decrypt(
        _b64url_decode(str(frame["nonce"])),
        _b64url_decode(str(frame["ciphertext"])),
        _salt_wrap_associated_data(session_id),
    )
    payload = json.loads(plaintext.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeVerifyError("salt lease 解密结果不是对象")
    return SaltLease(
        lease_id=str(payload["lease_id"]),
        purpose=_salt_purpose(str(payload["purpose"])),
        scope=_encryption_scope(str(payload["scope"])),
        profile=(
            _encryption_profile(str(payload["profile"]))
            if payload.get("profile") is not None
            else None
        ),
        salt=_b64url_decode(str(payload["salt"])),
        expires_at=datetime.fromtimestamp(int(payload["expires_at"]), UTC),
    )


def _salt_ws_url(base_url: str, scope: EncryptionScope) -> str:
    parsed = httpx.URL(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return str(parsed.copy_with(scheme=scheme, path=f"/api/{scope}/encryption/salts"))


def _derive_salt_wrap_key(key_material: bytes, wrap_salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=wrap_salt,
        info=SALT_WRAP_INFO,
    ).derive(key_material)


def _salt_wrap_associated_data(session_id: str) -> bytes:
    return f"blog-cms:wss-salt-wrap:{session_id}".encode()


def _login_capsule_signing_input(capsule: dict[str, Any], path: str) -> bytes:
    return "\n".join(
        (
            str(capsule["scheme"]),
            str(capsule["session_id"]),
            str(capsule["challenge_id"]),
            str(capsule["salt_id"]),
            "POST",
            path,
            str(capsule["issued_at"]),
            str(capsule["nonce"]),
            str(capsule["ciphertext"]),
        ),
    ).encode("utf-8")


def _derive_key(
    key_material: bytes,
    profile: EncryptionProfile,
    salt: bytes,
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=f"blog-cms:{profile}".encode(),
    ).derive(key_material)


def _associated_data(profile: EncryptionProfile) -> bytes:
    return f"blog-cms:{profile}:json".encode()


def _b64url(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _encryption_scope(value: str) -> EncryptionScope:
    if value not in {"admin", "public"}:
        raise RuntimeVerifyError(f"未知加密 scope：{value}")
    return value  # type: ignore[return-value]


def _encryption_profile(value: str) -> EncryptionProfile:
    if value not in {"sensitive-v1", "content-v1"}:
        raise RuntimeVerifyError(f"未知加密 profile：{value}")
    return value  # type: ignore[return-value]


def _salt_purpose(value: str) -> SaltPurpose:
    if value not in {"esid", "login_capsule", "request", "response"}:
        raise RuntimeVerifyError(f"未知 salt purpose：{value}")
    return value  # type: ignore[return-value]


if __name__ == "__main__":
    main()
