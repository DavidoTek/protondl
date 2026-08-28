import asyncio
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from protondl.core.errors import AlreadyInstalledError, InstallCancelledError
from protondl.core.models import (
    Arch,
    CancelToken,
    CompatTool,
    CompatToolType,
    CompatToolVersionInfo,
    InstallMode,
    InstallProgress,
    InstallStep,
    ReleaseData,
)
from protondl.installers.dxvk import DXVKInstaller
from protondl.installers.ge_proton import GEProtonInstaller
from protondl.launchers.lutris import LutrisLauncher
from protondl.util.version_file import read_version_file, write_version_file


def _make_tar_gz(tool_folder: str, file_count: int = 1) -> bytes:
    buffer = BytesIO()
    content = b"test"
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        for i in range(file_count):
            info = tarfile.TarInfo(f"{tool_folder}/file{i}.txt")
            info.size = len(content)
            tf.addfile(info, BytesIO(content))
    return buffer.getvalue()


def _mock_install(
    monkeypatch: pytest.MonkeyPatch,
    installer: Any,
    version: str,
    archive_bytes: dict[Arch, bytes],
) -> dict[str, Any]:
    """Patches the fetch/download/verify steps and counts downloads."""
    calls: dict[str, Any] = {"downloads": 0, "current_arch": None}

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        calls["current_arch"] = arch
        return ReleaseData(
            version=v,
            date="2026-08-03",
            download="https://example.com/tool.tar.gz",
            size=len(archive_bytes[arch]),
        )

    async def mock_download_file(
        url: str,
        destination: Path,
        client: Any,
        progress_callback: Any = None,
        known_size: int = 0,
        cancel_token: Any = None,
    ) -> None:
        calls["downloads"] += 1
        destination.write_bytes(archive_bytes[calls["current_arch"]])

    async def mock_verify_checksum(client: Any, release_data: ReleaseData, file_path: Path) -> None:
        pass

    monkeypatch.setattr(installer, "_fetch_release_data", mock_fetch_release_data)
    monkeypatch.setattr("protondl.core.base_installer.download_file", mock_download_file)
    monkeypatch.setattr(installer, "_verify_checksum", mock_verify_checksum)
    return calls


def test_install_raises_when_version_already_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()
    version = "GE-Proton11-3"
    archive_bytes = _make_tar_gz(version)

    calls = _mock_install(
        monkeypatch, installer, version, {Arch.X86_64: archive_bytes, Arch.AARCH64: archive_bytes}
    )

    asyncio.run(installer.install(version, launcher, arch=Arch.AARCH64))
    assert calls["downloads"] == 1

    with pytest.raises(AlreadyInstalledError, match="GE-Proton11-3 \\(aarch64\\) is already"):
        asyncio.run(installer.install(version, launcher, arch=Arch.AARCH64))
    assert calls["downloads"] == 1


def test_install_allows_different_arch_same_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()
    version = "GE-Proton11-3"
    x86_bytes = _make_tar_gz(version)
    aarch64_bytes = _make_tar_gz(version + "-aarch64")

    calls = _mock_install(
        monkeypatch,
        installer,
        version,
        {Arch.X86_64: x86_bytes, Arch.AARCH64: aarch64_bytes},
    )

    asyncio.run(installer.install(version, launcher, arch=Arch.X86_64))
    asyncio.run(installer.install(version, launcher, arch=Arch.AARCH64))

    assert calls["downloads"] == 2
    x86_dir = tmp_path / "runners" / "wine" / version
    aarch64_dir = tmp_path / "runners" / "wine" / f"{version}-aarch64"
    x86_info = read_version_file(x86_dir)
    aarch64_info = read_version_file(aarch64_dir)
    assert x86_info is not None
    assert x86_info.arch == Arch.X86_64
    assert aarch64_info is not None
    assert aarch64_info.arch == Arch.AARCH64


