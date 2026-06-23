import asyncio
from typing import Any, Literal

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.encryption import EncryptionProfile
from app.schemas.encryption import (
    ENCRYPTION_CIPHERTEXT_MAX_LENGTH,
    ENCRYPTION_NONCE_MAX_LENGTH,
    ENCRYPTION_SESSION_ID_MAX_LENGTH,
    EncryptionSessionScope,
)
from app.services.encryption import (
    EncryptionSessionError,
    EncryptionSessionManager,
)
from app.services.encryption_salts import (
    EncryptionSaltError,
    SaltLeaseService,
    SaltPurpose,
    WrappedSaltFrame,
)


class SaltFrameRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=ENCRYPTION_SESSION_ID_MAX_LENGTH)
    wrap_salt: str = Field(min_length=1, max_length=128)
    nonce: str = Field(min_length=1, max_length=ENCRYPTION_NONCE_MAX_LENGTH)
    ciphertext: str = Field(min_length=1, max_length=ENCRYPTION_CIPHERTEXT_MAX_LENGTH)

    model_config = ConfigDict(extra="forbid")


class SaltLeaseRequestPayload(BaseModel):
    kind: Literal["salt_request"] = "salt_request"
    purpose: SaltPurpose
    profile: EncryptionProfile | None = None
    count: int = Field(default=1, ge=1, le=8)

    model_config = ConfigDict(extra="forbid")


class SaltLeaseBatchRequestPayload(BaseModel):
    kind: Literal["salt_batch_request"]
    items: list[SaltLeaseRequestPayload] = Field(min_length=1, max_length=8)

    model_config = ConfigDict(extra="forbid")


class SaltPingPayload(BaseModel):
    kind: Literal["ping"]
    seq: int = Field(ge=0, le=2_147_483_647)
    ts: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class SaltFrameResponse(BaseModel):
    type: Literal["salt_leases"] = "salt_leases"
    frames: list[SaltFrameRequest]

    model_config = ConfigDict(extra="forbid")


class SaltPongResponse(BaseModel):
    type: Literal["pong"] = "pong"
    frame: SaltFrameRequest

    model_config = ConfigDict(extra="forbid")


_SALT_STREAM_IDLE_TIMEOUT_SECONDS = 90


async def salt_websocket(
    websocket: WebSocket,
    *,
    scope: EncryptionSessionScope,
    manager: EncryptionSessionManager,
    salt_leases: SaltLeaseService,
) -> None:
    await websocket.accept()
    try:
        while True:
            try:
                raw_payload = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=_SALT_STREAM_IDLE_TIMEOUT_SECONDS,
                )
                request_frame = SaltFrameRequest.model_validate(raw_payload)
                session = await manager.get_session_for_salt_stream(
                    session_id=request_frame.session_id,
                    scope=scope,
                )
                request_payload = salt_leases.unwrap_request(
                    WrappedSaltFrame(
                        session_id=request_frame.session_id,
                        wrap_salt=request_frame.wrap_salt,
                        nonce=request_frame.nonce,
                        ciphertext=request_frame.ciphertext,
                    ),
                    key_material=session.key_material,
                    context_seed=session.context_seed,
                    scope=scope,
                )
                if request_payload.get("kind") == "ping":
                    ping = SaltPingPayload.model_validate(request_payload)
                    await websocket.send_json(
                        SaltPongResponse(
                            frame=SaltFrameRequest(
                                **salt_leases.wrap_payload(
                                    session_id=session.session_id,
                                    payload={
                                        "kind": "pong",
                                        "seq": ping.seq,
                                        "ts": ping.ts,
                                    },
                                    key_material=session.key_material,
                                    context_seed=session.context_seed,
                                    scope=scope,
                                ).__dict__,
                            ),
                        ).model_dump(mode="json"),
                    )
                    continue

                lease_requests = _parse_lease_requests(request_payload)
                if sum(request.count for request in lease_requests) > 8:
                    raise ValueError("too many salt leases requested")
                for lease_request in lease_requests:
                    _validate_purpose(scope=scope, request=lease_request)
                frames = [
                    salt_leases.wrap(
                        lease=salt_leases.issue(
                            session_id=session.session_id,
                            scope=scope,
                            purpose=lease_request.purpose,
                            profile=lease_request.profile,
                        ),
                        key_material=session.key_material,
                        context_seed=session.context_seed,
                    )
                    for lease_request in lease_requests
                    for _ in range(lease_request.count)
                ]
                await websocket.send_json(
                    SaltFrameResponse(
                        frames=[
                            SaltFrameRequest(
                                session_id=frame.session_id,
                                wrap_salt=frame.wrap_salt,
                                nonce=frame.nonce,
                                ciphertext=frame.ciphertext,
                            )
                            for frame in frames
                        ],
                    ).model_dump(mode="json"),
                )
            except TimeoutError:
                await websocket.close(code=1001)
                return
            except (
                EncryptionSessionError,
                EncryptionSaltError,
                ValidationError,
                ValueError,
            ):
                await websocket.close(code=1008)
                return
    except WebSocketDisconnect:
        return


def _normalize_salt_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "kind" not in payload:
        return {"kind": "salt_request", **payload}
    return payload


def _parse_lease_requests(payload: dict[str, Any]) -> list[SaltLeaseRequestPayload]:
    normalized = _normalize_salt_request_payload(payload)
    if normalized.get("kind") == "salt_batch_request":
        batch = SaltLeaseBatchRequestPayload.model_validate(normalized)
        return batch.items
    return [SaltLeaseRequestPayload.model_validate(normalized)]


def _validate_purpose(
    *,
    scope: EncryptionSessionScope,
    request: SaltLeaseRequestPayload,
) -> None:
    if request.purpose in {"request", "response"} and request.profile is None:
        raise ValueError("profile is required for request and response salts")
    if request.purpose == "login_capsule":
        if scope != "admin" or request.profile != EncryptionProfile.SENSITIVE:
            raise ValueError("login capsule salts are admin sensitive only")
    if request.purpose == "esid" and request.profile is not None:
        raise ValueError("esid salt must not bind a profile")
