from protondl.installers.proton_tkg import ProtonTkgInstaller
from protondl.launchers.steam import SteamLauncher


class ProtonTkgValveWineInstaller(ProtonTkgInstaller):
    name = "Proton-Tkg (Valve Wine)"
    description = (
        "Custom Proton build for running Windows games, built with the Wine-tkg build system. "
        "This build is based on Valve Wine bleeding_edge."
    )
    advanced = True
    supported_launchers = [SteamLauncher]

    proton_package_name = "wine-valvexbe"