def test_install_force_reinstalls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()
    version = "GE-Proton11-3"
    archive_bytes = _make_tar_gz(version)

    calls = _mock_install(
        monkeypatch, installer, version, {Arch.X86_64: archive_bytes, Arch.AARCH64: archive_bytes}
    )

    asyncio.run(installer.install(version, launcher, arch=Arch.AARCH64))
    installed_dir = tmp_path / "runners" / "wine" / version
    assert read_version_file(installed_dir) is not None

    asyncio.run(installer.install(version, launcher, arch=Arch.AARCH64, force=True))

    assert calls["downloads"] == 2
    info = read_version_file(installed_dir)
    assert info is not None
    assert info.arch == Arch.AARCH64


def test_find_installed_tool_matches_version_and_arch(tmp_path: Path) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()
    version = "GE-Proton11-3"

    installed_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / version
    installed_dir.mkdir(parents=True)
    (installed_dir / "file.txt").write_text("test", encoding="utf-8")
    write_version_file(
        installed_dir,
        CompatToolVersionInfo(
            compat_tool=installer.name,
            version=version,
            installed_at=1,
            arch=Arch.X86_64,
        ),
    )

    found = installer.find_installed_tool(launcher, version, Arch.X86_64)
    assert found is not None
    assert found.install_dir == installed_dir

    assert installer.find_installed_tool(launcher, version, Arch.AARCH64) is None
    assert installer.find_installed_tool(launcher, "GE-Proton11-4", Arch.X86_64) is None


def test_install_writes_version_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()

    version = "GE-Proton11-3"
    archive_bytes = _make_tar_gz(version)

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v,
            date="2026-08-03",
            download="https://example.com/GE-Proton11-3.tar.gz",
            size=len(archive_bytes),
        )

    async def mock_download_file(
        url: str,
        destination: Path,
        client: Any,
        progress_callback: Any = None,
        known_size: int = 0,
        cancel_token: Any = None,
    ) -> None:
        destination.write_bytes(archive_bytes)

    async def mock_verify_checksum(client: Any, release_data: ReleaseData, file_path: Path) -> None:
        pass

    monkeypatch.setattr(installer, "_fetch_release_data", mock_fetch_release_data)
    monkeypatch.setattr("protondl.core.base_installer.download_file", mock_download_file)
    monkeypatch.setattr(installer, "_verify_checksum", mock_verify_checksum)

    asyncio.run(installer.install(version, launcher, arch=Arch.AARCH64))

    installed_dir = tmp_path / "runners" / "wine" / version
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "GE-Proton"
    assert stored_info.version == version
    assert isinstance(stored_info.installed_at, int)
    assert stored_info.installed_at > 0
    assert stored_info.arch == Arch.AARCH64
    assert stored_info.translation_details is not None
    assert stored_info.translation_details.from_os == "windows"
    assert stored_info.translation_details.from_arch == "x86_64"
    assert stored_info.translation_details.to_os == "linux"
    assert stored_info.translation_details.to_arch == "aarch64"


def test_install_returns_version_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()

    version = "GE-Proton11-3"
    archive_bytes = _make_tar_gz(version)

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v,
            date="2026-08-03",
            download="https://example.com/GE-Proton11-3.tar.gz",
            size=len(archive_bytes),
        )

    async def mock_download_file(
        url: str,
        destination: Path,
        client: Any,
        progress_callback: Any = None,
        known_size: int = 0,
        cancel_token: Any = None,
    ) -> None:
        destination.write_bytes(archive_bytes)

    async def mock_verify_checksum(client: Any, release_data: ReleaseData, file_path: Path) -> None:
        pass

    monkeypatch.setattr(installer, "_fetch_release_data", mock_fetch_release_data)
    monkeypatch.setattr("protondl.core.base_installer.download_file", mock_download_file)
    monkeypatch.setattr(installer, "_verify_checksum", mock_verify_checksum)

    info = asyncio.run(installer.install(version, launcher, arch=Arch.AARCH64))

    assert info.compat_tool == "GE-Proton"
    assert info.version == version
    assert info.arch == Arch.AARCH64
    assert info.translation_details is not None


def test_install_unsupported_arch_raises(tmp_path: Path) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = DXVKInstaller()

    with pytest.raises(ValueError, match="does not support architecture 'aarch64'"):
        asyncio.run(installer.install("dxvk-2.3", launcher, arch=Arch.AARCH64))


