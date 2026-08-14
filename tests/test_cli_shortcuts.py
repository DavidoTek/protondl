from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from protondl.cli import app
from protondl.core.models import InstallMode
from protondl.launchers.steam import SteamGame, SteamLauncher

runner = CliRunner()


class _FakeSteamLauncher(SteamLauncher):
    def __init__(self, shortcuts: list[SteamGame] | None = None) -> None:
        super().__init__("Steam", Path("/tmp/steam"), InstallMode.NATIVE)
        self.shortcuts = list(shortcuts or [])
        self.added: SteamGame | None = None
        self.add_args: dict[str, str] = {}
        self.removed: list[SteamGame] = []

    def get_shortcuts(self) -> list[SteamGame]:
        return self.shortcuts

    def add_shortcut(
        self,
        name: str,
        exe: str,
        startdir: str = "",
        icon: str = "",
        user: str = "",
    ) -> SteamGame:
        self.add_args = {"name": name, "exe": exe, "startdir": startdir, "icon": icon, "user": user}
        game = SteamGame(3722544834, name, Path("/tmp/steam/userdata/123"))
        game.shortcut_id = "0"
        game.shortcut_exe = exe
        game.shortcut_startdir = startdir
        game.shortcut_icon = icon
        game.shortcut_user = user or "123"
        self.added = game
        return game

    def remove_shortcuts(self, shortcuts: Sequence[SteamGame]) -> None:
        self.removed.extend(shortcuts)


class _NonSteamLauncher:
    name = "Lutris"


def _fake_shortcut(id: str, name: str, user: str = "123") -> SteamGame:
    game = SteamGame(int(id) if id.isdigit() else -1, name, Path("/tmp/steam/userdata/123"))
    game.shortcut_id = "0"
    game.shortcut_exe = "/opt/games/test.exe"
    game.shortcut_startdir = "/opt/games"
    game.shortcut_icon = ""
    game.shortcut_user = user
    return game


def test_list_shortcuts(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _FakeSteamLauncher(
        [_fake_shortcut("3722544834", "My Game"), _fake_shortcut("1234567890", "Another")]
    )
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(app, ["list-shortcuts", "1"])

    assert result.exit_code == 0
    assert "Steam Shortcuts" in result.stdout
    assert "My Game" in result.stdout
    assert "Another" in result.stdout
    assert "/opt/games/test.exe" in result.stdout
    assert "123" in result.stdout


def test_list_shortcuts_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _FakeSteamLauncher([])
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(app, ["list-shortcuts", "1"])

    assert result.exit_code == 0
    assert "No shortcuts found" in result.stdout


def test_list_shortcuts_non_steam_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: _NonSteamLauncher())

    result = runner.invoke(app, ["list-shortcuts", "1"])

    assert result.exit_code == 1
    assert "does not support Steam shortcuts" in result.stdout


def test_add_shortcut(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _FakeSteamLauncher([])
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(
        app,
        ["add-shortcut", "1", "My Game", "/opt/games/MyGame.sh"],
    )

    assert result.exit_code == 0
    assert launcher.add_args == {
        "name": "My Game",
        "exe": "/opt/games/MyGame.sh",
        "startdir": "",
        "icon": "",
        "user": "",
    }
    assert "Shortcut 'My Game' added to Steam" in result.stdout
    assert "appid 3722544834" in result.stdout


def test_add_shortcut_with_options(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _FakeSteamLauncher([])
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(
        app,
        [
            "add-shortcut",
            "1",
            "My Game",
            "/opt/games/MyGame.sh",
            "--startdir",
            "/opt/games",
            "--icon",
            "/opt/games/icon.png",
            "--user",
            "456",
        ],
    )

    assert result.exit_code == 0
    assert launcher.add_args == {
        "name": "My Game",
        "exe": "/opt/games/MyGame.sh",
        "startdir": "/opt/games",
        "icon": "/opt/games/icon.png",
        "user": "456",
    }
    assert "user 456" in result.stdout


def test_add_shortcut_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingLauncher(_FakeSteamLauncher):
        def add_shortcut(
            self,
            name: str,
            exe: str,
            startdir: str = "",
            icon: str = "",
            user: str = "",
        ) -> SteamGame:
            raise ValueError("Shortcut name and executable are required")

    launcher = _FailingLauncher()
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(app, ["add-shortcut", "1", "", "/opt/games/MyGame.sh"])

    assert result.exit_code == 1
    assert "Failed to add shortcut" in result.stdout


def test_add_shortcut_non_steam_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: _NonSteamLauncher())

    result = runner.invoke(
        app,
        ["add-shortcut", "1", "My Game", "/opt/games/MyGame.sh"],
    )

    assert result.exit_code == 1
    assert "does not support Steam shortcuts" in result.stdout


def test_remove_shortcuts_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    shortcut = _fake_shortcut("3722544834", "My Game")
    launcher = _FakeSteamLauncher([shortcut])
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(app, ["remove-shortcuts", "1", "3722544834"])

    assert result.exit_code == 0
    assert launcher.removed == [shortcut]
    assert "Removed 1 shortcut(s): 'My Game'" in result.stdout


def test_remove_shortcuts_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    shortcut = _fake_shortcut("3722544834", "My Game")
    launcher = _FakeSteamLauncher([shortcut])
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(app, ["remove-shortcuts", "1", "my game"])

    assert result.exit_code == 0
    assert launcher.removed == [shortcut]


def test_remove_shortcuts_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _fake_shortcut("3722544834", "My Game")
    s2 = _fake_shortcut("1234567890", "Another Game")
    launcher = _FakeSteamLauncher([s1, s2])
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(app, ["remove-shortcuts", "1", "3722544834", "another game"])

    assert result.exit_code == 0
    assert launcher.removed == [s1, s2]


def test_remove_shortcuts_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _FakeSteamLauncher([])
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: launcher)

    result = runner.invoke(app, ["remove-shortcuts", "1", "3722544834"])

    assert result.exit_code == 1
    assert "Shortcut '3722544834' not found" in result.stdout


def test_remove_shortcuts_non_steam_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.shortcuts.select_launcher", lambda spec: _NonSteamLauncher())

    result = runner.invoke(app, ["remove-shortcuts", "1", "3722544834"])

    assert result.exit_code == 1
    assert "does not support Steam shortcuts" in result.stdout
