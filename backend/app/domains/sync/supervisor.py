"""Singleton WebSocket supervisor for live Weave -> CBT synchronization."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets

from redis.exceptions import RedisError
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.core.database import async_session_factory
from app.core.redis import redis_client
from app.domains.node.exceptions import (
    NodeIdentityNotFoundError,
    NodeIdentityStorageError,
)
from app.domains.node.identity_store import node_identity_store
from app.domains.sync.service import sync_service
from app.integrations.weave.academics import weave_academics_gateway

logger = logging.getLogger(__name__)

SYNC_LEADER_KEY = "weave-cbt:sync:websocket-leader"
SYNC_LEADER_TTL_SECONDS = 30
SYNC_LEADER_RENEW_SECONDS = 10
RECONNECT_MIN_SECONDS = 2
RECONNECT_MAX_SECONDS = 30

_RENEW_LEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""
_RELEASE_LEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class SyncSupervisor:
    """Maintain one live Weave socket across multiple local API processes."""

    def __init__(self) -> None:
        self._stop = asyncio.Event()

    async def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        # Lifespan/test reloads may start the same singleton again after a
        # graceful shutdown. A previous stop must not permanently disable it.
        self._stop.clear()
        backoff = RECONNECT_MIN_SECONDS

        while not self._stop.is_set():
            try:
                identity = node_identity_store.load()
            except NodeIdentityNotFoundError:
                # An unpaired installation is a normal startup state.
                await self._sleep(5)
                continue
            except NodeIdentityStorageError:
                # Corrupt/unreadable identity is serious but must not crash the
                # FastAPI process that still serves the local recovery UI.
                logger.exception("Unable to load persistent CBT installation identity.")
                await self._sleep(15)
                continue

            lease_token = secrets.token_urlsafe(24)
            if not await self._acquire_lease(lease_token):
                await self._sleep(5)
                continue

            try:
                await self._reconcile_once()
                await self._stream(
                    identity.server_credential.get_secret_value(),
                    lease_token,
                )
                backoff = RECONNECT_MIN_SECONDS
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Weave CBT live synchronization supervisor failed.")
                await self._sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)
            finally:
                await self._release_lease(lease_token)

    async def _stream(self, credential: str, lease_token: str) -> None:
        async with connect(
            weave_academics_gateway.stream_url(),
            additional_headers={"Authorization": f"Bearer {credential}"},
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            proxy=None,
        ) as websocket:
            while not self._stop.is_set():
                if not await self._renew_lease(lease_token):
                    logger.warning(
                        "CBT sync WebSocket lease was lost; closing local stream."
                    )
                    return

                try:
                    raw_message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=SYNC_LEADER_RENEW_SECONDS,
                    )
                except TimeoutError:
                    continue
                except ConnectionClosed:
                    return

                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8")
                try:
                    message = json.loads(raw_message)
                except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
                    logger.warning("Ignoring malformed Weave CBT WebSocket frame.")
                    continue
                if not isinstance(message, dict):
                    continue

                message_type = message.get("type")
                if message_type in {"cbt.sync.reconcile", "cbt.sync.change"}:
                    await self._reconcile_once()
                elif (
                    message_type == "connection.ready"
                    and message.get("reconciliation_required") is True
                ):
                    await self._reconcile_once()

    async def _reconcile_once(self) -> None:
        async with async_session_factory() as db:
            await sync_service.reconcile(db)

    @staticmethod
    async def _acquire_lease(token: str) -> bool:
        try:
            return bool(
                await redis_client.set(
                    SYNC_LEADER_KEY,
                    token,
                    nx=True,
                    ex=SYNC_LEADER_TTL_SECONDS,
                )
            )
        except RedisError:
            logger.warning("Redis unavailable; live sync leader lease not acquired.")
            return False

    @staticmethod
    async def _renew_lease(token: str) -> bool:
        try:
            result = await redis_client.eval(
                _RENEW_LEASE_SCRIPT,
                1,
                SYNC_LEADER_KEY,
                token,
                SYNC_LEADER_TTL_SECONDS,
            )
            return bool(result)
        except RedisError:
            return False

    @staticmethod
    async def _release_lease(token: str) -> None:
        try:
            await redis_client.eval(
                _RELEASE_LEASE_SCRIPT,
                1,
                SYNC_LEADER_KEY,
                token,
            )
        except RedisError:
            pass

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            pass


sync_supervisor = SyncSupervisor()
