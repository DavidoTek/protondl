from collections.abc import Sequence
from pathlib import Path

from protondl.core.base_launcher import Game, Launcher
from protondl.core.models import CompatToolType, InstallMode


class HeroicLauncher(Launcher):
    supported_tools_folders = {
        CompatToolType.PROTON: Path("tools/proton"),
        CompatToolType.WINE: Path("tools/wine"),
        CompatToolType.DXVK: Path("tools/dxvk"),
        CompatToolType.VKD3D: Path("tools/vkd3d"),
    }

    @classmethod
    def discover(cls) -> list[Launcher]:
        found: list[Launcher] = []

        native_root = Path("~/.config/heroic").expanduser()
        if native_root.exists() and cls._is_valid_heroic_home(native_root):
            found.append(cls("Heroic", native_root, InstallMode.NATIVE))

        flatpak_root = Path("~/.var/app/com.heroicgameslauncher.hgl/config/heroic").expanduser()
        if flatpak_root.exists() and cls._is_valid_heroic_home(flatpak_root):
            found.append(cls("Heroic Flatpak", flatpak_root, InstallMode.FLATPAK))

        return found

    @staticmethod
    def _is_valid_heroic_home(path: Path) -> bool:
        # Heroic base directory should contain a tools folder where wine/proton runners are stored.
        return (path / "tools").is_dir()

    def get_compatibility_tools_path(self, tool_type: CompatToolType) -> Path:
        if tool_type not in self.supported_tools_folders:
            raise ValueError(
                "HeroicLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders}, got {tool_type}"
            )

        path = self.root_path / self.supported_tools_folders[tool_type]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_game_list(self) -> Sequence[Game]:
        raise NotImplementedError()
