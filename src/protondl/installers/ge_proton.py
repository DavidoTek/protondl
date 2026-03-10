from protondl.core.base_installer import CtInstaller
from protondl.core.models import CompatToolType


class GEProtonInstaller(CtInstaller):
    name = "GE-Proton"
    description = "A community-built version of Proton with additional features and fixes."
    tool_type = CompatToolType.PROTON
    advanced = False
    info_url = "https://github.com/GloriousEggroll/proton-ge-custom"
    release_info_url = "https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/{version}"
    api_url = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"
    release_format = ".tar.gz"
    checksum_suffix = ".sha512sum"
