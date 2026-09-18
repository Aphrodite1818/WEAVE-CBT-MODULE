import os
import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.workers.producer import ArqProducer, durable_exam_job_id  # noqa: E402


class ArqProducerDeduplicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_shot_exam_job_uses_deterministic_job_id(self):
        exam_id = str(uuid4())
        redis = AsyncMock()
        redis.enqueue_job.return_value = object()
        producer = ArqProducer()
        producer._redis = redis

        queued = await producer.enqueue("finalize_exam_close", exam_id)

        self.assertTrue(queued)
        redis.enqueue_job.assert_awaited_once_with(
            "finalize_exam_close",
            exam_id,
            _job_id=f"weave-cbt:finalize_exam_close:{exam_id}",
        )

    async def test_existing_deterministic_job_counts_as_scheduled(self):
        exam_id = str(uuid4())
        redis = AsyncMock()
        redis.enqueue_job.return_value = None
        producer = ArqProducer()
        producer._redis = redis

        queued = await producer.enqueue("sync_exam_results", exam_id)

        self.assertTrue(queued)

    async def test_repeatable_completion_evaluation_is_not_deduplicated(self):
        exam_id = str(uuid4())
        redis = AsyncMock()
        redis.enqueue_job.return_value = None
        producer = ArqProducer()
        producer._redis = redis

        queued = await producer.enqueue("evaluate_exam_completion", exam_id)

        self.assertFalse(queued)
        redis.enqueue_job.assert_awaited_once_with(
            "evaluate_exam_completion",
            exam_id,
        )
        self.assertIsNone(durable_exam_job_id("evaluate_exam_completion", exam_id))


if __name__ == "__main__":
    unittest.main()
