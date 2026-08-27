import asyncio
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from protondl.core.base_launcher import Game, Launcher
from protondl.core.config import RequestConfig
from protondl.core.models import (
    Arch,
    CancelToken,
    CompatTool,
    CompatToolType,
    CompatToolVersionInfo,
    InstallCancelledError,
    InstallMode,
    InstallProgress,
    InstallStep,
    ProgressCallback,
    ReleaseVersion,
    ToolUpdate,
)
from protondl.util.helpers import check_for_updates, detect_host_arch, update_compatibility_tools


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
    def __init__(
        self,
        name: str,
        releases: list[ReleaseVersion] | None = None,
        new_tool: CompatTool | None = None,
        new_info: CompatToolVersionInfo | None = None,
        supported_archs: tuple[Arch, ...] = (Arch.X86_64,),
        variant_of: Callable[[str], str] | None = None,
    ) -> None:
        self.name = name
        self._releases = releases or []
        self.new_tool = new_tool
        self.new_info = new_info
        self.fetch_count = 0
        self.install_calls: list[str] = []
        self.install_archs: list[Arch | None] = []
        self.supported_archs = supported_archs
        self._variant_of = variant_of or (lambda version: "")
        self.request_config = None

    def variant_of(self, version: str) -> str:
        return self._variant_of(version)

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        self.fetch_count += 1
        start = (page - 1) * count
        return self._releases[start : start + count]

    async def install(
        self,
        version: str,
        launcher: _FakeLauncher,
        arch: Arch | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CompatToolVersionInfo:
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        self.install_calls.append(version)
        self.install_archs.append(arch)
        if progress_callback is not None:
            progress_callback(InstallProgress(step=InstallStep.FINISHING, current=1, total=1))
        if self.new_tool is not None:
            launcher._installed_tools.append(self.new_tool)
        if self.new_info is not None:
            return self.new_info
        return CompatToolVersionInfo(compat_tool=self.name, version=version, installed_at=1)

    def resolve_arch(self, arch: Arch | None) -> Arch:
        if arch is not None:
            return arch
        host_arch = detect_host_arch()
        if host_arch in self.supported_archs:
            return host_arch
        return Arch.X86_64


class _FailingInstaller(_FakeInstaller):
    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        raise ConnectionError("offline")


def _tool(name: str) -> CompatTool:
    return CompatTool(
        full_name=name, tool_type=CompatToolType.PROTON, install_dir=Path(f"/fake/{name}")
    )


def _version_info(name: str) -> CompatToolVersionInfo:
    return CompatToolVersionInfo(compat_tool="GE-Proton", version=name, installed_at=1)


def _arch_version_info(
    name: str, version: str, arch: Arch, compat_tool: str = "GE-Proton"
) -> CompatToolVersionInfo:
    return CompatToolVersionInfo(
        compat_tool=compat_tool, version=version, installed_at=1, arch=arch
    )


def _mock_installer_lookup(monkeypatch: pytest.MonkeyPatch, installer: _FakeInstaller) -> None:
    monkeypatch.setattr(
        "protondl.installers.get_installer_by_name", lambda name, request_config=None: installer
    )


def _mock_version_files(
    monkeypatch: pytest.MonkeyPatch, versions: dict[str, CompatToolVersionInfo | None]
) -> None:
    def read_version_file(install_dir: Path) -> CompatToolVersionInfo | None:
        return versions.get(install_dir.name)

    monkeypatch.setattr("protondl.util.version_file.read_version_file", read_version_file)


def _lutris_variant(version: str) -> str:
    return "fshack" if "fshack-" in version else ""


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

    def fake_lookup(
        name: str, request_config: RequestConfig | None = None
    ) -> _FakeInstaller | None:
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
    monkeypatch.setattr(
        "protondl.installers.get_installer_by_name", lambda name, request_config=None: None
    )

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

    progress: list[InstallProgress] = []
    asyncio.run(update_compatibility_tools(launcher, [update], progress_callback=progress.append))

    assert installer.install_calls == ["GE-Proton11-3"]
    assert launcher.removed == ["GE-Proton10-5", "GE-Proton11-2"]
    assert [p.step for p in progress] == [InstallStep.FINISHING, InstallStep.COMPLETED]
    assert [(p.tool, p.tool_index, p.tool_total) for p in progress] == [
        ("GE-Proton", 1, 1),
        ("GE-Proton", 1, 1),
    ]


def test_update_compatibility_tools_cancel_before_first_tool(
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

    cancel_token = CancelToken()
    cancel_token.cancel()

    with pytest.raises(InstallCancelledError):
        asyncio.run(update_compatibility_tools(launcher, [update], cancel_token=cancel_token))

    assert installer.install_calls == []
    assert launcher.removed == []


def test_update_compatibility_tools_cancel_stops_before_remaining_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_a = _tool("GE-Proton10-5")
    old_b = _tool("DXVK-2.3")
    launcher = _FakeLauncher([old_a, old_b])
    update_a = ToolUpdate(
        compat_tool_name="GE-Proton",
        latest_version="GE-Proton11-3",
        installed_versions=["GE-Proton10-5"],
        installed_tools=[old_a],
    )
    update_b = ToolUpdate(
        compat_tool_name="DXVK",
        latest_version="DXVK-2.4",
        installed_versions=["DXVK-2.3"],
        installed_tools=[old_b],
    )
    cancel_token = CancelToken()
    installer = _FakeInstaller("GE-Proton")

    async def install_then_cancel(
        version: str,
        launcher: _FakeLauncher,
        arch: Arch | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CompatToolVersionInfo:
        installer.install_calls.append(version)
        if cancel_token is not None:
            cancel_token.cancel()
        return CompatToolVersionInfo(compat_tool="GE-Proton", version=version, installed_at=1)

    monkeypatch.setattr(installer, "install", install_then_cancel)
    _mock_installer_lookup(monkeypatch, installer)

    with pytest.raises(InstallCancelledError):
        asyncio.run(
            update_compatibility_tools(launcher, [update_a, update_b], cancel_token=cancel_token)
        )

    assert installer.install_calls == ["GE-Proton11-3"]


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
    monkeypatch.setattr(
        "protondl.installers.get_installer_by_name", lambda name, request_config=None: installer
    )

    progress: list[InstallProgress] = []
    asyncio.run(
        update_compatibility_tools(
            launcher,
            updates,
            keep_old=True,
            progress_callback=progress.append,
        )
    )

    assert installer.install_calls == ["GE-Proton11-3", "dxvk-2.3"]
    assert [p.step for p in progress] == [
        InstallStep.FINISHING,
        InstallStep.COMPLETED,
        InstallStep.FINISHING,
        InstallStep.COMPLETED,
    ]
    assert [(p.tool, p.tool_index, p.tool_total) for p in progress] == [
        ("GE-Proton", 1, 2),
        ("GE-Proton", 1, 2),
        ("DXVK", 2, 2),
        ("DXVK", 2, 2),
    ]


def test_update_compatibility_tools_returns_newly_installed_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _tool("GE-Proton10-5")
    new = _tool("GE-Proton11-3")
    new_info = CompatToolVersionInfo(
        compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=7
    )
    launcher = _FakeLauncher([old])
    _mock_version_files(monkeypatch, {"GE-Proton11-3": new_info})
    update = ToolUpdate(
        compat_tool_name="GE-Proton",
        latest_version="GE-Proton11-3",
        installed_versions=["GE-Proton10-5"],
        installed_tools=[old],
    )
    installer = _FakeInstaller("GE-Proton", new_tool=new, new_info=new_info)
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(update_compatibility_tools(launcher, [update]))

    assert result == {("GE-Proton", None, ""): new}


def test_update_compatibility_tools_matches_tool_when_dir_name_differs_from_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _tool("dxvk-2.2")
    new = _tool("dxvk-2.3")
    new_info = CompatToolVersionInfo(compat_tool="DXVK", version="v2.3", installed_at=8)
    launcher = _FakeLauncher([old])
    _mock_version_files(monkeypatch, {"dxvk-2.3": new_info})
    update = ToolUpdate(
        compat_tool_name="DXVK",
        latest_version="v2.3",
        installed_versions=["dxvk-2.2"],
        installed_tools=[old],
    )
    installer = _FakeInstaller("DXVK", new_tool=new, new_info=new_info)
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(update_compatibility_tools(launcher, [update]))

    assert result == {("DXVK", None, ""): new}


def test_update_compatibility_tools_matches_workflow_run_id_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _tool("proton-valvexbe-123")
    new = _tool("proton-valvexbe-456")
    new_info = CompatToolVersionInfo(compat_tool="Proton-Tkg", version="456", installed_at=9)
    launcher = _FakeLauncher([old])
    _mock_version_files(monkeypatch, {"proton-valvexbe-456": new_info})
    update = ToolUpdate(
        compat_tool_name="Proton-Tkg",
        latest_version="456",
        installed_versions=["123"],
        installed_tools=[old],
    )
    installer = _FakeInstaller("Proton-Tkg", new_tool=new, new_info=new_info)
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(update_compatibility_tools(launcher, [update]))

    assert result == {("Proton-Tkg", None, ""): new}


def test_update_compatibility_tools_skips_update_when_new_tool_not_found(
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

    result = asyncio.run(update_compatibility_tools(launcher, [update]))

    assert result == {}


def test_check_for_updates_x86_64_walks_back_to_newest_x86_64_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5")])
    _mock_version_files(
        monkeypatch,
        {"GE-Proton10-5": _arch_version_info("GE-Proton10-5", "GE-Proton10-5", Arch.X86_64)},
    )
    releases = [
        ReleaseVersion("GE-Proton11-3", (Arch.AARCH64,)),
        ReleaseVersion("GE-Proton11-2", (Arch.X86_64, Arch.AARCH64)),
    ]
    installer = _FakeInstaller("GE-Proton", releases, supported_archs=(Arch.X86_64, Arch.AARCH64))
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.unchecked == []
    assert result.up_to_date == []
    assert len(result.updates) == 1
    update = result.updates[0]
    assert update.compat_tool_name == "GE-Proton"
    assert update.arch == Arch.X86_64
    assert update.latest_version == "GE-Proton11-2"
    assert update.installed_versions == ["GE-Proton10-5"]


def test_check_for_updates_walks_back_across_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5-aarch64")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5-aarch64": _arch_version_info(
                "GE-Proton10-5-aarch64", "GE-Proton10-5", Arch.AARCH64
            )
        },
    )
    releases = [ReleaseVersion(f"GE-Proton-{i}", (Arch.X86_64,)) for i in range(30)]
    releases.append(ReleaseVersion("GE-Proton11-2", (Arch.X86_64, Arch.AARCH64)))
    installer = _FakeInstaller("GE-Proton", releases, supported_archs=(Arch.X86_64, Arch.AARCH64))
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert installer.fetch_count == 2
    assert result.unchecked == []
    assert len(result.updates) == 1
    update = result.updates[0]
    assert update.arch == Arch.AARCH64
    assert update.latest_version == "GE-Proton11-2"


def test_check_for_updates_unsupported_arch_is_unchecked_without_fetching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5-aarch64")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5-aarch64": _arch_version_info(
                "GE-Proton10-5-aarch64", "GE-Proton10-5", Arch.AARCH64
            )
        },
    )
    installer = _FakeInstaller("GE-Proton", [ReleaseVersion("GE-Proton11-3", (Arch.X86_64,))])
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert installer.fetch_count == 0
    assert result.updates == []
    assert result.up_to_date == []
    assert result.unchecked == ["GE-Proton10-5-aarch64"]


