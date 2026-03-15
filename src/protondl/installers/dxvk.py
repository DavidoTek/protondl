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
