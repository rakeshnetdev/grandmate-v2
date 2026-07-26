"""Worker contract tests.

Phase 1 has no real jobs, so these validate the base contract using a stub. The property
that matters is error containment: one bad job must not take down a worker process.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.workers.base import Job, JobContext, JobResult, JobStatus


class _Payload(BaseModel):
    value: int


class _EchoJob(Job[_Payload]):
    name = "echo"

    async def handle(self, payload: _Payload, context: JobContext) -> JobResult:
        return JobResult(status=JobStatus.COMPLETED, detail=str(payload.value))


class _ExplodingJob(Job[_Payload]):
    name = "exploding"

    async def handle(self, payload: _Payload, context: JobContext) -> JobResult:
        raise ValueError("boom")


async def test_successful_job_returns_completed() -> None:
    result = await _EchoJob().run(_Payload(value=7), JobContext(idempotency_key="k-1"))

    assert result.status is JobStatus.COMPLETED
    assert result.detail == "7"


async def test_failing_job_is_contained_not_raised() -> None:
    """An exception becomes a structured result rather than escaping the worker loop."""
    result = await _ExplodingJob().run(_Payload(value=1), JobContext(idempotency_key="k-2"))

    assert result.status is JobStatus.FAILED
    assert result.error == {"type": "ValueError"}
    assert result.detail == "boom"


def test_job_context_generates_distinct_ids_but_keeps_the_idempotency_key() -> None:
    """Retries get a new job_id; the idempotency key is what identifies the work."""
    first = JobContext(idempotency_key="same-key")
    second = JobContext(idempotency_key="same-key", attempt=2)

    assert first.job_id != second.job_id
    assert first.idempotency_key == second.idempotency_key
    assert second.attempt == 2
