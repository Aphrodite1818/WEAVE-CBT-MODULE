"""FastAPI-side ARQ producer infrastructure."""

from __future__ import annotations

import logging
from typing import Any

from arq.connections import ArqRedis
from redis.exceptions import RedisError

from app.workers.broker import create_arq_pool


logger = logging.getLogger(__name__)


# These jobs represent durable, exam-scoped operations whose authoritative
# state lives in PostgreSQL. Multiple API replicas may discover or request the
# same work at nearly the same time, especially during runtime recovery.
#
# A deterministic ARQ job ID prevents duplicate queue entries while one copy is
# already queued/running (or while its short-lived result key is retained).
# `evaluate_exam_completion` is intentionally excluded because it is a
# repeatable evaluation trigger and may need to run again after exam state
# changes.
_UNIQUE_DURABLE_EXAM_JOBS = frozenset(
    {
        "prepare_exam_roster",
        "reconcile_exam_roster",
        "finalize_exam_close",
        "finalize_exam_cancellation",
        "sync_exam_results",
    }
)


def durable_exam_job_id(
    function_name: str,
    *args: Any,
) -> str | None:
    """Return a deterministic ARQ job ID for one-shot exam-scoped work."""

    if function_name not in _UNIQUE_DURABLE_EXAM_JOBS or not args:
        return None

    exam_identity = str(args[0]).strip()
    if not exam_identity:
        return None

    return f"weave-cbt:{function_name}:{exam_identity}"


class ArqProducer:
    """Own the FastAPI process's ARQ connection used to enqueue jobs.

    PostgreSQL remains the durable source of truth. Redis/ARQ is only the
    delivery mechanism, so an enqueue failure must not invalidate business
    state which has already been committed successfully.
    """

    def __init__(self) -> None:
        self._redis: ArqRedis | None = None

    @property
    def is_available(self) -> bool:
        """Report whether this process currently owns an ARQ producer pool."""

        return self._redis is not None

    async def start(self) -> None:
        """Create the process-local ARQ pool without making Redis startup-fatal."""

        if self._redis is not None:
            return

        try:
            self._redis = await create_arq_pool()
        except (RedisError, OSError):
            self._redis = None
            logger.warning(
                "ARQ producer could not connect to Redis during startup; "
                "background work will rely on maintenance recovery",
                exc_info=True,
            )

    async def enqueue(
        self,
        function_name: str,
        *args: Any,
        **job_options: Any,
    ) -> bool:
        """Ensure one ARQ job is queued for the requested durable work.

        For one-shot exam-scoped jobs, this method automatically supplies a
        deterministic ARQ job ID. That makes simultaneous enqueue attempts from
        several FastAPI replicas collapse into one queue entry.

        True means the requested work is queued or an equivalent deterministic
        job already exists. False means queue delivery was unavailable.
        """

        redis = self._redis

        if redis is None:
            logger.warning(
                "Could not enqueue ARQ job %s because the producer is unavailable",
                function_name,
            )
            return False

        if job_options.get("_job_id") is None:
            generated_job_id = durable_exam_job_id(function_name, *args)
            if generated_job_id is not None:
                job_options["_job_id"] = generated_job_id

        requested_job_id = job_options.get("_job_id")

        try:
            job = await redis.enqueue_job(
                function_name,
                *args,
                **job_options,
            )
        except (RedisError, OSError):
            logger.exception(
                "Failed to enqueue ARQ job %s",
                function_name,
            )
            return False

        if job is None:
            if requested_job_id is not None:
                logger.debug(
                    "ARQ job %s is already queued or retained under job ID %s",
                    function_name,
                    requested_job_id,
                )
                return True

            logger.warning(
                "ARQ did not enqueue job %s",
                function_name,
            )
            return False

        return True

    async def close(self) -> None:
        """Close the FastAPI process's ARQ Redis connection."""

        redis = self._redis
        self._redis = None

        if redis is not None:
            await redis.aclose()


arq_producer = ArqProducer()
