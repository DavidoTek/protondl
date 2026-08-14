import typer
from rich.table import Table

from protondl.cli import app, console
from protondl.cli.helpers import select_launcher
from protondl.launchers.steam import SteamGame, SteamLauncher


def _require_steam_launcher(launcher: object) -> SteamLauncher:
    """
    Returns the launcher if it is a SteamLauncher, otherwise exits with an error.

    Args:
        launcher: The launcher selected via select_launcher().

    Returns:
        SteamLauncher: The launcher cast to SteamLauncher.

    Raises:
        typer.Exit: If the launcher does not support shortcuts.
    """
    if not isinstance(launcher, SteamLauncher):
        console.print(
            f"[red]{getattr(launcher, 'name', 'Launcher')} does not support Steam shortcuts.[/red]"
        )
        raise typer.Exit(code=1)
    return launcher


@app.command(name="list-shortcuts")
def list_shortcuts(
    launcher: str = typer.Argument(
        ...,
        help=(
            "The ID of the launcher from 'list-launchers', "
            "or a '<type>:<path>' spec (e.g. 'steam:~/mySteam')"
        ),
    ),
) -> None:
    """
    List all Steam shortcuts (non-Steam games).
    """
    steam_launcher = _require_steam_launcher(select_launcher(launcher))

    try:
        shortcuts = steam_launcher.get_shortcuts()
    except Exception as e:
        console.print(f"[red]Failed to read the shortcuts of {steam_launcher.name}: {e}[/red]")
        raise typer.Exit(code=1) from e

    if not shortcuts:
        console.print(f"[yellow]No shortcuts found for {steam_launcher.name}.[/yellow]")
        return

    table = Table(title=f"Steam Shortcuts: [bold cyan]{steam_launcher.name}[/bold cyan]")
    table.add_column("AppID", justify="right", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Executable", overflow="ellipsis")
    table.add_column("Start Directory", overflow="ellipsis")
    table.add_column("Steam User", style="magenta")

    for shortcut in sorted(shortcuts, key=lambda x: x.name):
        table.add_row(
            shortcut.id,
            shortcut.name,
            shortcut.shortcut_exe,
            shortcut.shortcut_startdir,
            shortcut.shortcut_user,
        )

    console.print(table)


@app.command(name="add-shortcut")
def add_shortcut(
    launcher: str = typer.Argument(
        ...,
        help=(
            "The ID of the launcher from 'list-launchers', "
            "or a '<type>:<path>' spec (e.g. 'steam:~/mySteam')"
        ),
    ),
    name: str = typer.Argument(..., help="Display name of the shortcut"),
    executable: str = typer.Argument(..., help="Path to the executable to launch"),
    startdir: str = typer.Option(
        "",
        "--startdir",
        help="Working directory for the launch (default: empty)",
    ),
    icon: str = typer.Option(
        "",
        "--icon",
        help="Path to the icon used for the shortcut (default: empty)",
    ),
    user: str = typer.Option(
        "",
        "--user",
        help="Steam user (userdata folder name) to add the shortcut to (default: auto-detected)",
    ),
) -> None:
    """
    Add a new Steam shortcut (non-Steam game).

    Example:
        protondl add-shortcut 1 "My Game" "/opt/games/MyGame.sh" --startdir /opt/games
    """
    steam_launcher = _require_steam_launcher(select_launcher(launcher))

    try:
        shortcut = steam_launcher.add_shortcut(
            name=name,
            exe=executable,
            startdir=startdir,
            icon=icon,
            user=user,
        )
    except ValueError as e:
        console.print(f"[red]Failed to add shortcut: {e}[/red]")
        raise typer.Exit(code=1) from e

    target = shortcut.shortcut_user or "(auto-detected)"
    console.print(
        f"[bold green]Shortcut '{shortcut.name}' added to {steam_launcher.name}"
        f" (user {target}, appid {shortcut.appid}).[/bold green]"
    )


@app.command(name="remove-shortcuts")
def remove_shortcuts(
    launcher: str = typer.Argument(
        ...,
        help=(
            "The ID of the launcher from 'list-launchers', "
            "or a '<type>:<path>' spec (e.g. 'steam:~/mySteam')"
        ),
    ),
    shortcut_ids: list[str] = typer.Argument(  # noqa: B008
        ...,
        help="AppID or name of the shortcuts to remove, e.g., '1234567890' or 'My Game'",
    ),
) -> None:
    """
    Remove Steam shortcuts (non-Steam games).

    Accepts one or more shortcut AppIDs or names as shown by 'list-shortcuts'.

    Example:
        protondl remove-shortcuts 1 1234567890 "My Game"
    """
    steam_launcher = _require_steam_launcher(select_launcher(launcher))

    try:
        shortcuts = steam_launcher.get_shortcuts()
    except Exception as e:
        console.print(f"[red]Failed to read the shortcuts of {steam_launcher.name}: {e}[/red]")
        raise typer.Exit(code=1) from e

    by_id = {shortcut.id: shortcut for shortcut in shortcuts}
    by_name = {shortcut.name.lower(): shortcut for shortcut in shortcuts}

    to_remove: list[SteamGame] = []
    for shortcut_id in shortcut_ids:
        shortcut = by_id.get(shortcut_id) or by_name.get(shortcut_id.lower())
        if shortcut is None:
            console.print(
                f"[red]Shortcut '{shortcut_id}' not found in {steam_launcher.name}.[/red]"
            )
            raise typer.Exit(code=1)
        to_remove.append(shortcut)

    try:
        steam_launcher.remove_shortcuts(to_remove)
    except Exception as e:
        console.print(f"[red]Failed to remove shortcuts: {e}[/red]")
        raise typer.Exit(code=1) from e

    names = ", ".join(f"'{shortcut.name}'" for shortcut in to_remove)
    console.print(f"[bold green]Removed {len(to_remove)} shortcut(s): {names}.[/bold green]")
