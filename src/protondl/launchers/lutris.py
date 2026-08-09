from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from protondl.core.base_launcher import Game, Launcher
from protondl.core.models import CompatTool, CompatToolType, InstallMode
from protondl.util.lutris import get_lutris_game_list


class LutrisGame(Game):
    """
    Represents a game managed by the Lutris launcher.

    This class extends the base `Game` class with Lutris-specific metadata
    extracted from Lutris' pga.db database and per-game configuration files.

    Attributes:
        slug (str): The game's slug, used as identifier in Lutris.
        runner (str): The runner that manages the game (e.g. "wine", "steam").
        installer_slug (str): The slug of the installer used to install the game.
        installed_at (int): UNIX timestamp when the game was installed.
        appid (int | None): The Steam AppID, if the game runs via Steam.
    """

    __slots__ = Game.__slots__ + (
        "appid",
        "slug",
        "runner",
        "installer_slug",
        "installed_at",
    )

    def __init__(
        self,
        slug: str,
        name: str,
        install_path: Path,
        runner: str,
        installer_slug: str = "",
        installed_at: int = 0,
        appid: int | None = None,
    ) -> None:
        """
        Initializes a new LutrisGame instance.

        Args:
            slug (str): The game's slug.
            name (str): The display name of the game.
            install_path (Path): The directory where the game is installed.
            runner (str): The runner that manages the game.
            installer_slug (str): The slug of the installer used to install the game.
            installed_at (int): UNIX timestamp when the game was installed.
            appid (int | None): The Steam AppID, if the game runs via Steam.
        """
        super().__init__(slug, name, "", install_path)
        self.appid = appid
        self.slug = slug
        self.runner = runner
        self.installer_slug = installer_slug
        self.installed_at = installed_at


