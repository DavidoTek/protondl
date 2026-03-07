from pathlib import Path

from protondl.core.base_launcher import Launcher
from protondl.core.models import InstallMode


class SteamLauncher(Launcher):
    @classmethod
    def discover(cls) -> list[Launcher]:
        found: list[Launcher] = []

        # 1. Native Steam Discovery
        native_roots = [
            Path("~/.local/share/Steam").expanduser(),
            Path("~/.steam/root").expanduser(),
            Path("~/.steam/steam").expanduser(),
            Path("~/.steam/debian-installation").expanduser(),
        ]

        unique_native_paths = {}
        for root in native_roots:
            if root.exists():
                # resolve() gets the absolute physical path, removing symlinks
                try:
                    resolved = root.resolve()
                    unique_native_paths[resolved] = root
                except (OSError, RuntimeError):
                    continue

        for resolved_path in unique_native_paths.keys():
            if cls._is_valid_steam_home(resolved_path):
                found.append(cls("Steam", resolved_path, InstallMode.NATIVE))

        # 2. Flatpak Discovery
        flatpak_path = Path("~/.var/app/com.valvesoftware.Steam/.local/share/Steam").expanduser()
        if flatpak_path.exists() and cls._is_valid_steam_home(flatpak_path):
            found.append(cls("Steam Flatpak", flatpak_path, InstallMode.FLATPAK))

        # 3. Snap Discovery
        snap_path = Path("~/snap/steam/common/.steam/root").expanduser()
        if snap_path.exists() and cls._is_valid_steam_home(snap_path):
            found.append(cls("Steam Snap", snap_path, InstallMode.SNAP))

        return found

    @staticmethod
    def _is_valid_steam_home(path: Path) -> bool:
        """
        Validates that the path is an actual Steam installation and not just
        a leftover empty directory.
        """
        return (path / "config").is_dir() or (path / "ubuntu12_32").exists()

    def get_compatibility_tools_path(self) -> Path:
        path = self.root_path / "compatibilitytools.d"
        path.mkdir(parents=True, exist_ok=True)
        return path
