import asyncio

import httpx
import typer
from rich.table import Table

from protondl.cli import app, console
from protondl.cli.helpers import resolve_installed_tool, select_launcher
from protondl.core.base_launcher import Game
from protondl.launchers.steam import SteamGame, SteamLauncher
from protondl.services import (
    AWACYIndex,
    fetch_awacy_index,
    get_awacy_status_by_id,
)


@app.command(name="list-games")
def list_games(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
    awacy: bool = typer.Option(
        False,
        "--awacy",
        help="Show AWACY anti-cheat status for each listed game",
    ),
) -> None:
    """
    List all compatibility tools currently installed for a specific launcher.
    """
    target_launcher = select_launcher(launcher_id)

    awacy_index: AWACYIndex | None = None
    if awacy:
        try:
            with console.status("[bold blue]Fetching AWACY data...", spinner="dots"):
                awacy_index = asyncio.run(fetch_awacy_index())
        except (httpx.HTTPError, ValueError) as e:
            console.print(f"[red]Failed to fetch AWACY data: {e}[/red]")
            raise typer.Exit(code=1) from e

    with console.status(
        f"[bold blue]Scanning {target_launcher.name} directories...", spinner="bouncingBar"
    ):
        games = target_launcher.get_game_list()

    if not games:
        console.print(f"[yellow]No games found for {target_launcher.name}.[/yellow]")
        return

    table = Table(title=f"Installed Games: [bold cyan]{target_launcher.name}[/bold cyan]")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Game Name", style="green")
    table.add_column("Compatibility Tool", overflow="ellipsis")
    table.add_column("Path", overflow="ellipsis")
    if awacy:
        table.add_column("AWACY Status", style="magenta")

    for game in sorted(games, key=lambda x: x.name):
        row = [game.id, game.name, game.compat_tool_name, str(game.install_path)]
        if awacy and awacy_index is not None:
            row.append(get_awacy_status_by_id(game.id, awacy_index).value)

        table.add_row(*row)

    console.print(table)


@app.command(name="get-steam-deck-status")
def get_steam_deck_status(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
    game_id: str = typer.Argument(..., help="ID of the Steam game, e.g., 123456"),
) -> None:
    """
    Show the Steam Deck compatibility status for a Steam game.
    """
    target_launcher = select_launcher(launcher_id)

    if not isinstance(target_launcher, SteamLauncher):
        console.print(
            f"[red]{target_launcher.name} does not support Steam Deck status lookups.[/red]"
        )
        raise typer.Exit(code=1)

    steam_launcher = target_launcher
    game_by_id: dict[str, SteamGame] = {game.id: game for game in steam_launcher.get_game_list()}

    game = game_by_id.get(game_id)
    if not game:
        console.print(f"[red]Game ID '{game_id}' not found in {target_launcher.name}.[/red]")
        raise typer.Exit(code=1)

    try:
        recommended_runtime, compat_type = game.get_steamdeck_compatibility()
    except ValueError as e:
        console.print(f"[red]Failed to read Steam Deck compatibility for {game.name}: {e}[/red]")
        raise typer.Exit(code=1) from e

    recommended_label = recommended_runtime or "none"
    console.print(
        f"{game.name}: Steam Deck status {compat_type.name}"
        f" (recommended runtime: {recommended_label})"
    )


@app.command(name="set-tool")
def set_tool(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
    game_id: str = typer.Argument(..., help="ID of the game, e.g., 123456"),
    compat_tool_name: str = typer.Argument(..., help="Name of the tool, e.g., GE-Proton10-10"),
) -> None:
    """
    Assign a compatibility tool to one or more games in a launcher.

    Example:
        protondl set-game-tools 1 123456 GE-Proton10-10
    """
    target_launcher = select_launcher(launcher_id)

    with console.status(
        f"[bold blue]Setting compatibility tools for games in {target_launcher.name}...",
        spinner="bouncingBar",
    ):
        games = target_launcher.get_game_list()
        game_by_id = {game.id: game for game in games}

        if game_id not in game_by_id:
            console.print(f"[red]Game ID '{game_id}' not found in {target_launcher.name}.[/red]")
            raise typer.Exit(code=1)

        result_map: dict[Game, str | None] = {
            game_by_id[game_id]: None if compat_tool_name == "none" else compat_tool_name
        }

        try:
            target_launcher.set_games_tools(result_map)
        except Exception as e:
            console.print(f"[red]Failed to set game tools: {e}[/red]")
            raise typer.Exit(code=1) from e

    console.print("[bold green]Game compatibility tool mapping updated successfully.[/bold green]")


@app.command(name="set-global-tool")
def set_global_tool(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
    compat_tool_name: str = typer.Argument(
        ...,
        help=(
            "Name or index of the tool from 'list-installed' " + "(e.g., 'GE-Proton10-10' or '1')"
        ),
    ),
) -> None:
    """
    Set the global/default compatibility tool for a launcher.
    """
    target_launcher = select_launcher(launcher_id)

    try:
        installed_tools = sorted(target_launcher.get_installed_tools(), key=lambda x: x.full_name)
    except Exception as e:
        console.print(f"[red]Failed to read installed tools: {e}[/red]")
        raise typer.Exit(code=1) from e

    if not installed_tools:
        console.print(
            f"[yellow]No installed compatibility tools found for {target_launcher.name}.[/yellow]"
        )
        raise typer.Exit(code=1)

    selected_tool = resolve_installed_tool(installed_tools, compat_tool_name)

    if not selected_tool:
        console.print(
            "[red]Tool not found. Use 'list-installed <launcher_id>'"
            + "to find a valid name/index.[/red]"
        )
        raise typer.Exit(code=1)

    try:
        target_launcher.set_global_tool(selected_tool)
    except NotImplementedError as e:
        console.print(
            f"[red]Global tool configuration is not supported for {target_launcher.name} yet.[/red]"
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[red]Failed to set global tool: {e}[/red]")
        raise typer.Exit(code=1) from e

    console.print(
        f"[bold green]Global compatibility tool set to {selected_tool.full_name} for "
        + f"{target_launcher.name}.[/bold green]"
    )
