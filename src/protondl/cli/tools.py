import asyncio

import typer
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from protondl.cli import app, console, state
from protondl.cli.helpers import (
    parse_arch,
    resolve_installed_tool,
    resolve_installer,
    select_launcher,
)
from protondl.core.models import CompatToolType
from protondl.installers import CT_INSTALLERS, get_tools_for_launcher
from protondl.util.helpers import detect_host_arch


@app.command(name="list-tools")
def list_supported_tools(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
) -> None:
    """
    List all compatibility tools supported by a specific launcher instance.
    """
    target_launcher = select_launcher(launcher_id)
    compatible_tools = get_tools_for_launcher(target_launcher)
    compatible_tools.sort(key=lambda t: CT_INSTALLERS.index(t))

    if not compatible_tools:
        console.print(f"[yellow]No compatible tools found for {target_launcher.name}.[/yellow]")
        return

    table = Table(
        title=f"Compatible Tools for [bold cyan]{target_launcher.name}[/bold cyan]"
        + f"({target_launcher.install_mode.value})",
        header_style="bold magenta",
    )

    table.add_column("ID", justify="center", style="cyan", no_wrap=True)
    table.add_column("Tool Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("More Info", style="blue")

    for tool in compatible_tools:
        global_id = CT_INSTALLERS.index(tool) + 1
        table.add_row(str(global_id), tool.name, tool.description, tool.info_url)

    console.print(table)


@app.command(name="list-versions")
def list_versions(
    tool_name: str = typer.Argument(
        ..., help="The name or global ID of the tool (e.g., 'GE-Proton' or '1')"
    ),
    count: int = typer.Option(
        30, "--count", "-c", help="Number of versions to show", min=1, max=100
    ),
    page: int = typer.Option(1, "--page", "-p", help="Page number of the release list", min=1),
    arch: str | None = typer.Option(
        None,
        "--arch",
        help=(
            "Filter versions by architecture (e.g., 'x86_64' or 'aarch64'). "
            "If omitted, all architectures are listed."
        ),
    ),
) -> None:
    """
    Fetch and list all available remote versions for a specific tool.
    """
    installer = resolve_installer(tool_name)

    if not installer:
        console.print(f"[red]Error: Tool '{tool_name}' not found in registry.[/red]")
        raise typer.Exit(1)

    requested_arch = parse_arch(arch) if arch else None
    if requested_arch is not None and requested_arch not in installer.supported_archs:
        supported = ", ".join(a.value for a in installer.supported_archs)
        console.print(
            f"[red]Error: Architecture '{requested_arch.value}' is not supported by "
            f"{installer.name}. Supported: {supported}.[/red]"
        )
        raise typer.Exit(1)

    installer.request_config = state["request_config"]

    try:
        with console.status(
            f"[bold blue]Fetching versions for {installer.name}...", spinner="dots"
        ):
            versions = asyncio.run(installer.fetch_releases(count=count, page=page))
    except Exception as e:
        console.print(f"[red]Failed to fetch versions: {e}[/red]")
        raise typer.Exit(1) from e

    if requested_arch is not None:
        versions = [release for release in versions if requested_arch in release.archs]

    if not versions:
        console.print(f"[yellow]No versions found for {installer.name}.[/yellow]")
        return

    table = Table(title=f"Available Versions: [bold cyan]{installer.name}[/bold cyan]")
    table.add_column("Version String", style="green")

    show_archs = len(installer.supported_archs) > 1
    if show_archs:
        table.add_column("Architectures", style="dim")

    for release in versions:
        row = [release.version]
        if show_archs:
            row.append(", ".join(a.value for a in release.archs))
        table.add_row(*row)

    console.print(table)


@app.command(name="install")
def install_tool(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
    tool_name: str = typer.Argument(
        ..., help="Name or ID of the tool to install (e.g., 'GE-Proton' or '1')"
    ),
    version: str = typer.Argument(
        ..., help="Version to install (e.g., 'latest' or 'GE-Proton9-2')"
    ),
    arch: str | None = typer.Option(
        None,
        "--arch",
        help=(
            "Architecture to install (e.g., 'x86_64' or 'aarch64'). "
            "Defaults to the host architecture if supported by the tool, otherwise x86_64."
        ),
    ),
) -> None:
    """
    Download and install a compatibility tool for a specific launcher.
    """
    target_launcher = select_launcher(launcher_id)
    installer = resolve_installer(tool_name)

    if not installer:
        console.print(f"[red]Error: Tool '{tool_name}' is not supported.[/red]")
        raise typer.Exit(1)

    requested_arch = parse_arch(arch) if arch else None
    if requested_arch is not None and requested_arch not in installer.supported_archs:
        supported = ", ".join(a.value for a in installer.supported_archs)
        console.print(
            f"[red]Error: Architecture '{requested_arch.value}' is not supported by "
            f"{installer.name}. Supported: {supported}.[/red]"
        )
        raise typer.Exit(1)

    installer.request_config = state["request_config"]

    if not installer.supports_launcher(target_launcher):
        console.print(
            f"[red]Error: {installer.name} does not support {target_launcher.name}.[/red]"
        )
        raise typer.Exit(1)

    if requested_arch is None:
        host_arch = detect_host_arch()
        if host_arch not in installer.supported_archs:
            console.print(
                f"[yellow]Note: {installer.name} does not provide a {host_arch.value} build; "
                "installing the x86_64 build.[/yellow]"
            )

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

            info = asyncio.run(
                installer.install(
                    version,
                    target_launcher,
                    arch=requested_arch,
                    progress_callback=update_spinner,
                )
            )
        arch_name = info.arch.value if info.arch else "unknown"
        console.print(
            f"[bold green]Successfully installed {installer.name} ({arch_name})![/bold green]"
        )
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
    target_launcher = select_launcher(launcher_id)

    with console.status(
        f"[bold blue]Scanning {target_launcher.name} directories...", spinner="bouncingBar"
    ):
        installed_tools = target_launcher.get_installed_tools()

    if not installed_tools:
        console.print(
            f"[yellow]No custom compatibility tools found for {target_launcher.name}.[/yellow]"
        )
        return

    global_tool_names = []
    for tool_type in CompatToolType:
        try:
            global_tool = target_launcher.get_global_tool(tool_type)
            if global_tool:
                global_tool_names.append(global_tool.full_name)
        except Exception:
            pass

    table = Table(title=f"Installed Tools: [bold cyan]{target_launcher.name}[/bold cyan]")
    table.add_column("Index", justify="right", style="dim")
    table.add_column("Tool Name", style="green")
    table.add_column("Type", style="cyan")
    table.add_column("Path", style="dim", overflow="ellipsis")

    for idx, tool in enumerate(sorted(installed_tools, key=lambda x: x.full_name), 1):
        is_global = tool.full_name in global_tool_names
        table.add_row(
            str(idx),
            tool.full_name,
            tool.tool_type.value + ("*" if is_global else ""),
            str(tool.install_dir),
        )

    console.print(table)


@app.command(name="remove")
def remove_tool(
    launcher_id: int = typer.Argument(..., help="The ID of the launcher from 'list-launchers'"),
    tool_name: str = typer.Argument(
        ...,
        help=(
            "Name or index of the tool from 'list-installed' " + "(e.g., 'GE-Proton10-12' or '1')"
        ),
    ),
) -> None:
    """
    Remove an installed compatibility tool from a launcher.
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

    selected_tool = resolve_installed_tool(installed_tools, tool_name)

    if not selected_tool:
        console.print(
            "[red]Tool not found. Use 'list-installed <launcher_id>'"
            + "to find a valid name/index.[/red]"
        )
        raise typer.Exit(code=1)

    try:
        target_launcher.remove_tool(selected_tool)
    except Exception as e:
        console.print(f"[red]Failed to remove tool: {e}[/red]")
        raise typer.Exit(code=1) from e

    console.print(
        f"[bold green]Successfully removed {selected_tool.full_name} "
        + f"from {target_launcher.name}![/bold green]"
    )
    console.print(f"Please restart {target_launcher.name} to see the changes.")
