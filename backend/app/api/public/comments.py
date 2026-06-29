from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from app.api.dependencies import (
    CommentServiceDependency,
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    RateLimitServiceDependency,
    SettingsDependency,
)
from app.api.encrypted_response import decrypt_encrypted_request, encrypted_response
from app.api.limits import enforce_rate_limit
from app.api.public.common import (
    record_public_access,
    validate_decrypted_payload,
    validate_public_content_session,
)
from app.core.encryption import EncryptionProfile
from app.core.request import client_ip
from app.schemas.comments import (
    PublicCommentCreateRequest,
    PublicCommentCreateResponse,
    PublicCommentDeleteRequest,
    PublicCommentDeleteResponse,
    PublicCommentListResponse,
    PublicOwnedCommentsRequest,
    PublicOwnedCommentsResponse,
)
from app.schemas.content import SLUG_PATTERN
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.comments import (
    CommentClosedError,
    CommentDuplicateError,
    CommentNotFoundError,
    CommentParentInvalidError,
    CommentQueueFullError,
    CommentRiskLimitedError,
    CommentStateConflictError,
    CommentTokenInvalidError,
)
from app.services.rate_limit import RateLimitRule

router = APIRouter(tags=["public-comments"])


@router.get("/posts/{slug}/comments", response_model=EncryptedApiResponse)
async def list_public_comments(
    slug: Annotated[
        str,
        Path(min_length=1, max_length=220, pattern=SLUG_PATTERN),
    ],
    request: Request,
    comments: CommentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    await validate_public_content_session(request, encryption_manager)
    try:
        items, total = await comments.list_public_comments(
            slug=slug,
            limit=limit,
            offset=offset,
        )
    except CommentNotFoundError as exc:
        raise _not_found("post not found") from exc
    await record_public_access(
        logs,
        request=request,
        access_type="public_comments_list",
        status_code=status.HTTP_200_OK,
        entity_type="post",
    )
    return await _public_comment_response(
        PublicCommentListResponse(items=items, total=total),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/posts/{slug}/comments", response_model=EncryptedApiResponse)
async def create_public_comment(
    slug: Annotated[
        str,
        Path(min_length=1, max_length=220, pattern=SLUG_PATTERN),
    ],
    payload: EncryptedApiRequest,
    request: Request,
    comments: CommentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
    rate_limiter: RateLimitServiceDependency,
) -> EncryptedApiResponse:
    await _enforce_comment_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        logs=logs,
        settings=settings,
        action="create",
    )
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    comment_payload = validate_decrypted_payload(
        PublicCommentCreateRequest,
        decrypted_payload,
    )
    try:
        created = await comments.create_public_comment(
            slug=slug,
            payload=comment_payload,
            client_ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
            accept_language=request.headers.get("accept-language"),
        )
    except CommentNotFoundError as exc:
        raise _not_found("post not found") from exc
    except CommentClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="comments are closed",
        ) from exc
    except CommentParentInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid comment parent",
        ) from exc
    except CommentDuplicateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="duplicate comment",
        ) from exc
    except CommentQueueFullError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="comment review queue is full",
        ) from exc
    except CommentRiskLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="comment risk limited",
        ) from exc
    await record_public_access(
        logs,
        request=request,
        access_type="public_comment_create",
        status_code=status.HTTP_200_OK,
        entity_type="post",
        detail_json={"status": created.comment.status},
    )
    return await _public_comment_response(
        PublicCommentCreateResponse(
            comment=created.comment,
            delete_token=created.delete_token,
            message="评论已提交，等待审核",
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/posts/{slug}/comments/owned", response_model=EncryptedApiResponse)
async def list_owned_public_comments(
    slug: Annotated[
        str,
        Path(min_length=1, max_length=220, pattern=SLUG_PATTERN),
    ],
    payload: EncryptedApiRequest,
    request: Request,
    comments: CommentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
    rate_limiter: RateLimitServiceDependency,
) -> EncryptedApiResponse:
    await _enforce_comment_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        logs=logs,
        settings=settings,
        action="owned",
        max_attempts=settings.comment_owned_rate_limit_max_attempts,
        window_seconds=settings.comment_owned_rate_limit_window_seconds,
    )
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    owned_payload = validate_decrypted_payload(
        PublicOwnedCommentsRequest,
        decrypted_payload,
    )
    try:
        items = await comments.list_owned_comments(
            slug=slug,
            receipts=owned_payload.receipts,
        )
    except CommentNotFoundError as exc:
        raise _not_found("post not found") from exc
    await record_public_access(
        logs,
        request=request,
        access_type="public_comments_owned",
        status_code=status.HTTP_200_OK,
        entity_type="post",
    )
    return await _public_comment_response(
        PublicOwnedCommentsResponse(items=items),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post(
    "/posts/{slug}/comments/{comment_id}/delete",
    response_model=EncryptedApiResponse,
)
async def delete_public_comment(
    slug: Annotated[
        str,
        Path(min_length=1, max_length=220, pattern=SLUG_PATTERN),
    ],
    comment_id: Annotated[int, Path(ge=1)],
    payload: EncryptedApiRequest,
    request: Request,
    comments: CommentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
    rate_limiter: RateLimitServiceDependency,
) -> EncryptedApiResponse:
    await _enforce_comment_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        logs=logs,
        settings=settings,
        action="delete",
    )
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    delete_payload = validate_decrypted_payload(
        PublicCommentDeleteRequest,
        decrypted_payload,
    )
    try:
        comment = await comments.delete_public_comment(
            slug=slug,
            comment_id=comment_id,
            delete_token=delete_payload.delete_token,
        )
    except (
        CommentNotFoundError,
        CommentTokenInvalidError,
        CommentStateConflictError,
    ) as exc:
        raise _not_found("comment not found") from exc
    await record_public_access(
        logs,
        request=request,
        access_type="public_comment_delete",
        status_code=status.HTTP_200_OK,
        entity_type="comment",
        entity_id=comment.id,
        detail_json={"status": comment.status},
    )
    return await _public_comment_response(
        PublicCommentDeleteResponse(id=comment.id, status=comment.status),
        request=request,
        encryption_manager=encryption_manager,
    )


async def _public_comment_response(
    payload,
    *,
    request: Request,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    return await encrypted_response(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )


async def _enforce_comment_rate_limit(
    *,
    request: Request,
    rate_limiter: RateLimitServiceDependency,
    logs: LogServiceDependency,
    settings: SettingsDependency,
    action: str,
    max_attempts: int | None = None,
    window_seconds: int | None = None,
) -> None:
    await enforce_rate_limit(
        request=request,
        limiter=rate_limiter,
        logs=logs,
        key=f"comment:{client_ip(request) or 'unknown'}:{action}",
        rule=RateLimitRule(
            max_attempts=max_attempts or settings.comment_rate_limit_max_attempts,
            window_seconds=window_seconds or settings.comment_rate_limit_window_seconds,
        ),
        event_type="rate_limit.comment",
        detail_json={"scope": "public", "action": action},
    )


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
