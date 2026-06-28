from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any, Literal
from urllib import error
from urllib import request as urllib_request
from urllib.parse import urlsplit, urlunsplit

from app.core.config import Settings

TelemetryKind = Literal["metrics", "logs", "events", "traces"]
TelemetryPayload = dict[str, Any]

_LOGGER = logging.getLogger(__name__)
_MAX_BATCH_ITEMS = 100
_MAX_PAYLOAD_BYTES = 256 * 1024
_MAX_EVENT_PAYLOAD_BYTES = 64 * 1024
_QUEUE_MAX_SIZE = 5_000
_FLUSH_INTERVAL_SECONDS = 1.0
_DEFAULT_TIMEOUT_SECONDS = 5.0
_DEFAULT_RETRY_ATTEMPTS = 3
_METRIC_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EVENT_TYPE_PATTERN = _METRIC_NAME_PATTERN
_LOG_LEVEL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class _QueuedItem:
    kind: TelemetryKind
    payload: TelemetryPayload


class TelemetryService:
    def __init__(
        self,
        *,
        endpoint: str | None,
        api_key: str | None,
        enabled: bool,
        source: str,
        environment: str,
        version: str,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        retry_attempts: int = _DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        self.endpoint = _normalize_endpoint(endpoint)
        self.api_key = _normalize_text(api_key, 256)
        self.enabled = bool(enabled and self.endpoint and self.api_key)
        self.source = _normalize_text(source, 128) or "blog-backend"
        self.environment = _normalize_text(environment, 32) or "development"
        self.version = _normalize_text(version, 32) or "0.0.0"
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.retry_attempts = max(1, int(retry_attempts))
        self._queue: queue.Queue[_QueuedItem | object] = queue.Queue(
            maxsize=_QUEUE_MAX_SIZE,
        )
        self._worker_thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._disabled_permanently = False

    @classmethod
    def disabled(
        cls,
        *,
        source: str = "blog-backend",
        environment: str = "development",
        version: str = "0.0.0",
    ) -> TelemetryService:
        return cls(
            endpoint=None,
            api_key=None,
            enabled=False,
            source=source,
            environment=environment,
            version=version,
        )

    def start(self) -> None:
        if not self.enabled or self._disabled_permanently:
            return
        with self._state_lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._run_worker,
                name="blog-telemetry",
                daemon=True,
            )
            self._worker_thread.start()

    def stop(self) -> None:
        thread = self._worker_thread
        if not self.enabled or self._disabled_permanently or thread is None:
            return
        self._stop_event.set()
        try:
            self._queue.put_nowait(_STOP)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(_STOP)
            except queue.Empty:
                pass
            except queue.Full:
                _LOGGER.debug("telemetry queue stayed full during shutdown")
        thread.join(timeout=self.timeout_seconds * 2)
        self._worker_thread = None
        self._stop_event.clear()

    def record_metric(
        self,
        *,
        name: str,
        value: int | float,
        timestamp: datetime | None = None,
        unit: str | None = None,
        type: str | None = None,
        source: str | None = None,
        tags: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        if not self._ready:
            return
        if not _METRIC_NAME_PATTERN.fullmatch(name):
            return
        if isinstance(value, bool) or not isfinite(float(value)):
            return
        metric: TelemetryPayload = {
            "name": name,
            "value": float(value) if isinstance(value, float) else int(value),
            "source": _normalize_text(source, 128) or self.source,
        }
        metric["timestamp"] = _to_timestamp(timestamp or datetime.now(UTC))
        if unit is not None:
            unit_value = _normalize_text(unit, 32)
            if unit_value:
                metric["unit"] = unit_value
        if type is not None:
            type_value = _normalize_text(type, 32)
            if type_value:
                metric["type"] = type_value
        normalized_tags = _normalize_object_map(tags)
        if normalized_tags:
            metric["tags"] = normalized_tags
        normalized_payload = _normalize_object_map(payload)
        if normalized_payload:
            metric["payload"] = normalized_payload
        self._enqueue("metrics", metric)

    def record_event(
        self,
        *,
        type: str,
        payload: dict[str, object],
        timestamp: datetime | None = None,
        source: str | None = None,
    ) -> None:
        if not self._ready or not _EVENT_TYPE_PATTERN.fullmatch(type):
            return
        event: TelemetryPayload = {
            "type": type,
            "payload": _normalize_object_map(payload) or {},
            "source": _normalize_text(source, 128) or self.source,
            "timestamp": _to_timestamp(timestamp or datetime.now(UTC)),
        }
        if _event_payload_size(event) > _MAX_EVENT_PAYLOAD_BYTES:
            _LOGGER.debug("dropping oversized telemetry event payload: %s", type)
            return
        self._enqueue("events", event)

    def record_log(
        self,
        *,
        level: str,
        message: str,
        timestamp: datetime | None = None,
        logger: str | None = None,
        source: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        attributes: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        if not self._ready or not _LOG_LEVEL_PATTERN.fullmatch(level):
            return
        cleaned_message = _normalize_text(message, 8_192)
        if not cleaned_message:
            return
        log_item: TelemetryPayload = {
            "level": level,
            "message": cleaned_message,
            "source": _normalize_text(source, 128) or self.source,
            "timestamp": _to_timestamp(timestamp or datetime.now(UTC)),
        }
        if logger is not None:
            logger_value = _normalize_text(logger, 128)
            if logger_value:
                log_item["logger"] = logger_value
        if trace_id is not None:
            trace_id_value = _normalize_text(trace_id, 128)
            if trace_id_value:
                log_item["trace_id"] = trace_id_value
        if span_id is not None:
            span_id_value = _normalize_text(span_id, 128)
            if span_id_value:
                log_item["span_id"] = span_id_value
        normalized_attributes = _normalize_object_map(attributes)
        if normalized_attributes:
            log_item["attributes"] = normalized_attributes
        normalized_payload = _normalize_object_map(payload)
        if normalized_payload:
            log_item["payload"] = normalized_payload
        self._enqueue("logs", log_item)

    def record_span(
        self,
        *,
        trace_id: str,
        span_id: str,
        name: str,
        start_time: datetime,
        end_time: datetime | None = None,
        duration_ms: int | float | None = None,
        status_code: str | None = None,
        source: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        if not self._ready:
            return
        trace_id_value = _normalize_text(trace_id, 128)
        span_id_value = _normalize_text(span_id, 128)
        name_value = _normalize_text(name, 256)
        if not trace_id_value or not span_id_value or not name_value:
            return
        span: TelemetryPayload = {
            "trace_id": trace_id_value,
            "span_id": span_id_value,
            "name": name_value,
            "start_time": _to_timestamp(start_time),
            "source": _normalize_text(source, 128) or self.source,
        }
        if parent_span_id is not None:
            parent_span_id_value = _normalize_text(parent_span_id, 128)
            if parent_span_id_value:
                span["parent_span_id"] = parent_span_id_value
        if end_time is not None:
            span["end_time"] = _to_timestamp(end_time)
        if (
            duration_ms is not None
            and isfinite(float(duration_ms))
            and duration_ms >= 0
        ):
            span["duration_ms"] = float(duration_ms)
        if status_code is not None:
            status_value = _normalize_text(status_code, 32)
            if status_value:
                span["status_code"] = status_value
        normalized_attributes = _normalize_object_map(attributes)
        if normalized_attributes:
            span["attributes"] = normalized_attributes
        normalized_payload = _normalize_object_map(payload)
        if normalized_payload:
            span["payload"] = normalized_payload
        self._enqueue("traces", span)

    def request_tags(
        self,
        *,
        component: str,
        scope: str,
        route: str,
        method: str,
        status_code: int,
        outcome: str,
    ) -> dict[str, str]:
        return {
            "environment": self.environment,
            "version": self.version,
            "component": _normalize_text(component, 128) or "system",
            "scope": _normalize_text(scope, 32) or "system",
            "route": _normalize_text(route, 500) or "/",
            "method": _normalize_text(method.upper(), 16) or "GET",
            "status_code": str(int(status_code)),
            "status_family": f"{int(status_code) // 100}xx",
            "outcome": _normalize_text(outcome, 32) or "ok",
        }

    def _enqueue(self, kind: TelemetryKind, payload: TelemetryPayload) -> None:
        if not self._ready:
            return
        self.start()
        try:
            self._queue.put_nowait(_QueuedItem(kind=kind, payload=payload))
        except queue.Full:
            _LOGGER.debug("telemetry queue is full; dropping %s payload", kind)

    def _run_worker(self) -> None:
        buffers: dict[TelemetryKind, list[TelemetryPayload]] = {
            "metrics": [],
            "logs": [],
            "events": [],
            "traces": [],
        }
        last_flush = time.monotonic()
        while True:
            timeout = max(
                0.1,
                _FLUSH_INTERVAL_SECONDS - (time.monotonic() - last_flush),
            )
            try:
                item = self._queue.get(timeout=timeout)
            except queue.Empty:
                self._flush_buffers(buffers)
                last_flush = time.monotonic()
                if self._stop_event.is_set():
                    break
                continue

            if item is _STOP:
                self._flush_buffers(buffers)
                break

            if not isinstance(item, _QueuedItem):
                continue

            buffers[item.kind].append(item.payload)
            if len(buffers[item.kind]) >= _MAX_BATCH_ITEMS:
                self._flush_kind(item.kind, buffers[item.kind])
                buffers[item.kind].clear()
                last_flush = time.monotonic()

        self._flush_buffers(buffers)

    def _flush_buffers(
        self,
        buffers: dict[TelemetryKind, list[TelemetryPayload]],
    ) -> None:
        for kind, items in buffers.items():
            if not items:
                continue
            self._flush_kind(kind, items)
            items.clear()

    def _flush_kind(self, kind: TelemetryKind, items: list[TelemetryPayload]) -> None:
        batches = _chunk_payloads(kind, items)
        for batch in batches:
            self._send_with_retry(kind=kind, payload=batch)

    def _send_with_retry(
        self,
        *,
        kind: TelemetryKind,
        payload: TelemetryPayload,
    ) -> None:
        attempt = 0
        while attempt < self.retry_attempts and not self._disabled_permanently:
            attempt += 1
            try:
                self._send_once(kind=kind, payload=payload)
                return
            except _TelemetryPermanentError as exc:
                _LOGGER.warning("telemetry send failed permanently: %s", exc)
                self._disabled_permanently = True
                return
            except _TelemetryRetryableError as exc:
                retry_after = exc.retry_after_seconds or min(
                    8.0,
                    0.5 * (2 ** (attempt - 1)),
                )
                _LOGGER.debug(
                    "telemetry send retryable failure for %s: %s (retry_after=%.2f)",
                    kind,
                    exc,
                    retry_after,
                )
                time.sleep(retry_after)
        _LOGGER.debug("telemetry batch dropped after retries: %s", kind)

    def _send_once(self, *, kind: TelemetryKind, payload: TelemetryPayload) -> None:
        if not self.endpoint or not self.api_key:
            return
        path = {
            "metrics": "metrics",
            "logs": "logs",
            "events": "events",
            "traces": "traces",
        }[kind]
        if (
            kind == "events"
            and "events" in payload
            and isinstance(payload["events"], list)
        ):
            path = "batch"
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        ).encode("utf-8")
        if len(body) > _MAX_PAYLOAD_BYTES:
            raise _TelemetryPermanentError("telemetry payload exceeds size limit")

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-API-Key": self.api_key,
        }
        request = urllib_request.Request(
            _endpoint_url(self.endpoint, path),
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib_request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                if 200 <= getattr(response, "status", 200) < 300:
                    return
                response_status = getattr(response, "status", 0)
                raise _TelemetryPermanentError(
                    f"unexpected telemetry response status: {response_status}",
                )
        except error.HTTPError as exc:
            if exc.code == 401 or exc.code == 403 or exc.code == 422:
                raise _TelemetryPermanentError(
                    f"telemetry rejected payload with HTTP {exc.code}",
                ) from exc
            if exc.code == 429 or 500 <= exc.code < 600:
                raise _TelemetryRetryableError(
                    f"telemetry service returned HTTP {exc.code}",
                    retry_after_seconds=_retry_after_seconds(exc.headers),
                ) from exc
            raise _TelemetryPermanentError(
                f"telemetry service returned HTTP {exc.code}",
            ) from exc
        except error.URLError as exc:
            raise _TelemetryRetryableError(
                f"telemetry request failed: {exc.reason}",
            ) from exc

    @property
    def _ready(self) -> bool:
        return self.enabled and not self._disabled_permanently


class _TelemetryPermanentError(Exception):
    pass


class _TelemetryRetryableError(Exception):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


_STOP = object()


def create_telemetry_service(settings: Settings) -> TelemetryService:
    return TelemetryService(
        endpoint=settings.telemetry_endpoint,
        api_key=settings.telemetry_api_key,
        enabled=settings.telemetry_enabled,
        source="blog-backend",
        environment=settings.environment,
        version=settings.version,
    )


def _chunk_payloads(
    kind: TelemetryKind,
    items: list[TelemetryPayload],
) -> list[TelemetryPayload]:
    if not items:
        return []
    if kind == "events":
        return _chunk_events(items)
    key = {
        "metrics": "metrics",
        "logs": "logs",
        "traces": "spans",
    }[kind]
    return _chunk_envelope(key=key, items=items)


def _chunk_events(items: list[TelemetryPayload]) -> list[TelemetryPayload]:
    safe_items = [
        item for item in items if _event_payload_size(item) <= _MAX_EVENT_PAYLOAD_BYTES
    ]
    if len(safe_items) == 1:
        return [safe_items[0]]
    return _chunk_envelope(key="events", items=safe_items)


def _chunk_envelope(
    *,
    key: str,
    items: list[TelemetryPayload],
) -> list[TelemetryPayload]:
    batches: list[TelemetryPayload] = []
    current: list[TelemetryPayload] = []
    for item in items:
        item_payload = {key: [item]}
        item_size = _payload_size(item_payload)
        if item_size > _MAX_PAYLOAD_BYTES:
            _LOGGER.debug("dropping oversized telemetry item for %s", key)
            continue
        candidate = current + [item]
        payload = {key: candidate}
        size = _payload_size(payload)
        if size <= _MAX_PAYLOAD_BYTES and len(candidate) <= _MAX_BATCH_ITEMS:
            current = candidate
            continue
        batches.append({key: current})
        current = [item]
    if current:
        batches.append({key: current})
    return batches


def _payload_size(payload: TelemetryPayload) -> int:
    return len(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        ).encode("utf-8"),
    )


def _event_payload_size(event: TelemetryPayload) -> int:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return 0
    return _payload_size(payload)


def _endpoint_url(endpoint: str, path: str) -> str:
    parsed = urlsplit(endpoint)
    base_path = parsed.path.rstrip("/")
    if base_path.endswith("/api/v1/ingest"):
        ingest_base = base_path
    elif base_path.endswith("/api/v1"):
        ingest_base = f"{base_path}/ingest"
    elif base_path:
        ingest_base = f"{base_path}/api/v1/ingest"
    else:
        ingest_base = "/api/v1/ingest"
    target = f"{ingest_base}/{path.lstrip('/')}"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, target, parsed.query, parsed.fragment),
    )


