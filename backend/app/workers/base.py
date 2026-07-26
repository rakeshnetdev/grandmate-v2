"""Worker scaffold.

Phase 1 establishes the job contract; the queue backend is chosen in Phase 3 when there
is a real workload. Defining the contract first means Phase 3 swaps in a broker rather
than inventing a shape under delivery pressure.

The important property is **idempotency**. Analysis jobs will be retried — on worker
crash, on broker redelivery, on a user clicking twice — and a retried job must not
produce a duplicate row or a second charge against an API budget. Every job therefore
carries an ``idempotency_key`` and every handler is expected to be safe to run twice with
the same key.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


class JobStatus(StrEnum):
    """Lifecycle of a background job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    # Distinct from FAILED: the job ran, found its work already done, and stopped.
    SKIPPED = "skipped"


class JobContext(BaseModel):
    """Metadata carried by every job execution.

    ``idempotency_key`` is the deduplication identity. Two enqueues with the same key
    refer to the same unit of work, whatever the ``job_id``.
    """

    job_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    idempotency_key: str
    attempt: int = 1
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobResult(BaseModel):
    """Outcome of a job execution."""

    status: JobStatus
    detail: str | None = None
    # Structured failure context for debugging. Never contains secrets.
    error: dict[str, Any] | None = None


PayloadT = TypeVar("PayloadT", bound=BaseModel)


class Job(ABC, Generic[PayloadT]):
    """Base class for background jobs.

    Subclasses implement :meth:`handle`. The :meth:`run` wrapper adds logging and turns
    an unexpected exception into a structured ``JobResult`` rather than letting it escape
    into the worker loop, so one bad job cannot take down a worker process.
    """

    name: str

    @abstractmethod
    async def handle(self, payload: PayloadT, context: JobContext) -> JobResult:
        """Do the work. Must be safe to execute twice with the same idempotency key."""

    async def run(self, payload: PayloadT, context: JobContext) -> JobResult:
        """Execute with logging and error containment."""
        log = logger.bind(
            job=self.name,
            job_id=str(context.job_id),
            idempotency_key=context.idempotency_key,
            attempt=context.attempt,
        )
        log.info("job_started")
        try:
            result = await self.handle(payload, context)
        except Exception as exc:
            log.exception("job_failed")
            return JobResult(
                status=JobStatus.FAILED,
                detail=str(exc),
                error={"type": type(exc).__name__},
            )
        log.info("job_finished", status=result.status)
        return result


__all__ = ["Job", "JobContext", "JobResult", "JobStatus"]
