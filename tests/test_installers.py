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
from protondl.installers import get_all_installers
from protondl.installers.boxtron import BoxtronInstaller
from protondl.installers.dwproton import DWProtonInstaller
from protondl.installers.kron4ek_wine import Kron4ekWineInstaller
from protondl.installers.lutris_wine import LutrisWineInstaller
from protondl.installers.luxtorpeda import LuxtorpedaInstaller
from protondl.installers.proton_cachyos import ProtonCachyOSInstaller
from protondl.installers.proton_em import ProtonEMInstaller
from protondl.installers.proton_tkg_ntsync import ProtonTkgNtsyncInstaller
from protondl.installers.rtsp_proton import RTSPProtonInstaller
from protondl.installers.steam_play_none import SteamPlayNoneInstaller
from protondl.installers.steam_tinkerlaunch import (
    SteamTinkerLaunchGitInstaller,
    SteamTinkerLaunchInstaller,
)
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


def _make_tar_gz(tool_folder: str) -> bytes:
    buffer = BytesIO()
    content = b"test"
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
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
        ("Luxtorpeda", CompatToolType.PROTON, False, ".tar.xz", ".sha512"),
        ("Kron4ek Wine-Builds Vanilla", CompatToolType.WINE, False, ".tar.xz", ""),
        ("Proton-Tkg (Wine Master NTSYNC)", CompatToolType.PROTON, True, ".tar.gz", ""),
        ("dwproton", CompatToolType.PROTON, True, ".tar.xz", ".sha512sum"),
        ("Proton-CachyOS", CompatToolType.PROTON, False, ".tar.xz", ".sha512sum"),
        ("Steam-Play-None", CompatToolType.PROTON, False, ".tar.gz", ""),
        ("SteamTinkerLaunch", CompatToolType.PROTON, False, ".tar.gz", ""),
        ("SteamTinkerLaunch-git", CompatToolType.PROTON, True, ".tar.gz", ""),
    ],
)
def test_new_installer_attributes(
    name: str, tool_type: CompatToolType, advanced: bool, release_format: str, checksum_suffix: str
) -> None:
    all_installers = get_all_installers()
    installer = all_installers[[i.name for i in all_installers].index(name)]
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
    all_installers = get_all_installers()
    names = [installer.name for installer in all_installers]
    assert len(names) == len(set(names))
    for name in [
        "Boxtron",
        "Roberta",
        "Proton-EM",
        "RTSP Proton",
        "vkd3d-lutris",
        "Lutris-Wine",
        "Luxtorpeda",
        "Kron4ek Wine-Builds Vanilla",
        "Proton-Tkg (Wine Master NTSYNC)",
        "dwproton",
        "Proton-CachyOS",
        "Steam-Play-None",
        "SteamTinkerLaunch",
        "SteamTinkerLaunch-git",
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
        (LuxtorpedaInstaller(), "steam", True),
        (LuxtorpedaInstaller(), "lutris", True),
        (Kron4ekWineInstaller(), "lutris", True),
        (Kron4ekWineInstaller(), "heroic", True),
        (Kron4ekWineInstaller(), "steam", False),
        (DWProtonInstaller(), "steam", True),
        (DWProtonInstaller(), "lutris", True),
        (DWProtonInstaller(), "heroic", True),
        (DWProtonInstaller(), "bottles", True),
        (ProtonCachyOSInstaller(), "steam", True),
        (ProtonCachyOSInstaller(), "lutris", True),
        (ProtonCachyOSInstaller(), "heroic", True),
        (ProtonCachyOSInstaller(), "bottles", True),
        (SteamPlayNoneInstaller(), "steam", True),
        (SteamPlayNoneInstaller(), "lutris", False),
        (SteamPlayNoneInstaller(), "heroic", False),
        (SteamPlayNoneInstaller(), "bottles", False),
        (SteamTinkerLaunchInstaller(), "steam", True),
        (SteamTinkerLaunchInstaller(), "lutris", False),
        (SteamTinkerLaunchInstaller(), "heroic", False),
        (SteamTinkerLaunchInstaller(), "bottles", False),
        (SteamTinkerLaunchGitInstaller(), "steam", True),
        (SteamTinkerLaunchGitInstaller(), "lutris", False),
        (SteamTinkerLaunchGitInstaller(), "heroic", False),
        (SteamTinkerLaunchGitInstaller(), "bottles", False),
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


def test_luxtorpeda_uses_fixed_install_dir(tmp_path: Path) -> None:
    installer = LuxtorpedaInstaller()
    install_dir = tmp_path / "compatibilitytools.d"
    install_dir.mkdir()
    before = set(install_dir.iterdir())

    assert installer._find_installed_dir(install_dir, before, "v77.1.0") is None

    target = install_dir / "luxtorpeda"
    target.mkdir()
    assert installer._find_installed_dir(install_dir, before, "v77.1.0") == target


def test_luxtorpeda_install_writes_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    installer = LuxtorpedaInstaller()
    version = "v77.1.0"
    archive_bytes = _make_tar_xz("luxtorpeda")

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v,
            date="2026-05-27",
            download="https://example.com/luxtorpeda-v77.1.0.tar.xz",
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

    installed_dir = tmp_path / "compatibilitytools.d" / "luxtorpeda"
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "Luxtorpeda"
    assert stored_info.version == version
    assert info.arch == Arch.X86_64


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


DWPROTON_RELEASE = {
    "tag_name": "dwproton-11.0-11",
    "published_at": "2026-08-07T23:32:56+01:00",
    "assets": [
        {
            "name": "dwproton-11.0-11-x86_64.sha512sum",
            "size": 20,
            "browser_download_url": "https://example.com/dwproton-11.0-11-x86_64.sha512sum",
        },
        {
            "name": "dwproton-11.0-11-x86_64.tar.xz",
            "size": 200,
            "browser_download_url": "https://example.com/dwproton-11.0-11-x86_64.tar.xz",
        },
        {
            "name": "dwproton-11.0-11-x86_64.tar.xz.torrent",
            "size": 30,
            "browser_download_url": "https://example.com/dwproton-11.0-11-x86_64.tar.xz.torrent",
        },
    ],
}


def test_dwproton_fetch_release_data_ignores_torrent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, DWPROTON_RELEASE)

    installer = DWProtonInstaller()
    release_data = asyncio_run(installer._fetch_release_data("dwproton-11.0-11", Arch.X86_64))

    assert release_data.version == "dwproton-11.0-11"
    assert release_data.download == "https://example.com/dwproton-11.0-11-x86_64.tar.xz"
    assert release_data.checksum == "https://example.com/dwproton-11.0-11-x86_64.sha512sum"
    assert release_data.original_filename == "dwproton-11.0-11-x86_64.tar.xz"


