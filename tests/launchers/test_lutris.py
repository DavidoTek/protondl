import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml

from protondl.core.models import (
    CompatTool,
    CompatToolType,
    CompatToolVersionInfo,
    InstallMode,
)
from protondl.launchers.lutris import LutrisLauncher
from protondl.util.version_file import write_version_file


def test_get_installed_tools_detects_types_via_version_file(tmp_path: Path) -> None:
    """
    Lutris stores Proton and Wine tools in the same folder (runners/wine).
    The tool type must be resolved from protondl_version.json.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    wine_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON)

    proton_tool = wine_dir / "GE-Proton11-3"
    wine_tool = wine_dir / "wine-tkg-master"
    manual_tool = wine_dir / "Some-Manual-Tool"
    for tool_dir in (proton_tool, wine_tool, manual_tool):
        tool_dir.mkdir()

    write_version_file(
        proton_tool,
        CompatToolVersionInfo(
            compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=1785769458
        ),
    )
    write_version_file(
        wine_tool,
        CompatToolVersionInfo(
            compat_tool="Wine-Tkg (Wine Master)", version="wine-tkg-master", installed_at=1785769458
        ),
    )

    tools = launcher.get_installed_tools()
    tools_by_name = {tool.full_name: tool for tool in tools}

    assert len(tools) == 3
    assert tools_by_name["GE-Proton11-3"].tool_type == CompatToolType.PROTON
    assert tools_by_name["wine-tkg-master"].tool_type == CompatToolType.WINE
    assert tools_by_name["Some-Manual-Tool"].tool_type == CompatToolType.PROTON


def test_get_installed_tools_filters_by_resolved_type(tmp_path: Path) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    wine_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON)

    proton_tool = wine_dir / "GE-Proton11-3"
    wine_tool = wine_dir / "wine-tkg-master"
    for tool_dir in (proton_tool, wine_tool):
        tool_dir.mkdir()

    write_version_file(
        proton_tool,
        CompatToolVersionInfo(
            compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=1785769458
        ),
    )
    write_version_file(
        wine_tool,
        CompatToolVersionInfo(
            compat_tool="Wine-Tkg (Wine Master)", version="wine-tkg-master", installed_at=1785769458
        ),
    )

    wine_tools = launcher.get_installed_tools([CompatToolType.WINE])
    assert [tool.full_name for tool in wine_tools] == ["wine-tkg-master"]
    assert all(tool.tool_type == CompatToolType.WINE for tool in wine_tools)


def test_get_installed_tools_without_version_file_defaults_to_folder_type(
    tmp_path: Path,
) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    wine_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON)
    (wine_dir / "Some-Manual-Tool").mkdir()

    tools = launcher.get_installed_tools()

    assert len(tools) == 1
    assert tools[0].full_name == "Some-Manual-Tool"
    assert tools[0].tool_type == CompatToolType.PROTON


def test_remove_tool_delegates_to_matching_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that Launcher.remove_tool delegates to the installer referenced by the
    tool's protondl_version.json.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    tool_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / "GE-Proton11-3"
    tool_dir.mkdir(parents=True)
    write_version_file(
        tool_dir,
        CompatToolVersionInfo(
            compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=1785769458
        ),
    )

    removed: list[tuple[CompatTool, object]] = []

    class FakeInstaller:
        def remove(self, tool: CompatTool, launcher: object) -> None:
            removed.append((tool, launcher))
            shutil.rmtree(tool.install_dir)

    monkeypatch.setattr("protondl.installers.get_installer_by_name", lambda _name: FakeInstaller())

    launcher.remove_tool(CompatTool("GE-Proton11-3", CompatToolType.PROTON, tool_dir))

    assert len(removed) == 1
    assert removed[0][0].full_name == "GE-Proton11-3"
    assert removed[0][1] is launcher
    assert not tool_dir.exists()


def test_remove_tool_deletes_folder_when_no_installer_matches(tmp_path: Path) -> None:
    """
    Test that Launcher.remove_tool deletes the folder directly when no matching
    installer can be found.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    tool_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / "Some-Manual-Tool"
    tool_dir.mkdir(parents=True)

    launcher.remove_tool(CompatTool("Some-Manual-Tool", CompatToolType.PROTON, tool_dir))

    assert not tool_dir.exists()


def test_remove_tool_outside_tools_dir_raises(tmp_path: Path) -> None:
    """
    Test that Launcher.remove_tool refuses directories outside the supported tools root.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    outside_dir = tmp_path / "somewhere-else"
    outside_dir.mkdir()

    with pytest.raises(ValueError, match="not inside the proton compatibility tools directory"):
        launcher.remove_tool(CompatTool("Some-Manual-Tool", CompatToolType.PROTON, outside_dir))


def test_remove_tool_missing_dir_raises(tmp_path: Path) -> None:
    """
    Test that Launcher.remove_tool raises FileNotFoundError for a missing directory.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    missing_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / "Not-There"

    with pytest.raises(FileNotFoundError):
        launcher.remove_tool(CompatTool("Not-There", CompatToolType.PROTON, missing_dir))


