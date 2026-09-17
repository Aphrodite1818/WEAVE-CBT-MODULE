"""FastAPI-side ARQ producer infrastructure."""

from __future__ import annotations

import logging
from typing import Any

from arq.connections import ArqRedis
from redis.exceptions import RedisError

from app.workers.broker import create_arq_pool


logger = logging.getLogger(__name__)


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
        """Attempt to enqueue one ARQ job.

        False means the job was not queued. Callers should log that condition
        but should not roll back already-committed PostgreSQL state; the
        maintenance sweep can reconstruct durable work later.
        """

        redis = self._redis

        if redis is None:
            logger.warning(
                "Could not enqueue ARQ job %s because the producer is unavailable",
                function_name,
            )
            return False

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
