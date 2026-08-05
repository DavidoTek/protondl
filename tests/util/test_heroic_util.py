import json
from pathlib import Path

import pytest

from protondl.util.heroic import (
    get_gog_installed_entry,
    get_heroic_default_settings,
    get_heroic_game_config,
    get_heroic_gog_executable,
    get_heroic_gog_games,
    get_heroic_legendary_games,
    get_heroic_nile_games,
    get_heroic_sideload_games,
    resolve_heroic_install_path,
)


def _write(tmp_path: Path, rel_path: str, data: object) -> Path:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_get_heroic_sideload_games_returns_empty_when_no_library(tmp_path: Path) -> None:
    assert get_heroic_sideload_games(tmp_path) == []


def test_get_heroic_sideload_games_reads_games_key(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "sideload_apps/library.json",
        {"games": [{"app_name": "sideload-1", "title": "Sideload Game", "runner": "sideload"}]},
    )

    games = get_heroic_sideload_games(tmp_path)

    assert games == [{"app_name": "sideload-1", "title": "Sideload Game", "runner": "sideload"}]


def test_get_heroic_gog_games_reads_store_cache_library(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "store_cache/gog_library.json",
        {
            "games": [{"app_name": "1207658695", "title": "Beneath a Steel Sky", "runner": "gog"}],
            "__timestamp": 0,
        },
    )
    _write(
        tmp_path,
        "gog_store/installed.json",
        {
            "installed": [
                {
                    "appName": "1207658695",
                    "install_path": "/games/Beneath a Steel Sky",
                    "platform": "windows",
                    "executable": "",
                    "is_dlc": False,
                }
            ]
        },
    )

    games = get_heroic_gog_games(tmp_path)

    assert len(games) == 1
    game = games[0]
    assert game["app_name"] == "1207658695"
    assert game["is_installed"] is True
    assert game["install_path"] == "/games/Beneath a Steel Sky"
    assert game["platform"] == "windows"
    assert game["is_dlc"] is False


def test_get_heroic_gog_games_falls_back_to_legacy_library(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "gog_store/library.json",
        {"games": [{"app_name": "123", "title": "Legacy GOG Game", "runner": "gog"}]},
    )

    games = get_heroic_gog_games(tmp_path)

    assert len(games) == 1
    assert games[0]["app_name"] == "123"
    assert games[0]["is_installed"] is False


def test_get_heroic_gog_games_raises_for_corrupt_library(tmp_path: Path) -> None:
    broken = tmp_path / "store_cache" / "gog_library.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError):
        get_heroic_gog_games(tmp_path)


def test_get_gog_installed_entry_returns_matching_entry(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "gog_store/installed.json",
        {
            "installed": [
                {"appName": "1207658695", "install_path": "/games/a"},
                {"appName": "1207659013", "install_path": "/games/b"},
            ]
        },
    )

    assert get_gog_installed_entry(tmp_path, "1207659013") == {
        "appName": "1207659013",
        "install_path": "/games/b",
    }
    assert get_gog_installed_entry(tmp_path, "missing") == {}


def test_get_heroic_legendary_games_reads_new_layout(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "legendaryConfig/legendary/installed.json",
        {
            "Hornbill": {
                "title": "The Alto Collection",
                "install_path": "/games/TheAltoCollection",
                "executable": "The Alto Collection.exe",
                "platform": "Windows",
                "is_dlc": False,
            }
        },
    )
    _write(
        tmp_path,
        "store_cache/legendary_library.json",
        {
            "library": [
                {
                    "app_name": "Hornbill",
                    "title": "The Alto Collection",
                    "developer": "Land & Sea",
                    "store_url": "https://store.epicgames.com",
                }
            ]
        },
    )

    games = get_heroic_legendary_games(tmp_path)

    assert len(games) == 1
    game = games[0]
    assert game["app_name"] == "Hornbill"
    assert game["runner"] == "legendary"
    assert game["is_installed"] is True
    assert game["install_path"] == "/games/TheAltoCollection"
    assert game["developer"] == "Land & Sea"


def test_get_heroic_legendary_games_falls_back_to_legacy_path(tmp_path: Path) -> None:
    root = tmp_path / "config"
    _write(
        tmp_path,
        "legendary/installed.json",
        {"LegacyGame": {"title": "Legacy Game", "install_path": "/games/legacy"}},
    )

    games = get_heroic_legendary_games(root)

    assert len(games) == 1
    assert games[0]["app_name"] == "LegacyGame"
    assert games[0]["install_path"] == "/games/legacy"


