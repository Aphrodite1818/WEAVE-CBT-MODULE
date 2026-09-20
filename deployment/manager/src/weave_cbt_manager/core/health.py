"""Runtime health assessment for the local WEAVE CBT stack."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .deployment import DeploymentService


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    runtime_ready: bool
    services_ready: bool
    web_reachable: bool
    detail: str

    @property
    def healthy(self) -> bool:
        return self.runtime_ready and self.services_ready and self.web_reachable


class HealthService:
    REQUIRED_RUNNING = {"postgres": 1, "redis": 1, "api": 3, "worker": 1, "nginx": 1}

    def __init__(self, deployment: DeploymentService) -> None:
        self.deployment = deployment

    @staticmethod
    def _records(raw: str) -> list[dict[str, object]]:
        raw = raw.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass
        records: list[dict[str, object]] = []
        for line in raw.splitlines():
            try:
                item = json.loads(line.strip())
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(item, dict):
                records.append(item)
        return records

    @staticmethod
    def _web_reachable() -> bool:
        request = Request("http://127.0.0.1/staff", method="GET", headers={"User-Agent": "WEAVE-CBT-Manager"})
        try:
            with urlopen(request, timeout=3) as response:
                return 200 <= response.status < 500
        except HTTPError as exc:
            return 200 <= exc.code < 500
        except (URLError, OSError, TimeoutError):
            return False

    def snapshot(self) -> HealthSnapshot:
        try:
            self.deployment.docker.ensure_ready()
            records = self._records(self.deployment.compose_ps_json())
        except Exception as exc:
            return HealthSnapshot(False, False, False, str(exc))
        counts: dict[str, int] = {}
        migration_ok = False
        for record in records:
            service = str(record.get("Service") or record.get("service") or "")
            state = str(record.get("State") or record.get("state") or "").lower()
            health = str(record.get("Health") or record.get("health") or "").lower()
            exit_code = record.get("ExitCode", record.get("exit_code"))
            if service == "migrate" and state in {"exited", "stopped"}:
                migration_ok = str(exit_code or "0") == "0"
            if state == "running" and health not in {"unhealthy", "starting"}:
                counts[service] = counts.get(service, 0) + 1
        missing = [f"{service} ({counts.get(service, 0)}/{expected})" for service, expected in self.REQUIRED_RUNNING.items() if counts.get(service, 0) < expected]
        services_ready = not missing and (migration_ok or not any(str(r.get("Service")) == "migrate" for r in records))
        web_reachable = self._web_reachable() if services_ready else False
        detail = "Healthy" if services_ready and web_reachable else "; ".join(missing) or "Web endpoint is not reachable."
        return HealthSnapshot(True, services_ready, web_reachable, detail)

    def wait_until_healthy(self, *, timeout_seconds: float = 120, interval_seconds: float = 3) -> HealthSnapshot:
        deadline = time.monotonic() + timeout_seconds
        last = self.snapshot()
        while not last.healthy and time.monotonic() < deadline:
            time.sleep(interval_seconds)
            last = self.snapshot()
        return last
