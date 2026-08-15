from protondl.core.models import CompatToolType
from protondl.installers.steam_tool import SteamToolInstaller


class RobertaInstaller(SteamToolInstaller):
    name = "Roberta"
    description = "Steam Play compatibility tool to run adventure games using native Linux ScummVM."
    tool_type = CompatToolType.PROTON
    advanced = False
    info_url = "https://github.com/dreamer/roberta"
    release_info_url = "https://github.com/dreamer/roberta/releases/tag/{version}"
    api_url = "https://api.github.com/repos/dreamer/roberta/releases"
    release_format = ".tar.xz"
    checksum_suffix = ""

    fixed_dir_name = "roberta"