def test_dwproton_install_writes_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    installer = DWProtonInstaller()
    version = "dwproton-11.0-11"
    archive_bytes = _make_tar_xz(version)

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v,
            date="2026-08-07",
            download="https://example.com/dwproton-11.0-11-x86_64.tar.xz",
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

    installed_dir = tmp_path / "compatibilitytools.d" / version
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "dwproton"
    assert stored_info.version == version
    assert info.arch == Arch.X86_64


CACHYOS_RELEASE: dict[str, Any] = {
    "tag_name": "cachyos-11.0-20260703-slr",
    "published_at": "2026-07-22T00:57:55Z",
    "assets": [
        {
            "name": "proton-cachyos-11.0-20260703-slr-arm64.sha512sum",
            "size": 20,
            "browser_download_url": "https://example.com/arm64.sha512sum",
        },
        {
            "name": "proton-cachyos-11.0-20260703-slr-arm64.tar.xz",
            "size": 300,
            "browser_download_url": "https://example.com/arm64.tar.xz",
        },
        {
            "name": "proton-cachyos-11.0-20260703-slr-x86_64.sha512sum",
            "size": 20,
            "browser_download_url": "https://example.com/x86_64.sha512sum",
        },
        {
            "name": "proton-cachyos-11.0-20260703-slr-x86_64.tar.xz",
            "size": 100,
            "browser_download_url": "https://example.com/x86_64.tar.xz",
        },
        {
            "name": "proton-cachyos-11.0-20260703-slr-x86_64_v3.sha512sum",
            "size": 20,
            "browser_download_url": "https://example.com/v3.sha512sum",
        },
        {
            "name": "proton-cachyos-11.0-20260703-slr-x86_64_v3.tar.xz",
            "size": 200,
            "browser_download_url": "https://example.com/v3.tar.xz",
        },
    ],
}


