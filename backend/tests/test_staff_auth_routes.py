from __future__ import annotations

import inspect
import os
import unittest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("WEAVE_API_BASE_URL", "https://weave.invalid")

from app.domains.auth.router import refresh_staff, router


class StaffAuthRouteContractTests(unittest.TestCase):
    def test_expected_staff_auth_routes_are_exposed(self):
        route_methods = {
            (route.path, method)
            for route in router.routes
            for method in (route.methods or set())
        }

        self.assertIn(("/auth/login", "POST"), route_methods)
        self.assertIn(("/auth/refresh", "POST"), route_methods)
        self.assertIn(("/auth/session", "GET"), route_methods)
        self.assertIn(("/auth/logout", "POST"), route_methods)

    def test_refresh_requires_idempotency_key_header(self):
        parameter = inspect.signature(refresh_staff).parameters["idempotency_key"]
        self.assertEqual(parameter.default.alias, "Idempotency-Key")
        self.assertTrue(parameter.default.is_required())


if __name__ == "__main__":
    unittest.main()
