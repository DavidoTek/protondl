from collections.abc import Callable
from typing import Any

import httpx

from protondl.core.base_installer import CtInstaller
from protondl.core.models import Arch, CompatToolType, ReleaseData, ReleaseVersion
from protondl.util.download import check_rate_limits, fetch_project_release_data


class LutrisWineInstaller(CtInstaller):
    name = "Lutris-Wine"
    description = (
        "Compatibility tool 'Wine' to run Windows games on Linux, improved by Lutris "
        "to offer better compatibility or performance in certain games."
    )
    tool_type = CompatToolType.WINE
    advanced = False
    info_url = "https://github.com/lutris/wine"
    release_info_url = "https://github.com/lutris/wine/releases/tag/{version}"
    api_url = "https://api.github.com/repos/lutris/wine/releases"
    release_format = ".tar.xz"
    checksum_suffix = ""

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        """
        List available releases, appending a separate 'lutris-fshack-' variant
        version for every release that also ships a fshack build.
        """
        versions: list[ReleaseVersion] = []
        headers = self.request_config.get_headers(self.api_url)
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            response = await client.get(self.api_url, params={"per_page": count, "page": page})
            for release in check_rate_limits(response.json()):
                tag_name = release.get("tag_name")
                if not tag_name:
                    continue
                assets = release.get("assets", [])
                archs = tuple(self._release_archs_from_assets(assets))
                versions.append(ReleaseVersion(version=tag_name, archs=archs))
                if any("lutris-fshack" in asset.get("name", "") for asset in assets):
                    fshack_version = tag_name.replace("lutris-", "lutris-fshack-", 1)
                    versions.append(ReleaseVersion(version=fshack_version, archs=archs))
        return versions

    async def _fetch_release_data(self, version: str, arch: Arch) -> ReleaseData:
        """
        Fetches the release data of the matching (fshack or regular) Lutris-Wine build.

        The fshack variant is identified by a 'lutris-fshack-' prefix in the
        version string; it maps back to the regular release tag while only
        considering fshack assets (and vice versa).
        """
        is_fshack = "fshack-" in version
        tag = version.replace("fshack-", "")
        asset_condition = self._fshack_asset_condition(is_fshack)

        release_data = await fetch_project_release_data(
            release_url=self.api_url,
            release_format=self.release_format,
            config=self.request_config,
            tag=tag,
            checksum_suffix=self.checksum_suffix,
            asset_condition=asset_condition,
        )
        release_data.version = version
        return release_data

    def variant_of(self, version: str) -> str:
        return "fshack" if "fshack-" in version else ""

    @staticmethod
    def _fshack_asset_condition(is_fshack: bool) -> Callable[[dict[str, Any]], bool]:
        """
        Returns the asset filter for fshack or regular builds.
        """

        def condition(asset: dict[str, Any]) -> bool:
            return ("fshack" in asset.get("name", "")) == is_fshack

        return condition