def _cachyos_with_hwcaps(
    monkeypatch: pytest.MonkeyPatch, hwcaps: set[str]
) -> ProtonCachyOSInstaller:
    monkeypatch.setattr(
        "protondl.installers.proton_cachyos.detect_hwcaps", lambda: frozenset(hwcaps)
    )
    return ProtonCachyOSInstaller()


def test_cachyos_asset_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    installer = _cachyos_with_hwcaps(monkeypatch, {"x86_64", "x86_64_v2", "x86_64_v3"})

    assert installer._asset_matches_arch(
        "proton-cachyos-11.0-20260703-slr-x86_64_v3.tar.xz", Arch.X86_64, ".tar.xz"
    )
    assert installer._asset_matches_arch(
        "proton-cachyos-11.0-20260703-slr-x86_64.tar.xz", Arch.X86_64, ".tar.xz"
    )
    assert installer._asset_matches_arch(
        "proton-cachyos-11.0-20260703-slr-arm64.tar.xz", Arch.AARCH64, ".tar.xz"
    )
    assert not installer._asset_matches_arch(
        "proton-cachyos-11.0-20260703-slr-arm64.tar.xz", Arch.X86_64, ".tar.xz"
    )
    assert installer._release_archs_from_assets(CACHYOS_RELEASE["assets"]) == [
        Arch.X86_64,
        Arch.AARCH64,
    ]


def test_cachyos_excludes_unsupported_hwcap_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = _cachyos_with_hwcaps(monkeypatch, {"x86_64"})

    assert not installer._asset_matches_arch(
        "proton-cachyos-11.0-20260703-slr-x86_64_v3.tar.xz", Arch.X86_64, ".tar.xz"
    )
    assert not installer._asset_matches_arch(
        "proton-cachyos-11.0-20260703-slr-x86_64_v4.tar.xz", Arch.X86_64, ".tar.xz"
    )
    assert installer._asset_matches_arch(
        "proton-cachyos-11.0-20260703-slr-x86_64.tar.xz", Arch.X86_64, ".tar.xz"
    )


def test_cachyos_release_with_only_unsupported_variants_not_advertised_as_x86_64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release: dict[str, Any] = {
        "tag_name": "cachyos-12.0-20260722-slr",
        "published_at": "2026-07-22T00:57:55Z",
        "assets": [
            {
                "name": "proton-cachyos-12.0-20260722-slr-x86_64_v4.tar.xz",
                "size": 100,
                "browser_download_url": "https://example.com/v4.tar.xz",
            },
            {
                "name": "proton-cachyos-12.0-20260722-slr-arm64.tar.xz",
                "size": 300,
                "browser_download_url": "https://example.com/arm64.tar.xz",
            },
        ],
    }
    _fake_async_client(monkeypatch, [release])
    _cachyos_with_hwcaps(monkeypatch, {"x86_64"})

    releases = asyncio_run(ProtonCachyOSInstaller().fetch_releases())

    assert releases == [ReleaseVersion("cachyos-12.0-20260722-slr", (Arch.AARCH64,))]


