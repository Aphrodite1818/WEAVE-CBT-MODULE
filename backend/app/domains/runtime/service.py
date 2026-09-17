"""Crash-aware CBT runtime heartbeat and examination recovery."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text

from app.core.database import async_session_factory
from app.domains.exams.execution_service import ExamExecutionService
from app.domains.runtime.models import CBTRuntimeState
from app.domains.runtime.repository import RuntimeRepository
from app.workers.producer import arq_producer


logger = logging.getLogger(__name__)

RUNTIME_HEARTBEAT_INTERVAL_SECONDS = 5.0
RUNTIME_GAP_SUSPEND_AFTER_SECONDS = 20.0
RUNTIME_STARTUP_ADVISORY_LOCK_KEY = 873_421_945
RUNTIME_GAP_REASON = (
    "CBT server interruption detected. Examination paused automatically to protect "
    "candidate writing time."
)
RUNTIME_SHUTDOWN_EXAM_REASON = (
    "CBT server is shutting down. Examination paused automatically until an "
    "administrator confirms that the server and candidate devices are ready."
)


class RuntimeHeartbeatService:
    """Own one durable PostgreSQL heartbeat for the FastAPI runtime.

    An unclean restart backdates system suspension to the previous runtime's
    last durable heartbeat. Long in-process gaps (database outage, OS sleep,
    event-loop freeze) use the same protection. A graceful server shutdown also
    suspends ACTIVE exams first, so planned restarts cannot silently consume
    candidate writing time.
    """

    def __init__(self) -> None:
        self._runtime_id: UUID | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._last_successful_heartbeat_at: datetime | None = None
        self._last_successful_monotonic: float | None = None

    @property
    def runtime_id(self) -> UUID | None:
        return self._runtime_id

    async def _recover_pending_worker_operations(self) -> None:
        async with async_session_factory() as db:
            closing, cancelling = await ExamExecutionService.list_pending_operation_exam_ids(db)
            await db.rollback()

        for exam_id in closing:
            await arq_producer.enqueue("finalize_exam_close", str(exam_id))
        for exam_id in cancelling:
            await arq_producer.enqueue("finalize_exam_cancellation", str(exam_id))

        if closing or cancelling:
            logger.warning(
                "Recovered %s closing and %s cancelling exam operation(s)",
                len(closing),
                len(cancelling),
            )

    async def _recover_runtime_gap(
        self,
        outage_started_at: datetime,
        *,
        reason: str = RUNTIME_GAP_REASON,
    ) -> None:
        async with async_session_factory() as db:
            suspended = await ExamExecutionService.suspend_active_exams_after_runtime_gap(
                db,
                outage_started_at=outage_started_at,
                reason=reason,
            )
        if suspended:
            logger.warning(
                "Suspended %s active examination(s) after CBT runtime interruption",
                len(suspended),
            )

    async def start(self) -> None:
        if self._task is not None:
            return

        # Recovery intentionally happens before a new runtime row is created.
        # If the process dies halfway through recovery, the next boot sees the
        # same unclean predecessor and safely repeats recovery from the same
        # heartbeat cutoff.
        async with async_session_factory() as db:
            await db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": RUNTIME_STARTUP_ADVISORY_LOCK_KEY},
            )
            previous = await RuntimeRepository.get_latest_runtime_state(db, lock=True)
            previous_gap_at = (
                previous.last_heartbeat_at
                if previous is not None and previous.stopped_at is None
                else None
            )
            await db.commit()

        if previous_gap_at is not None:
            logger.warning(
                "Previous CBT runtime ended uncleanly; recovering from heartbeat %s",
                previous_gap_at.isoformat(),
            )
            await self._recover_runtime_gap(previous_gap_at)

        now = datetime.now(UTC)
        runtime_id = uuid4()
        async with async_session_factory() as db:
            runtime = CBTRuntimeState(
                runtime_id=runtime_id,
                started_at=now,
                last_heartbeat_at=now,
            )
            await RuntimeRepository.add_runtime_state(db, runtime)
            await db.commit()

        self._runtime_id = runtime_id
        self._last_successful_heartbeat_at = now
        self._last_successful_monotonic = time.monotonic()
        self._stop_event = asyncio.Event()

        await self._recover_pending_worker_operations()

        self._task = asyncio.create_task(
            self._run(),
            name="weave-cbt-runtime-heartbeat",
        )
        logger.info("CBT runtime heartbeat started: %s", runtime_id)

    async def _write_heartbeat(self, now: datetime) -> None:
        runtime_id = self._runtime_id
        if runtime_id is None:
            return
        async with async_session_factory() as db:
            runtime = await RuntimeRepository.get_runtime_state_by_id(db, runtime_id, lock=True)
            if runtime is None or runtime.stopped_at is not None:
                await db.rollback()
                raise RuntimeError("Active CBT runtime heartbeat row is unavailable")
            runtime.last_heartbeat_at = now
            await RuntimeRepository.save_runtime_state(db, runtime)
            await db.commit()

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=RUNTIME_HEARTBEAT_INTERVAL_SECONDS,
                )
                continue
            except TimeoutError:
                pass

            now = datetime.now(UTC)
            monotonic_now = time.monotonic()
            last_at = self._last_successful_heartbeat_at
            last_mono = self._last_successful_monotonic
            gap_seconds = monotonic_now - last_mono if last_mono is not None else 0.0

            try:
                if last_at is not None and gap_seconds >= RUNTIME_GAP_SUSPEND_AFTER_SECONDS:
                    # Do not advance the heartbeat before recovery. The previous
                    # durable timestamp is the conservative cutoff protecting
                    # candidate time through the entire unavailable interval.
                    await self._recover_runtime_gap(last_at)
                await self._write_heartbeat(now)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "CBT runtime heartbeat failed; active exams will be protected "
                    "if the gap reaches the recovery threshold"
                )
                continue

            self._last_successful_heartbeat_at = now
            self._last_successful_monotonic = monotonic_now

    async def stop(self, *, reason: str = "graceful_shutdown") -> None:
        task = self._task
        self._task = None
        self._stop_event.set()
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        runtime_id = self._runtime_id
        self._runtime_id = None
        if runtime_id is None:
            return

        now = datetime.now(UTC)
        try:
            # A graceful restart is still downtime to candidates. Pause ACTIVE
            # exams before recording the runtime as cleanly stopped.
            await self._recover_runtime_gap(
                now,
                reason=RUNTIME_SHUTDOWN_EXAM_REASON,
            )

            async with async_session_factory() as db:
                runtime = await RuntimeRepository.get_runtime_state_by_id(db, runtime_id, lock=True)
                if runtime is not None and runtime.stopped_at is None:
                    stopped_at = max(now, runtime.last_heartbeat_at)
                    runtime.last_heartbeat_at = stopped_at
                    runtime.stopped_at = stopped_at
                    runtime.shutdown_reason = reason[:500]
                    await RuntimeRepository.save_runtime_state(db, runtime)
                    await db.commit()
                else:
                    await db.rollback()
        except Exception:
            # If clean shutdown cannot be persisted, the next boot treats the
            # runtime as unclean and repeats conservative exam protection.
            logger.exception("Could not persist clean CBT runtime shutdown")

        logger.info("CBT runtime heartbeat stopped: %s", runtime_id)


runtime_heartbeat_service = RuntimeHeartbeatService()
