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
            '{"Service":"bootstrap","State":"exited","ExitCode":0}',
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


def test_health_rejects_missing_or_failed_database_initialization(monkeypatch):
    for initialization in ('', '{"Service":"bootstrap","State":"exited","ExitCode":1}', '{"Service":"bootstrap","State":"exited"}'):
        deployment = FakeDeployment()
        raw = deployment.compose_ps_json().replace('{"Service":"bootstrap","State":"exited","ExitCode":0}', initialization)
        deployment.compose_ps_json = lambda raw=raw: raw
        health = HealthService(deployment)
        monkeypatch.setattr(health, "_web_reachable", lambda: True)
        assert not health.snapshot().healthy
        assert "initialization" in health.snapshot().detail


def test_portal_404_is_not_healthy(monkeypatch):
    from urllib.error import HTTPError
    import weave_cbt_manager.core.health as module
    def missing(*args, **kwargs):
        raise HTTPError("http://localhost/staff", 404, "Not Found", {}, None)
    monkeypatch.setattr(module, "urlopen", missing)
    assert HealthService._web_reachable() is False