def test_cachyos_release_with_only_unsupported_variants_has_no_x86_64_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release: dict[str, Any] = {
        "tag_name": "cachyos-12.0-20260722-slr",
        "published_at": "2026-07-22T00:57:55Z",
        "assets": [
            {
                "name": "proton-cachyos-12.0-20260722-slr-x86_64_v4.tar.xz",
                "size": 100,
                "browser_download_url": "https://example.com/v4.tar.xz",
            },
        ],
    }
    _fake_async_client(monkeypatch, release)
    installer = _cachyos_with_hwcaps(monkeypatch, {"x86_64"})

    release_data = asyncio_run(
        installer._fetch_release_data("cachyos-12.0-20260722-slr", Arch.X86_64)
    )

    assert release_data.download is None


def test_cachyos_fetch_releases_lists_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, [CACHYOS_RELEASE])
    _cachyos_with_hwcaps(monkeypatch, {"x86_64", "x86_64_v2", "x86_64_v3"})

    releases = asyncio_run(ProtonCachyOSInstaller().fetch_releases())

    assert releases == [ReleaseVersion("cachyos-11.0-20260703-slr", (Arch.X86_64, Arch.AARCH64))]


def test_cachyos_selects_best_hwcap_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, CACHYOS_RELEASE)
    installer = _cachyos_with_hwcaps(monkeypatch, {"x86_64", "x86_64_v2", "x86_64_v3"})

    release_data = asyncio_run(
        installer._fetch_release_data("cachyos-11.0-20260703-slr", Arch.X86_64)
    )

    assert release_data.download == "https://example.com/v3.tar.xz"
    assert release_data.checksum == "https://example.com/v3.sha512sum"
    assert release_data.original_filename == "proton-cachyos-11.0-20260703-slr-x86_64_v3.tar.xz"


def test_cachyos_falls_back_to_plain_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, CACHYOS_RELEASE)
    installer = _cachyos_with_hwcaps(monkeypatch, {"x86_64"})

    release_data = asyncio_run(
        installer._fetch_release_data("cachyos-11.0-20260703-slr", Arch.X86_64)
    )

    assert release_data.download == "https://example.com/x86_64.tar.xz"
    assert release_data.checksum == "https://example.com/x86_64.sha512sum"


def test_cachyos_selects_arm64_build(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, CACHYOS_RELEASE)

    release_data = asyncio_run(
        ProtonCachyOSInstaller()._fetch_release_data("cachyos-11.0-20260703-slr", Arch.AARCH64)
    )

    assert release_data.download == "https://example.com/arm64.tar.xz"
    assert release_data.checksum == "https://example.com/arm64.sha512sum"


def test_cachyos_install_writes_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    installer = _cachyos_with_hwcaps(monkeypatch, {"x86_64", "x86_64_v2", "x86_64_v3"})
    version = "cachyos-11.0-20260703-slr"
    archive_bytes = _make_tar_xz(version)

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version=v,
            date="2026-07-22",
            download="https://example.com/v3.tar.xz",
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

    installed_dir = tmp_path / "compatibilitytools.d" / version
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "Proton-CachyOS"
    assert stored_info.version == version
    assert info.arch == Arch.X86_64


def test_steam_play_none_fetch_releases_returns_main() -> None:
    assert asyncio_run(SteamPlayNoneInstaller().fetch_releases()) == [ReleaseVersion("main")]


def test_steam_play_none_fetch_release_data() -> None:
    installer = SteamPlayNoneInstaller()
    release_data = asyncio_run(installer._fetch_release_data("main", Arch.X86_64))

    assert release_data.version == "main"
    assert release_data.download == (
        "https://github.com/Scrumplex/Steam-Play-None/archive/refs/heads/main.tar.gz"
    )
    assert release_data.original_filename == "main.tar.gz"
    assert release_data.checksum is None


