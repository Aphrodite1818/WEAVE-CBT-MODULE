from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.domains.academics.repository import AcademicRepository  # noqa: E402
from app.domains.auth.repository import AuthRepository  # noqa: E402
from app.domains.auth.service import (  # noqa: E402
    INVALID_LOCAL_STAFF_SESSION,
    LocalAuthService,
    LocalSessionAuthenticationError,
    SYNC_TRUST_REVOKED_REASON,
)


class _AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _db() -> AsyncMock:
    db = AsyncMock()
    db.begin = MagicMock(return_value=_AsyncContext())
    return db


def _teacher_actor():
    account_id = uuid4()
    membership_id = uuid4()
    return SimpleNamespace(
        id=uuid4(),
        weave_actor_id=str(account_id),
        weave_membership_id=str(membership_id),
        role="teacher",
        email="teacher@example.com",
        display_name="Teacher One",
        is_active=True,
        last_weave_revalidated_at=None,
    )


class StaffTrustTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_teacher_projection_deactivates_actor_and_revokes_session(self):
        db = _db()
        actor = _teacher_actor()
        now = datetime.now(UTC)
        session = SimpleNamespace(
            id=uuid4(),
            actor_id=actor.id,
            revoked_at=None,
            revocation_reason=None,
        )
        refresh = SimpleNamespace(
            id=uuid4(),
            session_id=session.id,
            revoked_at=None,
        )

        with (
            patch.object(
                AuthRepository,
                "list_actors",
                new=AsyncMock(return_value=[actor]),
            ),
            patch.object(
                AuthRepository,
                "get_actor_by_id",
                new=AsyncMock(return_value=actor),
            ),
            patch.object(
                AcademicRepository,
                "get_teacher_by_membership_id",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                AuthRepository,
                "save_actor",
                new=AsyncMock(return_value=actor),
            ) as save_actor,
            patch.object(
                AuthRepository,
                "list_sessions_for_actor",
                new=AsyncMock(return_value=[session]),
            ),
            patch.object(
                AuthRepository,
                "save_session",
                new=AsyncMock(return_value=session),
            ),
            patch.object(
                AuthRepository,
                "list_refresh_tokens_for_session",
                new=AsyncMock(return_value=[refresh]),
            ),
            patch.object(
                AuthRepository,
                "save_refresh_tokens",
                new=AsyncMock(return_value=[refresh]),
            ),
        ):
            await LocalAuthService.reconcile_synced_staff_trust(
                db,
                revalidated_at=now,
            )

        self.assertFalse(actor.is_active)
        self.assertEqual(actor.last_weave_revalidated_at, now)
        self.assertEqual(session.revoked_at, now)
        self.assertEqual(session.revocation_reason, SYNC_TRUST_REVOKED_REASON)
        self.assertEqual(refresh.revoked_at, now)
        save_actor.assert_awaited()

    async def test_live_teacher_projection_keeps_existing_local_trust(self):
        db = _db()
        actor = _teacher_actor()
        now = datetime.now(UTC)
        teacher = SimpleNamespace(
            id=uuid4(),
            teacher_account_id=uuid4(),
            status="active",
        )
        teacher.id = uuid4()
        teacher.teacher_account_id = type(teacher.id)(actor.weave_actor_id)

        with (
            patch.object(
                AuthRepository,
                "list_actors",
                new=AsyncMock(return_value=[actor]),
            ),
            patch.object(
                AuthRepository,
                "get_actor_by_id",
                new=AsyncMock(return_value=actor),
            ),
            patch.object(
                AcademicRepository,
                "get_teacher_by_membership_id",
                new=AsyncMock(return_value=teacher),
            ),
            patch.object(
                AuthRepository,
                "save_actor",
                new=AsyncMock(return_value=actor),
            ),
            patch.object(
                AuthRepository,
                "list_sessions_for_actor",
                new=AsyncMock(return_value=[]),
            ) as list_sessions,
        ):
            await LocalAuthService.reconcile_synced_staff_trust(
                db,
                revalidated_at=now,
            )

        self.assertTrue(actor.is_active)
        self.assertEqual(actor.last_weave_revalidated_at, now)
        list_sessions.assert_not_awaited()

    async def test_missing_admin_projection_revokes_local_admin_trust(self):
        db = _db()
        actor = SimpleNamespace(
            id=uuid4(),
            weave_actor_id=str(uuid4()),
            weave_membership_id=None,
            role="admin",
            email="admin@example.com",
            display_name="Admin",
            is_active=True,
            last_weave_revalidated_at=None,
        )
        now = datetime.now(UTC)

        with (
            patch.object(
                AuthRepository,
                "list_actors",
                new=AsyncMock(return_value=[actor]),
            ),
            patch.object(
                AuthRepository,
                "get_actor_by_id",
                new=AsyncMock(return_value=actor),
            ),
            patch.object(
                AcademicRepository,
                "get_admin_by_id",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                AuthRepository,
                "save_actor",
                new=AsyncMock(return_value=actor),
            ),
            patch.object(
                AuthRepository,
                "list_sessions_for_actor",
                new=AsyncMock(return_value=[]),
            ),
        ):
            await LocalAuthService.reconcile_synced_staff_trust(
                db,
                revalidated_at=now,
            )

        self.assertFalse(actor.is_active)


class StaffRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_rotates_token_without_calling_weave(self):
        db = _db()
        actor = _teacher_actor()
        now = datetime.now(UTC)
        session = SimpleNamespace(
            id=uuid4(),
            actor_id=actor.id,
            revoked_at=None,
            revocation_reason=None,
            expires_at=now + timedelta(hours=6),
            last_refreshed_at=None,
            last_seen_at=now,
        )
        stored_token = SimpleNamespace(
            id=uuid4(),
            session_id=session.id,
            token_hash="hash-old-token",
            expires_at=now + timedelta(hours=6),
            revoked_at=None,
            consumed_at=None,
            reuse_detected_at=None,
            replaced_by_token_id=None,
        )
        replacement_id = uuid4()

        async def add_refresh_token(_db, token):
            token.id = replacement_id
            return token

        with (
            patch.object(
                AuthRepository,
                "get_refresh_token_by_hash",
                new=AsyncMock(side_effect=[stored_token, stored_token]),
            ),
            patch.object(
                AuthRepository,
                "get_session_by_id",
                new=AsyncMock(side_effect=[session, session]),
            ),
            patch.object(
                AuthRepository,
                "get_actor_by_id",
                new=AsyncMock(return_value=actor),
            ),
            patch.object(
                AuthRepository,
                "add_refresh_token",
                new=AsyncMock(side_effect=add_refresh_token),
            ),
            patch.object(
                AuthRepository,
                "save_refresh_token",
                new=AsyncMock(return_value=stored_token),
            ),
            patch.object(
                AuthRepository,
                "save_session",
                new=AsyncMock(return_value=session),
            ),
            patch("app.domains.auth.service.hash_refresh_token", side_effect=lambda value: f"hash-{value}"),
            patch("app.domains.auth.service.generate_refresh_token", return_value="new-token"),
            patch("app.domains.auth.service.create_local_access_token", return_value="new-access"),
            patch(
                "app.domains.auth.service.node_identity_store.load",
                return_value=SimpleNamespace(server_id=uuid4()),
            ),
            patch(
                "app.domains.auth.service.weave_auth_gateway.authenticate_staff",
                new=AsyncMock(),
            ) as weave_authenticate,
        ):
            result = await LocalAuthService.refresh_staff(
                db,
                refresh_token="old-token",
            )

        self.assertEqual(result.access_token, "new-access")
        self.assertEqual(result.refresh_token, "new-token")
        self.assertIsNotNone(stored_token.consumed_at)
        self.assertEqual(stored_token.replaced_by_token_id, replacement_id)
        self.assertIsNotNone(session.last_refreshed_at)
        weave_authenticate.assert_not_awaited()

    async def test_reused_refresh_token_revokes_entire_local_session(self):
        db = _db()
        actor = _teacher_actor()
        now = datetime.now(UTC)
        session = SimpleNamespace(
            id=uuid4(),
            actor_id=actor.id,
            revoked_at=None,
            revocation_reason=None,
            expires_at=now + timedelta(hours=6),
            last_refreshed_at=None,
            last_seen_at=now,
        )
        stored_token = SimpleNamespace(
            id=uuid4(),
            session_id=session.id,
            token_hash="hash-old-token",
            expires_at=now + timedelta(hours=6),
            revoked_at=None,
            consumed_at=now - timedelta(minutes=1),
            reuse_detected_at=None,
            replaced_by_token_id=uuid4(),
        )

        with (
            patch.object(
                AuthRepository,
                "get_refresh_token_by_hash",
                new=AsyncMock(side_effect=[stored_token, stored_token]),
            ),
            patch.object(
                AuthRepository,
                "get_session_by_id",
                new=AsyncMock(side_effect=[session, session]),
            ),
            patch.object(
                AuthRepository,
                "get_actor_by_id",
                new=AsyncMock(return_value=actor),
            ),
            patch.object(
                AuthRepository,
                "save_refresh_token",
                new=AsyncMock(return_value=stored_token),
            ),
            patch.object(
                AuthRepository,
                "save_session",
                new=AsyncMock(return_value=session),
            ),
            patch.object(
                AuthRepository,
                "list_refresh_tokens_for_session",
                new=AsyncMock(return_value=[stored_token]),
            ),
            patch.object(
                AuthRepository,
                "save_refresh_tokens",
                new=AsyncMock(return_value=[stored_token]),
            ),
            patch("app.domains.auth.service.hash_refresh_token", return_value="hash-old-token"),
            patch(
                "app.domains.auth.service.node_identity_store.load",
                return_value=SimpleNamespace(server_id=uuid4()),
            ),
        ):
            with self.assertRaisesRegex(
                LocalSessionAuthenticationError,
                INVALID_LOCAL_STAFF_SESSION,
            ):
                await LocalAuthService.refresh_staff(
                    db,
                    refresh_token="old-token",
                )

        self.assertIsNotNone(stored_token.reuse_detected_at)
        self.assertIsNotNone(session.revoked_at)
