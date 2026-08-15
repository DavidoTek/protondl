from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.core.models import CompatToolType
from protondl.installers.boxtron import BoxtronInstaller
from protondl.installers.dwproton import DWProtonInstaller
from protondl.installers.dxvk import DXVKInstaller
from protondl.installers.dxvk_async import DXVKAsyncInstaller
from protondl.installers.dxvk_nightly import DXVKNightlyInstaller
from protondl.installers.ge_proton import GEProtonInstaller
from protondl.installers.kron4ek_wine import Kron4ekWineInstaller
from protondl.installers.lutris_wine import LutrisWineInstaller
from protondl.installers.luxtorpeda import LuxtorpedaInstaller
from protondl.installers.proton_em import ProtonEMInstaller
from protondl.installers.proton_tkg import ProtonTkgInstaller
from protondl.installers.proton_tkg_ntsync import ProtonTkgNtsyncInstaller
from protondl.installers.proton_tkg_valvewine import ProtonTkgValveWineInstaller
from protondl.installers.proton_tkg_winemaster import ProtonTkgWinemasterInstaller
from protondl.installers.roberta import RobertaInstaller
from protondl.installers.rtsp_proton import RTSPProtonInstaller
from protondl.installers.vkd3d_lutris import VKD3DLutrisInstaller
from protondl.installers.vkd3dproton import VKD3DProtonInstaller
from protondl.installers.wine_tkg_winemaster import WineTkgWinemasterInstaller

CT_INSTALLERS = [
    GEProtonInstaller(),
    ProtonTkgInstaller(),
    ProtonTkgWinemasterInstaller(),
    ProtonTkgValveWineInstaller(),
    WineTkgWinemasterInstaller(),
    DXVKInstaller(),
    DXVKAsyncInstaller(),
    DXVKNightlyInstaller(),
    VKD3DProtonInstaller(),
    VKD3DLutrisInstaller(),
    BoxtronInstaller(),
    RobertaInstaller(),
    ProtonEMInstaller(),
    RTSPProtonInstaller(),
    LutrisWineInstaller(),
    LuxtorpedaInstaller(),
    Kron4ekWineInstaller(),
    ProtonTkgNtsyncInstaller(),
    DWProtonInstaller(),
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


def get_tool_type_by_name(name: str) -> CompatToolType | None:
    """
    Returns the compatibility tool type of the installer with the given name.

    Args:
        name (str): The name of the compatibility tool installer.

    Returns:
        CompatToolType | None: The tool type, or None if no matching installer exists.
    """
    for installer in CT_INSTALLERS:
        if installer.name == name:
            return installer.tool_type
    return None


def get_installer_by_name(name: str) -> CtInstaller | None:
    """
    Returns the compatibility tool installer with the given name.

    Args:
        name (str): The name of the compatibility tool installer.

    Returns:
        CtInstaller | None: The matching installer, or None if no installer exists.
    """
    for installer in CT_INSTALLERS:
        if installer.name == name:
            return installer
    return None
