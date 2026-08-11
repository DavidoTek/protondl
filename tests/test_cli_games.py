from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from protondl.cli import app
from protondl.cli.games import EXIT_CODE_GAME_LIST_ERROR, EXIT_CODE_STATUS_ERROR
from protondl.core.base_launcher import Game
from protondl.launchers.steam import SteamDeckCompatType, SteamGame
from protondl.services import AWACYIndex, AWACYStatus
from protondl.services.protondb import ProtonDBTier

runner = CliRunner()


class _FakeGame(Game):
    pass


class _ShortcutGame(Game):
    def __init__(self, id: str, name: str, install_path: Path, shortcut_id: str = "") -> None:
        super().__init__(id, name, "GE-Proton10-10", install_path)
        self.shortcut_id = shortcut_id


class _FakeSteamGame(SteamGame):
    def __init__(self, appid: int, name: str, install_path: Path, category: int = 0) -> None:
        super().__init__(appid, name, install_path)
        self.deck_compatibility = {
            "configuration": {"recommended_runtime": "proton_9"},
            "category": category,
        }


class _FakeLauncher:
    name = "Steam"

    def get_game_list(self) -> list[Game]:
        return [
            _FakeGame("123456", "Portal 2", "GE-Proton10-10", Path("/games/portal2")),
            _FakeGame("not-an-appid", "Custom Game", "GE-Proton10-10", Path("/games/custom")),
        ]


class _FakeShortcutLauncher:
    name = "Steam"

    def get_game_list(self) -> list[Game]:
        return [
            _FakeGame("123456", "Portal 2", "GE-Proton10-10", Path("/games/portal2")),
            _ShortcutGame("1234567890", "Custom Shortcut", Path("/games/shortcut"), "42"),
        ]


def test_list_games_with_protondb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: _FakeLauncher())

    async def fake_fetch_protondb_tiers(games: list[Game]) -> dict[str, ProtonDBTier]:
        return {"123456": ProtonDBTier.GOLD}

    monkeypatch.setattr("protondl.cli.games.fetch_protondb_tiers", fake_fetch_protondb_tiers)

    result = runner.invoke(app, ["list-games", "1", "--protondb"])

    assert result.exit_code == 0
    assert "ProtonDB" in result.stdout
    assert "Status" in result.stdout
    assert "Portal 2" in result.stdout
    assert "Gold" in result.stdout
    assert "Unknown" in result.stdout


def test_list_games_protondb_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: _FakeLauncher())

    async def fake_fetch_protondb_tiers(games: list[Game]) -> dict[str, ProtonDBTier | None]:
        return {"123456": None}

    monkeypatch.setattr("protondl.cli.games.fetch_protondb_tiers", fake_fetch_protondb_tiers)

    result = runner.invoke(app, ["list-games", "1", "--protondb"])

    assert result.exit_code == EXIT_CODE_STATUS_ERROR
    assert "Network Error" in result.stdout


def test_list_games_awacy_fetch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: _FakeLauncher())

    async def fake_fetch_awacy_index() -> AWACYIndex:
        request = httpx.Request("GET", "https://raw.githubusercontent.com/example")
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("500 Internal Server Error", request=request, response=response)

    monkeypatch.setattr("protondl.cli.games.fetch_awacy_index", fake_fetch_awacy_index)

    result = runner.invoke(app, ["list-games", "1", "--awacy"])

    assert result.exit_code == EXIT_CODE_STATUS_ERROR
    assert "Failed to fetch AWACY data" in result.stdout
    assert "Network Error" in result.stdout


def test_list_games_skips_shortcuts_for_protondb(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _FakeShortcutLauncher()
    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: launcher)

    captured: list[Game] = []

    async def fake_fetch_protondb_tiers(games: list[Game]) -> dict[str, ProtonDBTier | None]:
        captured.extend(games)
        return {"123456": ProtonDBTier.GOLD}

    monkeypatch.setattr("protondl.cli.games.fetch_protondb_tiers", fake_fetch_protondb_tiers)

    result = runner.invoke(app, ["list-games", "1", "--protondb"])

    assert result.exit_code == 0
    assert [game.id for game in captured] == ["123456"]