def test_steam_play_none_find_installed_dir_renames(
    tmp_path: Path,
) -> None:
    installer = SteamPlayNoneInstaller()
    install_dir = tmp_path / "compatibilitytools.d"
    install_dir.mkdir()
    before = set(install_dir.iterdir())

    assert installer._find_installed_dir(install_dir, before, "main") is None

    (install_dir / "Steam-Play-None-main").mkdir()

    target = installer._find_installed_dir(install_dir, before, "main")
    assert target == install_dir / "Steam-Play-None"
    assert not (install_dir / "Steam-Play-None-main").exists()


def test_steam_play_none_find_installed_dir_replaces_existing(tmp_path: Path) -> None:
    installer = SteamPlayNoneInstaller()
    install_dir = tmp_path / "compatibilitytools.d"
    install_dir.mkdir()
    before = set(install_dir.iterdir())
    old_dir = install_dir / "Steam-Play-None"
    old_dir.mkdir()
    (old_dir / "old.txt").write_text("old", encoding="utf-8")

    (install_dir / "Steam-Play-None-main").mkdir()
    target = installer._find_installed_dir(install_dir, before, "main")

    assert target == old_dir
    assert not (old_dir / "old.txt").exists()


def test_steam_play_none_install_writes_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    installer = SteamPlayNoneInstaller()
    archive_bytes = _make_tar_gz("Steam-Play-None-main")

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version="main",
            date="",
            download="https://example.com/main.tar.gz",
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

    info = asyncio.run(installer.install("main", launcher, arch=Arch.X86_64))

    installed_dir = tmp_path / "compatibilitytools.d" / "Steam-Play-None"
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()
    assert not (installed_dir.parent / "Steam-Play-None-main").exists()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "Steam-Play-None"
    assert stored_info.version == "main"
    assert info.arch == Arch.X86_64


STL_RELEASE_DICT = {
    "tag_name": "v12.12",
    "published_at": "2023-03-14T12:00:00Z",
    "tarball_url": "https://api.github.com/repos/sonic2kk/steamtinkerlaunch/tarball/v12.12",
    "assets": [],
}


def test_steam_tinkerlaunch_fetch_releases_returns_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, [STL_RELEASE_DICT])

    releases = asyncio_run(SteamTinkerLaunchInstaller().fetch_releases())

    assert [r.version for r in releases] == ["v12.12"]
    assert releases[0].archs == (Arch.X86_64,)


def test_steam_tinkerlaunch_fetch_release_data_uses_tarball_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, STL_RELEASE_DICT)

    release_data = asyncio_run(
        SteamTinkerLaunchInstaller()._fetch_release_data("v12.12", Arch.X86_64)
    )

    assert release_data.version == "v12.12"
    assert release_data.download == STL_RELEASE_DICT["tarball_url"]
    assert release_data.original_filename is None


def test_steam_tinkerlaunch_fetch_release_data_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, STL_RELEASE_DICT)

    release_data = asyncio_run(
        SteamTinkerLaunchInstaller()._fetch_release_data("latest", Arch.X86_64)
    )

    assert release_data.version == "v12.12"
    assert release_data.download == STL_RELEASE_DICT["tarball_url"]


def test_steam_tinkerlaunch_fetch_release_data_unknown_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, {"message": "Not Found"})

    with pytest.raises(ValueError):
        asyncio_run(SteamTinkerLaunchInstaller()._fetch_release_data("nope", Arch.X86_64))


