"""ARQ jobs for synchronizing calculated CBT results to Weave Cloud."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.database import async_session_factory
from app.domains.results.sync_service import result_sync_service

logger = logging.getLogger(__name__)


async def sync_exam_results(
    _ctx: dict,
    exam_id: str,
) -> None:
    """Synchronize all currently pending result batches for one examination.

    ResultSyncService owns claiming results, durable batch creation,
    synchronization state transitions, Weave communication, uncertain-batch
    retries, and transaction boundaries. This ARQ job only orchestrates work.
    """

    try:
        parsed_exam_id = UUID(exam_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "sync_exam_results received an invalid exam ID"
        ) from exc

    logger.info(
        "Starting result synchronization for exam %s",
        parsed_exam_id,
    )

    batches_processed = 0

    try:
        async with async_session_factory() as db:
            while True:
                response = await result_sync_service.sync_next_batch(
                    db,
                    exam_id=parsed_exam_id,
                )

                if response is None:
                    break

                batches_processed += 1

                logger.info(
                    (
                        "Synchronized result batch %s for exam %s: "
                        "received=%s applied=%s unchanged=%s rejected=%s"
                    ),
                    response.batch_id,
                    parsed_exam_id,
                    response.received,
                    response.applied,
                    response.unchanged,
                    response.rejected,
                )

    except Exception:
        logger.exception(
            "Result synchronization job failed for exam %s",
            parsed_exam_id,
        )
        raise

    logger.info(
        "Result synchronization completed for exam %s; batches=%s",
        parsed_exam_id,
        batches_processed,
    )
