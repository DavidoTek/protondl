import asyncio

import httpx
import typer

from protondl.cli import app, console
from protondl.services import (
    fetch_awacy_index,
    fetch_protondb_tier,
    get_awacy_status_by_id,
    get_awacy_status_by_slug,
)


@app.command(name="get-awacy-status")
def get_awacy_status(
    game_identifier: str = typer.Argument(..., help="Steam AppID or AWACY slug to look up"),
    slug: bool = typer.Option(
        False,
        "--slug",
        help="Treat the identifier as an AWACY slug instead of a Steam AppID",
    ),
) -> None:
    """
    Show the areweanticheatyet.com status for a game identifier.
    """
    try:
        index = asyncio.run(fetch_awacy_index())
    except (httpx.HTTPError, ValueError) as e:
        console.print(f"[red]Failed to fetch AWACY data: {e}[/red]")
        raise typer.Exit(code=1) from e

    status = (
        get_awacy_status_by_slug(game_identifier, index)
        if slug
        else get_awacy_status_by_id(game_identifier, index)
    )

    console.print(f"AWACY status of {game_identifier} is {status.value}")


@app.command(name="get-protondb-status")
def get_protondb_status(
    game_identifier: str = typer.Argument(..., help="Steam AppID to look up"),
) -> None:
    """
    Show the ProtonDB compatibility status for a game identifier.
    """
    try:
        _ = int(game_identifier)
    except ValueError:
        console.print(f"[red]Invalid Steam AppID: {game_identifier}[/red]")
        raise typer.Exit(code=1) from None

    try:
        tier = asyncio.run(fetch_protondb_tier(game_identifier))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"ProtonDB status of {game_identifier} is Unknown")
            return
        console.print(f"[red]Failed to fetch ProtonDB data: {e}[/red]")
        raise typer.Exit(code=1) from e
    except (httpx.HTTPError, ValueError) as e:
        console.print(f"[red]Failed to fetch ProtonDB data: {e}[/red]")
        raise typer.Exit(code=1) from e

    console.print(f"ProtonDB status of {game_identifier} is {tier.value.title()}")
