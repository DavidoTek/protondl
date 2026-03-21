from pathlib import Path
from typing import TypedDict

import vdf
from steam.utils.appcache import parse_appinfo


class CompatToolUsage(TypedDict):
    """Represents the compatibility tool configuration for a specific game."""

    name: str
    config: str
    priority: str


class CompatToolInfo(TypedDict):
    """Information about an installed Steam compatibility tool."""

    name: str
    from_oslist: str


def vdf_safe_load(vdf_file: Path) -> dict:  # type: ignore
    """
    Loads a vdf file and returns its contents as a dict.

    Args:
        vdf_file (Path): Path to the vdf file

    Returns:
        dict: Content of the vdf file

    Raises:
        ValueError: In case loading the vdf fails
    """
    data = {}

    try:
        # Replace Unicode errors, see https://github.com/DavidoTek/ProtonUp-Qt/issues/424
        with open(vdf_file, encoding="utf-8", errors="replace") as f:
            data = vdf.loads(f.read())
    except Exception as e:
        raise ValueError(f"Loading {vdf_file} failed: {e}") from e

    if not isinstance(data, dict):
        # Apparently, vdf.loads() can return None (issue #481)
        raise ValueError(f"Loading {vdf_file} did not return a dict, but {type(data)}: {data}")

    return data


def get_steam_vdf_compat_tool_mapping(config_data: dict) -> dict[str, CompatToolUsage]:  # type: ignore
    """
    Get the game compatibility tool mapping from the Steam configuration.
    Maps the appid to the compatibility tool used by that game.

    Args:
        config_data (dict): Data from config.vdf. Load it using vdf_safe_load first.

    Returns:
        dict[str, CompatToolUsage]: Game compatibility tool mapping

    Raises:
        ValueError: If the configuration does not contain the 'valve' key
    """
    s = config_data.get("InstallConfigStore", {}).get("Software", {})

    # Key may be 'Valve' or 'valve', see https://github.com/DavidoTek/ProtonUp-Qt/issues/226
    c = s.get("Valve") or s.get("valve")
    if not c:
        raise ValueError("Steam config does not contain the 'valve' key (ignore case)")

    m = c.get("Steam", {}).get("CompatToolMapping", {})

    return m  # type: ignore


def get_steam_ctool_info(steam_root: Path) -> dict[str, CompatToolInfo]:
    """
    Get a map with information about the compatibility tools.
    Maps the appid of the tool to information about that tool.

    Args:
        steam_root (Path): Steam root directory

    Returns:
        dict[str, CompatToolInfo]: Maps the appid to compatibility tool info

    Raises:
        ValueError: If fetching Steam compatibilty tool info failed.
    """
    appinfo_file = steam_root / "appcache" / "appinfo.vdf"
    if not appinfo_file.is_file():
        raise ValueError(f"Steam app info does not exist: {appinfo_file}")

    ctool_map = {}
    compat_tools = {}
    try:
        with open(appinfo_file, "rb") as f:
            _, apps = parse_appinfo(f, mapper=dict)
            for steam_app in apps:
                if steam_app.get("appid") == 891390:
                    compat_tools = (
                        steam_app.get("data", {})
                        .get("appinfo", {})
                        .get("extended", {})
                        .get("compat_tools", {})
                    )
                    break
    except Exception as e:
        raise ValueError(f"Error getting compatibility tool map from appinfo.vdf: {e}") from e
    else:
        for t in compat_tools:
            ctool_map[str(compat_tools.get(t, {}).get("appid", ""))] = CompatToolInfo(
                name=t, from_oslist=compat_tools.get(t, {}).get("from_oslist", "")
            )

    return ctool_map
