from protondl.core.models import CompatToolType
from protondl.installers.proton_tkg_winemaster import ProtonTkgWinemasterInstaller


class ProtonTkgNtsyncInstaller(ProtonTkgWinemasterInstaller):
    name = "Proton-Tkg (Wine Master NTSYNC)"
    description = (
        "Custom Proton build for running Windows games, built with the Wine-tkg build system. "
        "This build is based on Wine Master and patched with NTSYNC."
    )
    tool_type = CompatToolType.PROTON
    advanced = True

    proton_package_name = "proton-arch-ntsync-nopackage.yml"