def _create_pga_db(tmp_path: Path, rows: list[dict[str, object]]) -> None:
    con = sqlite3.connect(tmp_path / "pga.db")
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
                installed_at INTEGER,
                configpath TEXT
            )
            """
        )
        for row in rows:
            con.execute(
                """
                INSERT INTO games
                    (name, slug, installer_slug, runner, directory, installed, installed_at,
                    configpath)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("name", ""),
                    row.get("slug", ""),
                    row.get("installer_slug", ""),
                    row.get("runner", ""),
                    row.get("directory", ""),
                    row.get("installed", 1),
                    row.get("installed_at", 0),
                    row.get("configpath", ""),
                ),
            )
        con.commit()
    finally:
        con.close()


def _write_game_config(tmp_path: Path, filename: str, data: object) -> None:
    games_dir = tmp_path / "games"
    games_dir.mkdir(parents=True, exist_ok=True)
    (games_dir / filename).write_text(yaml.safe_dump(data), encoding="utf-8")


def _create_launcher(tmp_path: Path) -> LutrisLauncher:
    return LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE, config_dir=tmp_path)


def test_get_game_list_returns_installed_games(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _create_pga_db(
        tmp_path,
        [
            {
                "slug": "doom",
                "name": "Doom",
                "runner": "wine",
                "installer_slug": "doom",
                "directory": "/games/doom",
                "installed_at": 1234567890,
            },
            {
                "slug": "skyrim",
                "name": "The Elder Scrolls V: Skyrim",
                "runner": "wine",
                "installer_slug": "skyrim",
                "directory": "/games/skyrim",
                "installed_at": 1234567890,
            },
        ],
    )
    _write_game_config(
        tmp_path,
        "doom-1234567890.yml",
        {"game": {"exe": "DOOMx64.exe", "working_dir": "/games/doom"}},
    )
    _write_game_config(
        tmp_path,
        "skyrim-1234567890.yml",
        {"wine": {"version": "GE-Proton10-14"}, "game": {"working_dir": "/games/skyrim"}},
    )

    games = launcher.get_game_list()

    assert len(games) == 2
    games_by_slug = {game.slug: game for game in games}
    assert games_by_slug["doom"].name == "Doom"
    assert games_by_slug["doom"].runner == "wine"
    assert games_by_slug["doom"].install_path == Path("/games/doom")
    assert games_by_slug["skyrim"].compat_tool_name == "GE-Proton10-14"
    assert [game.name for game in games] == sorted(
        [game.name for game in games], key=lambda name: name
    )


def test_get_game_list_skips_uninstalled_games(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _create_pga_db(
        tmp_path,
        [
            {"slug": "installed", "name": "Installed Game", "runner": "wine"},
            {"slug": "removed", "name": "Removed Game", "runner": "wine", "installed": 0},
        ],
    )

    games = launcher.get_game_list()

    assert [game.slug for game in games] == ["installed"]


def test_get_game_list_resolves_install_dir_from_config(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
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
    _write_game_config(tmp_path, "manual.yml", {"game": {"working_dir": "/games/manual"}})

    games = launcher.get_game_list()

    assert len(games) == 1
    assert games[0].install_path == Path("/games/manual")


def test_get_game_list_uses_exe_directory_as_install_dir_fallback(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _create_pga_db(
        tmp_path,
        [{"slug": "manual", "name": "Manual Game", "runner": "wine", "directory": ""}],
    )
    _write_game_config(tmp_path, "manual.yml", {"game": {"exe": "/games/nested/game.exe"}})

    games = launcher.get_game_list()

    assert len(games) == 1
    assert games[0].install_path == Path("/games/nested")


def test_get_game_list_detects_steam_runner_from_appid(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _create_pga_db(
        tmp_path,
        [{"slug": "steam-game", "name": "Steam Game", "runner": "", "directory": ""}],
    )
    _write_game_config(
        tmp_path, "steam-game.yml", {"game": {"appid": 123456, "working_dir": "/games/steam"}}
    )

    games = launcher.get_game_list()

    assert len(games) == 1
    assert games[0].runner == "steam"


def test_get_game_list_returns_empty_without_pga_db(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)

    assert launcher.get_game_list() == []


def test_get_game_list_uses_cache(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    _create_pga_db(
        tmp_path, [{"slug": "game", "name": "Game", "runner": "wine", "directory": "/games"}]
    )

    first = launcher.get_game_list()
    second = launcher.get_game_list()

    assert first is second


def test_get_game_list_raises_for_missing_root(tmp_path: Path) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path / "missing", InstallMode.NATIVE)

    with pytest.raises(ValueError, match="does not exist"):
        launcher.get_game_list()


def test_get_game_list_raises_for_corrupt_pga_db(tmp_path: Path) -> None:
    launcher = _create_launcher(tmp_path)
    (tmp_path / "pga.db").write_bytes(b"not a sqlite database")

    with pytest.raises(ValueError, match="Could not load the Lutris game list"):
        launcher.get_game_list()
