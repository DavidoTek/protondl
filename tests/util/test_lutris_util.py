import sqlite3
from pathlib import Path

import pytest

from protondl.util.lutris import get_lutris_game_config, get_lutris_game_list


def _create_pga_db(
    tmp_path: Path, rows: list[dict[str, object]], with_configpath: bool = True
) -> Path:
    pga_db_file = tmp_path / "pga.db"
    con = sqlite3.connect(pga_db_file)
    try:
        con.execute(
            """
            CREATE TABLE games (
                id INTEGER PRIMARY KEY,
                name TEXT,
                slug TEXT,
                installer_slug TEXT,
                runner TEXT,
                directory TEXT,
                installed INTEGER,
                installed_at INTEGER
                {}
            )
            """.format(", configpath TEXT" if with_configpath else "")
        )
        for row in rows:
            con.execute(
                """
                INSERT INTO games
                    (name, slug, installer_slug, runner, directory, installed, installed_at
                    {})
                VALUES (?, ?, ?, ?, ?, ?, ?{})
                """.format(
                    ", configpath" if with_configpath else "",
                    ", ?" if with_configpath else "",
                ),
                (
                    row.get("name", ""),
                    row.get("slug", ""),
                    row.get("installer_slug", ""),
                    row.get("runner", ""),
                    row.get("directory", ""),
                    row.get("installed", 1),
                    row.get("installed_at", 0),
                    *([row.get("configpath", "")] if with_configpath else []),
                ),
            )
        con.commit()
    finally:
        con.close()
    return pga_db_file


def _write_yaml(tmp_path: Path, rel_path: str, data: object) -> Path:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_get_lutris_game_list_returns_empty_when_no_pga_db(tmp_path: Path) -> None:
    assert get_lutris_game_list(tmp_path, tmp_path) == []


def test_get_lutris_game_list_reads_installed_games(tmp_path: Path) -> None:
    _create_pga_db(
        tmp_path,
        [
            {"slug": "doom", "name": "Doom", "runner": "wine", "directory": "/games/doom"},
            {"slug": "skyrim", "name": "Skyrim", "runner": "wine", "directory": "/games/skyrim"},
        ],
    )

    games = get_lutris_game_list(tmp_path, tmp_path)

    assert len(games) == 2
    assert games[0]["slug"] == "doom"
    assert games[0]["name"] == "Doom"
    assert games[0]["runner"] == "wine"
    assert games[0]["directory"] == "/games/doom"


def test_get_lutris_game_list_filters_uninstalled_games(tmp_path: Path) -> None:
    _create_pga_db(
        tmp_path,
        [
            {"slug": "installed", "name": "Installed Game", "installed": 1},
            {"slug": "removed", "name": "Removed Game", "installed": 0},
        ],
    )

    games = get_lutris_game_list(tmp_path, tmp_path)

    assert [game["slug"] for game in games] == ["installed"]


def test_get_lutris_game_list_reads_game_config_for_missing_directory(tmp_path: Path) -> None:
    _create_pga_db(
        tmp_path,
        [
            {
                "slug": "manual",
                "name": "Manual Game",
                "runner": "wine",
                "installer_slug": "",
                "directory": "",
            }
        ],
    )
    _write_yaml(tmp_path, "games/manual.yml", {"game": {"working_dir": "/games/manual"}})

    games = get_lutris_game_list(tmp_path, tmp_path)

    assert len(games) == 1
    assert games[0]["config"]["game"]["working_dir"] == "/games/manual"


def test_get_lutris_game_list_uses_configpath_for_exact_match(tmp_path: Path) -> None:
    _create_pga_db(
        tmp_path,
        [
            {
                "slug": "quake",
                "name": "Quake",
                "runner": "wine",
                "installer_slug": "",
                "directory": "",
                "configpath": "quake-manual",
            }
        ],
    )
    _write_yaml(
        tmp_path,
        "games/quake2-1234567890.yml",
        {"game": {"exe": "/games/quake2/game.exe"}},
    )
    _write_yaml(tmp_path, "games/quake-manual.yml", {"game": {"working_dir": "/games/quake"}})

    games = get_lutris_game_list(tmp_path, tmp_path)

    assert len(games) == 1
    assert games[0]["configpath"] == "quake-manual"
    assert games[0]["config"]["game"]["working_dir"] == "/games/quake"


