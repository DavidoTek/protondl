import shutil
from pathlib import Path

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.core.models import Arch, CompatToolType, ReleaseData, ReleaseVersion
from protondl.launchers.steam import SteamLauncher

EXTRACTED_DIR_NAME = "Steam-Play-None-main"


class SteamPlayNoneInstaller(CtInstaller):
    name = "Steam-Play-None"
    description = "Runs Linux games as is, even if Valve recommends Proton for a game."
    tool_type = CompatToolType.PROTON
    advanced = False
    info_url = "https://github.com/Scrumplex/Steam-Play-None"
    release_info_url = "https://github.com/Scrumplex/Steam-Play-None"
    api_url = "https://github.com/Scrumplex/Steam-Play-None"
    release_format = ".tar.gz"
    checksum_suffix = ""

    download_url = "https://github.com/Scrumplex/Steam-Play-None/archive/refs/heads/main.tar.gz"

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        return [ReleaseVersion("main")]

    async def _fetch_release_data(self, version: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version="main",
            date="",
            download=self.download_url,
            original_filename="main.tar.gz",
        )

    def supports_launcher(self, launcher: Launcher) -> bool:
        return isinstance(launcher, SteamLauncher)

    def _find_installed_dir(
        self, install_dir: Path, before: set[Path], version: str
    ) -> Path | None:
        extracted = install_dir / EXTRACTED_DIR_NAME
        target = install_dir / "Steam-Play-None"
        if extracted.is_dir():
            if target.exists():
                shutil.rmtree(target)
            extracted.rename(target)
        return target if target.is_dir() else None
