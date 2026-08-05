from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from protondl.core.base_launcher import Launcher
    from protondl.core.models import CompatTool


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
