"""ARQ worker configuration for Weave CBT background jobs."""

from __future__ import annotations

import logging

from arq import cron

from app.core.database import engine
from app.integrations.weave.client import weave_client
from app.workers.broker import arq_redis_settings
from app.workers.candidates import prepare_exam_roster
from app.workers.maintenance import recover_background_work
from app.workers.results import sync_exam_results


logger = logging.getLogger(__name__)


async def on_startup(_ctx: dict) -> None:
    """Initialize worker-process resources."""

    logger.info("Weave CBT background worker started")


async def on_shutdown(_ctx: dict) -> None:
    """Cleanly release process-local resources owned by the worker."""

    await weave_client.close()
    await engine.dispose()

    logger.info("Weave CBT background worker stopped")


class WorkerSettings:
    """ARQ configuration for the Weave CBT background worker."""

    redis_settings = arq_redis_settings

    functions = [
        prepare_exam_roster,
        sync_exam_results,
    ]

    # Run maintenance every two minutes. Starting with an immediate sweep lets
    # a restarted worker reconstruct jobs missed while Redis/ARQ was offline.
    cron_jobs = [
        cron(
            coroutine=recover_background_work,
            minute=set(range(0, 60, 2)),
            second=0,
            run_at_startup=True,
            unique=True,
        )
    ]

    # Maximum number of async jobs this worker process may run concurrently.
    max_jobs = 10

    # Roster generation and large result synchronization may legitimately take
    # longer than ordinary request work. ARQ measures this value in seconds.
    job_timeout = 30 * 60

    # Domain state and PostgreSQL idempotency make duplicate execution safe.
    max_tries = 5

    # Keep completed ARQ result metadata briefly for operational inspection.
    keep_result = 60

    on_startup = on_startup
    on_shutdown = on_shutdown
