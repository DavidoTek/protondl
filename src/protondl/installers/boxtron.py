from protondl.core.models import CompatToolType
from protondl.installers.steam_tool import SteamToolInstaller


class BoxtronInstaller(SteamToolInstaller):
    name = "Boxtron"
    description = "Steam Play compatibility tool to run DOS games using native Linux DOSBox."
    tool_type = CompatToolType.PROTON
    advanced = False
    info_url = "https://github.com/dreamer/boxtron"
    release_info_url = "https://github.com/dreamer/boxtron/releases/tag/{version}"
    api_url = "https://api.github.com/repos/dreamer/boxtron/releases"
    release_format = ".tar.xz"
    checksum_suffix = ""

    fixed_dir_name = "boxtron"