def test_check_for_updates_aarch64_gets_newest_aarch64_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5-aarch64")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5-aarch64": _arch_version_info(
                "GE-Proton10-5-aarch64", "GE-Proton10-5", Arch.AARCH64
            )
        },
    )
    releases = [
        ReleaseVersion("GE-Proton11-3", (Arch.AARCH64,)),
        ReleaseVersion("GE-Proton11-2", (Arch.X86_64,)),
    ]
    installer = _FakeInstaller("GE-Proton", releases, supported_archs=(Arch.X86_64, Arch.AARCH64))
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.unchecked == []
    assert result.up_to_date == []
    assert len(result.updates) == 1
    update = result.updates[0]
    assert update.arch == Arch.AARCH64
    assert update.latest_version == "GE-Proton11-3"
    assert update.installed_versions == ["GE-Proton10-5"]


def test_check_for_updates_both_archs_update_to_same_latest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5"), _tool("GE-Proton10-5-aarch64")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5": _arch_version_info("GE-Proton10-5", "GE-Proton10-5", Arch.X86_64),
            "GE-Proton10-5-aarch64": _arch_version_info(
                "GE-Proton10-5-aarch64", "GE-Proton10-5", Arch.AARCH64
            ),
        },
    )
    releases = [ReleaseVersion("GE-Proton11-3", (Arch.X86_64, Arch.AARCH64))]
    installer = _FakeInstaller("GE-Proton", releases, supported_archs=(Arch.X86_64, Arch.AARCH64))
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.unchecked == []
    assert result.up_to_date == []
    assert len(result.updates) == 2
    by_arch = {update.arch: update for update in result.updates}
    assert set(by_arch) == {Arch.X86_64, Arch.AARCH64}
    assert by_arch[Arch.X86_64].latest_version == "GE-Proton11-3"
    assert by_arch[Arch.AARCH64].latest_version == "GE-Proton11-3"
    assert [tool.full_name for tool in by_arch[Arch.X86_64].installed_tools] == ["GE-Proton10-5"]
    assert [tool.full_name for tool in by_arch[Arch.AARCH64].installed_tools] == [
        "GE-Proton10-5-aarch64"
    ]


