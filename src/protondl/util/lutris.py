import sqlite3
from pathlib import Path
from typing import Any

import yaml

LUTRIS_GAMELIST_QUERY = (
    "SELECT slug, name, runner, installer_slug, installed_at, directory, configpath "
    "FROM games WHERE installed = 1"
)
LUTRIS_GAMELIST_QUERY_LEGACY = (
    "SELECT slug, name, runner, installer_slug, installed_at, directory "
    "FROM games WHERE installed = 1"
)


def get_lutris_game_list(root_path: Path, config_dir: Path) -> list[dict[str, Any]]:
    """
    Returns the installed game entries from Lutris' pga.db.

    The entries are read from the `games` table, filtered to installed games.
    The `directory` field may be empty for games added manually to Lutris; in
    that case the game's install directory has to be resolved from its
    configuration file.

    Args:
        root_path (Path): Lutris data directory containing pga.db.
        config_dir (Path): Lutris configuration directory, used to look up the
            game configuration files for entries without an install directory.

    Returns:
        list[dict]: The installed game entries.

    Raises:
        ValueError: If the pga.db file exists but cannot be read.
    """
    pga_db_file = root_path / "pga.db"
    if not pga_db_file.is_file():
        return []

    entries: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(pga_db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            query, has_configpath = _games_query(cur)
            cur.execute(query)
            for row in cur.fetchall():
                slug = row["slug"]
                name = row["name"]
                runner = row["runner"]
                installer_slug = row["installer_slug"]
                installed_at = row["installed_at"]
                directory = row["directory"]
                if has_configpath:
                    configpath = row["configpath"] or ""
                else:
                    configpath = ""
                config = get_lutris_game_config(
                    root_path, config_dir, slug, installer_slug, installed_at, configpath
                )
                entries.append(
                    {
                        "slug": slug,
                        "name": name,
                        "runner": runner,
                        "installer_slug": installer_slug,
                        "installed_at": installed_at,
                        "directory": directory,
                        "configpath": configpath,
                        "config": config,
                    }
                )
    except sqlite3.Error as e:
        raise ValueError(f"Loading the Lutris game list failed: {e}") from e

    return entries


def _games_query(cur: sqlite3.Cursor) -> tuple[str, bool]:
    """
    Returns the query for the installed games and whether the `configpath`
    column is available in the database.
    """
    cur.execute("PRAGMA table_info(games)")
    has_configpath = any(row[1] == "configpath" for row in cur.fetchall())
    if has_configpath:
        return LUTRIS_GAMELIST_QUERY, True
    return LUTRIS_GAMELIST_QUERY_LEGACY, False


def get_lutris_game_config(
    root_path: Path,
    config_dir: Path,
    slug: str,
    installer_slug: str,
    installed_at: int,
    configpath: str = "",
) -> dict[str, Any]:
    """
    Returns the game configuration of a Lutris game.

    Game configurations are stored as YAML files in the Lutris data directory
    (`<root_path>/games`) or, on older installations, in the configuration
    directory (`<config_dir>/games`). The `configpath` stored in Lutris'
    pga.db identifies the exact configuration file (`<configpath>.yml`); if it
    is not set, a file matching the installer slug and the installed timestamp
    is used (games installed via an installer), otherwise a file containing
    the game's slug (manually added games).

    Args:
        root_path (Path): Lutris data directory.
        config_dir (Path): Lutris configuration directory.
        slug (str): The game's slug.
        installer_slug (str): The slug of the installer used to install the game.
        installed_at (int): The timestamp when the game was installed.
        configpath (str): The game's configuration id from pga.db, if known.

    Returns:
        dict: The game's configuration, or an empty dict if no matching file
            exists or it cannot be loaded.
    """
    for games_dir in (config_dir / "games", root_path / "games"):
        config_file = _find_game_config_file(
            games_dir, slug, installer_slug, installed_at, configpath
        )
        if config_file is not None:
            return _load_lutris_game_config(config_file)
    return {}


def _find_game_config_file(
    games_dir: Path,
    slug: str,
    installer_slug: str,
    installed_at: int,
    configpath: str = "",
) -> Path | None:
    """
    Finds the configuration file for a game inside a Lutris games directory.

    An exact match on the game's configpath is preferred (Lutris stores the
    exact configuration id in its database), followed by a file matching the
    installer slug and the installed timestamp (used for games installed via an
    installer), otherwise a file matching the game's slug is used (manually
    added games).

    Args:
        games_dir (Path): A Lutris `games` directory.
        slug (str): The game's slug.
        installer_slug (str): The slug of the installer used to install the game.
        installed_at (int): The timestamp when the game was installed.
        configpath (str): The game's configuration id from pga.db, if known.

    Returns:
        Path | None: The path to the configuration file, or None if no match
            was found.
    """
    if not games_dir.is_dir():
        return None

    if configpath:
        config_file = games_dir / f"{configpath}.yml"
        if config_file.parent == games_dir and config_file.is_file():
            return config_file

    try:
        config_files = list(games_dir.iterdir())
    except OSError:
        return None

    config_files_by_stem = {
        config_file.stem: config_file
        for config_file in config_files
        if config_file.is_file() and config_file.suffix == ".yml"
    }

    if installer_slug and installed_at:
        installer_match = config_files_by_stem.get(f"{installer_slug}-{installed_at}")
        if installer_match is not None:
            return installer_match

    if slug:
        slug_match = config_files_by_stem.get(slug)
        if slug_match is not None:
            return slug_match

    return None


def _load_lutris_game_config(config_file: Path) -> dict[str, Any]:
    """
    Loads a Lutris game configuration file.

    Args:
        config_file (Path): Path to the game's YAML configuration file.

    Returns:
        dict: The game's configuration, or an empty dict if the file cannot
            be loaded.
    """
    try:
        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}

    return data if isinstance(data, dict) else {}
