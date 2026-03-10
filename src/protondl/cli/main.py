import asyncio

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from protondl.core.models import RequestConfig
from protondl.installers import CT_INSTALLERS, get_tools_for_launcher
from protondl.launchers import detect_all_launchers

app = typer.Typer(help="Proton Compatibility Tool Manager")
state = {"request_config": RequestConfig(github_token=None)}
console = Console()


@app.callback()
def main(
    github_token: str | None = typer.Option(
        None, "--github-token", "-t", help="GitHub API Token", envvar="GITHUB_TOKEN"
    ),
) -> None:
    """
    protondl compatibility tool downloader.
    """
    state["request_config"] = RequestConfig(github_token=github_token)


@app.command(name="list-launchers")
def list_launchers() -> None:
    """
    Scan the system and display all detected game launchers in a table.
    """
    launchers = detect_all_launchers()

    if not launchers:
        console.print("[yellow]No launchers detected on your system.[/yellow]")
        return

    # Create a Rich table for a modern look
    table = Table(
        title="Detected Launchers",
        caption="Use the [bold cyan]ID[/bold cyan] to target a specific launcher in other commands",
        title_style="bold magenta",
    )

    # Define columns
    table.add_column("ID", justify="center", style="cyan", no_wrap=True)
    table.add_column("Launcher Name", style="white")
    table.add_column("Mode", style="green")
    table.add_column("Root Path", style="dim")

    # Add rows using the index as the ID
    for idx, launcher in enumerate(launchers):
        table.add_row(
            str(idx),
            launcher.name,
            launcher.install_mode.value,
            str(launcher.root_path),
        )

    console.print(table)


