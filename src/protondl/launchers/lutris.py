from pathlib import Path

from protondl.core.base_launcher import Launcher
from protondl.core.models import CompatToolType, InstallMode


class LutrisLauncher(Launcher):
    supported_tools_folders = {
        CompatToolType.PROTON: Path("runners/wine"),
        CompatToolType.VKD3D: Path("runtime/vkd3d"),
    }

    @classmethod
    def discover(cls) -> list[Launcher]:
        found: list[Launcher] = []

        # 1. Native Lutris discovery (~/.local/share/lutris)
        native_root = Path("~/.local/share/lutris").expanduser()
        if native_root.exists() and cls._is_valid_lutris_home(native_root):
            found.append(cls("Lutris", native_root, InstallMode.NATIVE))

        # 2. Flatpak installation
        flatpak_root = Path("~/.var/app/net.lutris.Lutris/data/lutris").expanduser()
        if flatpak_root.exists() and cls._is_valid_lutris_home(flatpak_root):
            found.append(cls("Lutris Flatpak", flatpak_root, InstallMode.FLATPAK))

        return found

    @staticmethod
    def _is_valid_lutris_home(path: Path) -> bool:
        return (path / "runners").is_dir()

    def get_compatibility_tools_path(self, tool_type: CompatToolType) -> Path:
        if tool_type not in self.supported_tools_folders:
            raise ValueError(
                "LutrisLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders}, got {tool_type}"
            )

        path = self.root_path / self.supported_tools_folders[tool_type]
        path.mkdir(parents=True, exist_ok=True)
        return path
