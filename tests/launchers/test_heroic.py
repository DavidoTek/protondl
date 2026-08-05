import json
from pathlib import Path

import pytest

from protondl.core.base_launcher import Game
from protondl.core.models import CompatTool, CompatToolType, InstallMode
from protondl.launchers.heroic import DEFAULT_WINE_NAME, HeroicGame, HeroicLauncher
from protondl.util.helpers import json_safe_load


def _write(tmp_path: Path, rel_path: str, data: object) -> Path:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _install_tool(launcher: HeroicLauncher, tool_type: CompatToolType, name: str) -> Path:
    tools_dir = launcher.get_compatibility_tools_path(tool_type)
    tool_dir = tools_dir / name
    tool_dir.mkdir(parents=True, exist_ok=True)
    return tool_dir


def _create_launcher(tmp_path: Path) -> HeroicLauncher:
    return HeroicLauncher("Heroic", tmp_path, InstallMode.NATIVE)


def test_get_game_list_returns_installed_games(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)

    _write(
        tmp_path,
        "sideload_apps/library.json",
        {
            "games": [
                {
                    "app_name": "sideload-1",
                    "title": "Sideload Game",
                    "runner": "sideload",
                    "folder_name": "/games/Sideload Game",
                    "install": {"executable": "/games/Sideload Game/start.sh", "platform": "Linux"},
                }
            ]
        },
    )
    _write(
        tmp_path,
        "store_cache/gog_library.json",
        {
            "games": [
                {
                    "app_name": "1207658695",
                    "title": "Beneath a Steel Sky",
                    "runner": "gog",
                    "is_installed": False,
                },
                {
                    "app_name": "1207659013",
                    "title": "Treasure Adventure Game",
                    "runner": "gog",
                    "is_installed": False,
                },
                {
                    "app_name": "1435828982",
                    "title": "The Elder Scrolls: Arena",
                    "runner": "gog",
                    "is_installed": False,
                },
                {
                    "app_name": "gog-redist",
                    "title": "Galaxy Common Redistributables",
                    "runner": "gog",
                    "is_installed": True,
                    "install": {"is_dlc": True},
                },
            ]
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
                },
                {
                    "appName": "1207659013",
                    "install_path": "/games/Treasure Adventure Game",
                    "platform": "windows",
                    "executable": "",
                    "is_dlc": False,
                },
            ]
        },
    )
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
        "GamesConfig/Hornbill.json",
        {
            "Hornbill": {
                "wineVersion": {"bin": "/proton", "name": "GE-Proton10-14", "type": "proton"}
            },
            "version": "v0",
        },
    )

    games = launcher.get_game_list(cached=False)

    by_id = {game.id: game for game in games}
    assert set(by_id) == {"sideload-1", "1207658695", "1207659013", "gog-redist", "Hornbill"}

    assert by_id["Hornbill"].compat_tool_name == "GE-Proton10-14"
    assert by_id["Hornbill"].wine_type == "proton"
    assert by_id["Hornbill"].install_path == Path("/games/TheAltoCollection")
    assert by_id["Hornbill"].runner == "legendary"

    assert by_id["sideload-1"].is_installed is True
    assert by_id["sideload-1"].install_path == Path("/games/Sideload Game")

    assert by_id["1207658695"].runner == "gog"
    assert by_id["1207658695"].is_installed is True
    assert by_id["1207658695"].install_path == Path("/games/Beneath a Steel Sky")

    assert by_id["gog-redist"].is_dlc is True
    assert by_id["gog-redist"].is_installed is True

    assert all(game.is_installed for game in games)


def test_get_game_list_continues_when_one_store_is_broken(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    launcher = _create_launcher(tmp_path)

    _write(
        tmp_path,
        "legendaryConfig/legendary/installed.json",
        {"Hornbill": {"title": "The Alto Collection", "install_path": "/games/altoc"}},
    )
    broken = tmp_path / "nile_config" / "nile" / "installed.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{broken", encoding="utf-8")

    games = launcher.get_game_list(cached=False)

    assert [game.id for game in games] == ["Hornbill"]
    captured = capsys.readouterr()
    assert "Could not load the nile game list" in captured.out


def test_get_game_list_caches_and_rescans(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)

    _write(
        tmp_path,
        "sideload_apps/library.json",
        {"games": [{"app_name": "sideload-1", "title": "Sideload Game", "runner": "sideload"}]},
    )

    first = launcher.get_game_list(cached=False)
    assert [game.id for game in first] == ["sideload-1"]

    assert launcher.get_game_list() is first

    _write(
        tmp_path,
        "sideload_apps/library.json",
        {
            "games": [
                {"app_name": "sideload-1", "title": "Sideload Game", "runner": "sideload"},
                {"app_name": "sideload-2", "title": "Second Game", "runner": "sideload"},
            ]
        },
    )

    refreshed = launcher.get_game_list(cached=False)
    assert [game.id for game in refreshed] == ["sideload-2", "sideload-1"]


