from protondl.core.base_installer import CtInstaller
from protondl.core.models import CompatToolType


class DXVKAsyncInstaller(CtInstaller):
    name = "DXVK Async"
    description = (
        "Vulkan based implementation of Direct3D 8, 9, 10, and 11 for Linux/Wine"
        "with gplasync patch by Ph42oN."
    )
    tool_type = CompatToolType.DXVK
    advanced = False
    info_url = "https://gitlab.com/Ph42oN/dxvk-gplasync"
    release_info_url = "https://gitlab.com/Ph42oN/dxvk-gplasync/-/releases/{version}"
    api_url = "https://gitlab.com/api/v4/projects/43488626/releases"
    release_format = ".tar.gz"
    checksum_suffix = ""
