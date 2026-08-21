from pathlib import Path

import pytest
import typer

from protondl.cli.helpers import resolve_installer, select_launcher
from protondl.core.config import RequestConfig
from protondl.core.models import InstallMode
from protondl.installers import get_all_installers, get_installer_by_name
from protondl.launchers import create_launcher_from_path, is_valid_launcher_home
from protondl.launchers.heroic import HeroicLauncher
from protondl.launchers.lutris import LutrisLauncher
from protondl.launchers.steam import SteamLauncher


def test_select_launcher_by_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    monkeypatch.setattr("protondl.cli.helpers.get_launchers", lambda: [launcher])
    assert select_launcher("1") is launcher


def test_select_launcher_invalid_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.helpers.get_launchers", lambda: [])
    with pytest.raises(typer.Exit):
        select_launcher("1")


def test_select_launcher_custom_steam_path(tmp_path: Path) -> None:
    steam_path = tmp_path / "mySteam"
    (steam_path / "config").mkdir(parents=True)
    launcher = select_launcher(f"steam:{steam_path}")
    assert isinstance(launcher, SteamLauncher)
    assert launcher.root_path == steam_path
    assert launcher.install_mode == InstallMode.NATIVE


def test_select_launcher_custom_path_relative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mySteam" / "config").mkdir(parents=True)
    launcher = select_launcher("steam:mySteam")
    assert isinstance(launcher, SteamLauncher)
    assert launcher.root_path == Path("mySteam")


def test_select_launcher_custom_path_tilde(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "mySteam" / "config").mkdir(parents=True)
    launcher = select_launcher("steam:~/mySteam")
    assert isinstance(launcher, SteamLauncher)
    assert launcher.root_path == tmp_path / "mySteam"


def test_select_launcher_custom_path_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    launcher = select_launcher(f"STEAM:{tmp_path}")
    assert isinstance(launcher, SteamLauncher)


def test_select_launcher_custom_heroic_path(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    launcher = select_launcher(f"heroic:{tmp_path}")
    assert isinstance(launcher, HeroicLauncher)


def test_select_launcher_custom_path_missing() -> None:
    with pytest.raises(typer.Exit):
        select_launcher("steam:/does/not/exist")


def test_select_launcher_custom_path_not_a_launcher_home(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        select_launcher(f"steam:{tmp_path}")


def test_select_launcher_custom_path_allow_missing(tmp_path: Path) -> None:
    steam_path = tmp_path / "mySteam"
    launcher = select_launcher(f"steam:{steam_path}", allow_missing_path=True)
    assert isinstance(launcher, SteamLauncher)
    assert launcher.root_path == steam_path


def test_select_launcher_unknown_type() -> None:
    with pytest.raises(typer.Exit):
        select_launcher("origin:/some/path")


def test_select_launcher_malformed_spec() -> None:
    with pytest.raises(typer.Exit):
        select_launcher("steam")


def test_is_valid_launcher_home(tmp_path: Path) -> None:
    steam_path = tmp_path / "steam"
    (steam_path / "config").mkdir(parents=True)
    assert is_valid_launcher_home("steam", steam_path)
    assert not is_valid_launcher_home("steam", tmp_path)
    assert not is_valid_launcher_home("lutris", steam_path)
    assert not is_valid_launcher_home("unknown", steam_path)


def test_create_launcher_from_path_unknown_type() -> None:
    with pytest.raises(ValueError):
        create_launcher_from_path("origin", Path("/some/path"))


def test_create_launcher_from_path_lutris_config_dir(tmp_path: Path) -> None:
    launcher = create_launcher_from_path("lutris", tmp_path)
    assert isinstance(launcher, LutrisLauncher)
    assert launcher.config_dir == LutrisLauncher._default_config_dir(InstallMode.NATIVE)


def test_resolve_installer_by_name() -> None:
    all_installers = get_all_installers()
    result = resolve_installer(all_installers[0].name)
    assert result is not None
    assert result.name == all_installers[0].name


def test_resolve_installer_global_index() -> None:
    all_installers = get_all_installers()
    # numeric IDs correspond to install order and are independent of launcher
    assert resolve_installer("1").name == all_installers[0].name  # type: ignore[union-attr]
    assert resolve_installer(str(len(all_installers))).name == all_installers[-1].name  # type: ignore[union-attr]
    # out-of-range returns None
    assert resolve_installer(str(len(all_installers) + 1)) is None


def test_resolve_installer_passes_request_config() -> None:
    config = RequestConfig(github_token="token")
    result = resolve_installer("GE-Proton", request_config=config)
    assert result is not None
    assert result.request_config is config


def test_get_installer_by_name_passes_request_config() -> None:
    config = RequestConfig(github_token="token")
    installer = get_installer_by_name("GE-Proton", request_config=config)
    assert installer is not None
    assert installer.request_config is config


def test_get_all_installers_passes_request_config() -> None:
    config = RequestConfig(gitlab_token="token")
    for installer in get_all_installers(request_config=config):
        assert installer.request_config is config
