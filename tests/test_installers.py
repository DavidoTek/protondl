import asyncio
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from protondl.core.models import (
    Arch,
    CompatToolType,
    InstallMode,
    ReleaseData,
    ReleaseVersion,
)
from protondl.installers import CT_INSTALLERS
from protondl.installers.boxtron import BoxtronInstaller
from protondl.installers.kron4ek_wine import Kron4ekWineInstaller
from protondl.installers.lutris_wine import LutrisWineInstaller
from protondl.installers.proton_em import ProtonEMInstaller
from protondl.installers.proton_tkg_ntsync import ProtonTkgNtsyncInstaller
from protondl.installers.rtsp_proton import RTSPProtonInstaller
from protondl.installers.vkd3d_lutris import VKD3DLutrisInstaller
from protondl.launchers.bottles import BottlesLauncher
from protondl.launchers.heroic import HeroicLauncher
from protondl.launchers.lutris import LutrisLauncher
from protondl.launchers.steam import SteamLauncher
from protondl.util.version_file import read_version_file


class FakeResponse:
    def __init__(self, data: Any) -> None:
        self._data = data

    def json(self) -> Any:
        return self._data

    def raise_for_status(self) -> None:
        pass


class FakeClient:
    def __init__(self, data: Any) -> None:
        self._data = data

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def get(self, url: str, params: dict[str, Any] | None = None) -> FakeResponse:
        return FakeResponse(self._data)


def _fake_async_client(monkeypatch: pytest.MonkeyPatch, data: Any) -> None:
    def make_client(*args: Any, **kwargs: Any) -> FakeClient:
        return FakeClient(data)

    monkeypatch.setattr("protondl.util.download.httpx.AsyncClient", make_client)


def asyncio_run(coro: Any) -> Any:
    return asyncio.run(coro)


def _make_tar_xz(tool_folder: str) -> bytes:
    buffer = BytesIO()
    content = b"test"
    with tarfile.open(fileobj=buffer, mode="w:xz") as tf:
        info = tarfile.TarInfo(f"{tool_folder}/file.txt")
        info.size = len(content)
        tf.addfile(info, BytesIO(content))
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("name", "tool_type", "advanced", "release_format", "checksum_suffix"),
    [
        ("Boxtron", CompatToolType.PROTON, False, ".tar.xz", ""),
        ("Roberta", CompatToolType.PROTON, False, ".tar.xz", ""),
        ("Proton-EM", CompatToolType.PROTON, True, ".tar.xz", ""),
        ("RTSP Proton", CompatToolType.PROTON, True, ".tar.gz", ".sha512sum"),
        ("vkd3d-lutris", CompatToolType.VKD3D, False, ".tar.xz", ""),
        ("Lutris-Wine", CompatToolType.WINE, False, ".tar.xz", ""),
        ("Kron4ek Wine-Builds Vanilla", CompatToolType.WINE, False, ".tar.xz", ""),
        ("Proton-Tkg (Wine Master NTSYNC)", CompatToolType.PROTON, True, ".tar.gz", ""),
    ],
)
def test_new_installer_attributes(
    name: str, tool_type: CompatToolType, advanced: bool, release_format: str, checksum_suffix: str
) -> None:
    installer = CT_INSTALLERS[[i.name for i in CT_INSTALLERS].index(name)]
    assert installer.name == name
    assert installer.tool_type is tool_type
    assert installer.advanced is advanced
    assert installer.release_format == release_format
    assert installer.checksum_suffix == checksum_suffix
    assert installer.info_url
    assert installer.release_info_url
    assert installer.api_url
    assert installer.description


def test_new_installers_are_registered_once() -> None:
    names = [installer.name for installer in CT_INSTALLERS]
    assert len(names) == len(set(names))
    for name in [
        "Boxtron",
        "Roberta",
        "Proton-EM",
        "RTSP Proton",
        "vkd3d-lutris",
        "Lutris-Wine",
        "Kron4ek Wine-Builds Vanilla",
        "Proton-Tkg (Wine Master NTSYNC)",
    ]:
        assert name in names