def test_list_games_only_shortcuts_skips_protondb_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    class _OnlyShortcutsLauncher:
        name = "Steam"

        def get_game_list(self) -> list[Game]:
            return [
                _ShortcutGame("1234567890", "Custom Shortcut", Path("/games/shortcut"), "42"),
            ]

    monkeypatch.setattr(
        "protondl.cli.games.select_launcher",
        lambda launcher_id: _OnlyShortcutsLauncher(),
    )

    called = False

    async def fake_fetch_protondb_tiers(games: list[Game]) -> dict[str, ProtonDBTier | None]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr("protondl.cli.games.fetch_protondb_tiers", fake_fetch_protondb_tiers)

    result = runner.invoke(app, ["list-games", "1", "--protondb"])

    assert result.exit_code == 0
    assert called is False


def test_list_games_skips_shortcuts_for_awacy(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _FakeShortcutLauncher()
    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: launcher)

    async def fake_fetch_awacy_index() -> AWACYIndex:
        return AWACYIndex(by_slug={}, by_store_id={})

    calls: list[str] = []

    def fake_get_awacy_status_by_id(game_id: str, index: AWACYIndex) -> AWACYStatus:
        calls.append(game_id)
        return AWACYStatus.UNKNOWN

    monkeypatch.setattr("protondl.cli.games.fetch_awacy_index", fake_fetch_awacy_index)
    monkeypatch.setattr("protondl.cli.games.get_awacy_status_by_id", fake_get_awacy_status_by_id)

    result = runner.invoke(app, ["list-games", "1", "--awacy"])

    assert result.exit_code == 0
    assert calls == ["123456"]


def test_list_games_game_list_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingLauncher:
        name = "Steam"

        def get_game_list(self) -> list[Game]:
            raise ValueError("corrupt library data")

    launcher = _FailingLauncher()
    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: launcher)

    result = runner.invoke(app, ["list-games", "1"])

    assert result.exit_code == EXIT_CODE_GAME_LIST_ERROR
    assert "Failed to fetch the game list" in result.stdout


def test_list_games_awacy_network_error_skips_shortcuts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeShortcutLauncher()
    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: launcher)

    async def fake_fetch_awacy_index() -> AWACYIndex:
        request = httpx.Request("GET", "https://raw.githubusercontent.com/example")
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr("protondl.cli.games.fetch_awacy_index", fake_fetch_awacy_index)

    result = runner.invoke(app, ["list-games", "1", "--awacy"])

    assert result.exit_code == EXIT_CODE_STATUS_ERROR
    assert result.stdout.count("Network Error") == 1


def test_list_games_with_deck_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class _DeckLauncher:
        name = "Steam"

        def get_game_list(self) -> list[Game]:
            return [
                _FakeSteamGame(
                    123456,
                    "Portal 2",
                    Path("/games/portal2"),
                    category=SteamDeckCompatType.VERIFIED.value,
                ),
                _FakeSteamGame(
                    620,
                    "Portal",
                    Path("/games/portal"),
                    category=SteamDeckCompatType.PLAYABLE.value,
                ),
            ]

    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: _DeckLauncher())

    result = runner.invoke(app, ["list-games", "1", "--deck-status"])

    assert result.exit_code == 0
    assert "Deck" in result.stdout
    assert "VERIFIED" in result.stdout
    assert "proton_9" in result.stdout
    assert "PLAYABLE" in result.stdout


def test_list_games_deck_status_skips_shortcuts_and_non_steam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DeckLauncher:
        name = "Steam"

        def get_game_list(self) -> list[Game]:
            shortcut = _FakeSteamGame(1234567890, "Custom Shortcut", Path("/games/shortcut"))
            shortcut.shortcut_id = "42"
            return [
                _FakeGame("not-an-appid", "Custom Game", "GE-Proton10-10", Path("/games/custom")),
                shortcut,
            ]

    monkeypatch.setattr("protondl.cli.games.select_launcher", lambda launcher_id: _DeckLauncher())

    result = runner.invoke(app, ["list-games", "1", "--deck-status"])

    assert result.exit_code == 0
    assert "Deck" in result.stdout
    assert "Custom Game" in result.stdout
    assert "Shortcut" in result.stdout
    assert "VERIFIED" not in result.stdout
    assert "proton_9" not in result.stdout