def test_check_for_updates_both_archs_update_to_different_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5"), _tool("GE-Proton10-5-aarch64")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5": _arch_version_info("GE-Proton10-5", "GE-Proton10-5", Arch.X86_64),
            "GE-Proton10-5-aarch64": _arch_version_info(
                "GE-Proton10-5-aarch64", "GE-Proton10-5", Arch.AARCH64
            ),
        },
    )
    releases = [
        ReleaseVersion("GE-Proton11-3", (Arch.X86_64,)),
        ReleaseVersion("GE-Proton11-2", (Arch.X86_64, Arch.AARCH64)),
    ]
    installer = _FakeInstaller("GE-Proton", releases, supported_archs=(Arch.X86_64, Arch.AARCH64))
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.unchecked == []
    assert result.up_to_date == []
    assert len(result.updates) == 2
    by_arch = {update.arch: update for update in result.updates}
    assert by_arch[Arch.X86_64].latest_version == "GE-Proton11-3"
    assert by_arch[Arch.AARCH64].latest_version == "GE-Proton11-2"


def test_check_for_updates_single_arch_up_to_date_label_keeps_plain_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("dxvk-2.3")])
    _mock_version_files(
        monkeypatch,
        {
            "dxvk-2.3": CompatToolVersionInfo(
                compat_tool="DXVK", version="dxvk-2.3", installed_at=1, arch=Arch.X86_64
            )
        },
    )
    installer = _FakeInstaller("DXVK", [ReleaseVersion("dxvk-2.3")])
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.updates == []
    assert result.up_to_date == ["DXVK"]
    assert result.unchecked == []