def _retry_after_seconds(headers: Any) -> float | None:
    if headers is None:
        return None
    raw_value = headers.get("Retry-After")
    if raw_value is None:
        return None
    try:
        return max(0.5, float(raw_value))
    except (TypeError, ValueError):
        return None


def _normalize_endpoint(value: str | None) -> str | None:
    cleaned = _normalize_text(value, 2048)
    if cleaned is None:
        return None
    return cleaned.rstrip("/")


def _normalize_text(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:max_length]


def _normalize_object_map(value: dict[str, object] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        key_text = _normalize_text(str(key), 128)
        if not key_text:
            continue
        normalized = _normalize_json_value(item)
        if normalized is not None:
            cleaned[key_text] = normalized
    return cleaned or None


def _normalize_json_value(value: object) -> Any | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, str):
        return value[:8_192]
    if isinstance(value, datetime):
        return _to_timestamp(value)
    if isinstance(value, dict):
        return _normalize_object_map(value)
    if isinstance(value, (list, tuple)):
        items = [_normalize_json_value(item) for item in value]
        return [item for item in items if item is not None]
    if isinstance(value, set):
        items = [_normalize_json_value(item) for item in sorted(value, key=str)]
        return [item for item in items if item is not None]
    return _normalize_text(str(value), 8_192)


def _to_timestamp(value: datetime) -> str:
    current = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_default(value: object) -> Any:
    normalized = _normalize_json_value(value)
    if normalized is not None:
        return normalized
    return str(value)