def test_get_lutris_game_list_works_without_configpath_column(tmp_path: Path) -> None:
    _create_pga_db(
        tmp_path,
        [{"slug": "doom", "name": "Doom", "runner": "wine", "directory": "/games/doom"}],
        with_configpath=False,
    )

    games = get_lutris_game_list(tmp_path, tmp_path)

    assert len(games) == 1
    assert games[0]["slug"] == "doom"
    assert games[0]["configpath"] == ""


def test_get_lutris_game_list_handles_null_slug(tmp_path: Path) -> None:
    _create_pga_db(tmp_path, [{"slug": None, "name": "Broken Game", "runner": "wine"}])

    games = get_lutris_game_list(tmp_path, tmp_path)

    assert len(games) == 1
    assert games[0]["slug"] is None
    assert games[0]["config"] == {}


def test_get_lutris_game_list_raises_for_corrupt_pga_db(tmp_path: Path) -> None:
    pga_db_file = tmp_path / "pga.db"
    pga_db_file.write_bytes(b"not a sqlite database")

    with pytest.raises(ValueError, match="Loading the Lutris game list failed"):
        get_lutris_game_list(tmp_path, tmp_path)


def test_get_lutris_game_config_prefers_config_dir(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    _write_yaml(data_dir, "games/game.yml", {"game": {"exe": "/data/game.exe"}})
    _write_yaml(config_dir, "games/game.yml", {"game": {"exe": "/config/game.exe"}})

    config = get_lutris_game_config(data_dir, config_dir, "game", "", 0)

    assert config["game"]["exe"] == "/config/game.exe"


def test_get_lutris_game_config_falls_back_to_data_dir(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _write_yaml(data_dir, "games/game.yml", {"game": {"exe": "/data/game.exe"}})

    config = get_lutris_game_config(data_dir, tmp_path / "config", "game", "", 0)

    assert config["game"]["exe"] == "/data/game.exe"


def test_get_lutris_game_config_matches_installer_slug_and_timestamp(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path,
        "games/some-installer-1234567890.yml",
        {"game": {"exe": "/games/installed/game.exe"}},
    )

    config = get_lutris_game_config(tmp_path, tmp_path, "game", "some-installer", 1234567890)

    assert config["game"]["exe"] == "/games/installed/game.exe"


def test_get_lutris_game_config_uses_configpath(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path,
        "games/other-installer-9999999999.yml",
        {"game": {"exe": "/games/other/game.exe"}},
    )
    _write_yaml(tmp_path, "games/my-config.yml", {"game": {"exe": "/games/mine/game.exe"}})

    config = get_lutris_game_config(
        tmp_path, tmp_path, "other", "other-installer", 9999999999, "my-config"
    )

    assert config["game"]["exe"] == "/games/mine/game.exe"


def test_get_lutris_game_config_falls_back_to_slug(tmp_path: Path) -> None:
    _write_yaml(tmp_path, "games/manual.yml", {"game": {"exe": "/games/manual/game.exe"}})

    config = get_lutris_game_config(tmp_path, tmp_path, "manual", "some-installer", 123)

    assert config["game"]["exe"] == "/games/manual/game.exe"


def test_get_lutris_game_config_returns_empty_for_missing(tmp_path: Path) -> None:
    assert get_lutris_game_config(tmp_path, tmp_path, "missing", "", 0) == {}


def test_get_lutris_game_config_returns_empty_for_corrupt(tmp_path: Path) -> None:
    games_dir = tmp_path / "games"
    games_dir.mkdir(parents=True)
    (games_dir / "broken.yml").write_text("{broken", encoding="utf-8")

    assert get_lutris_game_config(tmp_path, tmp_path, "broken", "", 0) == {}


def test_get_lutris_game_config_returns_empty_for_non_dict(tmp_path: Path) -> None:
    _write_yaml(tmp_path, "games/list.yml", ["not", "a", "dict"])

    assert get_lutris_game_config(tmp_path, tmp_path, "list", "", 0) == {}
