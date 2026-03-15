from protondl.core.models import CompatToolType
from protondl.installers.proton_tkg import ProtonTkgInstaller


class WineTkgWinemasterInstaller(ProtonTkgInstaller):
    name = "Wine-Tkg (Wine Master)"
    description = (
        "Custom Wine build for running Windows games, built with the Wine-tkg build system."
        "This build is based on Wine Master."
    )
    tool_type = CompatToolType.WINE
    advanced = True

    proton_package_name = "wine-ubuntu.yml"
