import shutil
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path

from protondl.core.errors import raise_for_os_error
from protondl.core.models import CompatTool, CompatToolType, InstallMode
from protondl.util.version_file import read_version_file


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
        supported_tools_folders (dict[CompatToolType, Path]):
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
        # Tool types of protondl-installed tools are detected via protondl_version.json.
        # This disambiguates shared folders (e.g. Lutris stores Proton and Wine in
        # runners/wine). Tools without the file fall back to the folder's tool type.

        from protondl.installers import get_tool_type_by_name

        for tool_type, _ in self.supported_tools_folders.items():
            tools_path = self.get_compatibility_tools_path(tool_type)
            if not tools_path.exists():
                continue
            for item in tools_path.iterdir():
                if not item.is_dir() or item in seen_dirs:
                    continue

                detected_type = tool_type
                if info := read_version_file(item):
                    if resolved_type := get_tool_type_by_name(info.compat_tool):
                        detected_type = resolved_type

                if tool_types is not None and detected_type not in tool_types:
                    continue

                installed_tools.append(
                    CompatTool(full_name=item.name, tool_type=detected_type, install_dir=item)
                )
                seen_dirs.add(item)

        return installed_tools

    def remove_tool(self, tool: CompatTool) -> None:
        """
        Removes an installed compatibility tool.

        The tool's directory must be located inside one of the launcher's
        supported compatibility tools directories. If the tool was installed by
        a protondl installer (detected via its protondl_version.json), removal
        is delegated to that installer so it can perform additional cleanup.
        Otherwise, the tool's directory is deleted directly.

        Args:
            tool (CompatTool): The installed compatibility tool to remove.

        Raises:
            ValueError: If the tool's directory is not inside a supported
                compatibility tools directory.
            FileNotFoundError: If the tool's directory does not exist.
            NoWritePermissionError: If the tool's directory cannot be deleted.
                Also a PermissionError for backwards compatibility.
        """
        install_dir = tool.install_dir
        tools_path = self.get_compatibility_tools_path(tool.tool_type).resolve()
        if not install_dir.resolve().is_relative_to(tools_path):
            raise ValueError(
                f"Refusing to remove {install_dir}: not inside the "
                f"{tool.tool_type.value} compatibility tools directory."
            )
        if not install_dir.is_dir():
            raise FileNotFoundError(f"Compatibility tool directory does not exist: {install_dir}")

        from protondl.installers import get_installer_by_name

        installer = None
        if info := read_version_file(install_dir):
            installer = get_installer_by_name(info.compat_tool)

        if installer is not None:
            installer.remove(tool, self)
        else:
            try:
                shutil.rmtree(install_dir)
            except OSError as e:
                raise_for_os_error(e)

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

    @abstractmethod
    def set_games_tools(self, game_tool_map: Mapping[Game, str | None]) -> None:
        """
        Set which compatibility tools the games should use.

        Args:
            game_tool_map (Mapping[Game, str|None]):
                Maps the game to the compatibility tool name or None to use the global tool.

        Raises:
            RuntimeError: If setting the compatibility tools failed.
        """
        pass

    @abstractmethod
    def get_global_tool(self, tool_type: CompatToolType) -> CompatTool | None:
        """
        Get the global compatibility tool for the launcher.

        Args:
            tool_type (CompatToolType): The type of compatibility tool to retrieve.

        Returns:
            CompatTool | None: The global compatibility tool for
                the specified type, or None if not set.

        Raises:
            ValueError: If the launcher does not support the specified tool type.
            RuntimeError: If retrieving the global compatibility tool failed.
        """
        pass

    @abstractmethod
    def set_global_tool(self, tool: CompatTool) -> None:
        """
        Set the global compatibility tool for the launcher.
        If the launcher supports multiple global tools, the type is determined from tool.tool_type.

        Args:
            tool (CompatTool): The compatibility tool to set as the global default.

        Raises:
            ValueError: If the launcher does not support the specified tool type.
            RuntimeError: If setting the global compatibility tool failed.
        """
        pass