def test_install_reports_progress_steps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()

    version = "GE-Proton11-3"
    archive_bytes = _make_tar_gz(version)

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v,
            date="2026-08-03",
            download="https://example.com/GE-Proton11-3.tar.gz",
            size=len(archive_bytes),
        )

    async def mock_download_file(
        url: str,
        destination: Path,
        client: Any,
        progress_callback: Any = None,
        known_size: int = 0,
        cancel_token: Any = None,
    ) -> None:
        destination.write_bytes(archive_bytes)
        if progress_callback is not None:
            progress_callback(
                InstallProgress(
                    step=InstallStep.DOWNLOADING,
                    current=len(archive_bytes),
                    total=len(archive_bytes),
                )
            )

    async def mock_verify_checksum(client: Any, release_data: ReleaseData, file_path: Path) -> None:
        pass

    monkeypatch.setattr(installer, "_fetch_release_data", mock_fetch_release_data)
    monkeypatch.setattr("protondl.core.base_installer.download_file", mock_download_file)
    monkeypatch.setattr(installer, "_verify_checksum", mock_verify_checksum)

    events: list[InstallProgress] = []
    asyncio.run(
        installer.install(version, launcher, arch=Arch.AARCH64, progress_callback=events.append)
    )

    distinct_steps = list(dict.fromkeys(event.step for event in events))
    assert distinct_steps == [
        InstallStep.FETCHING_RELEASE,
        InstallStep.DOWNLOADING,
        InstallStep.VERIFYING,
        InstallStep.EXTRACTING,
        InstallStep.FINISHING,
    ]

    download_events = [e for e in events if e.step == InstallStep.DOWNLOADING]
    assert download_events[-1].current == len(archive_bytes)
    assert download_events[-1].total == len(archive_bytes)

    extract_events = [e for e in events if e.step == InstallStep.EXTRACTING]
    assert extract_events[-1].current == 1
    assert extract_events[-1].total == 1


def test_install_cancelled_before_start_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()
    version = "GE-Proton11-3"
    archive_bytes = _make_tar_gz(version)

    calls = _mock_install(
        monkeypatch, installer, version, {Arch.X86_64: archive_bytes, Arch.AARCH64: archive_bytes}
    )

    cancel_token = CancelToken()
    cancel_token.cancel()

    with pytest.raises(InstallCancelledError):
        asyncio.run(
            installer.install(version, launcher, arch=Arch.AARCH64, cancel_token=cancel_token)
        )

    assert calls["downloads"] == 0


def test_install_cancelled_during_download_removes_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()
    version = "GE-Proton11-3"
    cancel_token = CancelToken()
    seen_paths: list[Path] = []

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v, date="2026-08-03", download="https://example.com/tool.tar.gz", size=4
        )

    async def mock_download_file(
        url: str,
        destination: Path,
        client: Any,
        progress_callback: Any = None,
        known_size: int = 0,
        cancel_token: Any = None,
    ) -> None:
        seen_paths.append(destination)
        destination.write_bytes(b"te")  # partially downloaded
        if cancel_token is not None:
            cancel_token.cancel()
            cancel_token.raise_if_cancelled()

    monkeypatch.setattr(installer, "_fetch_release_data", mock_fetch_release_data)
    monkeypatch.setattr("protondl.core.base_installer.download_file", mock_download_file)

    with pytest.raises(InstallCancelledError):
        asyncio.run(
            installer.install(version, launcher, arch=Arch.AARCH64, cancel_token=cancel_token)
        )

    assert seen_paths and not seen_paths[0].exists()
    assert not (tmp_path / "runners" / "wine" / version).exists()


def test_install_cancelled_during_extraction_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = GEProtonInstaller()
    version = "GE-Proton11-3"
    archive_bytes = _make_tar_gz(version, file_count=5)
    cancel_token = CancelToken()

    calls = _mock_install(
        monkeypatch, installer, version, {Arch.X86_64: archive_bytes, Arch.AARCH64: archive_bytes}
    )

    def cancel_on_extract(event: InstallProgress) -> None:
        if event.step == InstallStep.EXTRACTING:
            cancel_token.cancel()

    with pytest.raises(InstallCancelledError):
        asyncio.run(
            installer.install(
                version,
                launcher,
                arch=Arch.AARCH64,
                progress_callback=cancel_on_extract,
                cancel_token=cancel_token,
            )
        )

    assert calls["downloads"] == 1
    install_dir = tmp_path / "runners" / "wine"
    assert not (install_dir / version).exists()
    assert list(install_dir.iterdir()) == []


