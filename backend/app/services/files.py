import hashlib
import hmac
import json
import re
import struct
import tempfile
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.core.auth import utc_now
from app.core.storage import StorageProvider
from app.models.file import BlogFile

ALLOWED_FILE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}
ALLOWED_VISIBILITIES = {"public", "private"}


class FileValidationError(Exception):
    pass


class FileTooLargeError(FileValidationError):
    pass


class InvalidFileTypeError(FileValidationError):
    pass


class InvalidFileVisibilityError(FileValidationError):
    pass


class ManagedFileNotFoundError(Exception):
    pass


class FileAccessDeniedError(Exception):
    pass


class InvalidFileAccessTokenError(Exception):
    pass


@dataclass(frozen=True)
class UploadFileCommand:
    original_name: str
    content_type: str | None
    data: bytes
    visibility: str
    public_listed: bool
    uploader_id: int | None
    alt_text: str | None
    max_size_bytes: int


@dataclass(frozen=True)
class FileWithUsage:
    file: BlogFile
    usage_count: int

    def __getattr__(self, name: str) -> object:
        return getattr(self.file, name)


@dataclass(frozen=True)
class TemporaryFileAccess:
    file: BlogFile
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class FileDownload:
    path: Path
    media_type: str
    filename: str


@dataclass(frozen=True)
class ArticleRenderToken:
    token: str
    expires: int


class FileRepositoryProtocol(Protocol):
    async def list_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[BlogFile, int]]: ...

    async def list_public_listed_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[BlogFile]: ...

    async def get_file(self, file_id: int) -> BlogFile | None: ...

    async def get_file_by_sha256(self, sha256: str) -> BlogFile | None: ...

    async def create_file(
        self,
        *,
        storage: str,
        bucket: str | None,
        object_key: str,
        public_url: str | None,
        original_name: str,
        mime_type: str,
        extension: str,
        size_bytes: int,
        sha256: str,
        width: int | None,
        height: int | None,
        alt_text: str | None,
        uploader_id: int | None,
        visibility: str,
        public_listed: bool,
    ) -> BlogFile: ...

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...


