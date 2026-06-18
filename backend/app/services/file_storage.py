import warnings
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.models.file import BlogFile
from app.services.file_errors import (
    InvalidFileTypeError,
    ManagedFileNotFoundError,
)
from app.services.file_uploads import (
    ALLOWED_VISIBILITIES,
    validate_image_dimensions,
)


def resolve_storage_path(
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


def iter_managed_storage_files(upload_root: Path) -> Sequence[Path]:
    files: list[Path] = []
    for visibility in sorted(ALLOWED_VISIBILITIES):
        base_path = upload_root / visibility
        if not base_path.exists():
            continue
        files.extend(path for path in base_path.rglob("*") if path.is_file())
    return sorted(files)


def storage_path_to_object_key(upload_root: Path, path: Path) -> str | None:
    root = upload_root.resolve()
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(root)
    except ValueError:
        return None
    parts = relative_path.parts
    if not parts or parts[0] not in ALLOWED_VISIBILITIES:
        return None
    return relative_path.as_posix()


def thumbnail_path(upload_root: Path, file: BlogFile) -> Path:
    return upload_root / ".thumbs" / f"{file.sha256[:32]}-360.jpg"


def create_thumbnail(
    *,
    source_path: Path,
    target_path: Path,
    max_side: int,
) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image_context = Image.open(source_path)
        with image_context as image:
            validate_image_dimensions(width=image.width, height=image.height)
            image.thumbnail((max_side, max_side))
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.save(target_path, format="JPEG", quality=78, optimize=True)
    except (
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        InvalidFileTypeError,
    ) as exc:
        raise ManagedFileNotFoundError("thumbnail generation failed") from exc


def article_render_reference_exists(
    *,
    post_slug: str,
    file_id: int,
    cover_file_id: int | None,
    content_md: str,
    content_html: str,
) -> bool:
    if cover_file_id == file_id:
        return True

    references = (
        f"/api/public/posts/{post_slug}/files/{file_id}/render",
        f"api/public/posts/{post_slug}/files/{file_id}/render",
    )
    return any(
        reference in content_md or reference in content_html
        for reference in references
    )
