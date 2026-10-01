from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from pydantic import SecretStr

from app.domains.auth.cloud_access import get_or_repair_weave_actor_access_token
from app.domains.auth.service import LocalAuthService, LocalSessionAuthenticationError
from app.integrations.weave.auth_schemas import WeaveActorTokenPair
from app.integrations.weave.exceptions import (
    WeaveRequestRejectedError,
    WeaveUnavailableError,
)


@asynccontextmanager
async def _unlocked(_session_id):
    yield


class CloudActorAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_cloud_access_token_returns_without_rotation(self):
        db = AsyncMock()
        session_id = uuid4()

        with patch.object(
            LocalAuthService,
            "get_weave_actor_access_token",
            new=AsyncMock(return_value="current-actor-token"),
        ) as current_token:
            result = await get_or_repair_weave_actor_access_token(
                db,
                session_id=session_id,
            )

        self.assertEqual(result, "current-actor-token")
        current_token.assert_awaited_once_with(db, session_id=session_id)

    async def test_expired_cloud_access_repairs_with_persisted_operation_id(self):
        db = AsyncMock()
        session_id = uuid4()
        operation_id = uuid4()
        token_pair = WeaveActorTokenPair(
            access_token=SecretStr("new-actor-access"),
            access_token_expires_at=datetime.now(UTC) + timedelta(minutes=20),
            refresh_token=SecretStr("new-actor-refresh"),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(hours=6),
        )
        installation = SimpleNamespace(
            server_credential=SecretStr("server-secret"),
        )

        with (
            patch.object(
                LocalAuthService,
                "get_weave_actor_access_token",
                new=AsyncMock(
                    side_effect=[
                        LocalSessionAuthenticationError("expired"),
                        LocalSessionAuthenticationError("expired"),
                    ]
                ),
            ),
            patch(
                "app.domains.auth.cloud_access.staff_refresh_lock",
                side_effect=_unlocked,
            ),
            patch(
                "app.domains.auth.cloud_access._prepare_cloud_repair",
                new=AsyncMock(return_value=(operation_id, "old-cloud-refresh")),
            ),
            patch(
                "app.domains.auth.cloud_access.node_identity_store.load",
                return_value=installation,
            ),
            patch(
                "app.domains.auth.cloud_access.weave_auth_gateway.refresh_staff_authorization",
                new=AsyncMock(return_value=token_pair),
            ) as cloud_refresh,
            patch(
                "app.domains.auth.cloud_access._complete_cloud_repair",
                new=AsyncMock(return_value="new-actor-access"),
            ) as complete,
        ):
            result = await get_or_repair_weave_actor_access_token(
                db,
                session_id=session_id,
            )

        self.assertEqual(result, "new-actor-access")
        cloud_refresh.assert_awaited_once_with(
            refresh_token="old-cloud-refresh",
            idempotency_key=operation_id,
            server_credential=installation.server_credential,
        )
        complete.assert_awaited_once_with(
            db,
            session_id=session_id,
            operation_id=operation_id,
            token_pair=token_pair,
        )

    async def test_network_failure_marks_repair_degraded_and_preserves_retry(self):
        db = AsyncMock()
        session_id = uuid4()
        operation_id = uuid4()
        installation = SimpleNamespace(
            server_credential=SecretStr("server-secret"),
        )

        with (
            patch.object(
                LocalAuthService,
                "get_weave_actor_access_token",
                new=AsyncMock(
                    side_effect=LocalSessionAuthenticationError("expired")
                ),
            ),
            patch(
                "app.domains.auth.cloud_access.staff_refresh_lock",
                side_effect=_unlocked,
            ),
            patch(
                "app.domains.auth.cloud_access._prepare_cloud_repair",
                new=AsyncMock(return_value=(operation_id, "old-cloud-refresh")),
            ),
            patch(
                "app.domains.auth.cloud_access.node_identity_store.load",
                return_value=installation,
            ),
            patch(
                "app.domains.auth.cloud_access.weave_auth_gateway.refresh_staff_authorization",
                new=AsyncMock(side_effect=WeaveUnavailableError("offline")),
            ),
            patch(
                "app.domains.auth.cloud_access._mark_cloud_repair_degraded",
                new=AsyncMock(),
            ) as mark_degraded,
        ):
            with self.assertRaises(WeaveUnavailableError):
                await get_or_repair_weave_actor_access_token(
                    db,
                    session_id=session_id,
                )

        mark_degraded.assert_awaited_once_with(
            db,
            session_id=session_id,
            operation_id=operation_id,
        )

    async def test_terminal_weave_rejection_revokes_local_session(self):
        db = AsyncMock()
        session_id = uuid4()
        operation_id = uuid4()
        installation = SimpleNamespace(
            server_credential=SecretStr("server-secret"),
        )

        with (
            patch.object(
                LocalAuthService,
                "get_weave_actor_access_token",
                new=AsyncMock(
                    side_effect=LocalSessionAuthenticationError("expired")
                ),
            ),
            patch(
                "app.domains.auth.cloud_access.staff_refresh_lock",
                side_effect=_unlocked,
            ),
            patch(
                "app.domains.auth.cloud_access._prepare_cloud_repair",
                new=AsyncMock(return_value=(operation_id, "old-cloud-refresh")),
            ),
            patch(
                "app.domains.auth.cloud_access.node_identity_store.load",
                return_value=installation,
            ),
            patch(
                "app.domains.auth.cloud_access.weave_auth_gateway.refresh_staff_authorization",
                new=AsyncMock(
                    side_effect=WeaveRequestRejectedError(
                        status_code=401,
                        detail="Actor authorization revoked.",
                    )
                ),
            ),
            patch(
                "app.domains.auth.cloud_access._revoke_cloud_session",
                new=AsyncMock(),
            ) as revoke,
        ):
            with self.assertRaises(WeaveRequestRejectedError):
                await get_or_repair_weave_actor_access_token(
                    db,
                    session_id=session_id,
                )

        revoke.assert_awaited_once()
        self.assertEqual(revoke.await_args.kwargs["session_id"], session_id)


if __name__ == "__main__":
    unittest.main()
