from __future__ import annotations

import typer

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
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
