from protondl.core.models import CompatToolType
from protondl.installers.proton_tkg import ProtonTkgInstaller


class ProtonTkgValveWineInstaller(ProtonTkgInstaller):
    name = "Proton-Tkg (Valve Wine)"
    description = (
        "Custom Proton build for running Windows games, built with the Wine-tkg build system. "
        "This build is based on Valve Wine bleeding_edge."
    )
    tool_type = CompatToolType.PROTON
    advanced = True

    proton_package_name = "wine-valvexbe"
