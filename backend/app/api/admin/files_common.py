from typing import Annotated

from fastapi import Depends, File, Form, Query, Request, UploadFile

from app.api.admin.dependencies import require_admin_permission
from app.api.encrypted_response import encrypted_response
from app.core.encryption import EncryptionProfile
from app.core.request import client_ip
from app.schemas.encryption import EncryptedApiResponse
from app.schemas.files import (
    FILE_ACCESS_TOKEN_MAX_LENGTH,
    AdminFileItem,
    AdminFileListResponse,
    AdminFileTemporaryUrlResponse,
    FileVisibility,
)
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager
from app.services.files import FileTooLargeError
from app.services.logs import LogService

UploadedFile = Annotated[UploadFile, File()]
FileVisibilityForm = Annotated[FileVisibility, Form()]
AltTextForm = Annotated[str | None, Form(max_length=255)]
PublicListedForm = Annotated[bool, Form()]
PreviewToken = Annotated[
    str | None,
    Query(min_length=16, max_length=FILE_ACCESS_TOKEN_MAX_LENGTH),
]
PreviewExpires = Annotated[int | None, Query(ge=1)]
FileUploaderDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("file:upload")),
]
FileDeleterDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("file:delete")),
]


async def record_admin_file_download_log(
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


async def read_upload_data(file: UploadFile, *, max_size_bytes: int) -> bytes:
    data = await file.read(max_size_bytes + 1)
    if len(data) > max_size_bytes:
        raise FileTooLargeError("file is too large")
    return data


async def files_response(
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


def file_audit_payload(file: object) -> dict[str, object]:
    return {
        "visibility": getattr(file, "visibility", None),
        "public_listed": getattr(file, "public_listed", None),
        "status": getattr(file, "status", None),
    }
