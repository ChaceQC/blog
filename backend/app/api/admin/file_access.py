from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.api.admin.files_common import (
    FileUploaderDependency,
    PreviewExpires,
    PreviewToken,
    record_admin_file_download_log,
)
from app.api.dependencies import (
    FileServiceDependency,
    LogServiceDependency,
    SettingsDependency,
)
from app.api.file_cache import signed_file_cache_headers
from app.services.files import (
    FileAccessDeniedError,
    InvalidFileAccessTokenError,
    ManagedFileNotFoundError,
)

router = APIRouter(tags=["admin-files"])


@router.get("/files/{file_id}/download")
async def download_admin_file(
    file_id: int,
    _: FileUploaderDependency,
    request: Request,
    service: FileServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> FileResponse:
    try:
        download = await service.prepare_admin_download(
            file_id=file_id,
            upload_root=settings.upload_root,
        )
    except ManagedFileNotFoundError as exc:
        await record_admin_file_download_log(
            request=request,
            logs=logs,
            file_id=file_id,
            status_code=status.HTTP_404_NOT_FOUND,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc
    except FileAccessDeniedError as exc:
        await record_admin_file_download_log(
            request=request,
            logs=logs,
            file_id=file_id,
            status_code=status.HTTP_403_FORBIDDEN,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="file is not downloadable",
        ) from exc

    await record_admin_file_download_log(
        request=request,
        logs=logs,
        file_id=file_id,
        status_code=status.HTTP_200_OK,
    )
    return FileResponse(
        download.path,
        media_type=download.media_type,
        filename=download.filename,
    )


@router.get("/files/{file_id}/preview")
async def preview_file(
    file_id: int,
    _: FileUploaderDependency,
    request: Request,
    service: FileServiceDependency,
    settings: SettingsDependency,
    token: PreviewToken = None,
    expires: PreviewExpires = None,
) -> FileResponse:
    if token is None or expires is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid preview access",
        )
    try:
        download = await service.prepare_admin_preview(
            file_id=file_id,
            token=token,
            expires=expires,
            secret_key=settings.secret_key,
            upload_root=settings.upload_root,
        )
    except ManagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc
    except (FileAccessDeniedError, InvalidFileAccessTokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid preview access",
        ) from exc

    return FileResponse(
        download.path,
        media_type=download.media_type,
        filename=download.filename,
        headers=signed_file_cache_headers(path=download.path, expires=expires),
    )


@router.get("/files/{file_id}/thumbnail")
async def thumbnail_file(
    file_id: int,
    _: FileUploaderDependency,
    service: FileServiceDependency,
    settings: SettingsDependency,
) -> FileResponse:
    try:
        thumbnail = await service.prepare_admin_thumbnail(
            file_id=file_id,
            upload_root=settings.upload_root,
        )
    except ManagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc
    except FileAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="file is not thumbnailable",
        ) from exc

    return FileResponse(
        thumbnail.path,
        media_type=thumbnail.media_type,
        filename=thumbnail.filename,
    )
