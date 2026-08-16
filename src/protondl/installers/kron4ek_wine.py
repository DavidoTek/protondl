from collections.abc import Callable
from typing import Any

import httpx

from protondl.core.base_installer import CtInstaller
from protondl.core.models import Arch, CompatToolType, ReleaseData, ReleaseVersion
from protondl.util.download import check_rate_limits, fetch_project_release_data

_WOW64_SUFFIX = " (wow64)"
_AMD64_SUFFIX = " (amd64)"


class Kron4ekWineInstaller(CtInstaller):
    name = "Kron4ek Wine-Builds Vanilla"
    description = (
        "Compatibility tool 'Wine' to run Windows games on Linux, compiled from the "
        "official WineHQ sources by Kron4ek."
    )
    tool_type = CompatToolType.WINE
    advanced = False
    info_url = "https://github.com/Kron4ek/Wine-Builds"
    release_info_url = "https://github.com/Kron4ek/Wine-Builds/releases/tag/{version}"
    api_url = "https://api.github.com/repos/Kron4ek/Wine-Builds/releases"
    release_format = ".tar.xz"
    checksum_suffix = ""

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        """
        List available releases, one version per (amd64 / amd64-wow64) build
        variant, e.g. '11.15 (amd64)' and '11.15 (wow64)'.
        """
        versions: list[ReleaseVersion] = []
        headers = self.request_config.get_headers(self.api_url)
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            response = await client.get(self.api_url, params={"per_page": count, "page": page})
            for release in check_rate_limits(response.json()):
                tag_name = release.get("tag_name")
                if not tag_name:
                    continue
                seen: set[str] = set()
                for asset in release.get("assets", []):
                    name = asset.get("name", "")
                    if (
                        "amd64-wow64" in name
                        and self.release_format in name
                        and "staging" not in name
                    ):
                        version = f"{tag_name}{_WOW64_SUFFIX}"
                    elif (
                        "amd64" in name
                        and self.release_format in name
                        and "staging" not in name
                        and "wow64" not in name
                    ):
                        version = f"{tag_name}{_AMD64_SUFFIX}"
                    else:
                        continue
                    if version not in seen:
                        seen.add(version)
                        versions.append(ReleaseVersion(version=version, archs=(Arch.X86_64,)))
        return versions

    async def _fetch_release_data(self, version: str, arch: Arch) -> ReleaseData:
        """
        Fetches the release data of the matching amd64 or amd64-wow64 build.

        The version string carries the build variant, e.g. '11.15 (amd64)' or
        '11.15 (wow64)'; it maps back to the plain release tag while only
        considering assets of the requested variant.
        """
        if version.endswith(_WOW64_SUFFIX):
            tag = version[: -len(_WOW64_SUFFIX)]
            asset_condition = self._wow64_asset_condition()
        elif version.endswith(_AMD64_SUFFIX):
            tag = version[: -len(_AMD64_SUFFIX)]
            asset_condition = self._amd64_asset_condition()
        else:
            raise ValueError(
                f"Invalid version '{version}' for {self.name}. "
                f"Must end with '{_AMD64_SUFFIX}' or '{_WOW64_SUFFIX}'."
            )

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
        if version.endswith(_WOW64_SUFFIX):
            return "wow64"
        if version.endswith(_AMD64_SUFFIX):
            return "amd64"
        return ""

    @staticmethod
    def _wow64_asset_condition() -> Callable[[dict[str, Any]], bool]:
        """
        Returns the asset filter for amd64-wow64 builds.
        """

        def condition(asset: dict[str, Any]) -> bool:
            name = asset.get("name", "")
            return "amd64-wow64" in name and "staging" not in name

        return condition

    @staticmethod
    def _amd64_asset_condition() -> Callable[[dict[str, Any]], bool]:
        """
        Returns the asset filter for plain amd64 builds.
        """

        def condition(asset: dict[str, Any]) -> bool:
            name = asset.get("name", "")
            return "amd64" in name and "staging" not in name and "wow64" not in name

        return condition