def test_steam_tinkerlaunch_find_installed_dir_renames_and_writes_vdfs(tmp_path: Path) -> None:
    installer = SteamTinkerLaunchInstaller()
    install_dir = tmp_path / "compatibilitytools.d"
    install_dir.mkdir()
    before = set(install_dir.iterdir())

    assert installer._find_installed_dir(install_dir, before, "v12.12") is None

    (install_dir / "sonic2kk-steamtinkerlaunch-9de3341").mkdir()

    target = installer._find_installed_dir(install_dir, before, "v12.12")

    assert target == install_dir / "SteamTinkerLaunch"
    assert not (install_dir / "sonic2kk-steamtinkerlaunch-9de3341").exists()
    assert (target / "compatibilitytool.vdf").is_file()
    assert (target / "toolmanifest.vdf").is_file()
    assert "Proton-stl" in (target / "compatibilitytool.vdf").read_text(encoding="utf-8")
    assert '"/steamtinkerlaunch run"' in (target / "toolmanifest.vdf").read_text(encoding="utf-8")


def test_steam_tinkerlaunch_find_installed_dir_replaces_existing(tmp_path: Path) -> None:
    installer = SteamTinkerLaunchInstaller()
    install_dir = tmp_path / "compatibilitytools.d"
    install_dir.mkdir()
    before = set(install_dir.iterdir())
    old_dir = install_dir / "SteamTinkerLaunch"
    old_dir.mkdir()
    (old_dir / "old.txt").write_text("old", encoding="utf-8")

    (install_dir / "sonic2kk-steamtinkerlaunch-9de3341").mkdir()
    target = installer._find_installed_dir(install_dir, before, "v12.12")

    assert target == old_dir
    assert not (old_dir / "old.txt").exists()


def test_steam_tinkerlaunch_install_writes_version_file_and_vdfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    installer = SteamTinkerLaunchInstaller()
    archive_bytes = _make_tar_gz("sonic2kk-steamtinkerlaunch-9de3341")

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version="v12.12",
            date="2023-03-14",
            download="https://example.com/tarball/v12.12",
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

    info = asyncio.run(installer.install("v12.12", launcher, arch=Arch.X86_64))

    installed_dir = tmp_path / "compatibilitytools.d" / "SteamTinkerLaunch"
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()
    assert (installed_dir / "compatibilitytool.vdf").is_file()
    assert (installed_dir / "toolmanifest.vdf").is_file()
    assert not (installed_dir.parent / "sonic2kk-steamtinkerlaunch-9de3341").exists()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "SteamTinkerLaunch"
    assert stored_info.version == "v12.12"
    assert info.arch == Arch.X86_64


def test_steam_tinkerlaunch_git_fetch_releases_returns_master() -> None:
    releases = asyncio_run(SteamTinkerLaunchGitInstaller().fetch_releases())
    assert releases == [ReleaseVersion("master")]


def test_steam_tinkerlaunch_git_fetch_release_data() -> None:
    installer = SteamTinkerLaunchGitInstaller()
    release_data = asyncio_run(installer._fetch_release_data("master", Arch.X86_64))

    assert release_data.version == "master"
    assert release_data.download == (
        "https://github.com/sonic2kk/steamtinkerlaunch/archive/refs/heads/master.tar.gz"
    )
    assert release_data.original_filename is None


def test_steam_tinkerlaunch_git_install_writes_version_file_and_vdfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = SteamLauncher("Steam", tmp_path, InstallMode.NATIVE)
    installer = SteamTinkerLaunchGitInstaller()
    archive_bytes = _make_tar_gz("sonic2kk-steamtinkerlaunch-9de3341")

    async def mock_fetch_release_data(v: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version="master",
            date="",
            download="https://example.com/master.tar.gz",
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

    info = asyncio.run(installer.install("master", launcher, arch=Arch.X86_64))

    installed_dir = tmp_path / "compatibilitytools.d" / "SteamTinkerLaunch"
    version_file = installed_dir / "protondl_version.json"
    assert version_file.is_file()
    assert (installed_dir / "compatibilitytool.vdf").is_file()
    assert (installed_dir / "toolmanifest.vdf").is_file()

    stored_info = read_version_file(installed_dir)
    assert stored_info is not None
    assert stored_info.compat_tool == "SteamTinkerLaunch-git"
    assert stored_info.version == "master"
    assert info.arch == Arch.X86_64
