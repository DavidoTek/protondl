from protondl.core.models import CompatToolType
from protondl.installers.steam_tool import SteamToolInstaller


class LuxtorpedaInstaller(SteamToolInstaller):
    name = "Luxtorpeda"
    description = "Provides Linux-native game engines for specific Windows-only games."
    tool_type = CompatToolType.PROTON
    advanced = False
    info_url = "https://codeberg.org/luxtorpeda/luxtorpeda"
    release_info_url = "https://codeberg.org/luxtorpeda/luxtorpeda/releases/tag/{version}"
    api_url = "https://codeberg.org/api/v1/repos/luxtorpeda/luxtorpeda/releases"
    release_format = ".tar.xz"
    checksum_suffix = ".sha512"

    fixed_dir_name = "luxtorpeda"