class LutrisLauncher(Launcher):
    supported_tools_folders = {
        CompatToolType.PROTON: Path("runners/wine"),
        CompatToolType.WINE: Path("runners/wine"),
        CompatToolType.DXVK: Path("runtime/dxvk"),
        CompatToolType.VKD3D: Path("runtime/vkd3d"),
    }

    @classmethod
    def discover(cls) -> list[Launcher]:
        found: list[Launcher] = []

        # 1. Native Lutris discovery (~/.local/share/lutris)
        native_root = Path("~/.local/share/lutris").expanduser()
        if native_root.exists() and cls._is_valid_lutris_home(native_root):
            found.append(
                cls(
                    "Lutris",
                    native_root,
                    InstallMode.NATIVE,
                    config_dir=cls._default_config_dir(InstallMode.NATIVE),
                )
            )

        # 2. Flatpak installation
        flatpak_root = Path("~/.var/app/net.lutris.Lutris/data/lutris").expanduser()
        if flatpak_root.exists() and cls._is_valid_lutris_home(flatpak_root):
            found.append(
                cls(
                    "Lutris Flatpak",
                    flatpak_root,
                    InstallMode.FLATPAK,
                    config_dir=cls._default_config_dir(InstallMode.FLATPAK),
                )
            )

        return found

    @staticmethod
    def _is_valid_lutris_home(path: Path) -> bool:
        return (path / "runners").is_dir()

    @staticmethod
    def _default_config_dir(install_mode: InstallMode) -> Path:
        if install_mode == InstallMode.FLATPAK:
            return Path("~/.var/app/net.lutris.Lutris/config/lutris").expanduser()
        return Path("~/.config/lutris").expanduser()

    def __init__(
        self,
        name: str,
        root_path: Path,
        install_mode: InstallMode,
        config_dir: Path | None = None,
    ) -> None:
        """
        Initializes a LutrisLauncher instance.

        Args:
            name: The human-readable name of the launcher.
            root_path: The filesystem path to Lutris' data directory.
            install_mode: The installation mode (native, flatpak).
            config_dir: The filesystem path to Lutris' configuration directory.
                Defaults to the standard configuration directory for the given
                install mode.
        """
        super().__init__(name, root_path, install_mode)
        self.config_dir = config_dir or self._default_config_dir(install_mode)
        self._cached_game_list: list[LutrisGame] = []

    def get_compatibility_tools_path(self, tool_type: CompatToolType) -> Path:
        if tool_type not in self.supported_tools_folders:
            raise ValueError(
                "LutrisLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders}, got {tool_type}"
            )

        path = self.root_path / self.supported_tools_folders[tool_type]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_game_list(self, cached: bool = True) -> Sequence[LutrisGame]:
        """
        Returns a list of games installed in this launcher.

        Games are read from Lutris' pga.db database and enriched with
        information from their per-game configuration files, such as the
        assigned compatibility tool and the install directory.

        Args:
            cached (bool): Whether to use the cached game list if available.

        Returns:
            Sequence[LutrisGame]: A list of installed Lutris games.

        Raises:
            ValueError: If the Lutris root directory is invalid or loading
                the game list failed.
        """
        if not self.root_path.is_dir():
            raise ValueError(f"Lutris directory does not exist: {self.root_path}")

        if cached and self._cached_game_list:
            return self._cached_game_list

        try:
            entries = get_lutris_game_list(self.root_path, self.config_dir)
        except ValueError as e:
            raise ValueError(f"Could not load the Lutris game list: {e}") from e

        games = [self._build_game(entry) for entry in entries]
        games.sort(key=lambda game: game.name)
        self._cached_game_list = games
        return games

    def _build_game(self, entry: dict[str, Any]) -> LutrisGame:
        """
        Builds a LutrisGame from a raw pga.db entry.

        The install directory is taken from the 'directory' column. If it is
        empty (games added manually to Lutris), it is resolved from the game's
        configuration file using the working directory or the executable's
        directory.

        Args:
            entry (dict): Raw pga.db game entry, including the parsed
                configuration file.

        Returns:
            LutrisGame: The built game.
        """
        slug = entry.get("slug") or ""
        name = entry.get("name") or ""
        runner = entry.get("runner") or ""
        installer_slug = entry.get("installer_slug") or ""
        installed_at = entry.get("installed_at") or 0

        install_dir = entry.get("directory")
        config = entry.get("config", {})
        game_config = config.get("game")

        if not isinstance(install_dir, str) or not install_dir:
            install_dir = self._resolve_install_dir(game_config)

        game = LutrisGame(
            slug=slug,
            name=name,
            install_path=Path(install_dir or "?"),
            runner=runner,
            installer_slug=installer_slug,
            installed_at=installed_at,
        )

        # If a Lutris game config has an 'appid' in its 'game' section in its yml,
        # assume the runner is Steam.
        if isinstance(game_config, dict) and game_config.get("appid") is not None:
            game.runner = "steam"
            try:
                game.appid = int(game_config["appid"])
            except (TypeError, ValueError):
                pass

        if isinstance(config.get("wine"), dict):
            wine_version = config.get("wine", {}).get("version")
            if isinstance(wine_version, str) and wine_version:
                game.compat_tool_name = wine_version

        return game

    @staticmethod
    def _resolve_install_dir(game_config: object) -> str:
        """
        Resolves a game's install directory from its configuration file.

        Args:
            game_config (object): The 'game' section of the game's configuration.

        Returns:
            str: The resolved install directory, or an empty string if it
                cannot be determined.
        """
        if not isinstance(game_config, dict):
            return ""

        working_dir = game_config.get("working_dir")
        if isinstance(working_dir, str) and working_dir:
            return str(Path(working_dir).expanduser())

        exe = game_config.get("exe")
        if isinstance(exe, str) and exe:
            exe_path = Path(exe).expanduser()
            if exe_path.is_absolute():
                return str(exe_path.parent)

        return ""

    def set_games_tools(self, game_tool_map: Mapping[Game, str | None]) -> None:
        raise NotImplementedError()

    def get_global_tool(self, tool_type: CompatToolType) -> CompatTool | None:
        raise NotImplementedError()

    def set_global_tool(self, tool: CompatTool) -> None:
        raise NotImplementedError()
