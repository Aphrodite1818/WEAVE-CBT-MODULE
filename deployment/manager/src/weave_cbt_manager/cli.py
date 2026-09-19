"""Terminal interface for the shared WEAVE CBT Manager core."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from weave_cbt_manager.constants import DEFAULT_SERVER_URL
from weave_cbt_manager.core.docker import DockerService
from weave_cbt_manager.core.health import HealthService
from weave_cbt_manager.core.installer import InstallEvent, InstallerService, InstallationError
from weave_cbt_manager.platforms.windows import WindowsPlatform

app = typer.Typer(
    name="weave-cbt",
    help="Install and manage a WEAVE CBT server.",
    no_args_is_help=True,
)
console = Console()


def _runtime() -> tuple[WindowsPlatform, DockerService, HealthService]:
    platform = WindowsPlatform()
    docker = DockerService(
        compose_file=platform.paths.compose_file,
        env_file=platform.paths.env_file,
    )
    return platform, docker, HealthService(docker)


@app.command()
def install() -> None:
    """Install or repair WEAVE CBT using the managed Docker deployment."""

    platform = WindowsPlatform()
    installer = InstallerService(platform)

    def report(event: InstallEvent) -> None:
        console.print(f"[cyan]{event.progress:>3}%[/cyan] {event.message}")

    try:
        installer.install(callback=report)
    except InstallationError as exc:
        console.print(f"[red]Installation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print("\n[bold green]WEAVE CBT is ready.[/bold green]")
    console.print(f"Staff: {DEFAULT_SERVER_URL}/staff")
    console.print(f"Student: {DEFAULT_SERVER_URL}/student")


@app.command()
def status() -> None:
    """Show the current local WEAVE CBT service status."""

    _, _, health = _runtime()
    report = health.inspect()

    table = Table(title="WEAVE CBT Server")
    table.add_column("Component")
    table.add_column("Status")
    for service in ("postgres", "redis", "api", "worker", "nginx"):
        running = service in report.running_services
        table.add_row(service, "Running" if running else "Stopped")
    table.add_row("Web", "Ready" if report.http_ready else "Unavailable")
    console.print(table)
    raise typer.Exit(code=0 if report.healthy else 1)


@app.command()
def start() -> None:
    """Start the managed WEAVE CBT stack."""

    _, docker, _ = _runtime()
    docker.up()
    console.print("[green]WEAVE CBT started.[/green]")


@app.command()
def stop() -> None:
    """Stop containers without deleting persistent volumes."""

    _, docker, _ = _runtime()
    docker.down()
    console.print("[yellow]WEAVE CBT stopped.[/yellow]")


@app.command()
def restart() -> None:
    """Restart the running WEAVE CBT containers."""

    _, docker, _ = _runtime()
    docker.restart()
    console.print("[green]WEAVE CBT restarted.[/green]")


@app.command()
def logs(
    service: str | None = typer.Argument(
        default=None,
        help="Optional Compose service name, for example api or worker.",
    ),
    tail: int = typer.Option(200, min=1, max=5000),
) -> None:
    """Print recent WEAVE CBT container logs."""

    _, docker, _ = _runtime()
    console.print(docker.logs(service, tail=tail))


if __name__ == "__main__":
    app()
