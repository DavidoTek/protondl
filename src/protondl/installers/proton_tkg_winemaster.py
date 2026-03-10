from protondl.installers.proton_tkg import ProtonTkgInstaller
from protondl.launchers.steam import SteamLauncher


class ProtonTkgWinemasterInstaller(ProtonTkgInstaller):
    name = "Proton-Tkg (Wine Master)"
    description = (
        "Custom Proton build for running Windows games, built with the Wine-tkg build system. "
        "This build is based on Wine Master."
    )
    advanced = True
    supported_launchers = [SteamLauncher]

    proton_package_name = "proton-arch-nopackage.yml"
