from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.installers.ge_proton import GEProtonInstaller

CT_INSTALLERS = [GEProtonInstaller()]


def get_tools_for_launcher(launcher: Launcher) -> list[CtInstaller]:
    """
    Returns a list of compatibility tool installers that support the specified launcher.

    Args:
        launcher (Launcher): The launcher instance.

    Returns:
        List[CtInstaller]: A filtered list of installers compatible with the launcher.
    """
    return [tool for tool in CT_INSTALLERS if tool.supports_launcher(launcher)]