def test_check_for_updates_multi_arch_up_to_date_label_includes_arch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("GE-Proton10-5"), _tool("GE-Proton10-5-aarch64")])
    _mock_version_files(
        monkeypatch,
        {
            "GE-Proton10-5": _arch_version_info("GE-Proton10-5", "GE-Proton10-5", Arch.X86_64),
            "GE-Proton10-5-aarch64": _arch_version_info(
                "GE-Proton10-5-aarch64", "GE-Proton10-5", Arch.AARCH64
            ),
        },
    )
    releases = [ReleaseVersion("GE-Proton10-5", (Arch.X86_64, Arch.AARCH64))]
    installer = _FakeInstaller("GE-Proton", releases, supported_archs=(Arch.X86_64, Arch.AARCH64))
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.updates == []
    assert set(result.up_to_date) == {"GE-Proton (x86_64)", "GE-Proton (aarch64)"}
    assert result.unchecked == []


def test_check_for_updates_multi_variant_does_not_cross_match_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("lutris-fshack-7.2")])
    _mock_version_files(
        monkeypatch,
        {
            "lutris-fshack-7.2": _arch_version_info(
                "lutris-fshack-7.2", "lutris-fshack-7.2", Arch.X86_64, "Lutris-Wine"
            )
        },
    )
    installer = _FakeInstaller(
        "Lutris-Wine",
        [ReleaseVersion("lutris-8.0"), ReleaseVersion("lutris-fshack-7.2")],
        variant_of=_lutris_variant,
    )
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.updates == []
    assert result.up_to_date == ["Lutris-Wine (fshack)"]
    assert result.unchecked == []


