from __future__ import annotations

import typer

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.core.models import Arch, CompatTool
from protondl.installers import CT_INSTALLERS
from protondl.launchers import detect_all_launchers


def get_launchers() -> list[Launcher]:
    """Return the list of detected launchers on the system."""
    return detect_all_launchers()


def select_launcher(launcher_id: int) -> Launcher:
    """
    Return a Launcher instance based on the provided numeric ID, starting from 1.
    The ID corresponds to the index shown in the 'list-launchers' command.

    Args:
        launcher_id (int): The numeric ID of the launcher to select.

    Returns:
        Launcher: The selected Launcher instance.

    Raises:
        typer.Exit: If the launcher_id is out of range.
    """

    launchers = get_launchers()
    idx = launcher_id - 1
    if not (0 <= idx < len(launchers)):
        typer.secho(f"Error: Launcher ID {launcher_id} is out of range.", fg="red")
        raise typer.Exit(code=1)

    return launchers[idx]


def resolve_installer(tool_name: str) -> CtInstaller | None:
    """
    Resolve a compatibility tool installer from a name or numeric identifier.

    Args:
        tool_name: human name or 1-based numeric ID of the tool.
        launcher: ignored; present to keep the API stable.

    Returns:
        The matching :class:`CtInstaller` instance, or ``None`` if no match
        exists.
    """
    installer = next(
        (i for i in CT_INSTALLERS if i.name.lower() == tool_name.lower()),
        None,
    )
    if installer:
        return installer

    if tool_name.isdigit():
        tool_id = int(tool_name) - 1
        if 0 <= tool_id < len(CT_INSTALLERS):
            return CT_INSTALLERS[tool_id]

    return None


def parse_arch(arch_str: str) -> Arch:
    """
    Parse an architecture string into an Arch enum value.

    Args:
        arch_str (str): The architecture string (e.g. "x86_64" or "aarch64").

    Returns:
        Arch: The matching Arch enum value.

    Raises:
        typer.Exit: If the architecture string is unknown.
    """
    try:
        return Arch(arch_str)
    except ValueError:
        supported = ", ".join(a.value for a in Arch)
        typer.secho(f"Error: Unknown architecture '{arch_str}'. Supported: {supported}.", fg="red")
        raise typer.Exit(code=1) from None


def resolve_installed_tool(installed_tools: list[CompatTool], tool_name: str) -> CompatTool | None:
    """
    Resolve an installed compatibility tool from a name or a 1-based index.
    The index refers to the position in the passed ``installed_tools`` list,
    matching the order shown by the 'list-installed' command.

    Args:
        installed_tools (list[CompatTool]): The list of installed tools to search.
        tool_name (str): The full name or the 1-based index of the tool.

    Returns:
        CompatTool | None: The matching tool, or ``None`` if no match exists.
    """
    if tool_name.isdigit():
        tool_idx = int(tool_name) - 1
        if 0 <= tool_idx < len(installed_tools):
            return installed_tools[tool_idx]
        return None

    return next(
        (tool for tool in installed_tools if tool.full_name.lower() == tool_name.lower()),
        None,
    )
