from collections.abc import Mapping, Sequence
from pathlib import Path

from protondl.core.base_launcher import Game, Launcher
from protondl.core.models import CompatTool, CompatToolType, InstallMode


class BottlesLauncher(Launcher):
    """
    Launcher integration for Bottles.

    Bottles stores custom runners in a shared ``runners`` directory. Proton and
    Wine tools are both managed from this location.
    """

    supported_tools_folders = {
        CompatToolType.PROTON: Path("runners"),
        CompatToolType.WINE: Path("runners"),
    }

    @classmethod
    def discover(cls) -> list[Launcher]:
        """
        Discover installed Bottles instances.

        Returns:
            list[Launcher]: Detected native and Flatpak Bottles launchers.
        """
        found: list[Launcher] = []

        native_root = Path("~/.local/share/bottles").expanduser()
        if native_root.exists() and cls._is_valid_bottles_home(native_root):
            found.append(cls("Bottles", native_root, InstallMode.NATIVE))

        flatpak_root = Path("~/.var/app/com.usebottles.bottles/data/bottles").expanduser()
        if flatpak_root.exists() and cls._is_valid_bottles_home(flatpak_root):
            found.append(cls("Bottles Flatpak", flatpak_root, InstallMode.FLATPAK))

        return found

    @staticmethod
    def _is_valid_bottles_home(path: Path) -> bool:
        """
        Validate whether the given path looks like a Bottles data directory.

        Args:
            path (Path): Candidate Bottles root path.

        Returns:
            bool: True if the expected runners directory exists, otherwise False.
        """
        return (path / "runners").is_dir()

    def get_compatibility_tools_path(self, tool_type: CompatToolType) -> Path:
        """
        Return the installation directory for a compatibility tool type.

        Args:
            tool_type (CompatToolType): Tool type to resolve.

        Returns:
            Path: Absolute path for the tool installation directory.

        Raises:
            ValueError: If the tool type is not supported by BottlesLauncher.
        """
        if tool_type not in self.supported_tools_folders:
            raise ValueError(
                "BottlesLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders}, got {tool_type}"
            )

        path = self.root_path / self.supported_tools_folders[tool_type]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_game_list(self) -> Sequence[Game]:
        raise NotImplementedError()

    def set_games_tools(self, game_tool_map: Mapping[Game, str | None]) -> None:
        raise NotImplementedError()

    def get_global_tool(self, tool_type: CompatToolType) -> CompatTool | None:
        raise NotImplementedError()

    def set_global_tool(self, tool: CompatTool) -> None:
        raise NotImplementedError()