def test_check_for_updates_multi_variant_gets_newest_same_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("lutris-fshack-7.2")])
    _mock_version_files(
        monkeypatch,
        {
            "lutris-fshack-7.2": _arch_version_info(
                "lutris-fshack-7.2", "lutris-fshack-7.2", Arch.X86_64, "Lutris-Wine"
            )
        },
    )
    installer = _FakeInstaller(
        "Lutris-Wine",
        [ReleaseVersion("lutris-8.0"), ReleaseVersion("lutris-fshack-7.3")],
        variant_of=_lutris_variant,
    )
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.unchecked == []
    assert len(result.updates) == 1
    update = result.updates[0]
    assert update.arch == Arch.X86_64
    assert update.variant == "fshack"
    assert update.latest_version == "lutris-fshack-7.3"
    assert update.installed_versions == ["lutris-fshack-7.2"]
    assert [tool.full_name for tool in update.installed_tools] == ["lutris-fshack-7.2"]


def test_check_for_updates_multi_variant_separates_installed_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _FakeLauncher([_tool("lutris-7.2"), _tool("lutris-fshack-7.2")])
    _mock_version_files(
        monkeypatch,
        {
            "lutris-7.2": _arch_version_info(
                "lutris-7.2", "lutris-7.2", Arch.X86_64, "Lutris-Wine"
            ),
            "lutris-fshack-7.2": _arch_version_info(
                "lutris-fshack-7.2", "lutris-fshack-7.2", Arch.X86_64, "Lutris-Wine"
            ),
        },
    )
    installer = _FakeInstaller(
        "Lutris-Wine",
        [ReleaseVersion("lutris-8.0"), ReleaseVersion("lutris-fshack-7.3")],
        variant_of=_lutris_variant,
    )
    _mock_installer_lookup(monkeypatch, installer)

    result = asyncio.run(check_for_updates(launcher))

    assert result.unchecked == []
    assert len(result.updates) == 2
    by_variant = {update.variant: update for update in result.updates}
    assert set(by_variant) == {"", "fshack"}
    assert [tool.full_name for tool in by_variant[""].installed_tools] == ["lutris-7.2"]
    assert [tool.full_name for tool in by_variant["fshack"].installed_tools] == [
        "lutris-fshack-7.2"
    ]
    assert by_variant[""].latest_version == "lutris-8.0"
    assert by_variant["fshack"].latest_version == "lutris-fshack-7.3"


def test_update_compatibility_tools_multi_variant_removes_only_matching_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    regular = _tool("lutris-7.2")
    fshack = _tool("lutris-fshack-7.2")
    launcher = _FakeLauncher([regular, fshack])
    updates = [
        ToolUpdate(
            "Lutris-Wine",
            "lutris-8.0",
            ["lutris-7.2"],
            [regular],
            arch=Arch.X86_64,
            variant="",
        ),
        ToolUpdate(
            "Lutris-Wine",
            "lutris-fshack-7.3",
            ["lutris-fshack-7.2"],
            [fshack],
            arch=Arch.X86_64,
            variant="fshack",
        ),
    ]
    installer = _FakeInstaller("Lutris-Wine", variant_of=_lutris_variant)
    _mock_installer_lookup(monkeypatch, installer)

    asyncio.run(update_compatibility_tools(launcher, updates))

    assert installer.install_calls == ["lutris-8.0", "lutris-fshack-7.3"]
    assert launcher.removed == ["lutris-7.2", "lutris-fshack-7.2"]


