"""Shared Arq  queue infrastructure for Weave CBT."""


from __future__ import annotations

from arq import create_pool 
from arq.connections import ArqRedis , RedisSettings

from app.core.settings import settings



arq_redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)


async def create_arq_pool() -> ArqRedis:
    return await create_pool(arq_redis_settings)