@pytest.mark.parametrize(
    ("installer", "launcher", "expected"),
    [
        (BoxtronInstaller(), "steam", True),
        (BoxtronInstaller(), "lutris", True),
        (BoxtronInstaller(), "bottles", True),
        (ProtonEMInstaller(), "steam", True),
        (ProtonEMInstaller(), "heroic", True),
        (VKD3DLutrisInstaller(), "lutris", True),
        (VKD3DLutrisInstaller(), "heroic", True),
        (VKD3DLutrisInstaller(), "steam", False),
        (VKD3DLutrisInstaller(), "bottles", False),
        (LutrisWineInstaller(), "lutris", True),
        (LutrisWineInstaller(), "bottles", True),
        (LutrisWineInstaller(), "steam", False),
        (Kron4ekWineInstaller(), "lutris", True),
        (Kron4ekWineInstaller(), "heroic", True),
        (Kron4ekWineInstaller(), "steam", False),
    ],
)
def test_supports_launcher(installer: Any, launcher: str, expected: bool, tmp_path: Path) -> None:
    launchers = {
        "steam": SteamLauncher("Steam", tmp_path, InstallMode.NATIVE),
        "lutris": LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE),
        "heroic": HeroicLauncher("Heroic", tmp_path, InstallMode.NATIVE),
        "bottles": BottlesLauncher("Bottles", tmp_path, InstallMode.NATIVE),
    }
    assert installer.supports_launcher(launchers[launcher]) is expected


def test_steam_tool_uses_fixed_install_dir(tmp_path: Path) -> None:
    installer = BoxtronInstaller()
    install_dir = tmp_path / "compatibilitytools.d"
    install_dir.mkdir()
    before = set(install_dir.iterdir())

    assert installer._find_installed_dir(install_dir, before, "v0.5.4") is None

    target = install_dir / "boxtron"
    target.mkdir()
    assert installer._find_installed_dir(install_dir, before, "v0.5.4") == target


def test_boxtron_install_writes_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    installer = BoxtronInstaller()
    version = "v0.5.4"
    archive_bytes = _make_tar_xz("boxtron")

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v,
            date="2026-08-03",
            download="https://example.com/boxtron.tar.xz",
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

    info = asyncio.run(installer.install(version, launcher, arch=Arch.X86_64))

    assert info.compat_tool == "Boxtron"
    assert info.version == version

    installed_dir = tmp_path / "compatibilitytools.d" / "boxtron"
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "Boxtron"
    assert stored_info.version == version


def test_proton_em_install_writes_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    installer = ProtonEMInstaller()
    version = "EM-10.0-37-HDR"
    archive_bytes = _make_tar_xz(version)

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v,
            date="2026-08-03",
            download="https://example.com/proton-EM-10.0-37-HDR.tar.xz",
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

    info = asyncio.run(installer.install(version, launcher, arch=Arch.X86_64))

    installed_dir = tmp_path / "runners" / "wine" / version
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "Proton-EM"
    assert stored_info.version == version
    assert info.arch == Arch.X86_64


LUTRIS_WINE_RELEASES = [
    {
        "tag_name": "lutris-wine-7.2",
        "assets": [
            {"name": "wine-lutris-7.2-x86_64.tar.xz"},
            {"name": "wine-lutris-fshack-7.2-x86_64.tar.xz"},
        ],
    },
    {
        "tag_name": "lutris-wine-7.2-2",
        "assets": [{"name": "wine-lutris-7.2-2-x86_64.tar.xz"}],
    },
]


def test_lutris_wine_fetch_releases_lists_fshack_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, LUTRIS_WINE_RELEASES)

    releases = asyncio_run(LutrisWineInstaller().fetch_releases())

    assert releases == [
        ReleaseVersion("lutris-wine-7.2", (Arch.X86_64,)),
        ReleaseVersion("lutris-fshack-wine-7.2", (Arch.X86_64,)),
        ReleaseVersion("lutris-wine-7.2-2", (Arch.X86_64,)),
    ]


LUTRIS_WINE_RELEASE = {
    "tag_name": "lutris-wine-7.2",
    "published_at": "2026-08-03T12:00:00Z",
    "assets": [
        {
            "name": "wine-lutris-7.2-x86_64.tar.xz",
            "size": 100,
            "browser_download_url": "https://example.com/regular.tar.xz",
        },
        {
            "name": "wine-lutris-fshack-7.2-x86_64.tar.xz",
            "size": 200,
            "browser_download_url": "https://example.com/fshack.tar.xz",
        },
    ],
}


@pytest.mark.parametrize(
    ("version", "expected_download"),
    [
        ("lutris-wine-7.2", "https://example.com/regular.tar.xz"),
        ("lutris-fshack-wine-7.2", "https://example.com/fshack.tar.xz"),
    ],
)
def test_lutris_wine_fetch_release_data_selects_variant(
    monkeypatch: pytest.MonkeyPatch, version: str, expected_download: str
) -> None:
    _fake_async_client(monkeypatch, LUTRIS_WINE_RELEASE)

    installer = LutrisWineInstaller()
    release_data = asyncio_run(installer._fetch_release_data(version, Arch.X86_64))

    assert release_data.download == expected_download
    assert release_data.version == version
    assert release_data.original_filename == (
        "wine-lutris-7.2-x86_64.tar.xz"
        if "fshack" not in version
        else "wine-lutris-fshack-7.2-x86_64.tar.xz"
    )