class _VariantInstaller(_FakeInstaller):
    def __init__(self, name: str) -> None:
        super().__init__(name)

    async def install(
        self,
        version: str,
        launcher: _FakeLauncher,
        arch: Arch | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CompatToolVersionInfo:
        launcher._installed_tools.append(_tool(version))
        return CompatToolVersionInfo(
            compat_tool=self.name, version=version, installed_at=1, arch=arch
        )


def test_update_compatibility_tools_returns_variant_keyed_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    new_regular = _tool("lutris-8.0")
    new_fshack = _tool("lutris-fshack-7.3")
    launcher = _FakeLauncher([new_regular, new_fshack])
    _mock_version_files(
        monkeypatch,
        {
            "lutris-8.0": _arch_version_info(
                "lutris-8.0", "lutris-8.0", Arch.X86_64, "Lutris-Wine"
            ),
            "lutris-fshack-7.3": _arch_version_info(
                "lutris-fshack-7.3", "lutris-fshack-7.3", Arch.X86_64, "Lutris-Wine"
            ),
        },
    )
    installer = _VariantInstaller("Lutris-Wine")
    _mock_installer_lookup(monkeypatch, installer)
    updates = [
        ToolUpdate(
            "Lutris-Wine",
            "lutris-8.0",
            ["lutris-7.2"],
            [_tool("lutris-7.2")],
            arch=Arch.X86_64,
            variant="",
        ),
        ToolUpdate(
            "Lutris-Wine",
            "lutris-fshack-7.3",
            ["lutris-fshack-7.2"],
            [_tool("lutris-fshack-7.2")],
            arch=Arch.X86_64,
            variant="fshack",
        ),
    ]

    result = asyncio.run(update_compatibility_tools(launcher, updates))

    assert set(result) == {
        ("Lutris-Wine", Arch.X86_64, ""),
        ("Lutris-Wine", Arch.X86_64, "fshack"),
    }
    assert result[("Lutris-Wine", Arch.X86_64, "")].full_name == "lutris-8.0"
    assert result[("Lutris-Wine", Arch.X86_64, "fshack")].full_name == "lutris-fshack-7.3"


def test_update_compatibility_tools_installs_each_arch_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    x86 = _tool("GE-Proton10-5")
    arm = _tool("GE-Proton10-5-aarch64")
    launcher = _FakeLauncher([x86, arm])
    updates = [
        ToolUpdate("GE-Proton", "GE-Proton11-3", ["GE-Proton10-5"], [x86], arch=Arch.X86_64),
        ToolUpdate("GE-Proton", "GE-Proton11-2", ["GE-Proton10-5"], [arm], arch=Arch.AARCH64),
    ]
    installer = _FakeInstaller("GE-Proton")
    _mock_installer_lookup(monkeypatch, installer)

    asyncio.run(update_compatibility_tools(launcher, updates))

    assert installer.install_calls == ["GE-Proton11-3", "GE-Proton11-2"]
    assert installer.install_archs == [Arch.X86_64, Arch.AARCH64]
    assert launcher.removed == ["GE-Proton10-5", "GE-Proton10-5-aarch64"]


def test_update_compatibility_tools_removes_only_updated_arch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    x86 = _tool("GE-Proton11-3")
    arm = _tool("GE-Proton10-5-aarch64")
    launcher = _FakeLauncher([x86, arm])
    update = ToolUpdate("GE-Proton", "GE-Proton11-2", ["GE-Proton10-5"], [arm], arch=Arch.AARCH64)
    installer = _FakeInstaller("GE-Proton")
    _mock_installer_lookup(monkeypatch, installer)

    asyncio.run(update_compatibility_tools(launcher, [update]))

    assert installer.install_calls == ["GE-Proton11-2"]
    assert installer.install_archs == [Arch.AARCH64]
    assert launcher.removed == ["GE-Proton10-5-aarch64"]