class FileService:
    def __init__(
        self,
        *,
        repository: FileRepositoryProtocol,
        storage: StorageProvider,
    ) -> None:
        self.repository = repository
        self.storage = storage

    async def list_files(self, *, limit: int, offset: int) -> list[FileWithUsage]:
        files = await self.repository.list_files(limit=limit, offset=offset)
        return [FileWithUsage(file=file, usage_count=count) for file, count in files]

    async def list_public_files(self, *, limit: int, offset: int) -> list[BlogFile]:
        return list(
            await self.repository.list_public_listed_files(
                limit=limit,
                offset=offset,
            ),
        )

    async def upload_file(self, command: UploadFileCommand) -> FileWithUsage:
        self._validate_size(command.data, command.max_size_bytes)
        self._validate_visibility(command.visibility)

        original_name = _normalize_original_name(command.original_name)
        extension = _extract_extension(original_name)
        expected_mime = self._validate_type(
            extension=extension,
            content_type=command.content_type,
            data=command.data,
        )
        sha256 = hashlib.sha256(command.data).hexdigest()
        existing_file = await self.repository.get_file_by_sha256(sha256)
        if existing_file is not None:
            return FileWithUsage(file=existing_file, usage_count=0)

        object_key = _build_object_key(
            visibility=command.visibility,
            extension=extension,
            sha256=sha256,
        )
        width, height = _read_image_size(command.data, expected_mime)
        temp_path = _write_temp_file(command.data)
        try:
            stored_object = await self.storage.save(temp_path, object_key)
        finally:
            temp_path.unlink(missing_ok=True)

        file = await self.repository.create_file(
            storage="local",
            bucket=None,
            object_key=stored_object.object_key,
            public_url=stored_object.public_url,
            original_name=original_name,
            mime_type=expected_mime,
            extension=extension.removeprefix("."),
            size_bytes=stored_object.size_bytes,
            sha256=stored_object.sha256,
            width=width,
            height=height,
            alt_text=command.alt_text,
            uploader_id=command.uploader_id,
            visibility=command.visibility,
            public_listed=(
                command.public_listed and command.visibility == "public"
            ),
        )
        await self.repository.commit()
        await self.repository.refresh(file)
        return FileWithUsage(file=file, usage_count=0)

    async def delete_file(self, file_id: int) -> FileWithUsage:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")

        file.status = "deleted"
        file.deleted_at = utc_now()
        await self.repository.commit()
        await self.repository.refresh(file)
        return FileWithUsage(file=file, usage_count=0)

    async def create_temporary_access(
        self,
        *,
        file_id: int,
        secret_key: str,
        expires_seconds: int,
    ) -> TemporaryFileAccess:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if file.visibility != "public" or file.status != "active":
            raise FileAccessDeniedError("file is not public")

        expires_at = utc_now() + timedelta(seconds=expires_seconds)
        token = _sign_file_token(
            file_id=file.id,
            sha256=file.sha256,
            expires_at=expires_at,
            secret_key=secret_key,
        )
        return TemporaryFileAccess(file=file, token=token, expires_at=expires_at)

    async def create_public_temporary_access(
        self,
        *,
        file_id: int,
        secret_key: str,
        expires_seconds: int,
    ) -> TemporaryFileAccess:
        access = await self.create_temporary_access(
            file_id=file_id,
            secret_key=secret_key,
            expires_seconds=expires_seconds,
        )
        if not access.file.public_listed:
            raise FileAccessDeniedError("file is not listed public")
        return access

    async def prepare_public_download(
        self,
        *,
        file_id: int,
        token: str,
        secret_key: str,
        upload_root: Path,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if file.visibility != "public" or file.status != "active":
            raise FileAccessDeniedError("file is not public")
        if not _verify_file_token(
            token,
            file_id=file.id,
            sha256=file.sha256,
            secret_key=secret_key,
        ):
            raise InvalidFileAccessTokenError("invalid temporary file token")

        path = _resolve_storage_path(upload_root, file.object_key)
        if path is None or not path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        return FileDownload(
            path=path,
            media_type=file.mime_type,
            filename=file.original_name,
        )

    async def prepare_article_render(
        self,
        *,
        file_id: int,
        post_slug: str,
        post_content_md: str,
        post_content_html: str,
        upload_root: Path,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if (
            file.visibility != "public"
            or file.status != "active"
            or not file.mime_type.startswith("image/")
        ):
            raise FileAccessDeniedError("file is not renderable")
        if not _article_render_reference_exists(
            post_slug=post_slug,
            file_id=file.id,
            content_md=post_content_md,
            content_html=post_content_html,
        ):
            raise FileAccessDeniedError("file is not referenced by post")

        path = _resolve_storage_path(upload_root, file.object_key)
        if path is None or not path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        return FileDownload(
            path=path,
            media_type=file.mime_type,
            filename=file.original_name,
        )

    async def prepare_admin_preview(
        self,
        *,
        file_id: int,
        token: str,
        expires: int,
        secret_key: str,
        upload_root: Path,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if file.status != "active" or not file.mime_type.startswith("image/"):
            raise FileAccessDeniedError("file is not previewable")
        if not verify_admin_file_preview_token(
            token=token,
            expires=expires,
            file_id=file.id,
            secret_key=secret_key,
        ):
            raise InvalidFileAccessTokenError("invalid preview token")

        path = _resolve_storage_path(upload_root, file.object_key, public_only=False)
        if path is None or not path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        return FileDownload(
            path=path,
            media_type=file.mime_type,
            filename=file.original_name,
        )

    def _validate_size(self, data: bytes, max_size_bytes: int) -> None:
        if not data:
            raise InvalidFileTypeError("empty file is not allowed")
        if len(data) > max_size_bytes:
            raise FileTooLargeError("file is too large")

    def _validate_visibility(self, visibility: str) -> None:
        if visibility not in ALLOWED_VISIBILITIES:
            raise InvalidFileVisibilityError("invalid file visibility")

    def _validate_type(
        self,
        *,
        extension: str,
        content_type: str | None,
        data: bytes,
    ) -> str:
        expected_mime = ALLOWED_FILE_TYPES.get(extension)
        normalized_mime = (content_type or "").split(";", maxsplit=1)[0].lower()
        if expected_mime is None or normalized_mime != expected_mime:
            raise InvalidFileTypeError("unsupported file type")
        if not _matches_file_signature(data, expected_mime):
            raise InvalidFileTypeError("file signature does not match mime type")
        return expected_mime


def _normalize_original_name(original_name: str) -> str:
    name = Path(original_name).name.strip()
    if not name or len(name) > 255:
        raise InvalidFileTypeError("invalid file name")
    return name


def _extract_extension(original_name: str) -> str:
    extension = Path(original_name).suffix.lower()
    if extension == ".jpeg":
        return ".jpg"
    return extension


def _build_object_key(*, visibility: str, extension: str, sha256: str) -> str:
    now = utc_now()
    return (
        f"{visibility}/{now:%Y}/{now:%m}/"
        f"{sha256[:24]}{extension.replace('.jpeg', '.jpg')}"
    )


def _write_temp_file(data: bytes) -> Path:
    with tempfile.NamedTemporaryFile(delete=False) as file:
        file.write(data)
        return Path(file.name)


def _matches_file_signature(data: bytes, mime_type: str) -> bool:
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if mime_type == "application/pdf":
        return data.startswith(b"%PDF-")
    return False


def _read_image_size(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if mime_type == "image/png" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    if mime_type == "image/gif" and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return width, height
    if mime_type == "image/jpeg":
        return _read_jpeg_size(data)
    return None, None


def _read_jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index : index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += length
    return None, None


def _sign_file_token(
    *,
    file_id: int,
    sha256: str,
    expires_at: datetime,
    secret_key: str,
) -> str:
    payload = {
        "exp": int(expires_at.timestamp()),
        "file_id": file_id,
        "sha256": sha256,
    }
    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_part = _base64url_encode(payload_bytes)
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_base64url_encode(signature)}"


def _verify_file_token(
    token: str,
    *,
    file_id: int,
    sha256: str,
    secret_key: str,
) -> bool:
    try:
        payload_part, signature_part = token.split(".", maxsplit=1)
        expected_signature = hmac.new(
            secret_key.encode("utf-8"),
            payload_part.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(
            signature_part,
            _base64url_encode(expected_signature),
        ):
            return False
        payload = json.loads(_base64url_decode(payload_part))
    except (BinasciiError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False

    return (
        payload.get("file_id") == file_id
        and payload.get("sha256") == sha256
        and isinstance(payload.get("exp"), int)
        and payload["exp"] > int(utc_now().timestamp())
    )


def create_article_render_token(
    *,
    post_slug: str,
    file_id: int,
    expires_seconds: int,
    secret_key: str,
) -> ArticleRenderToken:
    expires = int((utc_now() + timedelta(seconds=expires_seconds)).timestamp())
    payload = {
        "exp": expires,
        "file_id": file_id,
        "scope": "post_image_render",
        "slug": post_slug,
    }
    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_part = _base64url_encode(payload_bytes)
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return ArticleRenderToken(
        token=f"{payload_part}.{_base64url_encode(signature)}",
        expires=expires,
    )


def create_admin_file_preview_token(
    *,
    file_id: int,
    expires_seconds: int,
    secret_key: str,
) -> ArticleRenderToken:
    expires = int((utc_now() + timedelta(seconds=expires_seconds)).timestamp())
    payload = {
        "exp": expires,
        "file_id": file_id,
        "scope": "admin_file_preview",
    }
    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_part = _base64url_encode(payload_bytes)
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return ArticleRenderToken(
        token=f"{payload_part}.{_base64url_encode(signature)}",
        expires=expires,
    )


def verify_article_render_token(
    *,
    token: str,
    expires: int,
    post_slug: str,
    file_id: int,
    secret_key: str,
) -> bool:
    try:
        payload_part, signature_part = token.split(".", maxsplit=1)
        expected_signature = hmac.new(
            secret_key.encode("utf-8"),
            payload_part.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(
            signature_part,
            _base64url_encode(expected_signature),
        ):
            return False
        payload = json.loads(_base64url_decode(payload_part))
    except (BinasciiError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False

    return (
        payload.get("scope") == "post_image_render"
        and payload.get("slug") == post_slug
        and payload.get("file_id") == file_id
        and payload.get("exp") == expires
        and expires > int(utc_now().timestamp())
    )


def verify_admin_file_preview_token(
    *,
    token: str,
    expires: int,
    file_id: int,
    secret_key: str,
) -> bool:
    try:
        payload_part, signature_part = token.split(".", maxsplit=1)
        expected_signature = hmac.new(
            secret_key.encode("utf-8"),
            payload_part.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(
            signature_part,
            _base64url_encode(expected_signature),
        ):
            return False
        payload = json.loads(_base64url_decode(payload_part))
    except (BinasciiError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False

    return (
        payload.get("scope") == "admin_file_preview"
        and payload.get("file_id") == file_id
        and payload.get("exp") == expires
        and expires > int(utc_now().timestamp())
    )


def sign_article_render_urls(
    *,
    content_html: str,
    post_slug: str,
    expires_seconds: int,
    secret_key: str,
) -> str:
    pattern = re.compile(
        r'(?P<prefix>\bsrc=["\'])'
        r'(?P<path>/?api/public/posts/'
        + re.escape(post_slug)
        + r'/files/(?P<file_id>\d+)/render)'
        r'(?P<suffix>["\'])',
    )

    def replace(match: re.Match[str]) -> str:
        file_id = int(match.group("file_id"))
        access = create_article_render_token(
            post_slug=post_slug,
            file_id=file_id,
            expires_seconds=expires_seconds,
            secret_key=secret_key,
        )
        path = match.group("path")
        signed_path = f"{path}?expires={access.expires}&token={access.token}"
        return f"{match.group('prefix')}{signed_path}{match.group('suffix')}"

    return pattern.sub(replace, content_html)


def sign_admin_preview_image_urls(
    *,
    content_html: str,
    post_slug: str,
    expires_seconds: int,
    secret_key: str,
) -> str:
    pattern = re.compile(
        r'(?P<prefix>\bsrc=["\'])'
        r'(?P<path>/?api/public/posts/'
        + re.escape(post_slug)
        + r'/files/(?P<file_id>\d+)/render)'
        r'(?P<suffix>["\'])',
    )

    def replace(match: re.Match[str]) -> str:
        file_id = int(match.group("file_id"))
        access = create_admin_file_preview_token(
            file_id=file_id,
            expires_seconds=expires_seconds,
            secret_key=secret_key,
        )
        preview_path = (
            f"/api/admin/files/{file_id}/preview?"
            f"expires={access.expires}&token={access.token}"
        )
        return f"{match.group('prefix')}{preview_path}{match.group('suffix')}"

    return pattern.sub(replace, content_html)


def _resolve_storage_path(
    upload_root: Path,
    object_key: str,
    *,
    public_only: bool = True,
) -> Path | None:
    if public_only and not object_key.startswith("public/"):
        return None

    root = upload_root.resolve()
    path = (upload_root / object_key).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _article_render_reference_exists(
    *,
    post_slug: str,
    file_id: int,
    content_md: str,
    content_html: str,
) -> bool:
    references = (
        f"/api/public/posts/{post_slug}/files/{file_id}/render",
        f"api/public/posts/{post_slug}/files/{file_id}/render",
    )
    return any(
        reference in content_md or reference in content_html
        for reference in references
    )


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}").decode("utf-8")
