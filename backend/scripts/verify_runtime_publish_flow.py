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
    file_id: int
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

    def upload_public_image(
        self,
        *,
        session: EncryptionSession,
        csrf_token: str,
    ) -> dict[str, Any]:
        response = self.client.post(
            "/api/admin/files",
            headers={
                "X-CSRF-Token": csrf_token,
                "X-Encryption-Session": session.id,
            },
            data={
                "visibility": "public",
                "alt_text": "运行库闭环验证图",
                "public_listed": "true",
            },
            files={
                "file": (
                    "runtime-flow-cover.png",
                    _runtime_png(),
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

        uploaded = api.upload_public_image(
            session=admin_session,
            csrf_token=csrf_token,
        )
        file_id = int(uploaded["id"])
        slug = f"{args.slug_prefix}-{secrets.token_hex(4)}"
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

        public_files = api.encrypted_get(
            "/api/public/files?limit=20&offset=0",
            session=public_session,
            profile="content-v1",
        )
        if not any(item.get("id") == file_id for item in public_files["items"]):
            raise RuntimeVerifyError("公开文件栏没有返回刚上传的公开文件")
        temporary_url = api.encrypted_get(
            f"/api/public/files/{file_id}/temporary-url",
            session=public_session,
            profile="content-v1",
        )
        download_response = api.get_binary(str(temporary_url["url"]))
        _assert_media_type(download_response, "image/png", "公开文件下载")

        admin_download = api.get_binary(f"/api/admin/files/{file_id}/download")
        _assert_media_type(admin_download, "image/png", "后台鉴权文件下载")

        logs = api.encrypted_get(
            "/api/admin/access-logs?limit=50&offset=0",
            session=admin_session,
            profile="sensitive-v1",
        )
        access_types = {str(item["access_type"]) for item in logs["items"]}
        expected = {
            "public_posts_list",
            "public_post_detail",
            "post_image_thumbnail",
            "post_image_render",
            "public_file_temporary_url",
            "public_file_download",
            "admin_file_download",
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

        return RuntimeVerifyResult(
            post_id=post_id,
            post_slug=slug,
            file_id=file_id,
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
                "file_id": result.file_id,
                "checked_access_types": result.checked_access_types,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


def _runtime_png() -> bytes:
    image = Image.new("RGB", (960, 540), color=(247, 245, 239))
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 36, 924, 504), outline=(118, 76, 91), width=6)
    draw.line((92, 380, 868, 160), fill=(171, 90, 112), width=10)
    draw.ellipse((390, 170, 570, 350), fill=(230, 214, 202), outline=(60, 56, 54))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _extract_image_src(content_html: str, *, file_id: int) -> str:
    pattern = rf'src="([^"]*/files/{file_id}/render\?[^"]+)"'
    match = re.search(pattern, content_html)
    if match is None:
        raise RuntimeVerifyError("公开文章详情中没有找到正文图片渲染地址")
    return match.group(1).replace("&amp;", "&")


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