def test_set_games_tools_invalidates_cached_game_list(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _install_tool(launcher, CompatToolType.PROTON, "GE-Proton10-14")
    _write(
        tmp_path,
        "sideload_apps/library.json",
        {"games": [{"app_name": "sideload-1", "title": "Sideload Game", "runner": "sideload"}]},
    )

    first = launcher.get_game_list(cached=False)
    assert first[0].compat_tool_name == ""

    game = HeroicGame("sideload-1", "Sideload Game", tmp_path, "sideload", tmp_path)
    launcher.set_games_tools({game: "GE-Proton10-14"})

    refreshed = launcher.get_game_list()
    assert refreshed is not first
    assert refreshed[0].compat_tool_name == "GE-Proton10-14"


def test_get_game_list_raises_for_missing_root(tmp_path: Path) -> None:
    launcher = HeroicLauncher("Heroic", tmp_path / "not-here", InstallMode.NATIVE)

    with pytest.raises(ValueError, match="does not exist"):
        launcher.get_game_list(cached=False)


def test_get_game_config_returns_per_game_config(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "GamesConfig/Game1.json",
        {
            "Game1": {"wineVersion": {"name": "Wine-GE", "bin": "/wine", "type": "wine"}},
            "version": "v0",
        },
    )
    game = HeroicGame("Game1", "Game 1", tmp_path, "legendary", tmp_path)

    config = game.get_game_config()

    assert config["wineVersion"]["name"] == "Wine-GE"


def test_set_games_tools_writes_wine_version(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _install_tool(launcher, CompatToolType.PROTON, "GE-Proton10-14")
    game = HeroicGame("Game1", "Game 1", tmp_path, "legendary", tmp_path)

    launcher.set_games_tools({game: "GE-Proton10-14"})

    data = json_safe_load(tmp_path / "GamesConfig" / "Game1.json")
    assert data["Game1"]["wineVersion"] == {
        "bin": str(tmp_path / "tools" / "proton" / "GE-Proton10-14" / "proton"),
        "name": "GE-Proton10-14",
        "type": "proton",
    }


def test_set_games_tools_resets_to_default_wine(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _write(
        tmp_path,
        "GamesConfig/Game1.json",
        {
            "Game1": {
                "wineVersion": {"name": "GE-Proton10-14", "bin": "/proton", "type": "proton"}
            },
            "version": "v0",
            "explicit": True,
        },
    )
    game = HeroicGame("Game1", "Game 1", tmp_path, "legendary", tmp_path)

    launcher.set_games_tools({game: None})

    data = json_safe_load(tmp_path / "GamesConfig" / "Game1.json")
    assert data["Game1"]["wineVersion"] == {
        "bin": "",
        "name": DEFAULT_WINE_NAME,
        "type": "wine",
    }
    assert data["version"] == "v0"
    assert data["explicit"] is True


def test_set_games_tools_unknown_tool_raises_runtime_error(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    game = HeroicGame("Game1", "Game 1", tmp_path, "legendary", tmp_path)

    with pytest.raises(RuntimeError, match="Compatibility tool not found"):
        launcher.set_games_tools({game: "Not-Installed"})


def test_set_games_tools_rejects_non_heroic_game(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    foreign_game = Game("some-game", "Some Game", "", tmp_path)

    with pytest.raises(RuntimeError, match="not managed by Heroic"):
        launcher.set_games_tools({foreign_game: "GE-Proton"})


def test_get_global_tool_returns_matching_tool(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _install_tool(launcher, CompatToolType.PROTON, "GE-Proton10-14")
    _install_tool(launcher, CompatToolType.PROTON, "GE-Proton10-12")
    _write(
        tmp_path,
        "config.json",
        {
            "defaultSettings": {
                "wineVersion": {"bin": "/proton", "name": "GE-Proton10-12", "type": "proton"}
            }
        },
    )

    global_tool = launcher.get_global_tool(CompatToolType.PROTON)

    assert global_tool is not None
    assert global_tool.full_name == "GE-Proton10-12"


def test_get_global_tool_returns_none_when_not_set(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _install_tool(launcher, CompatToolType.PROTON, "GE-Proton10-14")
    _write(
        tmp_path,
        "config.json",
        {
            "defaultSettings": {
                "wineVersion": {"bin": "", "name": DEFAULT_WINE_NAME, "type": "wine"}
            }
        },
    )

    assert launcher.get_global_tool(CompatToolType.PROTON) is None


def test_set_global_tool_writes_config(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    tool_dir = _install_tool(launcher, CompatToolType.WINE, "Wine-GE")
    tool = CompatTool("Wine-GE", CompatToolType.WINE, tool_dir)

    launcher.set_global_tool(tool)

    data = json_safe_load(tmp_path / "config.json")
    assert data["defaultSettings"]["wineVersion"] == {
        "bin": str(tool_dir / "bin" / "wine"),
        "name": "Wine-GE",
        "type": "wine",
    }


def test_set_global_tool_preserves_existing_settings(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    tool_dir = _install_tool(launcher, CompatToolType.PROTON, "GE-Proton10-14")
    tool = CompatTool("GE-Proton10-14", CompatToolType.PROTON, tool_dir)
    _write(
        tmp_path,
        "config.json",
        {
            "defaultSettings": {"defaultInstallPath": "/home/user/Games/Heroic"},
            "version": "v0",
        },
    )

    launcher.set_global_tool(tool)

    data = json_safe_load(tmp_path / "config.json")
    assert data["defaultSettings"]["defaultInstallPath"] == "/home/user/Games/Heroic"
    assert data["defaultSettings"]["wineVersion"]["name"] == "GE-Proton10-14"


def test_get_global_tool_unsupported_type_raises(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)

    with pytest.raises(ValueError, match="HeroicLauncher only supports"):
        launcher.get_global_tool(CompatToolType.DXVK)


def test_set_global_tool_unsupported_type_raises(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    tool_dir = tmp_path / "tools" / "dxvk" / "dxvk-2.0"
    tool_dir.mkdir(parents=True)
    tool = CompatTool("dxvk-2.0", CompatToolType.DXVK, tool_dir)

    with pytest.raises(ValueError, match="HeroicLauncher only supports"):
        launcher.set_global_tool(tool)
