from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from protondl.core.models import CompatTool, CompatToolType, InstallMode


class Game:
    """
    Abstract base class for games.

    Attributes:
        id (str): Internal identifier
        name (str): The human-readable name/title of the game.
        compat_tool_name (str): Name of the used compatibility tool.
        install_path (Path): The filesystem path where the game is installed.
    """

    __slots__ = ("id", "name", "compat_tool_name", "install_path")

    def __init__(self, id: str, name: str, compat_tool_name: str, install_path: Path) -> None:
        self.id = id
        self.name = name
        self.compat_tool_name = compat_tool_name
        self.install_path = install_path
        super().__init__()


class Launcher(ABC):
    """
    Abstract base class for game launchers.

    Attributes:
        supported_tool_types (dict[CompatToolType, Path]):
            A mapping of supported compatibility tool types to their
            respective installation subdirectories, relative to the launcher's root path.
        name (str): The human-readable name of the launcher (e.g., "Steam", "Lutris (Flatpak)").
        root_path (Path): The filesystem path to the launcher's main directory.
        install_mode (InstallMode): The installation mode (native, flatpak, snap).
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

    def get_installed_tools(
        self, tool_types: list[CompatToolType] | None = None
    ) -> list[CompatTool]:
        """
        Returns a list of installed compatibility tools for this launcher by checking the
        compatibility tools directory.

        Args:
            tool_types (list[CompatToolType] | None):
                An optional list of tool types to filter by.
                If None, all supported tool types are checked.

        Returns:
            list[CompatTool]: A list of installed compatibility tools.
        """
        installed_tools = []
        seen_dirs = set()  # Avoid duplicates if multiple tool types share the same folder
        # TODO: Wine tools are detected as Proton tools since they share the same folder (Lutris)

        for tool_type, _ in self.supported_tools_folders.items():
            tools_path = self.get_compatibility_tools_path(tool_type)
            if tools_path.exists():
                for item in tools_path.iterdir():
                    if (
                        item.is_dir()
                        and item not in seen_dirs
                        and (tool_types is None or tool_type in tool_types)
                    ):
                        installed_tools.append(
                            CompatTool(full_name=item.name, tool_type=tool_type, install_dir=item)
                        )
                        seen_dirs.add(item)

        return installed_tools

    @abstractmethod
    def get_game_list(self) -> Sequence[Game]:
        """
        Returns a list of games installed in this launcher.

        Returns:
            Sequence[Game]: A list of Game instances representing the installed games.
                The type of Game may vary based on the launcher (e.g., SteamGame, LutrisGame)
                since Sequence is immutable and allows for covariant return types.

        Raises:
            ValueError: If loading the game list failed
        """
        pass
