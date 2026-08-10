from __future__ import annotations

import json
import platform
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from protondl.core.models import (
    Arch,
    CompatTool,
    RequestConfig,
    ToolUpdate,
    UpdateCheckResult,
)

if TYPE_CHECKING:
    from protondl.core.base_launcher import Launcher


def detect_host_arch() -> Arch:
    """
    Detects the CPU architecture of the current host.

    Returns:
        Arch: The detected host architecture. Unknown architectures default to Arch.X86_64.
    """
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return Arch.X86_64
    if machine in ("aarch64", "arm64"):
        return Arch.AARCH64
    return Arch.X86_64


def json_safe_load(json_file: Path) -> dict[str, Any]:
    """
    Loads a JSON file and returns its contents as a dict.

    Args:
        json_file (Path): Path to the JSON file.

    Returns:
        dict: Content of the JSON file.

    Raises:
        ValueError: In case loading the JSON file fails.
    """
    try:
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"Loading {json_file} failed: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Loading {json_file} did not return a dict, but {type(data)}: {data}")

    return cast(dict[str, Any], data)


def batch_update_games_tools(
    launcher: Launcher, from_tool: CompatTool | str, to_tool: CompatTool
) -> int:
    """
    Updates the compatibility tool for multiple games in batch.
    The from_tool can be specified as a CompatTool instance (exact version match)
    or as a string (matches any tool name containing the string).

    Args:
        launcher: The game launcher instance to operate on.
        from_tool: The compatibility tool to replace.
            Can be a CompatTool instance (exact version) or a string (tool name, e.g., "GE-Proton").
        to_tool: The new compatibility tool to set for the affected games.

    Returns:
        int: The number of games that were updated.

    Raises:
        RuntimeError: If updating the games' compatibility tools failed.
    """
    games = launcher.get_game_list()

    if isinstance(from_tool, str):
        games_to_update = [game for game in games if from_tool in game.compat_tool_name]
    else:
        games_to_update = [game for game in games if game.compat_tool_name == from_tool.full_name]

    game_tool_map = {game: to_tool.full_name for game in games_to_update}

    try:
        launcher.set_games_tools(game_tool_map)
    except RuntimeError as e:
        raise RuntimeError(f"Batch update of games' compatibility tools failed: {e}") from e

    return len(games_to_update)


async def check_for_updates(
    launcher: Launcher, request_config: RequestConfig | None = None
) -> UpdateCheckResult:
    """
    Checks all installed compatibility tools of a launcher for available updates.

    The latest version of each compatibility tool class is fetched once using its
    CtInstaller. Compatibility tools for which no CtInstaller can be determined
    (or for which fetching the latest version fails) are reported as unchecked.

    Args:
        launcher: The game launcher instance to operate on.
        request_config: Optional configuration for API requests, including auth tokens.

    Returns:
        UpdateCheckResult: The compatibility tools with an available update
            (including the latest version), the tools that are already at the
            newest version, and the tools that could not be checked.
    """
    from protondl.installers import get_installer_by_name
    from protondl.util.version_file import read_version_file

    installed_tools = launcher.get_installed_tools()
    unchecked: list[str] = []
    tools_by_installer: dict[str, list[CompatTool]] = {}
    versions_by_installer: dict[str, list[str]] = {}

    for tool in installed_tools:
        info = read_version_file(tool.install_dir)
        if info is None:
            unchecked.append(tool.full_name)
            continue

        installer = get_installer_by_name(info.compat_tool)
        if installer is None:
            unchecked.append(tool.full_name)
            continue

        if request_config is not None:
            installer.request_config = request_config

        tools_by_installer.setdefault(installer.name, []).append(tool)
        versions_by_installer.setdefault(installer.name, []).append(info.version)

    updates: list[ToolUpdate] = []
    up_to_date: list[str] = []
    for tool_name, tools in tools_by_installer.items():
        installer = get_installer_by_name(tool_name)
        assert installer is not None

        try:
            releases = await installer.fetch_releases(count=1)
        except Exception:
            unchecked.extend(tool.full_name for tool in tools)
            continue

        if not releases:
            unchecked.extend(tool.full_name for tool in tools)
            continue

        latest_version = releases[0].version
        installed_versions = versions_by_installer[tool_name]
        if latest_version not in installed_versions:
            updates.append(
                ToolUpdate(
                    compat_tool_name=tool_name,
                    latest_version=latest_version,
                    installed_versions=installed_versions,
                    installed_tools=tools,
                )
            )
        else:
            up_to_date.append(tool_name)

    return UpdateCheckResult(updates=updates, up_to_date=up_to_date, unchecked=unchecked)


async def update_compatibility_tools(
    launcher: Launcher,
    updates: list[ToolUpdate],
    keep_old: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
    request_config: RequestConfig | None = None,
) -> None:
    """
    Installs the newest version of all given compatibility tools.

    If keep_old is False, all older versions of the compatibility tools are removed
    after the new version was installed successfully.

    Args:
        launcher: The game launcher instance to operate on.
        updates: The compatibility tools to update, including the latest version.
        keep_old: Whether to keep older versions of the compatibility tools.
        progress_callback: Optional callback receiving the number of completed
            tools and the total number of tools to update.
        request_config: Optional configuration for API requests, including auth tokens.

    Raises:
        ValueError: If no CtInstaller exists for one of the compatibility tools.
    """
    from protondl.installers import get_installer_by_name

    total = len(updates)
    for index, update in enumerate(updates):
        installer = get_installer_by_name(update.compat_tool_name)
        if installer is None:
            raise ValueError(
                f"No installer found for compatibility tool '{update.compat_tool_name}'."
            )

        if request_config is not None:
            installer.request_config = request_config

        await installer.install(update.latest_version, launcher)

        if not keep_old:
            for tool in update.installed_tools:
                launcher.remove_tool(tool)

        if progress_callback is not None:
            progress_callback(index + 1, total)
