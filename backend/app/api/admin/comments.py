from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status

from app.api.admin.audit import record_admin_audit
from app.api.admin.content_common import (
    content_response,
    decrypt_content_payload,
    validate_decrypted_payload,
)
from app.api.admin.dependencies import (
    AdminContentEncryptionDependency,
    AdminCsrfDependency,
    require_admin_permission,
)
from app.api.dependencies import (
    CommentServiceDependency,
    EncryptionSessionManagerDependency,
    LogServiceDependency,
)
from app.schemas.comments import (
    AdminCommentItem,
    AdminCommentListResponse,
    AdminCommentReviewRequest,
    AdminCommentStatusFilter,
)
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.auth import AuthenticatedUser
from app.services.comments import CommentNotFoundError, CommentStateConflictError

router = APIRouter(tags=["admin-comments"])

CommentReviewerDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("comment:review")),
]


@router.get("/comments", response_model=EncryptedApiResponse)
async def list_admin_comments(
    _: CommentReviewerDependency,
    __: AdminContentEncryptionDependency,
    request: Request,
    comments: CommentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    status_filter: Annotated[
        AdminCommentStatusFilter,
        Query(alias="status"),
    ] = "pending",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    items, total = await comments.list_admin_comments(
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return await content_response(
        AdminCommentListResponse(items=items, total=total),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/comments/{comment_id}/review", response_model=EncryptedApiResponse)
async def review_admin_comment(
    comment_id: Annotated[int, Path(ge=1)],
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: CommentReviewerDependency,
    request: Request,
    comments: CommentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    review_payload = validate_decrypted_payload(
        AdminCommentReviewRequest,
        decrypted_payload,
    )
    try:
        comment = await comments.review_comment(
            comment_id=comment_id,
            action=review_payload.action,
            reviewer_id=current_user.id,
            reason_class=review_payload.reason_class,
        )
    except CommentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="comment not found",
        ) from exc
    except CommentStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="comment state conflict",
        ) from exc

    await _record_comment_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action=review_payload.action,
        comment=comment,
        reason_class=review_payload.reason_class,
    )
    return await content_response(
        comment,
        request=request,
        encryption_manager=encryption_manager,
    )


@router.delete("/comments/{comment_id}", response_model=EncryptedApiResponse)
async def delete_admin_comment(
    comment_id: Annotated[int, Path(ge=1)],
    _: AdminCsrfDependency,
    __: AdminContentEncryptionDependency,
    current_user: CommentReviewerDependency,
    request: Request,
    comments: CommentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    try:
        comment = await comments.review_comment(
            comment_id=comment_id,
            action="delete",
            reviewer_id=current_user.id,
            reason_class="admin_deleted",
        )
    except CommentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="comment not found",
        ) from exc
    except CommentStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="comment state conflict",
        ) from exc

    await _record_comment_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="delete",
        comment=comment,
        reason_class="admin_deleted",
    )
    return await content_response(
        comment,
        request=request,
        encryption_manager=encryption_manager,
    )


async def _record_comment_audit(
    *,
    logs: LogServiceDependency,
    request: Request,
    actor,
    action: str,
    comment: AdminCommentItem,
    reason_class: str | None,
) -> None:
    await record_admin_audit(
        logs=logs,
        request=request,
        actor=actor,
        action=f"comment.{action}",
        entity_type="comment",
        entity_id=comment.id,
        after_json={
            "status": comment.status,
            "review_status": action,
            "reason_class": reason_class,
            "deleted": action == "delete",
        },
    )
