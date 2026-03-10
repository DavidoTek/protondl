from __future__ import annotations

import typer

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.installers import CT_INSTALLERS, get_tools_for_launcher
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
        ValueError: If the launcher_id is out of range.
    """

    launchers = get_launchers()
    idx = launcher_id - 1
    if not (0 <= idx < len(launchers)):
        typer.secho(f"Error: Launcher ID {launcher_id} is out of range.", fg="red")
        raise typer.Exit(code=1)

    return launchers[idx]


def resolve_installer(tool_name: str, launcher: Launcher | None = None) -> CtInstaller | None:
    """
    Resolve a compatibility tool installer based on the provided tool name or numeric ID.

    Args:
        tool_name (str): The name or numeric ID of the tool to resolve.
        launcher (Launcher, optional): The launcher context to filter tools by. If provided,
            only tools compatible with this launcher will be considered for numeric ID resolution.

    Returns:
        CtInstaller | None: The resolved installer instance, or None if not found.
    """

    installer = next(
        (i for i in CT_INSTALLERS if i.name.lower() == tool_name.lower()),
        None,
    )
    if installer:
        return installer

    if tool_name.isdigit():
        tool_id = int(tool_name) - 1
        if launcher:
            candidates = get_tools_for_launcher(launcher)
        else:
            candidates = []
            for ln in get_launchers():
                candidates.extend(get_tools_for_launcher(ln))

        if 0 <= tool_id < len(candidates):
            return candidates[tool_id]

    return None
