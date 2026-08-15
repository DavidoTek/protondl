from protondl.core.base_installer import CtInstaller
from protondl.core.models import CompatToolType


class RTSPProtonInstaller(CtInstaller):
    name = "RTSP Proton"
    description = "Fork of GE-Proton with enhanced Windows Media Foundation support."
    tool_type = CompatToolType.PROTON
    advanced = True
    info_url = "https://github.com/SpookySkeletons/proton-ge-rtsp"
    release_info_url = "https://github.com/SpookySkeletons/proton-ge-rtsp/releases/tag/{version}"
    api_url = "https://api.github.com/repos/SpookySkeletons/proton-ge-rtsp/releases"
    release_format = ".tar.gz"
    checksum_suffix = ".sha512sum"
