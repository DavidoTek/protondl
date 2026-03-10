from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.installers.ge_proton import GEProtonInstaller
from protondl.installers.proton_tkg import ProtonTkgInstaller
from protondl.installers.proton_tkg_winemaster import ProtonTkgWinemasterInstaller

CT_INSTALLERS = [
    GEProtonInstaller(),
    ProtonTkgInstaller(),
    ProtonTkgWinemasterInstaller(),
]


def get_tools_for_launcher(launcher: Launcher, advanced: bool = True) -> list[CtInstaller]:
    """
    Returns a list of compatibility tool installers that support the specified launcher.

    Args:
        launcher (Launcher): The launcher instance.
        advanced (bool): Whether to include advanced tools.
    """
    return [
        tool
        for tool in CT_INSTALLERS
        if tool.supports_launcher(launcher) and (advanced or not tool.advanced)
    ]
