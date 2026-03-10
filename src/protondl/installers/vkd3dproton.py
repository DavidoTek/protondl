from protondl.core.base_installer import CtInstaller
from protondl.core.models import CompatToolType


class VKD3DProtonInstaller(CtInstaller):
    name = "vkd3d-proton"
    description = (
        "Fork of Wine's VKD3D which aims to implement the full "
        + "Direct3D 12 API on top of Vulkan (Valve Release)."
    )
    tool_type = CompatToolType.VKD3D
    advanced = False
    info_url = "https://github.com/HansKristian-Work/vkd3d-proton"
    release_info_url = "https://github.com/HansKristian-Work/vkd3d-proton/releases/tag/{version}"
    api_url = "https://api.github.com/repos/HansKristian-Work/vkd3d-proton/releases"
    release_format = ".tar.zst"
    checksum_suffix = ""
