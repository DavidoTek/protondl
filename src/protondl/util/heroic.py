from pathlib import Path
from typing import Any

from protondl.util.helpers import json_safe_load


def _get_list_of_dicts(data: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    """
    Extracts a list of dict entries from a JSON object using the first
    key that contains a list. Non-dict entries are skipped.

    Args:
        data (dict): JSON object to extract entries from.
        keys (str): Candidate keys, tried in order.

    Returns:
        list[dict]: The list of dict entries.
    """
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _app_name_of(entry: dict[str, Any]) -> str | None:
    """
    Returns the app name of a raw Heroic entry, which is stored under
    'appName' in installed entries and 'app_name' in library entries.

    Args:
        entry (dict): Raw Heroic JSON entry.

    Returns:
        str | None: The app name, or None if it is missing.
    """
    value = entry.get("appName", entry.get("app_name"))
    return value if isinstance(value, str) else None


def resolve_heroic_install_path(
    entry: dict[str, Any], default_install_path: Path | None = None
) -> Path | None:
    """
    Resolves the install directory of a raw Heroic entry.

    The install path is taken from the top-level 'install_path', the nested
    'install.install_path', the 'folder_name' (absolute or relative to
    Heroic's default install path) or the parent of 'install.executable'.

    Args:
        entry (dict): Raw Heroic JSON entry.
        default_install_path (Path | None): Heroic's default install directory
            used to resolve relative folder names.

    Returns:
        Path | None: The resolved install directory, or None if it cannot be
            determined.
    """
    install_path = entry.get("install_path")
    if isinstance(install_path, str) and install_path:
        return Path(install_path).expanduser()

    install = entry.get("install")
    if isinstance(install, dict):
        install_path = install.get("install_path")
        if isinstance(install_path, str) and install_path:
            return Path(install_path).expanduser()

    folder_name = entry.get("folder_name")
    if isinstance(folder_name, str) and folder_name:
        folder_path = Path(folder_name).expanduser()
        if folder_path.is_absolute():
            return folder_path
        if default_install_path is not None:
            return default_install_path / folder_path

    if isinstance(install, dict):
        executable = install.get("executable")
        if isinstance(executable, str) and executable:
            return Path(executable).expanduser().parent

    return None


def get_heroic_sideload_games(heroic_path: Path) -> list[dict[str, Any]]:
    """
    Returns the sideloaded game entries from sideload_apps/library.json.

    Args:
        heroic_path (Path): Heroic root directory.

    Returns:
        list[dict]: The sideloaded game entries.

    Raises:
        ValueError: If the library file exists but cannot be loaded.
    """
    library_file = heroic_path / "sideload_apps" / "library.json"
    if not library_file.is_file():
        return []
    data = json_safe_load(library_file)
    return _get_list_of_dicts(data, "games", "library")


def get_heroic_gog_installed_entries(heroic_path: Path) -> list[dict[str, Any]]:
    """
    Returns the installed GOG game entries from gog_store/installed.json.

    Args:
        heroic_path (Path): Heroic root directory.

    Returns:
        list[dict]: The installed GOG game entries.

    Raises:
        ValueError: If the file exists but cannot be loaded.
    """
    installed_file = heroic_path / "gog_store" / "installed.json"
    if not installed_file.is_file():
        return []
    data = json_safe_load(installed_file)
    return _get_list_of_dicts(data, "installed")


def get_heroic_gog_games(heroic_path: Path) -> list[dict[str, Any]]:
    """
    Returns the GOG library entries, enriched with install information from
    gog_store/installed.json.

    Modern Heroic versions store the library in store_cache/gog_library.json,
    older versions in gog_store/library.json. Both are supported.

    Args:
        heroic_path (Path): Heroic root directory.

    Returns:
        list[dict]: The GOG game entries.

    Raises:
        ValueError: If a library file exists but cannot be loaded.
    """
    library_file = heroic_path / "store_cache" / "gog_library.json"
    if not library_file.is_file():
        library_file = heroic_path / "gog_store" / "library.json"
    if not library_file.is_file():
        return []
    data = json_safe_load(library_file)

    installed_entries: dict[str, dict[str, Any]] = {}
    for entry in get_heroic_gog_installed_entries(heroic_path):
        app_name = _app_name_of(entry)
        if app_name is not None:
            installed_entries[app_name] = entry

    games = []
    for entry in _get_list_of_dicts(data, "games", "library"):
        app_name = entry.get("app_name")
        if not isinstance(app_name, str) or not app_name:
            continue
        installed = installed_entries.get(app_name)
        merged = dict(entry)
        if installed is not None:
            merged = {**installed, **entry}
            merged["is_installed"] = True
            merged["install_path"] = installed.get("install_path", "")
            merged["platform"] = installed.get("platform", "")
            merged["executable"] = installed.get("executable", "")
            merged["is_dlc"] = installed.get("is_dlc", entry.get("is_dlc", False))
        merged.setdefault("runner", "gog")
        merged.setdefault("title", "")
        merged.setdefault("is_installed", entry.get("is_installed", False))
        games.append(merged)

    return games


def get_gog_installed_entry(heroic_path: Path, app_name: str) -> dict[str, Any]:
    """
    Returns the installed GOG entry for the given app name, or an empty dict
    if the game is not installed.

    Args:
        heroic_path (Path): Heroic root directory.
        app_name (str): The game's app name.

    Returns:
        dict: The installed game entry.
    """
    for entry in get_heroic_gog_installed_entries(heroic_path):
        if entry.get("appName") == app_name:
            return entry
    return {}


def get_heroic_gog_executable(
    install_path: Path, app_name: str, wine_info: dict[str, Any], platform: str
) -> str:
    """
    Returns the executable for a GOG game.

    Native Linux games always use 'start.sh'. Windows games store the
    executable inside the 'goggame-<app_name>.info' play task metadata file.

    Args:
        install_path (Path): The game's install directory.
        app_name (str): The game's app name.
        wine_info (dict): The configured wineVersion of the game.
        platform (str): The platform of the installed game ('linux', 'windows' or empty).

    Returns:
        str: The executable path, or an empty string if it cannot be found.
    """
    if platform == "linux":
        return "start.sh"

    gameinfo_file = install_path / f"goggame-{app_name}.info"
    if not gameinfo_file.is_file():
        return "" if wine_info else "start.sh"

    try:
        data = json_safe_load(gameinfo_file)
    except ValueError:
        return ""

    game_name = data.get("name")
    if not isinstance(game_name, str):
        return ""

    play_tasks = data.get("playTasks")
    if not isinstance(play_tasks, list):
        return ""

    for play_task in play_tasks:
        if not isinstance(play_task, dict):
            continue
        if str(play_task.get("name", "")).lower() == game_name.lower():
            executable = play_task.get("path")
            if isinstance(executable, str):
                return executable

    return ""


def _get_legendary_installed_path(heroic_path: Path) -> Path | None:
    """
    Returns the path to the legendary installed.json file.

    Modern Heroic versions store it in legendaryConfig/legendary/installed.json,
    older versions in <heroic_path>/../legendary/installed.json.

    Args:
        heroic_path (Path): Heroic root directory.

    Returns:
        Path | None: The path, or None if neither file exists.
    """
    new_path = heroic_path / "legendaryConfig" / "legendary" / "installed.json"
    if new_path.is_file():
        return new_path
    legacy_path = heroic_path.parent / "legendary" / "installed.json"
    if legacy_path.is_file():
        return legacy_path
    return None


def _load_library_index(heroic_path: Path, filename: str, key: str) -> dict[str, dict[str, Any]]:
    """
    Loads a store cache library file into an index keyed by app name.

    Args:
        heroic_path (Path): Heroic root directory.
        filename (str): The library file name inside store_cache.
        key (str): The top-level key containing the library entries.

    Returns:
        dict: Map of app name to library entry.
    """
    library_file = heroic_path / "store_cache" / filename
    if not library_file.is_file():
        return {}
    try:
        data = json_safe_load(library_file)
    except ValueError:
        return {}

    index: dict[str, dict[str, Any]] = {}
    for entry in _get_list_of_dicts(data, key):
        app_name = entry.get("app_name")
        if isinstance(app_name, str) and app_name:
            index[app_name] = entry
    return index


def get_heroic_legendary_games(heroic_path: Path) -> list[dict[str, Any]]:
    """
    Returns the installed Epic Games (legendary) game entries.

    Entries are read from the legendary installed.json file and enriched with
    metadata (developer, artwork, store URL) from store_cache/legendary_library.json.

    Args:
        heroic_path (Path): Heroic root directory.

    Returns:
        list[dict]: The installed legendary game entries.

    Raises:
        ValueError: If the installed.json file exists but cannot be loaded.
    """
    installed_path = _get_legendary_installed_path(heroic_path)
    if installed_path is None:
        return []
    data = json_safe_load(installed_path)
    library = _load_library_index(heroic_path, "legendary_library.json", "library")

    games = []
    for app_name, game_data in data.items():
        if not isinstance(game_data, dict):
            continue
        merged = {**game_data, **library.get(app_name, {})}
        merged["app_name"] = app_name
        merged["runner"] = "legendary"
        merged["is_installed"] = True
        merged.setdefault("title", "")
        games.append(merged)

    return games


def _get_nile_installed_path(heroic_path: Path) -> Path | None:
    """
    Returns the path to the Nile (Amazon Games) installed.json file.

    Modern Heroic versions store it in nile_config/nile/installed.json,
    older versions in nile_store/installed.json.

    Args:
        heroic_path (Path): Heroic root directory.

    Returns:
        Path | None: The path, or None if neither file exists.
    """
    candidates = (
        heroic_path / "nile_config" / "nile" / "installed.json",
        heroic_path / "nile_store" / "installed.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def get_heroic_nile_games(heroic_path: Path) -> list[dict[str, Any]]:
    """
    Returns the installed Amazon Games (Nile) game entries.

    Entries are read from the Nile installed.json file and enriched with
    metadata from store_cache/nile_library.json.

    Args:
        heroic_path (Path): Heroic root directory.

    Returns:
        list[dict]: The installed Nile game entries.

    Raises:
        ValueError: If the installed.json file exists but cannot be loaded.
    """
    installed_path = _get_nile_installed_path(heroic_path)
    if installed_path is None:
        return []
    data = json_safe_load(installed_path)
    library = _load_library_index(heroic_path, "nile_library.json", "library")

    games = []
    for app_name, game_data in data.items():
        if not isinstance(game_data, dict):
            continue
        merged = {**game_data, **library.get(app_name, {})}
        merged["app_name"] = app_name
        merged["runner"] = "nile"
        merged["is_installed"] = True
        merged.setdefault("title", "")
        games.append(merged)

    return games


def get_heroic_game_config(heroic_path: Path, app_name: str) -> dict[str, Any]:
    """
    Returns the per-game configuration of a game from GamesConfig/<app_name>.json.

    Args:
        heroic_path (Path): Heroic root directory.
        app_name (str): The game's app name.

    Returns:
        dict: The game's configuration, or an empty dict if the file is
            missing or cannot be loaded.
    """
    config_file = heroic_path / "GamesConfig" / f"{app_name}.json"
    if not config_file.is_file():
        return {}
    try:
        data = json_safe_load(config_file)
    except ValueError:
        return {}
    entry = data.get(app_name)
    return entry if isinstance(entry, dict) else {}


def get_heroic_default_settings(heroic_path: Path) -> dict[str, Any]:
    """
    Returns the default settings from Heroic's config.json.

    Args:
        heroic_path (Path): Heroic root directory.

    Returns:
        dict: The default settings, or an empty dict if the file is missing
            or cannot be loaded.
    """
    config_file = heroic_path / "config.json"
    if not config_file.is_file():
        return {}
    try:
        data = json_safe_load(config_file)
    except ValueError:
        return {}
    settings = data.get("defaultSettings")
    return settings if isinstance(settings, dict) else {}
