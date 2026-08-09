import asyncio
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from protondl.core.models import (
    Arch,
    CompatTool,
    CompatToolType,
    InstallMode,
    ReleaseData,
)
from protondl.installers.dxvk import DXVKInstaller
from protondl.installers.ge_proton import GEProtonInstaller
from protondl.launchers.lutris import LutrisLauncher
from protondl.util.version_file import read_version_file


def _make_tar_gz(tool_folder: str) -> bytes:
    buffer = BytesIO()
    content = b"test"
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        info = tarfile.TarInfo(f"{tool_folder}/file.txt")
        info.size = len(content)
        tf.addfile(info, BytesIO(content))
    return buffer.getvalue()


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