KRON4EK_RELEASES = [
    {
        "tag_name": "11.15",
        "assets": [
            {"name": "sha256sums.txt"},
            {"name": "wine-11.15-amd64-wow64.tar.xz"},
            {"name": "wine-11.15-amd64.tar.xz"},
            {"name": "wine-11.15-staging-amd64-wow64.tar.xz"},
            {"name": "wine-11.15-staging-amd64.tar.xz"},
            {"name": "wine-11.15-x86.tar.xz"},
        ],
    },
]


def test_kron4ek_fetch_releases_lists_build_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, KRON4EK_RELEASES)

    releases = asyncio_run(Kron4ekWineInstaller().fetch_releases())

    assert releases == [
        ReleaseVersion("11.15 (wow64)", (Arch.X86_64,)),
        ReleaseVersion("11.15 (amd64)", (Arch.X86_64,)),
    ]


KRON4EK_RELEASE = {
    "tag_name": "11.15",
    "published_at": "2026-08-03T12:00:00Z",
    "assets": [
        {
            "name": "wine-11.15-amd64-wow64.tar.xz",
            "size": 100,
            "browser_download_url": "https://example.com/wow64.tar.xz",
        },
        {
            "name": "wine-11.15-amd64.tar.xz",
            "size": 200,
            "browser_download_url": "https://example.com/amd64.tar.xz",
        },
        {
            "name": "wine-11.15-staging-amd64-wow64.tar.xz",
            "size": 300,
            "browser_download_url": "https://example.com/staging-wow64.tar.xz",
        },
        {
            "name": "wine-11.15-staging-amd64.tar.xz",
            "size": 400,
            "browser_download_url": "https://example.com/staging.tar.xz",
        },
    ],
}


@pytest.mark.parametrize(
    ("version", "expected_download"),
    [
        ("11.15 (amd64)", "https://example.com/amd64.tar.xz"),
        ("11.15 (wow64)", "https://example.com/wow64.tar.xz"),
    ],
)
def test_kron4ek_fetch_release_data_selects_build_variant(
    monkeypatch: pytest.MonkeyPatch, version: str, expected_download: str
) -> None:
    _fake_async_client(monkeypatch, KRON4EK_RELEASE)

    installer = Kron4ekWineInstaller()
    release_data = asyncio_run(installer._fetch_release_data(version, Arch.X86_64))

    assert release_data.download == expected_download
    assert release_data.version == version


def test_kron4ek_fetch_release_data_rejects_invalid_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, KRON4EK_RELEASE)

    installer = Kron4ekWineInstaller()
    with pytest.raises(ValueError, match="Invalid version"):
        asyncio_run(installer._fetch_release_data("11.15", Arch.X86_64))


def test_vkd3d_lutris_asset_matching() -> None:
    installer = VKD3DLutrisInstaller()

    assert installer._asset_matches_arch("vkd3d-2.14.tar.xz", Arch.X86_64, ".tar.xz")
    assert not installer._asset_matches_arch("vkd3d-2.14.tar.xz", Arch.X86_64, ".tar.gz")
    assert installer._release_archs_from_assets([{"name": "vkd3d-2.14.tar.xz"}]) == [Arch.X86_64]


def test_rtsp_proton_asset_matching() -> None:
    installer = RTSPProtonInstaller()

    assert installer._asset_matches_arch(
        "proton-rtsp-11.0-20260609-2.tar.gz", Arch.X86_64, ".tar.gz"
    )
    assert installer._asset_matches_arch(
        "proton-rtsp-11.0-20260609-2.tar.gz.sha512sum", Arch.X86_64, ".sha512sum"
    )
    assert installer._release_archs_from_assets(
        [
            {"name": "proton-rtsp-11.0-20260609-2.tar.gz"},
            {"name": "proton-rtsp-11.0-20260609-2.tar.gz.sha512sum"},
        ]
    ) == [Arch.X86_64]


def test_ntsync_subclasses_winemaster_with_ntsync_package() -> None:
    installer = ProtonTkgNtsyncInstaller()
    assert installer.proton_package_name == "proton-arch-ntsync-nopackage.yml"
    assert installer.tool_type is CompatToolType.PROTON
    assert installer.advanced is True
