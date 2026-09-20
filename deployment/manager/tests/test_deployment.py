from weave_cbt_manager.core.deployment import DeploymentService
from weave_cbt_manager.runtime.base import RuntimeCommandResult


class FakeRuntime:
    def __init__(self): self.commands = []
    def execute(self, command, *, timeout=None):
        self.commands.append((list(command), timeout))
        return RuntimeCommandResult(0, "", "")


class FakeDocker:
    def __init__(self): self.compose_calls = []; self.pulled = False; self.started = False
    def ensure_ready(self): pass
    def compose(self, command, **kwargs): self.compose_calls.append((list(command), kwargs)); return RuntimeCommandResult(0, "", "")
    def pull(self, **kwargs): self.pulled = True
    def up(self, **kwargs): self.started = True
    def down(self, **kwargs): pass


def test_prepare_assets_does_not_shell_secrets_directly():
    runtime = FakeRuntime(); docker = FakeDocker(); service = DeploymentService(runtime, docker)
    service.prepare_assets(runtime_env="POSTGRES_PASSWORD='secret$123'\n", compose_yaml="services: {}\n", nginx_config="events {}\n")
    command_text = "\n".join(" ".join(command) for command, _ in runtime.commands)
    assert "secret$123" not in command_text
    assert "base64 -d" in command_text


def test_deploy_validates_pulls_and_starts():
    runtime = FakeRuntime(); docker = FakeDocker(); service = DeploymentService(runtime, docker)
    service.deploy()
    assert docker.pulled is True
    assert docker.started is True
    assert docker.compose_calls[0][0] == ["config", "--quiet"]
