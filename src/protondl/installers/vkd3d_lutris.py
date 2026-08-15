from protondl.core.models import CompatToolType
from protondl.installers.vkd3dproton import VKD3DProtonInstaller


class VKD3DLutrisInstaller(VKD3DProtonInstaller):
    name = "vkd3d-lutris"
    description = (
        "Fork of Wine's VKD3D which aims to implement the full Direct3D 12 API "
        "on top of Vulkan (Lutris Release)."
    )
    tool_type = CompatToolType.VKD3D
    advanced = False
    info_url = "https://github.com/lutris/vkd3d"
    release_info_url = "https://github.com/lutris/vkd3d/releases/tag/{version}"
    api_url = "https://api.github.com/repos/lutris/vkd3d/releases"
    release_format = ".tar.xz"
    checksum_suffix = ""
