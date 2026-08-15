import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.core.models import Arch, CompatToolType, ReleaseData, ReleaseVersion
from protondl.launchers.steam import SteamLauncher
from protondl.util.download import check_rate_limits

STL_DIR_NAME = "SteamTinkerLaunch"
STL_TARBALL_PREFIX = "sonic2kk-steamtinkerlaunch-"
STL_INTERNAL_NAME = "Proton-stl"


class SteamTinkerLaunchInstaller(CtInstaller):
    name = "SteamTinkerLaunch"
    description = (
        "Linux wrapper tool for use with the Steam client which allows for easy "
        "graphical configuration of game tools for Proton and native Linux games."
    )
    tool_type = CompatToolType.PROTON
    advanced = False
    info_url = "https://github.com/sonic2kk/steamtinkerlaunch"
    release_info_url = "https://github.com/sonic2kk/steamtinkerlaunch/releases/tag/{version}"
    api_url = "https://api.github.com/repos/sonic2kk/steamtinkerlaunch/releases"
    release_format = ".tar.gz"
    checksum_suffix = ""

    def supports_launcher(self, launcher: Launcher) -> bool:
        return isinstance(launcher, SteamLauncher)

    def _release_archs_from_assets(self, assets: Sequence[dict[str, Any]]) -> list[Arch]:
        return [Arch.X86_64]

    async def _fetch_release_data(self, version: str, arch: Arch) -> ReleaseData:
        if version in ("", "latest"):
            fetch_url = f"{self.api_url}/latest"
        else:
            fetch_url = f"{self.api_url}/tags/{version}"

        headers = self.request_config.get_headers(fetch_url)
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            resp = await client.get(fetch_url)
            data = check_rate_limits(resp.json())

            if not isinstance(data, dict) or "tag_name" not in data:
                raise ValueError(f"Release with version '{version}' not found.")

            return ReleaseData(
                version=data["tag_name"],
                date=data.get("published_at", "unknown").split("T")[0],
                download=data.get("tarball_url"),
            )

    def _find_installed_dir(
        self, install_dir: Path, before: set[Path], version: str
    ) -> Path | None:
        new_dirs = [d for d in install_dir.iterdir() if d.is_dir() and d not in before]
        matching = [d for d in new_dirs if d.name.startswith(STL_TARBALL_PREFIX)]
        extracted = (matching or new_dirs)[0] if new_dirs else None
        if extracted is None:
            return None

        target = install_dir / STL_DIR_NAME
        if target.exists():
            shutil.rmtree(target)
        extracted.rename(target)

        self._write_stl_metadata(target)
        return target

    def _write_stl_metadata(self, install_dir: Path) -> None:
        install_dir.joinpath("compatibilitytool.vdf").write_text(
            '"compatibilitytools"\n'
            "{\n"
            '  "compat_tools"\n'
            "  {\n"
            f'    "{STL_INTERNAL_NAME}" // Internal name of this tool\n'
            "    {\n"
            '      "install_path" "."\n'
            '      "display_name" "Steam Tinker Launch"\n'
            "\n"
            '      "from_oslist"  "windows"\n'
            '      "to_oslist"    "linux"\n'
            "    }\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        install_dir.joinpath("toolmanifest.vdf").write_text(
            '"manifest"\n'
            "{\n"
            '  "commandline" "/steamtinkerlaunch run"\n'
            '  "commandline_waitforexitandrun" "/steamtinkerlaunch waitforexitandrun"\n'
            "}\n",
            encoding="utf-8",
        )


class SteamTinkerLaunchGitInstaller(SteamTinkerLaunchInstaller):
    name = "SteamTinkerLaunch-git"
    description = (
        "Development release - may be unstable. "
        "Linux wrapper tool for use with the Steam client which allows for easy "
        "graphical configuration of game tools for Proton and native Linux games."
    )
    advanced = True
    release_info_url = "https://github.com/sonic2kk/steamtinkerlaunch"

    download_url = "https://github.com/sonic2kk/steamtinkerlaunch/archive/refs/heads/master.tar.gz"

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        return [ReleaseVersion("master")]

    async def _fetch_release_data(self, version: str, arch: Arch) -> ReleaseData:
        return ReleaseData(
            version="master",
            date="",
            download=self.download_url,
        )
