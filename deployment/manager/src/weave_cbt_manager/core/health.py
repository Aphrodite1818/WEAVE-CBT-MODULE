"""Health inspection for the managed WEAVE CBT stack."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from weave_cbt_manager.constants import DEFAULT_SERVER_URL
from weave_cbt_manager.core.docker import DockerService


EXPECTED_RUNNING_SERVICES = {"postgres", "redis", "api", "worker", "nginx"}


@dataclass(frozen=True, slots=True)
class HealthReport:
    docker_ready: bool
    running_services: frozenset[str]
    http_ready: bool

    @property
    def missing_services(self) -> frozenset[str]:
        return frozenset(EXPECTED_RUNNING_SERVICES.difference(self.running_services))

    @property
    def healthy(self) -> bool:
        return self.docker_ready and not self.missing_services and self.http_ready


class HealthService:
    def __init__(
        self,
        docker: DockerService,
        *,
        server_url: str = DEFAULT_SERVER_URL,
    ) -> None:
        self.docker = docker
        self.server_url = server_url.rstrip("/")

    def inspect(self) -> HealthReport:
        docker_ready = self.docker.docker_available() and self.docker.compose_available()
        running_services = (
            frozenset(self.docker.running_services()) if docker_ready else frozenset()
        )
        http_ready = False

        if docker_ready:
            try:
                response = httpx.get(
                    f"{self.server_url}/staff",
                    timeout=3.0,
                    follow_redirects=True,
                )
                http_ready = response.status_code < 500
            except httpx.HTTPError:
                http_ready = False

        return HealthReport(
            docker_ready=docker_ready,
            running_services=running_services,
            http_ready=http_ready,
        )
