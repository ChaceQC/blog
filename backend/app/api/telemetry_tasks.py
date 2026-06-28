from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from app.providers.telemetry import TelemetryService


def record_task_completed(
    telemetry: TelemetryService,
    *,
    task_name: str,
    outcome: str,
    duration_ms: float,
    deleted_rows: dict[str, int] | None = None,
    friend_link_counts: dict[str, int] | None = None,
) -> None:
    tags = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "component": "tasks",
        "scope": "system",
        "task_name": task_name,
        "outcome": outcome,
    }
    telemetry.record_metric(
        name="blog.task.completed.count",
        value=1,
        unit="count",
        type="counter",
        tags=tags,
        payload={"duration_ms": duration_ms},
    )
    if deleted_rows:
        for table, count in deleted_rows.items():
            telemetry.record_metric(
                name="blog.task.deleted.rows",
                value=count,
                unit="count",
                type="gauge",
                tags={
                    "environment": telemetry.environment,
                    "version": telemetry.version,
                    "component": "tasks",
                    "scope": "system",
                    "task_name": task_name,
                    "table": table,
                },
            )
    if friend_link_counts:
        for item_outcome, count in friend_link_counts.items():
            telemetry.record_metric(
                name="blog.friend_link.health.count",
                value=count,
                unit="count",
                type="gauge",
                tags={
                    "environment": telemetry.environment,
                    "version": telemetry.version,
                    "component": "tasks",
                    "scope": "system",
                    "outcome": item_outcome,
                },
            )
    event_payload: dict[str, object] = {
        "environment": telemetry.environment,
        "version": telemetry.version,
        "task_name": task_name,
        "outcome": outcome,
        "duration_ms": duration_ms,
    }
    if deleted_rows:
        event_payload["deleted_count"] = sum(
            count for count in deleted_rows.values() if count > 0
        )
        event_payload["deleted_rows"] = dict(deleted_rows)
    if friend_link_counts:
        event_payload["healthy_count"] = friend_link_counts.get("healthy", 0)
        event_payload["unhealthy_count"] = friend_link_counts.get("unhealthy", 0)
        event_payload["skipped_count"] = friend_link_counts.get("skipped", 0)
        event_payload["friend_link_counts"] = dict(friend_link_counts)
    telemetry.record_event(type="blog.task.completed", payload=event_payload)
    telemetry.record_log(
        level="info",
        message="Maintenance task completed",
        logger="blog.tasks",
        attributes={"task_name": task_name, "outcome": outcome},
        payload={
            "duration_ms": duration_ms,
            **(deleted_rows or {}),
            **(friend_link_counts or {}),
        },
    )
    telemetry.record_span(
        trace_id=uuid4().hex,
        span_id=uuid4().hex[:16],
        name=f"task {task_name}",
        start_time=datetime.fromtimestamp(
            time.time() - duration_ms / 1000,
            tz=UTC,
        ),
        end_time=datetime.now(UTC),
        duration_ms=duration_ms,
        status_code=outcome,
        source="blog-maintenance",
        attributes={"task_name": task_name, "outcome": outcome},
    )
