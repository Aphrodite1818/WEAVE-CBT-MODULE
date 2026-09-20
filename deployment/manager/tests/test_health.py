from weave_cbt_manager.core.health import HealthService


class FakeDocker:
    def ensure_ready(self): pass


class FakeDeployment:
    def __init__(self): self.docker = FakeDocker()
    def compose_ps_json(self):
        return "\n".join([
            '{"Service":"postgres","State":"running","Health":"healthy"}',
            '{"Service":"redis","State":"running","Health":"healthy"}',
            '{"Service":"api","State":"running","Health":""}',
            '{"Service":"api","State":"running","Health":""}',
            '{"Service":"api","State":"running","Health":""}',
            '{"Service":"worker","State":"running","Health":""}',
            '{"Service":"nginx","State":"running","Health":""}',
            '{"Service":"migrate","State":"exited","ExitCode":0}',
        ])


def test_health_requires_full_service_set(monkeypatch):
    service = HealthService(FakeDeployment())
    monkeypatch.setattr(service, "_web_reachable", lambda: True)
    assert service.snapshot().healthy is True


def test_health_rejects_missing_api_replica(monkeypatch):
    deployment = FakeDeployment(); original = deployment.compose_ps_json
    deployment.compose_ps_json = lambda: original().replace('{"Service":"api","State":"running","Health":""}\n', '', 1)
    service = HealthService(deployment)
    monkeypatch.setattr(service, "_web_reachable", lambda: True)
    snapshot = service.snapshot()
    assert snapshot.healthy is False
    assert "api" in snapshot.detail
