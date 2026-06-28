from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from app.api.telemetry import record_task_completed
from app.core.config import get_settings
from app.providers.telemetry import TelemetryService, create_telemetry_service


@dataclass
class TaskTelemetryReporter:
    service: TelemetryService
    started_at: float

    def finish(
        self,
        *,
        task_name: str,
        outcome: str,
        deleted_rows: dict[str, int] | None = None,
        friend_link_counts: dict[str, int] | None = None,
    ) -> None:
        record_task_completed(
            self.service,
            task_name=task_name,
            outcome=outcome,
            duration_ms=(perf_counter() - self.started_at) * 1000,
            deleted_rows=deleted_rows,
            friend_link_counts=friend_link_counts,
        )
        self.service.stop()


def start_task_telemetry() -> TaskTelemetryReporter:
    return TaskTelemetryReporter(
        service=create_telemetry_service(get_settings()),
        started_at=perf_counter(),
    )


def record_deployment_finished(
    *,
    status: str,
    duration_seconds: float | None = None,
    git_sha: str | None = None,
) -> None:
    settings = get_settings()
    service = create_telemetry_service(settings)
    payload: dict[str, object] = {
        "version": settings.version,
        "environment": settings.environment,
        "status": status,
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = duration_seconds
    if git_sha:
        payload["git_sha"] = git_sha
    service.record_event(
        type="blog.deployment.finished",
        source="blog-deploy",
        payload=payload,
    )
    service.stop()
