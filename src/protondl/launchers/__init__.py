from protondl.core.base_launcher import Launcher
from protondl.launchers.bottles import BottlesLauncher
from protondl.launchers.heroic import HeroicLauncher
from protondl.launchers.lutris import LutrisLauncher
from protondl.launchers.steam import SteamLauncher

# Registry of all launcher classes the library supports
SUPPORTED_LAUNCHER_CLASSES: list[type[Launcher]] = [
    SteamLauncher,
    LutrisLauncher,
    HeroicLauncher,
    BottlesLauncher,
]


def detect_all_launchers() -> list[Launcher]:
    """
    Iterates through all supported launcher types and returns every
    installed instance found on the machine.

    Returns:
        List[Launcher]: A list of detected Launcher instances.
    """
    installed_launchers = []
    for launcher_cls in SUPPORTED_LAUNCHER_CLASSES:
        installed_launchers.extend(launcher_cls.discover())
    return installed_launchers
