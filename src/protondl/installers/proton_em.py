from protondl.core.base_installer import CtInstaller
from protondl.core.models import CompatToolType


class ProtonEMInstaller(CtInstaller):
    name = "Proton-EM"
    description = (
        "Fork of Valve's Proton with Wine-Wayland and AMD FidelityFX Super Resolution 4 patches."
    )
    tool_type = CompatToolType.PROTON
    advanced = True
    info_url = "https://github.com/Etaash-mathamsetty/Proton"
    release_info_url = "https://github.com/Etaash-mathamsetty/Proton/releases/tag/{version}"
    api_url = "https://api.github.com/repos/Etaash-mathamsetty/Proton/releases"
    release_format = ".tar.xz"
    # Releases ship a .sha256sum asset; the base verifier computes SHA-512, so
    # the checksum is skipped to avoid a false mismatch.
    checksum_suffix = ""
