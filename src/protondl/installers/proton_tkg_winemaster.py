from protondl.core.models import CompatToolType
from protondl.installers.proton_tkg import ProtonTkgInstaller


class ProtonTkgWinemasterInstaller(ProtonTkgInstaller):
    name = "Proton-Tkg (Wine Master)"
    description = (
        "Custom Proton build for running Windows games, built with the Wine-tkg build system. "
        "This build is based on Wine Master."
    )
    tool_type = CompatToolType.PROTON
    advanced = True

    proton_package_name = "proton-arch-nopackage.yml"
