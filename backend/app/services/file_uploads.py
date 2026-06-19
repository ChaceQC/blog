import struct
import tempfile
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.auth import utc_now
from app.models.file import BlogFile
from app.services.file_errors import (
    FileTooLargeError,
    InvalidFileTypeError,
    InvalidFileVisibilityError,
)

ALLOWED_FILE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}
ALLOWED_VISIBILITIES = {"public", "private"}
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_SIDE = 12_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


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
class ValidatedUpload:
    original_name: str
    extension: str
    mime_type: str
    sha256: str
    width: int | None
    height: int | None
    object_key: str


def normalize_original_name(original_name: str) -> str:
    name = Path(original_name).name.strip()
    if not name or len(name) > 255:
        raise InvalidFileTypeError("invalid file name")
    return name


def extract_extension(original_name: str) -> str:
    extension = Path(original_name).suffix.lower()
    if extension == ".jpeg":
        return ".jpg"
    return extension


def build_object_key(*, visibility: str, extension: str, sha256: str) -> str:
    now = utc_now()
    return (
        f"{visibility}/{now:%Y}/{now:%m}/"
        f"{sha256[:24]}{extension.replace('.jpeg', '.jpg')}"
    )


def can_reuse_existing_upload(
    file: BlogFile,
    *,
    command: UploadFileCommand,
    original_name: str,
    expected_mime: str,
    extension: str,
) -> bool:
    public_listed = command.public_listed and command.visibility == "public"
    return (
        file.status == "active"
        and file.visibility == command.visibility
        and file.public_listed == public_listed
        and file.original_name == original_name
        and file.mime_type == expected_mime
        and file.extension == extension.removeprefix(".")
        and file.alt_text == command.alt_text
    )


def write_temp_file(data: bytes) -> Path:
    with tempfile.NamedTemporaryFile(delete=False) as file:
        file.write(data)
        return Path(file.name)


def validate_size(data: bytes, max_size_bytes: int) -> None:
    if not data:
        raise InvalidFileTypeError("empty file is not allowed")
    if len(data) > max_size_bytes:
        raise FileTooLargeError("file is too large")


def validate_visibility(visibility: str) -> None:
    if visibility not in ALLOWED_VISIBILITIES:
        raise InvalidFileVisibilityError("invalid file visibility")


def validate_type(
    *,
    extension: str,
    content_type: str | None,
    data: bytes,
) -> str:
    expected_mime = ALLOWED_FILE_TYPES.get(extension)
    normalized_mime = (content_type or "").split(";", maxsplit=1)[0].lower()
    if expected_mime is None or normalized_mime != expected_mime:
        raise InvalidFileTypeError("unsupported file type")
    if not matches_file_signature(data, expected_mime):
        raise InvalidFileTypeError("file signature does not match mime type")
    return expected_mime


def matches_file_signature(data: bytes, mime_type: str) -> bool:
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


def read_image_size(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if mime_type == "image/png" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    if mime_type == "image/gif" and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return width, height
    if mime_type == "image/jpeg":
        return read_jpeg_size(data)
    if mime_type == "image/webp":
        return read_pillow_image_size(data)
    return None, None


def validate_image_dimensions(*, width: int | None, height: int | None) -> None:
    if width is None or height is None:
        return
    if width <= 0 or height <= 0:
        raise InvalidFileTypeError("invalid image dimensions")
    if width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE:
        raise InvalidFileTypeError("image dimensions are too large")
    if width * height > MAX_IMAGE_PIXELS:
        raise InvalidFileTypeError("image pixel count is too large")


def read_jpeg_size(data: bytes) -> tuple[int | None, int | None]:
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


def read_pillow_image_size(data: bytes) -> tuple[int, int]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                return image.width, image.height
    except (
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidFileTypeError("invalid image file") from exc