def test_get_heroic_legendary_games_returns_empty_without_installed(tmp_path: Path) -> None:
    assert get_heroic_legendary_games(tmp_path) == []


def test_get_heroic_nile_games_reads_installed_and_library(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "nile_config/nile/installed.json",
        {"AmazonGame": {"title": "Amazon Game", "install_path": "/games/amazon"}},
    )
    _write(
        tmp_path,
        "store_cache/nile_library.json",
        {
            "library": [
                {"app_name": "AmazonGame", "title": "Amazon Game", "developer": "Amazon Dev"}
            ]
        },
    )

    games = get_heroic_nile_games(tmp_path)

    assert len(games) == 1
    game = games[0]
    assert game["runner"] == "nile"
    assert game["is_installed"] is True
    assert game["developer"] == "Amazon Dev"


def test_resolve_heroic_install_path_prefers_install_path(tmp_path: Path) -> None:
    entry = {"install_path": "~/Games/Heroic/Absolute", "folder_name": "Relative"}
    assert resolve_heroic_install_path(entry) == Path("~/Games/Heroic/Absolute").expanduser()


def test_resolve_heroic_install_path_resolves_relative_folder(tmp_path: Path) -> None:
    entry = {"folder_name": "My Game"}
    default = tmp_path / "Games"
    assert resolve_heroic_install_path(entry, default) == default / "My Game"


def test_resolve_heroic_install_path_uses_executable_parent(tmp_path: Path) -> None:
    entry = {"install": {"executable": "/home/user/games/My Game/start.sh"}}
    assert resolve_heroic_install_path(entry) == Path("/home/user/games/My Game")


def test_resolve_heroic_install_path_returns_none_without_info(tmp_path: Path) -> None:
    assert resolve_heroic_install_path({}) is None


def test_get_heroic_game_config_returns_entry_for_app_name(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "GamesConfig/Game1.json",
        {
            "Game1": {"wineVersion": {"name": "GE-Proton10-14", "bin": "/bin/proton"}},
            "version": "v0",
        },
    )

    config = get_heroic_game_config(tmp_path, "Game1")

    assert config["wineVersion"]["name"] == "GE-Proton10-14"


def test_get_heroic_game_config_returns_empty_for_missing_or_corrupt(tmp_path: Path) -> None:
    assert get_heroic_game_config(tmp_path, "Missing") == {}

    broken = tmp_path / "GamesConfig" / "Broken.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{broken", encoding="utf-8")
    assert get_heroic_game_config(tmp_path, "Broken") == {}


def test_get_heroic_default_settings_returns_default_settings(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "config.json",
        {
            "defaultSettings": {
                "defaultInstallPath": "/home/user/Games/Heroic",
                "wineVersion": {"name": "Wine-GE", "bin": "/bin/wine", "type": "wine"},
            },
            "version": "v0",
        },
    )

    settings = get_heroic_default_settings(tmp_path)

    assert settings["defaultInstallPath"] == "/home/user/Games/Heroic"
    assert settings["wineVersion"]["name"] == "Wine-GE"


def test_get_heroic_default_settings_returns_empty_for_missing(tmp_path: Path) -> None:
    assert get_heroic_default_settings(tmp_path) == {}


def test_get_heroic_gog_executable_uses_start_sh_for_native_games(tmp_path: Path) -> None:
    assert get_heroic_gog_executable(tmp_path, "1207658695", {}, "linux") == "start.sh"


def test_get_heroic_gog_executable_uses_start_sh_for_windows_without_wine_config(
    tmp_path: Path,
) -> None:
    assert get_heroic_gog_executable(tmp_path, "1207658695", {}, "") == "start.sh"


def test_get_heroic_gog_executable_reads_playtask(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "goggame-1207658695.info",
        {
            "name": "Beneath a Steel Sky",
            "playTasks": [
                {"name": "setup", "path": "setup.exe"},
                {"name": "Beneath a Steel Sky", "path": "game/windows/sky.exe"},
            ],
        },
    )

    executable = get_heroic_gog_executable(
        tmp_path, "1207658695", {"name": "Wine", "bin": "/bin/wine", "type": "wine"}, "windows"
    )

    assert executable == "game/windows/sky.exe"


def test_get_heroic_gog_executable_returns_empty_without_gameinfo(tmp_path: Path) -> None:
    executable = get_heroic_gog_executable(
        tmp_path, "1207658695", {"name": "Wine", "bin": "/bin/wine", "type": "wine"}, "windows"
    )

    assert executable == ""
