from collections.abc import Mapping
from typing import Any

from protondl.core.base_installer import CtInstaller
from protondl.core.models import CompatToolType


class DXVKInstaller(CtInstaller):
    name = "DXVK"
    description = "Vulkan based implementation of Direct3D 8, 9, 10, and 11 for Linux/Wine."
    tool_type = CompatToolType.DXVK
    advanced = False
    info_url = "https://github.com/doitsujin/dxvk"
    release_info_url = "https://github.com/doitsujin/dxvk/releases/tag/{version}"
    api_url = "https://api.github.com/repos/doitsujin/dxvk/releases"
    release_format = ".tar.gz"
    checksum_suffix = ""

    def _asset_priority(self, asset: Mapping[str, Any]) -> int:
        """
        Returns the priority of an asset matching the release format.

        DXVK releases also ship a "native" (Steam Runtime) build whose name
        also ends in ".tar.gz". Only the Wine build should be installed, so
        native assets get a lower priority.

        Args:
            asset (Mapping): The release asset (from the API response).

        Returns:
            int: The priority of the asset (higher is preferred).
        """
        if "native" in asset.get("name", "").lower():
            return 0
        return 1