def test_resolve_arch_uses_host_if_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.core.base_installer.detect_host_arch", lambda: Arch.AARCH64)
    assert GEProtonInstaller().resolve_arch(None) == Arch.AARCH64


def test_resolve_arch_falls_back_to_x86_64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.core.base_installer.detect_host_arch", lambda: Arch.AARCH64)
    assert DXVKInstaller().resolve_arch(None) == Arch.X86_64


def test_resolve_arch_explicit() -> None:
    assert GEProtonInstaller().resolve_arch(Arch.X86_64) == Arch.X86_64


def test_asset_matches_arch() -> None:
    installer = GEProtonInstaller()

    assert installer._asset_matches_arch("GE-Proton11-3.tar.gz", Arch.X86_64, ".tar.gz")
    assert not installer._asset_matches_arch("GE-Proton11-3-aarch64.tar.gz", Arch.X86_64, ".tar.gz")
    assert installer._asset_matches_arch("GE-Proton11-3-aarch64.tar.gz", Arch.AARCH64, ".tar.gz")
    assert not installer._asset_matches_arch("GE-Proton11-3.tar.gz", Arch.AARCH64, ".tar.gz")

    assert installer._asset_matches_arch("GE-Proton11-3.sha512sum", Arch.X86_64, ".sha512sum")
    assert installer._asset_matches_arch(
        "GE-Proton11-3-aarch64.sha512sum", Arch.AARCH64, ".sha512sum"
    )
    assert not installer._asset_matches_arch(
        "GE-Proton11-3-aarch64.sha512sum", Arch.X86_64, ".sha512sum"
    )


def test_release_archs_from_assets() -> None:
    installer = GEProtonInstaller()

    assets = [
        {"name": "GE-Proton11-3.tar.gz"},
        {"name": "GE-Proton11-3.sha512sum"},
        {"name": "GE-Proton11-3-aarch64.tar.gz"},
        {"name": "GE-Proton11-3-aarch64.sha512sum"},
    ]
    assert installer._release_archs_from_assets(assets) == [Arch.X86_64, Arch.AARCH64]

    x86_only = [{"name": "GE-Proton11-2.tar.gz"}]
    assert installer._release_archs_from_assets(x86_only) == [Arch.X86_64]

    assert DXVKInstaller()._release_archs_from_assets([{"name": "dxvk-2.3.tar.gz"}]) == [
        Arch.X86_64
    ]


def test_dxvk_asset_priority_prefers_non_native() -> None:
    installer = DXVKInstaller()

    assert installer._asset_priority({"name": "dxvk-3.0.2.tar.gz"}) == 1
    assert installer._asset_priority({"name": "dxvk-native-3.0.2-steamrt-sniper.tar.gz"}) == 0


def test_remove_deletes_install_dir(tmp_path: Path) -> None:
    """
    Test that the default CtInstaller.remove deletes the tool's directory.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    tool_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / "GE-Proton11-3"
    tool_dir.mkdir(parents=True)
    (tool_dir / "file.txt").write_text("test", encoding="utf-8")

    installer = GEProtonInstaller()
    tool = CompatTool("GE-Proton11-3", CompatToolType.PROTON, tool_dir)

    installer.remove(tool, launcher)

    assert not tool_dir.exists()


def test_remove_missing_install_dir_raises(tmp_path: Path) -> None:
    """
    Test that CtInstaller.remove raises FileNotFoundError for a missing directory.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    tool_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / "Not-There"
    installer = GEProtonInstaller()
    tool = CompatTool("Not-There", CompatToolType.PROTON, tool_dir)

    with pytest.raises(FileNotFoundError):
        installer.remove(tool, launcher)
