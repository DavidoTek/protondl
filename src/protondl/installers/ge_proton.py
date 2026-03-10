from protondl.core.base_installer import CtInstaller
from protondl.launchers.lutris import LutrisLauncher
from protondl.launchers.steam import SteamLauncher


class GEProtonInstaller(CtInstaller):
    name = "GE-Proton"
    description = "A community-built version of Proton with additional features and fixes."
    advanced = False
    supported_launchers = [SteamLauncher, LutrisLauncher]
    info_url = "https://github.com/GloriousEggroll/proton-ge-custom"
    release_info_url = "https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/{version}"
    api_url = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"
    release_format = ".tar.gz"
    checksum_suffix = ".sha512sum"