@app.command(name="list-tools")
def list_supported_tools(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
) -> None:
    """
    List all compatibility tools supported by a specific launcher instance.
    """
    # 1. Get all launchers to resolve the ID
    launchers = detect_all_launchers()

    if not (0 <= launcher_id < len(launchers)):
        console.print(f"[red]Error: Launcher ID {launcher_id} is out of range.[/red]")
        raise typer.Exit(code=1)

    target_launcher = launchers[launcher_id]

    # 2. Filter tools using our generic function
    compatible_tools = get_tools_for_launcher(target_launcher)

    if not compatible_tools:
        console.print(f"[yellow]No compatible tools found for {target_launcher.name}.[/yellow]")
        return

    # 3. Display the results in a pretty table
    table = Table(
        title=f"Compatible Tools for [bold cyan]{target_launcher.name}[/bold cyan]"
        + f"({target_launcher.install_mode.value})",
        header_style="bold magenta",
    )

    table.add_column("Tool Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("More Info", style="blue")

    for tool in compatible_tools:
        table.add_row(tool.name, tool.description, tool.info_url)

    console.print(table)


@app.command(name="list-versions")
def list_versions(
    tool_name: str = typer.Argument(..., help="The name of the tool (e.g., 'GE-Proton')"),
    count: int = typer.Option(
        30, "--count", "-c", help="Number of versions to show", min=1, max=100
    ),
    page: int = typer.Option(1, "--page", "-p", help="Page number of the release list", min=1),
) -> None:
    """
    Fetch and list all available remote versions for a specific tool.
    """
    # 1. Find the installer by name
    installer = next((i for i in CT_INSTALLERS if i.name.lower() == tool_name.lower()), None)

    if not installer:
        console.print(f"[red]Error: Tool '{tool_name}' not found in registry.[/red]")
        raise typer.Exit(1)

    installer.request_config = state["request_config"]

    # 2. Fetch versions with a loading spinner
    try:
        with console.status(
            f"[bold blue]Fetching versions for {installer.name}...", spinner="dots"
        ):
            # Run the async fetch_releases method
            versions = asyncio.run(installer.fetch_releases(count=count, page=page))
    except Exception as e:
        console.print(f"[red]Failed to fetch versions: {e}[/red]")
        raise typer.Exit(1) from e

    if not versions:
        console.print(f"[yellow]No versions found for {installer.name}.[/yellow]")
        return

    # 3. Display in a table
    table = Table(title=f"Available Versions: [bold cyan]{installer.name}[/bold cyan]")
    table.add_column("Index", justify="right", style="dim")
    table.add_column("Version String", style="green")

    for idx, version in enumerate(versions):
        table.add_row(str(idx), version)

    console.print(table)


@app.command(name="install")
def install_tool(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
    tool_name: str = typer.Argument(..., help="Name of the tool to install (e.g., 'GE-Proton')"),
    version: str = typer.Argument(
        ..., help="Version to install (e.g., 'latest' or 'GE-Proton9-2')"
    ),
) -> None:
    """
    Download and install a compatibility tool for a specific launcher.
    """
    # 1. Resolve Launcher
    launchers = detect_all_launchers()
    if not (0 <= launcher_id < len(launchers)):
        console.print(f"[red]Error: Launcher ID {launcher_id} not found.[/red]")
        raise typer.Exit(1)

    target_launcher = launchers[launcher_id]

    # 2. Resolve Installer (Case-insensitive search)
    # We look through our registry for a tool with a matching name
    installer = next((i for i in CT_INSTALLERS if i.name.lower() == tool_name.lower()), None)

    if not installer:
        console.print(f"[red]Error: Tool '{tool_name}' is not supported.[/red]")
        raise typer.Exit(1)

    installer.request_config = state["request_config"]

    # 3. Check Compatibility
    if not installer.supports_launcher(target_launcher):
        console.print(
            f"[red]Error: {installer.name} does not support {target_launcher.name}.[/red]"
        )
        raise typer.Exit(1)

    # 4. Execute Installation (Handling the Async call)
    console.print(
        f"Preparing to install [bold cyan]{installer.name}[/bold cyan] "
        + f"to [bold green]{target_launcher.name}[/bold green]..."
    )

    try:
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            download_task = progress.add_task(f"Downloading {installer.name}...", total=None)

            def update_spinner(chunk_size: int, total_size: int) -> None:
                if progress.tasks[download_task].total is None and total_size > 0:
                    progress.update(download_task, total=total_size)
                progress.update(download_task, advance=chunk_size)

            asyncio.run(
                installer.install(version, target_launcher, progress_callback=update_spinner)
            )
        console.print(f"[bold green]Successfully installed {installer.name}![/bold green]")
        console.print(f"Please restart {target_launcher.name} to see the changes.")
    except Exception as e:
        console.print(f"[red]Installation failed: {e}[/red]")
        raise typer.Exit(1) from e


@app.command(name="list-installed")
def list_installed_tools(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
) -> None:
    """
    List all compatibility tools currently installed for a specific launcher.
    """
    launchers = detect_all_launchers()
    if not (0 <= launcher_id < len(launchers)):
        console.print(f"[red]Error: Launcher ID {launcher_id} not found.[/red]")
        raise typer.Exit(1)

    target_launcher = launchers[launcher_id]

    with console.status(
        f"[bold blue]Scanning {target_launcher.name} directories...", spinner="bouncingBar"
    ):
        installed_tools = target_launcher.get_installed_tools()

    if not installed_tools:
        console.print(
            f"[yellow]No custom compatibility tools found for {target_launcher.name}.[/yellow]"
        )
        return

    table = Table(title=f"Installed Tools: [bold cyan]{target_launcher.name}[/bold cyan]")
    table.add_column("Index", justify="right", style="dim")
    table.add_column("Tool Folder Name", style="green")
    table.add_column("Path", style="dim", overflow="ellipsis")

    for idx, tool in enumerate(sorted(installed_tools, key=lambda x: x.full_name), 1):
        table.add_row(str(idx), tool.full_name, str(tool.install_dir))

    console.print(table)


if __name__ == "__main__":
    app()
