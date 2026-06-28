from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import (
    AdminContentEncryptionDependency,
    AdminCsrfDependency,
)
from app.api.admin.files_common import (
    AltTextForm,
    FileDeleterDependency,
    FileUploaderDependency,
    FileVisibilityForm,
    PublicListedForm,
    UploadedFile,
    file_audit_payload,
    files_response,
    read_upload_data,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    FileServiceDependency,
    LogServiceDependency,
    SettingsDependency,
)
from app.api.telemetry import (
    record_file_deleted_telemetry,
    record_file_upload_telemetry,
    record_temporary_url_telemetry,
)
from app.core.request import client_ip
from app.core.urls import public_file_download_url
from app.schemas.encryption import EncryptedApiResponse
from app.schemas.files import (
    AdminFileItem,
    AdminFileListResponse,
    AdminFileTemporaryUrlResponse,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.files import (
    FileAccessDeniedError,
    FileTooLargeError,
    FileValidationError,
    ManagedFileNotFoundError,
    UploadFileCommand,
)

router = APIRouter(tags=["admin-files"])


@router.get("/files", response_model=EncryptedApiResponse)
async def list_files(
    _: FileUploaderDependency,
    __: AdminContentEncryptionDependency,
    request: Request,
    service: FileServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    files = await service.list_admin_files(limit=limit, offset=offset)
    return await files_response(
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
                data=await read_upload_data(
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
        telemetry = getattr(request.app.state, "telemetry_service", None)
        if telemetry is not None:
            record_file_upload_telemetry(
                telemetry,
                outcome="error",
                visibility=visibility,
                public_listed=public_listed,
            )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file is too large",
        ) from exc
    except FileValidationError as exc:
        telemetry = getattr(request.app.state, "telemetry_service", None)
        if telemetry is not None:
            record_file_upload_telemetry(
                telemetry,
                outcome="error",
                visibility=visibility,
                public_listed=public_listed,
            )
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
        after_json=file_audit_payload(uploaded_file),
    )
    telemetry = getattr(request.app.state, "telemetry_service", None)
    if telemetry is not None:
        record_file_upload_telemetry(
            telemetry,
            outcome="ok",
            visibility=visibility,
            public_listed=public_listed,
            entity_id=uploaded_file.id,
            size_bytes=uploaded_file.size_bytes,
        )
    return await files_response(
        AdminFileItem.model_validate(uploaded_file),
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
        after_json=file_audit_payload(file),
    )
    telemetry = getattr(request.app.state, "telemetry_service", None)
    if telemetry is not None:
        record_file_deleted_telemetry(
            telemetry,
            entity_id=file.id,
            actor_id=current_user.id,
        )
    return await files_response(
        AdminFileItem.model_validate(file),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/files/{file_id}/temporary-url", response_model=EncryptedApiResponse)
async def create_file_temporary_url(
    file_id: int,
    _: FileUploaderDependency,
    __: AdminContentEncryptionDependency,
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
    response = await files_response(
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
        detail_json=None,
    )
    telemetry = getattr(request.app.state, "telemetry_service", None)
    if telemetry is not None:
        record_temporary_url_telemetry(
            telemetry,
            scope="admin",
            entity_id=access.file.id,
            expires_seconds=settings.file_temporary_url_expire_seconds,
        )
    return response
