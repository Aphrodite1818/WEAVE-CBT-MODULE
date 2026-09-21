from weave_cbt_manager.core.deployment import DeploymentService
from weave_cbt_manager.runtime.base import RuntimeCommandResult


class FakeRuntime:
    def __init__(self):
        self.commands = []
        self.writes = []
        self.execute_result = RuntimeCommandResult(0, "", "")

    def execute(self, command, *, timeout=None):
        self.commands.append((list(command), timeout))
        return self.execute_result

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


def test_prepare_assets_writes_non_secret_files_before_runtime_env():
    runtime = FakeRuntime()
    docker = FakeDocker()
    service = DeploymentService(runtime, docker)

    service.prepare_assets(
        runtime_env="POSTGRES_PASSWORD='secret$123'\n",
        compose_yaml="services: {}\n",
        nginx_config="events {}\n",
    )

    assert runtime.commands == []
    assert runtime.writes == [
        ("/opt/weave-cbt/compose.yaml", "services: {}\n", "0644", 30),
        ("/opt/weave-cbt/nginx/nginx.conf", "events {}\n", "0644", 30),
        (
            "/opt/weave-cbt/runtime.env",
            "POSTGRES_PASSWORD='secret$123'\n",
            "0600",
            30,
        ),
    ]


def test_config_exists_requires_all_runtime_assets():
    runtime = FakeRuntime()
    docker = FakeDocker()
    service = DeploymentService(runtime, docker)

    assert service.config_exists() is True
    command, timeout = runtime.commands[-1]
    assert timeout == 10
    assert command[:2] == ["sh", "-c"]
    assert command[-3:] == [
        "/opt/weave-cbt/runtime.env",
        "/opt/weave-cbt/compose.yaml",
        "/opt/weave-cbt/nginx/nginx.conf",
    ]
    assert "test -s" in command[2]

    runtime.execute_result = RuntimeCommandResult(1, "", "missing")
    assert service.config_exists() is False


def test_deploy_validates_pulls_and_starts():
    runtime = FakeRuntime()
    docker = FakeDocker()
    service = DeploymentService(runtime, docker)
    service.deploy()
    assert docker.pulled is True
    assert docker.started is True
    assert docker.compose_calls[0][0] == ["config", "--quiet"]


def test_set_image_uses_positional_arguments_not_shell_interpolation():
    runtime = FakeRuntime()
    docker = FakeDocker()
    service = DeploymentService(runtime, docker)

    image = "ghcr.io/aphrodite1818/weave-cbt-module:sha-test"
    service.set_image(image)

    command, timeout = runtime.commands[-1]
    assert timeout == 20
    assert command[:2] == ["sh", "-c"]
    assert command[-2:] == ["/opt/weave-cbt/runtime.env", image]
    assert image not in command[2]
