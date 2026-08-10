import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from protondl.core.base_launcher import Game, Launcher
from protondl.core.models import (
    CompatTool,
    CompatToolType,
    CompatToolVersionInfo,
    InstallMode,
    ReleaseVersion,
    ToolUpdate,
)
from protondl.util.helpers import check_for_updates, update_compatibility_tools


class _FakeLauncher(Launcher):
    supported_tools_folders: dict[CompatToolType, Path] = {}

    def __init__(self, installed_tools: list[CompatTool]) -> None:
        super().__init__("Fake", Path("/fake"), InstallMode.NATIVE)
        self._installed_tools = installed_tools
        self.removed: list[str] = []

    @classmethod
    def discover(cls) -> list[Launcher]:
        return []

    def get_installed_tools(
        self, tool_types: list[CompatToolType] | None = None
    ) -> list[CompatTool]:
        return self._installed_tools

    def get_compatibility_tools_path(self, tool_type: CompatToolType) -> Path:
        raise NotImplementedError

    def get_game_list(self) -> Sequence[Game]:
        return []

    def set_games_tools(self, game_tool_map: Mapping[Game, str | None]) -> None:
        raise NotImplementedError

    def get_global_tool(self, tool_type: CompatToolType) -> CompatTool | None:
        raise NotImplementedError

    def set_global_tool(self, tool: CompatTool) -> None:
        raise NotImplementedError

    def remove_tool(self, tool: CompatTool) -> None:
        self.removed.append(tool.full_name)


class _FakeInstaller:
    def __init__(self, name: str, releases: list[ReleaseVersion] | None = None) -> None:
        self.name = name
        self._releases = releases or []
        self.fetch_count = 0
        self.install_calls: list[str] = []
        self.request_config = None

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        self.fetch_count += 1
        return self._releases

    async def install(self, version: str, launcher: _FakeLauncher) -> None:
        self.install_calls.append(version)


class _FailingInstaller(_FakeInstaller):
    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        raise ConnectionError("offline")


def _tool(name: str) -> CompatTool:
    return CompatTool(
        full_name=name, tool_type=CompatToolType.PROTON, install_dir=Path(f"/fake/{name}")
    )


def _version_info(name: str) -> CompatToolVersionInfo:
    return CompatToolVersionInfo(compat_tool="GE-Proton", version=name, installed_at=1)


def _mock_installer_lookup(monkeypatch: pytest.MonkeyPatch, installer: _FakeInstaller) -> None:
    monkeypatch.setattr("protondl.installers.get_installer_by_name", lambda name: installer)


def _mock_version_files(
    monkeypatch: pytest.MonkeyPatch, versions: dict[str, CompatToolVersionInfo | None]
) -> None:
    def read_version_file(install_dir: Path) -> CompatToolVersionInfo | None:
        return versions.get(install_dir.name)

    monkeypatch.setattr("protondl.util.version_file.read_version_file", read_version_file)


def test_check_for_updates_returns_available_update(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5"), _tool("GE-Proton11-2")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5": _version_info("GE-Proton10-5"),
            "GE-Proton11-2": _version_info("GE-Proton11-2"),
        },
    )
    installer = _FakeInstaller("GE-Proton", [ReleaseVersion("GE-Proton11-3")])
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.unchecked == []
    assert result.up_to_date == []
    assert len(result.updates) == 1
    update = result.updates[0]
    assert update.compat_tool_name == "GE-Proton"
    assert update.latest_version == "GE-Proton11-3"
    assert update.installed_versions == ["GE-Proton10-5", "GE-Proton11-2"]
    assert [tool.full_name for tool in update.installed_tools] == [
        "GE-Proton10-5",
        "GE-Proton11-2",
    ]


def test_check_for_updates_fetches_once_per_installer_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5"), _tool("GE-Proton11-2")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5": _version_info("GE-Proton10-5"),
            "GE-Proton11-2": _version_info("GE-Proton11-2"),
        },
    )
    installer = _FakeInstaller("GE-Proton", [ReleaseVersion("GE-Proton11-3")])
    _mock_installer_lookup(monkeypatch, installer)

    asyncio.run(check_for_updates(launcher))

    assert installer.fetch_count == 1


def test_check_for_updates_mixed_updates_and_up_to_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5"), _tool("dxvk-2.3")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5": _version_info("GE-Proton10-5"),
            "dxvk-2.3": CompatToolVersionInfo(
                compat_tool="DXVK", version="dxvk-2.3", installed_at=1
            ),
        },
    )

    def fake_lookup(name: str) -> _FakeInstaller | None:
        if name == "GE-Proton":
            return _FakeInstaller("GE-Proton", [ReleaseVersion("GE-Proton11-3")])
        if name == "DXVK":
            return _FakeInstaller("DXVK", [ReleaseVersion("dxvk-2.3")])
        return None

    monkeypatch.setattr("protondl.installers.get_installer_by_name", fake_lookup)

    result = asyncio.run(check_for_updates(launcher))

    assert [update.compat_tool_name for update in result.updates] == ["GE-Proton"]
    assert result.up_to_date == ["DXVK"]
    assert result.unchecked == []


