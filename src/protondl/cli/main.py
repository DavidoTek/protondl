from rich.table import Table

# Import submodules so they register their commands on `app`
from protondl.cli import app, console, games, services, tools  # noqa: F401
from protondl.cli.helpers import get_launchers

if __name__ == "__main__":
    app()


@app.command(name="list-launchers")
def list_launchers() -> None:
    """
    Scan the system and display all detected game launchers in a table.
    """
    launchers = get_launchers()

    if not launchers:
        console.print("[yellow]No launchers detected on your system.[/yellow]")
        return

    table = Table(
        title="Detected Launchers",
        caption=(
            "Use the [bold cyan]ID[/bold cyan] to target a specific launcher in other commands, "
            "or a '<type>:<path>' spec for custom installations (e.g. 'steam:~/mySteam')"
        ),
        title_style="bold magenta",
    )

    table.add_column("ID", justify="center", style="cyan", no_wrap=True)
    table.add_column("Launcher Name", style="white")
    table.add_column("Mode", style="green")
    table.add_column("Root Path", style="dim")

    for idx, launcher in enumerate(launchers, 1):
        table.add_row(
            str(idx),
            launcher.name,
            launcher.install_mode.value,
            str(launcher.root_path),
        )

    console.print(table)
