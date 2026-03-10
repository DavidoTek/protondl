from abc import ABC, abstractmethod
from pathlib import Path

from protondl.core.models import CompatTool, CompatToolType, InstallMode


class Launcher(ABC):
    """
    Abstract base class for game launchers.

    Attributes:
        supported_tool_types: A mapping of supported compatibility tool types to their
            respective installation subdirectories, relative to the launcher's root path.
    """

    supported_tools_folders: dict[CompatToolType, Path]

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
    def get_compatibility_tools_path(self, tool_type: CompatToolType) -> Path:
        """
        Returns the directory path where compatibility tools should be installed for this launcher.
        The folder is created if the launcher is detected but the folder doesn't exist yet.

        Args:
            tool_type: The type of compatibility tool (e.g., Proton, VKD3D, ...) to determine the
                appropriate installation path.

        Returns:
            Path: The path to the compatibility tools directory.

        Raises:
            ValueError: If the launcher does not support the specified tool type.
        """
        pass

    def get_installed_tools(self) -> list[CompatTool]:
        """
        Returns a list of installed compatibility tools for this launcher by checking the
        compatibility tools directory.

        Returns:
            list[CompatTool]: A list of installed compatibility tools.
        """
        installed_tools = []

        for tool_type, _ in self.supported_tools_folders.items():
            tools_path = self.get_compatibility_tools_path(tool_type)
            if tools_path.exists():
                installed_tools.extend(
                    [
                        CompatTool(full_name=item.name, tool_type=tool_type, install_dir=item)
                        for item in tools_path.iterdir()
                        if item.is_dir()
                    ]
                )

        return installed_tools
