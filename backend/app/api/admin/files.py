from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import (
    AdminCsrfDependency,
    require_admin_permission,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    FileServiceDependency,
    LogServiceDependency,
    SettingsDependency,
)
from app.api.encrypted_response import encrypted_response
from app.core.encryption import EncryptionProfile
from app.core.request import client_ip
from app.core.urls import public_file_download_url
from app.schemas.encryption import EncryptedApiResponse
from app.schemas.files import (
    AdminFileItem,
    AdminFileListResponse,
    AdminFileTemporaryUrlResponse,
    FileVisibility,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager
from app.services.files import (
    FileAccessDeniedError,
    FileTooLargeError,
    FileValidationError,
    InvalidFileAccessTokenError,
    ManagedFileNotFoundError,
    UploadFileCommand,
)
from app.services.logs import LogService

router = APIRouter(tags=["admin-files"])
UploadedFile = Annotated[UploadFile, File()]
FileVisibilityForm = Annotated[FileVisibility, Form()]
AltTextForm = Annotated[str | None, Form(max_length=255)]
PublicListedForm = Annotated[bool, Form()]
PreviewToken = Annotated[str | None, Query(min_length=16)]
PreviewExpires = Annotated[int | None, Query(ge=1)]
FileUploaderDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("file:upload")),
]
FileDeleterDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("file:delete")),
]


@router.get("/files", response_model=EncryptedApiResponse)
async def list_files(
    _: FileUploaderDependency,
    request: Request,
    service: FileServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    files = await service.list_admin_files(limit=limit, offset=offset)
    return await _files_response(
        AdminFileListResponse(
            items=[AdminFileItem.model_validate(file) for file in files],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/files", response_model=EncryptedApiResponse)
async def upload_file(
    current_user: FileUploaderDependency,
    request: Request,
    _: AdminCsrfDependency,
    service: FileServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
    file: UploadedFile,
    visibility: FileVisibilityForm = "public",
    alt_text: AltTextForm = None,
    public_listed: PublicListedForm = False,
) -> EncryptedApiResponse:
    try:
        uploaded_file = await service.upload_file(
            UploadFileCommand(
                original_name=file.filename or "uploaded-file",
                content_type=file.content_type,
                data=await _read_upload_data(
                    file,
                    max_size_bytes=settings.upload_max_size_bytes,
                ),
                visibility=visibility,
                public_listed=public_listed,
                uploader_id=current_user.id,
                alt_text=alt_text,
                max_size_bytes=settings.upload_max_size_bytes,
            ),
        )
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file is too large",
        ) from exc
    except FileValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid file upload",
        ) from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="file.upload",
        entity_type="file",
        entity_id=uploaded_file.id,
        after_json=_file_audit_payload(uploaded_file),
    )
    return await _files_response(
        AdminFileItem.model_validate(service.admin_file_response(uploaded_file)),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.delete("/files/{file_id}", response_model=EncryptedApiResponse)
async def delete_file(
    file_id: int,
    _: AdminCsrfDependency,
    current_user: FileDeleterDependency,
    request: Request,
    service: FileServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    try:
        file = await service.delete_file(file_id)
    except ManagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="file.delete",
        entity_type="file",
        entity_id=file.id,
        after_json=_file_audit_payload(file),
    )
    return await _files_response(
        AdminFileItem.model_validate(service.admin_file_response(file)),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/files/{file_id}/temporary-url", response_model=EncryptedApiResponse)
async def create_file_temporary_url(
    file_id: int,
    _: FileUploaderDependency,
    request: Request,
    service: FileServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    try:
        access = await service.create_temporary_access(
            file_id=file_id,
            secret_key=settings.secret_key,
            expires_seconds=settings.file_temporary_url_expire_seconds,
        )
    except ManagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc
    except FileAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="file is not public",
        ) from exc

    payload = AdminFileTemporaryUrlResponse(
        url=public_file_download_url(file_id=access.file.id, token=access.token),
        expires_at=access.expires_at,
    )
    response = await _files_response(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    await logs.record_access_log(
        access_type="admin_file_temporary_url",
        method=request.method,
        path=str(request.url.path),
        status_code=status.HTTP_200_OK,
        entity_type="file",
        entity_id=access.file.id,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        detail_json={"expires_at": access.expires_at.isoformat()},
    )
    return response


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
        await _record_admin_file_download_log(
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
        await _record_admin_file_download_log(
            request=request,
            logs=logs,
            file_id=file_id,
            status_code=status.HTTP_403_FORBIDDEN,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="file is not downloadable",
        ) from exc

    await _record_admin_file_download_log(
        request=request,
        logs=logs,
        file_id=file_id,
        status_code=status.HTTP_200_OK,
        detail_json={
            "filename": download.filename,
            "media_type": download.media_type,
        },
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


async def _record_admin_file_download_log(
    *,
    request: Request,
    logs: LogService,
    file_id: int,
    status_code: int,
    detail_json: dict[str, object] | None = None,
) -> None:
    await logs.record_access_log(
        access_type="admin_file_download",
        method=request.method,
        path=str(request.url.path),
        status_code=status_code,
        entity_type="file",
        entity_id=file_id,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        detail_json=detail_json,
    )


async def _read_upload_data(file: UploadFile, *, max_size_bytes: int) -> bytes:
    data = await file.read(max_size_bytes + 1)
    if len(data) > max_size_bytes:
        raise FileTooLargeError("file is too large")
    return data


async def _files_response(
    payload: AdminFileItem | AdminFileListResponse | AdminFileTemporaryUrlResponse,
    *,
    request: Request,
    encryption_manager: EncryptionSessionManager,
) -> EncryptedApiResponse:
    return await encrypted_response(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )


def _file_audit_payload(file: object) -> dict[str, object]:
    return {
        "original_name": getattr(file, "original_name", None),
        "mime_type": getattr(file, "mime_type", None),
        "visibility": getattr(file, "visibility", None),
        "public_listed": getattr(file, "public_listed", None),
        "status": getattr(file, "status", None),
    }
