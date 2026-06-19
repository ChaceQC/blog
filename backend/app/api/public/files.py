from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.api.dependencies import (
    ContentServiceDependency,
    EncryptionSessionManagerDependency,
    FileServiceDependency,
    LogServiceDependency,
    SettingsDependency,
)
from app.api.encrypted_response import encrypted_response
from app.api.file_cache import signed_file_cache_headers
from app.api.public.common import (
    record_public_access,
    validate_public_content_session,
)
from app.core.encryption import EncryptionProfile
from app.core.urls import public_file_download_url
from app.schemas.encryption import EncryptedApiResponse
from app.schemas.files import (
    AdminFileTemporaryUrlResponse,
    PublicFileItem,
    PublicFileListResponse,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.content import ContentNotFoundError
from app.services.files import (
    FileAccessDeniedError,
    InvalidFileAccessTokenError,
    ManagedFileNotFoundError,
    verify_article_render_token,
)

router = APIRouter(tags=["public-files"])
TemporaryFileToken = Annotated[str, Query(min_length=16)]
ArticleImageToken = Annotated[str | None, Query(min_length=16)]
ArticleImageExpires = Annotated[int | None, Query(ge=1)]
PublicFileContentServiceDependency = ContentServiceDependency


@router.get("/files", response_model=EncryptedApiResponse)
async def list_public_files(
    request: Request,
    service: FileServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    await validate_public_content_session(request, encryption_manager)
    files = await service.list_public_files(limit=limit, offset=offset)
    total = await service.count_public_files()
    response = await encrypted_response(
        PublicFileListResponse(
            items=[PublicFileItem.model_validate(file) for file in files],
            total=total,
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await _record_file_access(
        logs,
        request=request,
        access_type="public_files_list",
        status_code=status.HTTP_200_OK,
        file_id=0,
        entity_type="file",
        entity_id=None,
    )
    return response


@router.get("/files/{file_id}/temporary-url", response_model=EncryptedApiResponse)
async def create_public_file_temporary_url(
    file_id: int,
    request: Request,
    service: FileServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    await validate_public_content_session(request, encryption_manager)
    try:
        access = await service.create_public_temporary_access(
            file_id=file_id,
            secret_key=settings.secret_key,
            expires_seconds=settings.file_temporary_url_expire_seconds,
        )
    except ManagedFileNotFoundError as exc:
        await _record_file_access(
            logs,
            request=request,
            access_type="public_file_temporary_url",
            status_code=status.HTTP_404_NOT_FOUND,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc
    except FileAccessDeniedError as exc:
        await _record_file_access(
            logs,
            request=request,
            access_type="public_file_temporary_url",
            status_code=status.HTTP_403_FORBIDDEN,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="file is not listed public",
        ) from exc

    response = await encrypted_response(
        AdminFileTemporaryUrlResponse(
            url=public_file_download_url(file_id=access.file.id, token=access.token),
            expires_at=access.expires_at,
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await _record_file_access(
        logs,
        request=request,
        access_type="public_file_temporary_url",
        status_code=status.HTTP_200_OK,
        file_id=file_id,
    )
    return response


@router.get("/files/{file_id}/download")
async def download_public_file(
    file_id: int,
    token: TemporaryFileToken,
    request: Request,
    service: FileServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> FileResponse:
    try:
        download = await service.prepare_public_download(
            file_id=file_id,
            token=token,
            secret_key=settings.secret_key,
            upload_root=settings.upload_root,
        )
    except ManagedFileNotFoundError as exc:
        await _record_file_access(
            logs,
            request=request,
            access_type="public_file_download",
            status_code=status.HTTP_404_NOT_FOUND,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc
    except (FileAccessDeniedError, InvalidFileAccessTokenError) as exc:
        await _record_file_access(
            logs,
            request=request,
            access_type="public_file_download",
            status_code=status.HTTP_403_FORBIDDEN,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid file access",
        ) from exc

    await _record_file_access(
        logs,
        request=request,
        access_type="public_file_download",
        status_code=status.HTTP_200_OK,
        file_id=file_id,
    )
    return FileResponse(
        download.path,
        media_type=download.media_type,
        filename=download.filename,
    )


@router.get("/posts/{slug}/files/{file_id}/render")
async def render_post_file(
    slug: str,
    file_id: int,
    request: Request,
    content_service: PublicFileContentServiceDependency,
    file_service: FileServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
    token: ArticleImageToken = None,
    expires: ArticleImageExpires = None,
) -> FileResponse:
    if token is None or expires is None or not verify_article_render_token(
        token=token,
        expires=expires,
        post_slug=slug,
        file_id=file_id,
        secret_key=settings.secret_key,
    ):
        await _record_file_access(
            logs,
            request=request,
            access_type="post_image_render",
            status_code=status.HTTP_403_FORBIDDEN,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid image access",
        )

    try:
        post = await content_service.get_public_post_by_slug(slug)
        download = await file_service.prepare_article_render(
            file_id=file_id,
            post_slug=slug,
            post_cover_file_id=post.cover_file_id,
            post_content_md=post.content_md,
            post_content_html=post.content_html,
            upload_root=settings.upload_root,
        )
    except (ContentNotFoundError, ManagedFileNotFoundError) as exc:
        await _record_file_access(
            logs,
            request=request,
            access_type="post_image_render",
            status_code=status.HTTP_404_NOT_FOUND,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc
    except FileAccessDeniedError as exc:
        await _record_file_access(
            logs,
            request=request,
            access_type="post_image_render",
            status_code=status.HTTP_403_FORBIDDEN,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="file is not referenced by post",
        ) from exc

    await _record_file_access(
        logs,
        request=request,
        access_type="post_image_render",
        status_code=status.HTTP_200_OK,
        file_id=file_id,
    )
    return FileResponse(
        download.path,
        media_type=download.media_type,
        filename=download.filename,
        headers=signed_file_cache_headers(path=download.path, expires=expires),
    )


@router.get("/posts/{slug}/files/{file_id}/thumbnail")
async def thumbnail_post_file(
    slug: str,
    file_id: int,
    request: Request,
    content_service: PublicFileContentServiceDependency,
    file_service: FileServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
    token: ArticleImageToken = None,
    expires: ArticleImageExpires = None,
) -> FileResponse:
    if token is None or expires is None or not verify_article_render_token(
        token=token,
        expires=expires,
        post_slug=slug,
        file_id=file_id,
        secret_key=settings.secret_key,
    ):
        await _record_file_access(
            logs,
            request=request,
            access_type="post_image_thumbnail",
            status_code=status.HTTP_403_FORBIDDEN,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid image access",
        )

    try:
        post = await content_service.get_public_post_by_slug(slug)
        thumbnail = await file_service.prepare_article_thumbnail(
            file_id=file_id,
            post_slug=slug,
            post_cover_file_id=post.cover_file_id,
            post_content_md=post.content_md,
            post_content_html=post.content_html,
            upload_root=settings.upload_root,
        )
    except (ContentNotFoundError, ManagedFileNotFoundError) as exc:
        await _record_file_access(
            logs,
            request=request,
            access_type="post_image_thumbnail",
            status_code=status.HTTP_404_NOT_FOUND,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc
    except FileAccessDeniedError as exc:
        await _record_file_access(
            logs,
            request=request,
            access_type="post_image_thumbnail",
            status_code=status.HTTP_403_FORBIDDEN,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="file is not referenced by post",
        ) from exc

    await _record_file_access(
        logs,
        request=request,
        access_type="post_image_thumbnail",
        status_code=status.HTTP_200_OK,
        file_id=file_id,
    )
    return FileResponse(
        thumbnail.path,
        media_type=thumbnail.media_type,
        filename=thumbnail.filename,
        headers=signed_file_cache_headers(path=thumbnail.path, expires=expires),
    )


async def _record_file_access(
    logs: LogServiceDependency,
    *,
    request: Request,
    access_type: str,
    status_code: int,
    file_id: int,
    entity_type: str | None = "file",
    entity_id: int | None = None,
    detail_json: dict[str, object] | None = None,
) -> None:
    await record_public_access(
        logs,
        request=request,
        access_type=access_type,
        status_code=status_code,
        entity_type=entity_type,
        entity_id=file_id if entity_id is None and file_id > 0 else entity_id,
        detail_json=detail_json,
    )
