from __future__ import annotations

from pathlib import Path

import typer
from rich.progress import Progress, TaskID

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.core.models import Arch, CompatTool, InstallProgress
from protondl.installers import CT_INSTALLERS
from protondl.launchers import (
    LAUNCHER_TYPE_MAP,
    create_launcher_from_path,
    detect_all_launchers,
    is_valid_launcher_home,
)


def get_launchers() -> list[Launcher]:
    """Return the list of detected launchers on the system."""
    return detect_all_launchers()


def select_launcher(launcher: str, *, allow_missing_path: bool = False) -> Launcher:
    """
    Return a Launcher instance based on a launcher spec.

    The spec can be either the numeric ID of a detected launcher (starting from 1,
    as shown by 'list-launchers'), or a '<type>:<path>' spec pointing to a custom
    installation path (e.g. 'steam:~/mySteam' for a non-standard Steam install).

    Custom paths are validated: they must exist and look like a data directory of
    the given launcher type. Set ``allow_missing_path`` to True to skip the checks,
    e.g. for the 'install' command, which creates the path on demand.

    Args:
        launcher (str): The launcher ID or '<type>:<path>' spec to select.
        allow_missing_path (bool): If True, do not reject a path that does not
            exist or does not look like a launcher data directory yet.

    Returns:
        Launcher: The selected Launcher instance.

    Raises:
        typer.Exit: If the launcher spec is invalid, the ID is out of range,
            or the custom path is invalid.
    """

    if launcher.isdigit():
        launchers = get_launchers()
        launcher_id = int(launcher)
        idx = launcher_id - 1
        if not (0 <= idx < len(launchers)):
            typer.secho(f"Error: Launcher ID {launcher_id} is out of range.", fg="red")
            raise typer.Exit(code=1)
        return launchers[idx]

    launcher_type, sep, launcher_path = launcher.partition(":")
    if not sep or not launcher_path:
        typer.secho(
            "Error: Invalid launcher spec. Use the ID from 'list-launchers' "
            + "or a '<type>:<path>' spec (e.g. 'steam:~/mySteam').",
            fg="red",
        )
        raise typer.Exit(code=1)

    if launcher_type.lower() not in LAUNCHER_TYPE_MAP:
        supported = ", ".join(LAUNCHER_TYPE_MAP)
        typer.secho(
            f"Error: Unknown launcher type '{launcher_type}'. Supported types: {supported}.",
            fg="red",
        )
        raise typer.Exit(code=1)

    root_path = Path(launcher_path).expanduser()
    if not allow_missing_path:
        if not root_path.is_dir():
            typer.secho(f"Error: Launcher path does not exist: {root_path}", fg="red")
            raise typer.Exit(code=1)
        if not is_valid_launcher_home(launcher_type, root_path):
            typer.secho(
                f"Error: '{root_path}' is not a valid {launcher_type} installation directory.",
                fg="red",
            )
            raise typer.Exit(code=1)

    try:
        return create_launcher_from_path(launcher_type, root_path)
    except ValueError as e:
        typer.secho(f"Error: {e}", fg="red")
        raise typer.Exit(code=1) from None


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


def update_install_progress(progress: Progress, task_id: TaskID, event: InstallProgress) -> None:
    """
    Applies an InstallProgress event to a rich progress task.

    The task description is set to the current step, prefixed with the tool name
    when the event is part of an update run. Steps with a known total render a
    progress bar, steps without one show an indeterminate (pulsing) bar.

    Args:
        progress: The rich Progress instance to update.
        task_id: The task within the Progress instance to update.
        event: The InstallProgress event to apply.
    """
    label = event.step.value
    if event.tool:
        label = f"{event.tool}: {label}"
    if event.total > 0:
        progress.update(task_id, description=label, total=event.total, completed=event.current)
    else:
        progress.update(task_id, description=label, total=None)
