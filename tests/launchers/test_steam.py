from pathlib import Path
from typing import Any

import pytest

from protondl.core.models import CompatTool, CompatToolType, InstallMode
from protondl.launchers.steam import SteamAppType, SteamDeckCompatType, SteamGame, SteamLauncher
from protondl.util.steam import (
    get_steam_vdf_compat_tool_mapping,
    vdf_safe_load,
    write_steam_shortcuts,
)


def test_get_compatibility_tools_path(tmp_path: Path) -> None:
    """
    Test that the compatibility tools path is correctly determined
    and is created if it doesn't exist.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    path = launcher.get_compatibility_tools_path(CompatToolType.PROTON)
    assert path == tmp_path / "compatibilitytools.d"
    assert path.exists()


def test_get_installed_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that installed compatibility tools are correctly identified from the filesystem
    and from the Steam configuration files.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    path = launcher.get_compatibility_tools_path(CompatToolType.PROTON)
    config_path = tmp_path / "config"
    config_path.mkdir(parents=True, exist_ok=True)
    steamapps_path = tmp_path / "steamapps"
    common_path = steamapps_path / "common"
    common_path.mkdir(parents=True, exist_ok=True)

    official_proton_appid = "1493710"
    official_proton_name = "Proton Experimental"
    fixtures_dir = Path(__file__).parent

    libraryfolders_fixture = (fixtures_dir / "libraryfolders.vdf").read_text(encoding="utf-8")
    (config_path / "libraryfolders.vdf").write_text(
        libraryfolders_fixture.replace("/home/user/.local/share/Steam", tmp_path.as_posix()),
        encoding="utf-8",
    )
    (config_path / "config.vdf").write_text(
        (fixtures_dir / "config.vdf").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    appcache_path = tmp_path / "appcache"
    appcache_path.mkdir(parents=True, exist_ok=True)
    (appcache_path / "appinfo.vdf").write_bytes(b"dummy")

    launcher._cached_ctool_map = {
        official_proton_appid: {
            "name": official_proton_name,
            "from_oslist": "windows",
        }
    }

    def mock_parse_appinfo(
        _file: Any, mapper: type[dict[Any, Any]] = dict
    ) -> tuple[None, list[dict[str, Any]]]:
        return None, [
            {
                "appid": int(official_proton_appid),
                "data": {
                    "appinfo": {
                        "common": {
                            "name": official_proton_name,
                        },
                        "extended": {},
                    }
                },
            }
        ]

    monkeypatch.setattr("protondl.launchers.steam.parse_appinfo", mock_parse_appinfo)

    (path / "GE-Proton-Test").mkdir()

    installed_tools = launcher.get_installed_tools([CompatToolType.PROTON])
    assert len(installed_tools) == 2
    installed_tool_names = {tool.full_name for tool in installed_tools}
    assert installed_tool_names == {"GE-Proton-Test", "Proton Experimental"}
    assert all(tool.tool_type == CompatToolType.PROTON for tool in installed_tools)


def test_get_steamdeck_compatibility_returns_recommended_runtime_and_category() -> None:
    """
    Test that SteamGame returns the recommended runtime and Steam Deck category.
    """
    game = SteamGame(275850, "No Man's Sky", Path("/games/No Man's Sky"))
    game.deck_compatibility = {
        "configuration": {"recommended_runtime": "proton_9"},
        "category": SteamDeckCompatType.VERIFIED.value,
    }

    recommended_runtime, compat_type = game.get_steamdeck_compatibility()

    assert recommended_runtime == "proton_9"
    assert compat_type == SteamDeckCompatType.VERIFIED


def test_get_steamdeck_compatibility_returns_unknown_for_missing_category() -> None:
    """
    Test that SteamGame returns UNKNOWN when the Steam Deck category is missing.
    """
    game = SteamGame(275850, "No Man's Sky", Path("/games/No Man's Sky"))
    missing_category: Any = {"configuration": {"recommended_runtime": "proton_9"}}
    game.deck_compatibility = missing_category

    recommended_runtime, compat_type = game.get_steamdeck_compatibility()

    assert recommended_runtime == "proton_9"
    assert compat_type == SteamDeckCompatType.UNKNOWN


def test_get_game_list_reads_libraryfolders_and_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that get_game_list reads appids from libraryfolders and applies config mapping.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    config_path = tmp_path / "config"
    config_path.mkdir(parents=True, exist_ok=True)

    fixtures_dir = Path(__file__).parent
    libraryfolders_fixture = (fixtures_dir / "libraryfolders.vdf").read_text(encoding="utf-8")
    (config_path / "libraryfolders.vdf").write_text(
        libraryfolders_fixture.replace("/home/user/.local/share/Steam", tmp_path.as_posix()),
        encoding="utf-8",
    )
    (config_path / "config.vdf").write_text(
        (fixtures_dir / "config.vdf").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    monkeypatch.setattr(launcher, "_update_steam_game_list_with_app_info", lambda games: games)

    games = launcher.get_game_list(shortcuts=False, cached=False)

    assert {game.appid for game in games} == {275850, 1070560, 1391110, 1493710}
    assert all(game.libraryfolder_id == "0" for game in games)

    mapped_game = next(game for game in games if game.appid == 275850)
    assert mapped_game.compat_tool_name == "GE-Proton10-14"

    cached_games = launcher.get_game_list(shortcuts=False)
    assert cached_games is games


def test_set_games_tools(tmp_path: Path) -> None:
    """
    Test that compatibility tool mappings are updated, removed, and added.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    config_path = tmp_path / "config"
    config_path.mkdir(parents=True, exist_ok=True)

    fixtures_dir = Path(__file__).parent
    config_vdf_file = config_path / "config.vdf"
    config_vdf_file.write_text(
        (fixtures_dir / "config.vdf").read_text(encoding="utf-8"), encoding="utf-8"
    )

    launcher.set_games_tools(
        {
            SteamGame(275850, "No Man's Sky", tmp_path): "GE-Proton10-99",
            SteamGame(0, "", tmp_path): None,
        }
    )

    config_data = vdf_safe_load(config_vdf_file)
    compat_tool_mapping = get_steam_vdf_compat_tool_mapping(config_data)

    assert compat_tool_mapping["275850"]["name"] == "GE-Proton10-99"
    assert "0" not in compat_tool_mapping


