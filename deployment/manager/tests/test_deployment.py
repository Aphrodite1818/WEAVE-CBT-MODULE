from weave_cbt_manager.core.deployment import DeploymentService
from weave_cbt_manager.runtime.base import RuntimeCommandResult


class FakeRuntime:
    def __init__(self):
        self.commands = []
        self.writes = []

    def execute(self, command, *, timeout=None):
        self.commands.append((list(command), timeout))
        return RuntimeCommandResult(0, "", "")

    def write_text_file(self, path, content, *, mode, timeout=None):
        self.writes.append((path, content, mode, timeout))
        return RuntimeCommandResult(0, "", "")


class FakeDocker:
    def __init__(self):
        self.compose_calls = []
        self.pulled = False
        self.started = False

    def ensure_ready(self):
        pass

    def compose(self, command, **kwargs):
        self.compose_calls.append((list(command), kwargs))
        return RuntimeCommandResult(0, "", "")

    def pull(self, **kwargs):
        self.pulled = True

    def up(self, **kwargs):
        self.started = True

    def down(self, **kwargs):
        pass


def test_prepare_assets_uses_runtime_file_channel_for_secrets():
    runtime = FakeRuntime()
    docker = FakeDocker()
    service = DeploymentService(runtime, docker)

    service.prepare_assets(
        runtime_env="POSTGRES_PASSWORD='secret$123'\n",
        compose_yaml="services: {}\n",
        nginx_config="events {}\n",
    )

    assert runtime.commands == []
    assert len(runtime.writes) == 3
    assert runtime.writes[0] == (
        "/opt/weave-cbt/runtime.env",
        "POSTGRES_PASSWORD='secret$123'\n",
        "0600",
        20,
    )
    assert runtime.writes[1][0] == "/opt/weave-cbt/compose.yaml"
    assert runtime.writes[1][2] == "0644"
    assert runtime.writes[2][0] == "/opt/weave-cbt/nginx/nginx.conf"
    assert runtime.writes[2][2] == "0644"


def test_deploy_validates_pulls_and_starts():
    runtime = FakeRuntime()
    docker = FakeDocker()
    service = DeploymentService(runtime, docker)
    service.deploy()
    assert docker.pulled is True
    assert docker.started is True
    assert docker.compose_calls[0][0] == ["config", "--quiet"]
