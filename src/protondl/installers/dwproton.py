from protondl.installers.ge_proton import GEProtonInstaller


class DWProtonInstaller(GEProtonInstaller):
    name = "dwproton"
    description = "Dawn Winery's custom Proton fork with fixes for various games."
    advanced = True
    info_url = "https://dawn.wine/dawn-winery/dwproton"
    release_info_url = "https://dawn.wine/dawn-winery/dwproton/releases/tag/{version}"
    api_url = "https://dawn.wine/api/v1/repos/dawn-winery/dwproton/releases"
    release_format = ".tar.xz"
    checksum_suffix = ".sha512sum"
