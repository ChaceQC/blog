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

from app.api.admin.dependencies import (
    AdminCsrfDependency,
    EncryptionSessionManagerDependency,
    FileServiceDependency,
    SettingsDependency,
    require_admin_permission,
)
from app.api.admin.encrypted_response import encrypted_response
from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiResponse
from app.schemas.files import AdminFileItem, AdminFileListResponse, FileVisibility
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager
from app.services.files import (
    FileTooLargeError,
    FileValidationError,
    ManagedFileNotFoundError,
    UploadFileCommand,
)

router = APIRouter(tags=["admin-files"])
UploadedFile = Annotated[UploadFile, File()]
FileVisibilityForm = Annotated[FileVisibility, Form()]
AltTextForm = Annotated[str | None, Form(max_length=255)]
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
    offset: int = Query(default=0, ge=0),
) -> EncryptedApiResponse:
    files = await service.list_files(limit=limit, offset=offset)
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
    file: UploadedFile,
    visibility: FileVisibilityForm = "public",
    alt_text: AltTextForm = None,
) -> EncryptedApiResponse:
    try:
        uploaded_file = await service.upload_file(
            UploadFileCommand(
                original_name=file.filename or "uploaded-file",
                content_type=file.content_type,
                data=await file.read(),
                visibility=visibility,
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

    return await _files_response(
        AdminFileItem.model_validate(uploaded_file),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.delete("/files/{file_id}", response_model=EncryptedApiResponse)
async def delete_file(
    file_id: int,
    _: AdminCsrfDependency,
    __: FileDeleterDependency,
    request: Request,
    service: FileServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        file = await service.delete_file(file_id)
    except ManagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        ) from exc

    return await _files_response(
        AdminFileItem.model_validate(file),
        request=request,
        encryption_manager=encryption_manager,
    )


async def _files_response(
    payload: AdminFileItem | AdminFileListResponse,
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