def test_get_global_tool_returns_matching_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that get_global_tool returns the installed tool matching the global mapping.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    config_path = tmp_path / "config"
    config_path.mkdir(parents=True, exist_ok=True)

    fixtures_dir = Path(__file__).parent
    (config_path / "config.vdf").write_text(
        (fixtures_dir / "config.vdf").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    installed_tools = [
        CompatTool(
            "GE-Proton10-14",
            CompatToolType.PROTON,
            tmp_path / "compatibilitytools.d" / "GE-Proton10-14",
        ),
        CompatTool(
            "GE-Proton10-12",
            CompatToolType.PROTON,
            tmp_path / "compatibilitytools.d" / "GE-Proton10-12",
        ),
    ]
    monkeypatch.setattr(launcher, "get_installed_tools", lambda _tool_types: installed_tools)

    global_tool = launcher.get_global_tool(CompatToolType.PROTON)

    assert global_tool is not None
    assert global_tool.full_name == "GE-Proton10-12"
    assert global_tool.tool_type == CompatToolType.PROTON


def test_get_global_tool_returns_none_when_no_mapping_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that get_global_tool returns None when no installed tool matches the global mapping.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    config_path = tmp_path / "config"
    config_path.mkdir(parents=True, exist_ok=True)

    fixtures_dir = Path(__file__).parent
    (config_path / "config.vdf").write_text(
        (fixtures_dir / "config.vdf").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    installed_tools = [
        CompatTool(
            "GE-Proton9-99",
            CompatToolType.PROTON,
            tmp_path / "compatibilitytools.d" / "GE-Proton9-99",
        )
    ]
    monkeypatch.setattr(launcher, "get_installed_tools", lambda _tool_types: installed_tools)

    assert launcher.get_global_tool(CompatToolType.PROTON) is None


def test_set_global_tool_updates_global_mapping(tmp_path: Path) -> None:
    """
    Test that set_global_tool updates the global compat tool mapping (appid 0).
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    config_path = tmp_path / "config"
    config_path.mkdir(parents=True, exist_ok=True)

    fixtures_dir = Path(__file__).parent
    config_vdf_file = config_path / "config.vdf"
    config_vdf_file.write_text(
        (fixtures_dir / "config.vdf").read_text(encoding="utf-8"), encoding="utf-8"
    )

    launcher.set_global_tool(
        CompatTool(
            "GE-Proton10-22",
            CompatToolType.PROTON,
            tmp_path / "compatibilitytools.d" / "GE-Proton10-22",
        )
    )

    config_data = vdf_safe_load(config_vdf_file)
    compat_tool_mapping = get_steam_vdf_compat_tool_mapping(config_data)

    assert compat_tool_mapping["0"]["name"] == "GE-Proton10-22"


def test_get_compatibility_tools_path_unsupported_type_raises(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)

    with pytest.raises(ValueError, match="SteamLauncher only supports"):
        launcher.get_compatibility_tools_path(CompatToolType.WINE)


def test_get_global_tool_unsupported_type_raises(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)

    with pytest.raises(ValueError, match="SteamLauncher only supports"):
        launcher.get_global_tool(CompatToolType.WINE)


def test_set_global_tool_unsupported_type_raises(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)

    with pytest.raises(ValueError, match="SteamLauncher only supports"):
        launcher.set_global_tool(
            CompatTool(
                "wine-tkg",
                CompatToolType.WINE,
                tmp_path / "compatibilitytools.d" / "wine-tkg",
            )
        )


def test_remove_tool_rejects_steam_managed_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that SteamLauncher.remove_tool rejects tools managed by Steam.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    steam_managed_dir = tmp_path / "steamapps" / "common" / "Proton Experimental"
    steam_managed_dir.mkdir(parents=True)

    managed_game = SteamGame(1493710, "Proton Experimental", steam_managed_dir)
    managed_game.app_type = SteamAppType.COMPAT_TOOL
    monkeypatch.setattr(launcher, "get_game_list", lambda: [managed_game])

    with pytest.raises(ValueError, match="managed by Steam"):
        launcher.remove_tool(
            CompatTool("Proton Experimental", CompatToolType.PROTON, steam_managed_dir)
        )

    assert steam_managed_dir.exists()


def test_get_game_list_raises_when_libraryfolders_cannot_be_loaded(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    config_path = tmp_path / "config"
    config_path.mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError, match="Could not load library data"):
        launcher.get_game_list(shortcuts=False, cached=False)


def test_get_game_list_continues_when_config_mapping_cannot_be_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    config_path = tmp_path / "config"
    config_path.mkdir(parents=True, exist_ok=True)

    fixtures_dir = Path(__file__).parent
    libraryfolders_fixture = (fixtures_dir / "libraryfolders.vdf").read_text(encoding="utf-8")
    (config_path / "libraryfolders.vdf").write_text(
        libraryfolders_fixture.replace("/home/user/.local/share/Steam", tmp_path.as_posix()),
        encoding="utf-8",
    )

    monkeypatch.setattr(launcher, "_update_steam_game_list_with_app_info", lambda games: games)

    games = launcher.get_game_list(shortcuts=False, cached=False)

    assert {game.appid for game in games} == {275850, 1070560, 1391110, 1493710}
    assert all(game.compat_tool_name == "" for game in games)


def test_get_shortcuts_returns_shortcuts(tmp_path: Path) -> None:
    """
    Test that non-Steam shortcuts are returned as SteamGame entries.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    write_steam_shortcuts(
        tmp_path,
        [
            {
                "user": "123",
                "sid": "0",
                "appid": 3722544834,
                "name": "Test Game",
                "exe": "/opt/games/test.exe",
                "startdir": "/opt/games",
                "icon": "/opt/games/test.png",
            }
        ],
    )

    shortcuts = launcher.get_shortcuts()

    assert len(shortcuts) == 1
    shortcut = shortcuts[0]
    assert shortcut.name == "Test Game"
    assert shortcut.appid == 3722544834
    assert shortcut.shortcut_id == "0"
    assert shortcut.shortcut_user == "123"
    assert shortcut.shortcut_exe == "/opt/games/test.exe"
    assert shortcut.shortcut_startdir == "/opt/games"
    assert shortcut.shortcut_icon == "/opt/games/test.png"
    assert shortcut.app_type == SteamAppType.GAME


def test_get_shortcuts_returns_empty_list_when_no_shortcuts(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)

    assert launcher.get_shortcuts() == []


def test_add_shortcut_uses_most_recent_user(tmp_path: Path) -> None:
    """
    Test that a shortcut is added to the most recently logged in user if
    there are no existing shortcuts.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "loginusers.vdf").write_text(
        '"users"\n'
        "{\n"
        '\t"76561197960265851"\n'
        "\t{\n"
        '\t\t"AccountName"\t\t"user1"\n'
        '\t\t"MostRecent"\t\t"1"\n'
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )

    game = launcher.add_shortcut("Test Game", "/opt/games/test.exe")

    assert game.shortcut_user == "123"
    assert game.shortcut_id == "0"
    assert game.appid == 3722544834

    shortcuts = launcher.get_shortcuts()
    assert len(shortcuts) == 1
    assert shortcuts[0].name == "Test Game"
    assert shortcuts[0].shortcut_exe == "/opt/games/test.exe"


def test_add_shortcut_uses_most_common_user(tmp_path: Path) -> None:
    """
    Test that a shortcut is added to the most common user of existing
    shortcuts.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    write_steam_shortcuts(
        tmp_path,
        [
            {
                "user": "123",
                "sid": "0",
                "appid": 1000,
                "name": "Game",
                "exe": "/games/game",
                "startdir": "",
                "icon": "",
            },
            {
                "user": "456",
                "sid": "0",
                "appid": 1001,
                "name": "Game 2",
                "exe": "/games/game2",
                "startdir": "",
                "icon": "",
            },
            {
                "user": "123",
                "sid": "1",
                "appid": 1002,
                "name": "Game 3",
                "exe": "/games/game3",
                "startdir": "",
                "icon": "",
            },
        ],
    )

    game = launcher.add_shortcut("New Game", "/opt/games/new.exe")

    assert game.shortcut_user == "123"
    assert game.shortcut_id == "2"

    shortcuts = launcher.get_shortcuts()
    assert len([s for s in shortcuts if s.shortcut_user == "123"]) == 3


def test_add_shortcut_with_explicit_user(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)

    game = launcher.add_shortcut("Game", "/opt/games/game", user="999")

    assert game.shortcut_user == "999"
    assert game.shortcut_id == "0"


def test_add_shortcut_raises_without_name_or_exe(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)

    with pytest.raises(ValueError, match="name and executable"):
        launcher.add_shortcut("", "/opt/games/game", user="123")

    with pytest.raises(ValueError, match="name and executable"):
        launcher.add_shortcut("Game", "", user="123")


def test_add_shortcut_raises_without_user(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)

    with pytest.raises(ValueError, match="No Steam user found"):
        launcher.add_shortcut("Game", "/opt/games/game")


def test_update_shortcuts(tmp_path: Path) -> None:
    """
    Test that the name, executable, start directory and icon of a shortcut
    are updated.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    write_steam_shortcuts(
        tmp_path,
        [
            {
                "user": "123",
                "sid": "0",
                "appid": 1000,
                "name": "Game",
                "exe": "/games/game",
                "startdir": "",
                "icon": "",
            }
        ],
    )

    shortcuts = launcher.get_shortcuts()
    shortcuts[0].name = "Renamed"
    shortcuts[0].shortcut_exe = "/games/renamed"
    shortcuts[0].shortcut_startdir = "/games"
    shortcuts[0].shortcut_icon = "/icons/renamed.png"

    launcher.update_shortcuts(shortcuts)

    updated = launcher.get_shortcuts()
    assert len(updated) == 1
    assert updated[0].name == "Renamed"
    assert updated[0].shortcut_exe == "/games/renamed"
    assert updated[0].shortcut_startdir == "/games"
    assert updated[0].shortcut_icon == "/icons/renamed.png"


def test_update_shortcuts_raises_without_shortcut_id(tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)

    with pytest.raises(ValueError, match="no shortcut_id"):
        launcher.update_shortcuts([SteamGame(1000, "Game", tmp_path)])


def test_remove_shortcuts(tmp_path: Path) -> None:
    """
    Test that shortcuts are removed from the shortcuts.vdf file.
    """
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    write_steam_shortcuts(
        tmp_path,
        [
            {
                "user": "123",
                "sid": "0",
                "appid": 1000,
                "name": "Game",
                "exe": "/games/game",
                "startdir": "",
                "icon": "",
            },
            {
                "user": "123",
                "sid": "1",
                "appid": 1001,
                "name": "Game 2",
                "exe": "/games/game2",
                "startdir": "",
                "icon": "",
            },
        ],
    )

    shortcuts = launcher.get_shortcuts()
    launcher.remove_shortcuts([shortcuts[0]])

    remaining = launcher.get_shortcuts()
    assert len(remaining) == 1
    assert remaining[0].shortcut_id == "1"
