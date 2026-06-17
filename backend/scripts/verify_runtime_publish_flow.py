from __future__ import annotations

import argparse
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
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

EncryptionProfile = Literal["sensitive-v1", "content-v1"]
EncryptionScope = Literal["admin", "public"]

SALT = b"blog-cms-encryption-v1"


@dataclass(frozen=True)
class EncryptionSession:
    id: str
    scope: EncryptionScope
    shared_key: bytes
    profiles: list[str]


@dataclass(frozen=True)
class RuntimeVerifyResult:
    post_id: int
    post_slug: str
    page_id: int
    page_slug: str
    file_id: int
    private_file_id: int
    category_slug: str
    tag_slug: str
    checked_admin_routes: list[str]
    checked_access_types: list[str]


class RuntimeVerifyError(Exception):
    pass


class RuntimeApiClient:
    def __init__(self, *, base_url: str, timeout: float) -> None:
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            follow_redirects=False,
        )

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
        aesgcm = AESGCM(_derive_key(session.shared_key, profile))
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
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        ciphertext = AESGCM(_derive_key(session.shared_key, profile)).encrypt(
            nonce,
            plaintext,
            _associated_data(profile),
        )
        return {
            "session_id": session.id,
            "profile": profile,
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
        response = self.client.post(
            "/api/admin/auth/login",
            headers={"X-Encryption-Session": session.id},
            json={"username": username, "password": password},
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
                "X-Encryption-Session": session.id,
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
                "X-Encryption-Session": session.id,
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
                "X-Encryption-Session": session.id,
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
                "X-Encryption-Session": session.id,
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
            headers={"X-Encryption-Session": session.id},
        )
        _raise_for_status(response, f"GET {path} 失败")
        return self.decrypt(response.json(), session=session, profile=profile)

    def get_binary(self, url: str) -> httpx.Response:
        response = self.client.get(url)
        _raise_for_status(response, f"请求文件 {url} 失败")
        return response

    def get_text(self, path: str) -> str:
        response = self.client.get(path)
        _raise_for_status(response, f"GET {path} 失败")
        return response.text


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
        scheduled_response = api.client.get(
            f"/api/public/posts/{scheduled_slug}",
            headers={"X-Encryption-Session": public_session.id},
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

        private_public_response = api.client.get(
            f"/api/public/files/{private_file_id}/temporary-url",
            headers={"X-Encryption-Session": public_session.id},
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
            category_slug=category_slug,
            tag_slug=tag_slug,
            checked_admin_routes=admin_route_checks,
            checked_access_types=sorted(expected),
        )
    finally:
        api.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="验证真实运行库的上传、文章发布、公开访问和日志闭环",
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
        help="验证完成后保留文章 published 状态，默认归档验证文章",
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
                "category_slug": result.category_slug,
                "tag_slug": result.tag_slug,
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


def _derive_key(key_material: bytes, profile: EncryptionProfile) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        info=f"blog-cms:{profile}".encode(),
    ).derive(key_material)


def _associated_data(profile: EncryptionProfile) -> bytes:
    return f"blog-cms:{profile}:json".encode()


def _b64url(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


if __name__ == "__main__":
    main()
