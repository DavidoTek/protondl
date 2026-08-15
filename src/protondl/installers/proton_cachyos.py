import re
from collections.abc import Mapping
from typing import Any

from protondl.core.models import Arch, ReleaseData
from protondl.installers.ge_proton import GEProtonInstaller
from protondl.util.download import fetch_project_release_data
from protondl.util.helpers import detect_hwcaps

_HWCAP_RE = re.compile(r"-x86_64(_v[234])?\.tar\.xz$")
_HWCAP_LEVELS = {"": 1, "_v2": 2, "_v3": 3, "_v4": 4}


class ProtonCachyOSInstaller(GEProtonInstaller):
    name = "Proton-CachyOS"
    description = (
        "Steam compatibility tool from the CachyOS Linux distribution "
        "with CPU-specific optimizations."
    )
    advanced = False
    info_url = "https://github.com/CachyOS/proton-cachyos"
    release_info_url = "https://github.com/CachyOS/proton-cachyos/releases/tag/{version}"
    api_url = "https://api.github.com/repos/CachyOS/proton-cachyos/releases"
    release_format = ".tar.xz"
    checksum_suffix = ".sha512sum"

    supported_archs = (Arch.X86_64, Arch.AARCH64)
    arch_release_suffixes = {Arch.X86_64: "-x86_64", Arch.AARCH64: "-arm64"}

    def _asset_matches_arch(self, name: str, arch: Arch, file_suffix: str) -> bool:
        if arch is Arch.X86_64:
            return re.search(rf"-x86_64(_v[234])?{re.escape(file_suffix)}$", name) is not None
        return super()._asset_matches_arch(name, arch, file_suffix)

    def _asset_priority(self, asset: Mapping[str, Any]) -> int:
        name = asset.get("name", "")
        match = _HWCAP_RE.search(str(name))
        if match is None:
            return 0
        suffix = match.group(1) or ""
        variant = f"x86_64{suffix}"
        if variant not in detect_hwcaps():
            return 0
        return _HWCAP_LEVELS[suffix]

    async def _fetch_release_data(self, version: str, arch: Arch) -> ReleaseData:
        release_data = await fetch_project_release_data(
            release_url=self.api_url,
            release_format=self.release_format,
            config=self.request_config,
            tag=version,
            checksum_suffix="",
            asset_condition=lambda asset: self._asset_matches_arch(
                asset.get("name", ""), arch, self.release_format
            ),
            asset_priority=self._asset_priority,
        )
        if release_data.download and release_data.download.endswith(self.release_format):
            release_data.checksum = (
                release_data.download[: -len(self.release_format)] + self.checksum_suffix
            )
        return release_data