def test_check_for_updates_no_update_when_latest_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton11-3")])
    _mock_version_files(monkeypatch, {"GE-Proton11-3": _version_info("GE-Proton11-3")})
    installer = _FakeInstaller("GE-Proton", [ReleaseVersion("GE-Proton11-3")])
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.updates == []
    assert result.up_to_date == ["GE-Proton"]
    assert result.unchecked == []


def test_check_for_updates_unchecked_without_version_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("SomeOtherTool")])
    _mock_version_files(monkeypatch, {"SomeOtherTool": None})
    _mock_installer_lookup(monkeypatch, _FakeInstaller("GE-Proton"))

    result = asyncio.run(check_for_updates(launcher))

    assert result.updates == []
    assert result.up_to_date == []
    assert result.unchecked == ["SomeOtherTool"]


def test_check_for_updates_unchecked_without_matching_installer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("UnknownTool-1.0")])
    info = CompatToolVersionInfo(compat_tool="Unknown", version="UnknownTool-1.0", installed_at=1)
    _mock_version_files(monkeypatch, {"UnknownTool-1.0": info})
    monkeypatch.setattr("protondl.installers.get_installer_by_name", lambda name: None)

    result = asyncio.run(check_for_updates(launcher))

    assert result.updates == []
    assert result.up_to_date == []
    assert result.unchecked == ["UnknownTool-1.0"]


def test_check_for_updates_unchecked_when_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5")])
    _mock_version_files(monkeypatch, {"GE-Proton10-5": _version_info("GE-Proton10-5")})
    _mock_installer_lookup(monkeypatch, _FailingInstaller("GE-Proton"))

    result = asyncio.run(check_for_updates(launcher))

    assert result.updates == []
    assert result.up_to_date == []
    assert result.unchecked == ["GE-Proton10-5"]


def test_update_compatibility_tools_installs_latest_and_removes_old(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_1 = _tool("GE-Proton10-5")
    old_2 = _tool("GE-Proton11-2")
    launcher = _FakeLauncher([old_1, old_2])
    update = ToolUpdate(
        compat_tool_name="GE-Proton",
        latest_version="GE-Proton11-3",
        installed_versions=["GE-Proton10-5", "GE-Proton11-2"],
        installed_tools=[old_1, old_2],
    )
    installer = _FakeInstaller("GE-Proton")
    _mock_installer_lookup(monkeypatch, installer)

    progress: list[tuple[int, int]] = []
    asyncio.run(
        update_compatibility_tools(
            launcher, [update], progress_callback=lambda done, total: progress.append((done, total))
        )
    )

    assert installer.install_calls == ["GE-Proton11-3"]
    assert launcher.removed == ["GE-Proton10-5", "GE-Proton11-2"]
    assert progress == [(1, 1)]


def test_update_compatibility_tools_keeps_old_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _tool("GE-Proton10-5")
    launcher = _FakeLauncher([old])
    update = ToolUpdate(
        compat_tool_name="GE-Proton",
        latest_version="GE-Proton11-3",
        installed_versions=["GE-Proton10-5"],
        installed_tools=[old],
    )
    installer = _FakeInstaller("GE-Proton")
    _mock_installer_lookup(monkeypatch, installer)

    asyncio.run(update_compatibility_tools(launcher, [update], keep_old=True))

    assert installer.install_calls == ["GE-Proton11-3"]
    assert launcher.removed == []


def test_update_compatibility_tools_reports_progress_for_all_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _tool("GE-Proton10-5")
    launcher = _FakeLauncher([old])
    updates = [
        ToolUpdate("GE-Proton", "GE-Proton11-3", ["GE-Proton10-5"], [old]),
        ToolUpdate("DXVK", "dxvk-2.3", ["dxvk-2.2"], [_tool("dxvk-2.2")]),
    ]
    installer = _FakeInstaller("GE-Proton")
    monkeypatch.setattr("protondl.installers.get_installer_by_name", lambda name: installer)

    progress: list[tuple[int, int]] = []
    asyncio.run(
        update_compatibility_tools(
            launcher,
            updates,
            keep_old=True,
            progress_callback=lambda done, total: progress.append((done, total)),
        )
    )

    assert installer.install_calls == ["GE-Proton11-3", "dxvk-2.3"]
    assert progress == [(1, 2), (2, 2)]
