from abc import ABC, abstractmethod
from pathlib import Path

from protondl.core.models import InstallMode


class Launcher(ABC):
    def __init__(self, name: str, root_path: Path, install_mode: InstallMode) -> None:
        """
        Initializes a Launcher instance.

        Args:
            name: The human-readable name of the launcher (e.g., "Steam", "Lutris").
            root_path: The filesystem path to the launcher's main directory.
            install_mode: The installation mode (native, flatpak, snap) indicating how
                the launcher is installed on the system.
        """
        self.name = name
        self.root_path = root_path
        self.install_mode = install_mode
        super().__init__()

    @classmethod
    @abstractmethod
    def discover(cls) -> list["Launcher"]:
        """
        Discovers installed game launchers on the system.

        Returns:
            list[Launcher]: A list of Launcher instances representing detected launchers.
        """
        pass

    @abstractmethod
    def get_compatibility_tools_path(self) -> Path:
        """
        Returns the directory path where compatibility tools should be installed for this launcher.
        The folder is created if the launcher is detected but the folder doesn't exist yet.

        Returns:
            Path: The path to the compatibility tools directory.
        """
        pass
