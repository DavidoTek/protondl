from pathlib import Path

from protondl.core.base_launcher import Launcher
from protondl.core.models import InstallMode


class LutrisLauncher(Launcher):
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

    def get_compatibility_tools_path(self) -> Path:
        path = self.root_path / "runners" / "wine"
        path.mkdir(parents=True, exist_ok=True)
        return path
