from collections.abc import Callable
from pathlib import Path

from protondl.core.base_launcher import Launcher
from protondl.core.models import InstallMode
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

# Mapping of launcher type identifiers used in '<type>:<path>' specs to their classes
LAUNCHER_TYPE_MAP: dict[str, type[Launcher]] = {
    "steam": SteamLauncher,
    "lutris": LutrisLauncher,
    "heroic": HeroicLauncher,
    "bottles": BottlesLauncher,
}

# Validators that check whether a path looks like the launcher's data directory
LAUNCHER_HOME_VALIDATORS: dict[str, Callable[[Path], bool]] = {
    "steam": SteamLauncher._is_valid_steam_home,
    "lutris": LutrisLauncher._is_valid_lutris_home,
    "heroic": HeroicLauncher._is_valid_heroic_home,
    "bottles": BottlesLauncher._is_valid_bottles_home,
}


def is_valid_launcher_home(launcher_type: str, root_path: Path) -> bool:
    """
    Check whether a path looks like the data directory of a launcher type.

    Args:
        launcher_type: The launcher type identifier, one of
            ``steam``, ``lutris``, ``heroic`` or ``bottles``.
        root_path: The candidate launcher data directory.

    Returns:
        bool: True if the path is a valid data directory of the launcher type,
            False if it is not or the launcher type is unknown.
    """
    validator = LAUNCHER_HOME_VALIDATORS.get(launcher_type.lower())
    if validator is None:
        return False
    return validator(root_path)


def create_launcher_from_path(launcher_type: str, root_path: Path) -> Launcher:
    """
    Create a launcher instance for a custom installation path.

    Launchers installed at non-standard locations (e.g. a Steam installation
    in ``~/mySteam`` instead of ``~/.steam/root``) can be targeted by
    constructing them directly from their root path.

    Args:
        launcher_type: The launcher type identifier, one of
            ``steam``, ``lutris``, ``heroic`` or ``bottles``.
        root_path: The filesystem path to the launcher's main directory.
            The path may not exist yet; installers create the required
            directories on demand.

    Returns:
        Launcher: A Launcher instance of the matching type rooted at
            ``root_path``.

    Raises:
        ValueError: If ``launcher_type`` is not a known launcher type.
    """
    launcher_cls = LAUNCHER_TYPE_MAP.get(launcher_type.lower())
    if launcher_cls is None:
        supported = ", ".join(LAUNCHER_TYPE_MAP)
        raise ValueError(f"Unknown launcher type '{launcher_type}'. Supported types: {supported}.")

    if launcher_cls is LutrisLauncher:
        return LutrisLauncher(
            launcher_type.capitalize(),
            root_path,
            InstallMode.NATIVE,
            config_dir=LutrisLauncher._default_config_dir(InstallMode.NATIVE),
        )
    return launcher_cls(launcher_type.capitalize(), root_path, InstallMode.NATIVE)


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
