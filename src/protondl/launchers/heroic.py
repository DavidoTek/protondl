import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from protondl.core.base_launcher import Game, Launcher
from protondl.core.models import CompatTool, CompatToolType, InstallMode
from protondl.util.helpers import json_safe_load
from protondl.util.heroic import (
    get_heroic_default_settings,
    get_heroic_game_config,
    get_heroic_gog_executable,
    get_heroic_gog_games,
    get_heroic_legendary_games,
    get_heroic_nile_games,
    get_heroic_sideload_games,
    resolve_heroic_install_path,
)

DEFAULT_WINE_NAME = "Default Wine - Not Found"

GameSourceLoader = Callable[[Path], list[dict[str, Any]]]


def _get_str(data: Mapping[str, Any], key: str, default: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else default


def _get_bool(data: Mapping[str, Any], key: str, default: bool) -> bool:
    value = data.get(key)
    return value if isinstance(value, bool) else default


class HeroicGame(Game):
    """
    Represents a game managed by the Heroic Games Launcher.

    This class extends the base `Game` class with Heroic-specific metadata
    extracted from Heroic's library, installed and per-game configuration files.

    Attributes:
        runner (str): The store backend that manages the game
            ("legendary", "gog", "nile" or "sideload").
        app_name (str): The internal app name used by Heroic.
        developer (str): The developer of the game.
        store_url (str): URL of the game's store page.
        art_cover (str): URL of the game's cover art.
        art_square (str): URL of the game's square art.
        is_installed (bool): Whether the game is installed.
        platform (str): The platform of the installed version, e.g. "Windows".
        executable (str): The main executable of the game.
        is_dlc (bool): Whether the game is DLC.
        wine_bin (str): Path to the wine/proton binary configured for the game.
        wine_type (str): Type of the configured runner ("wine" or "proton").
        wine_prefix (str): Wine prefix used for the game.
        heroic_path (Path): The Heroic root directory.
    """

    __slots__ = Game.__slots__ + (
        "runner",
        "app_name",
        "developer",
        "store_url",
        "art_cover",
        "art_square",
        "is_installed",
        "platform",
        "executable",
        "is_dlc",
        "wine_bin",
        "wine_type",
        "wine_prefix",
        "heroic_path",
    )

    def __init__(
        self,
        app_name: str,
        name: str,
        install_path: Path,
        runner: str,
        heroic_path: Path,
        developer: str = "",
        store_url: str = "",
        art_cover: str = "",
        art_square: str = "",
        is_installed: bool = True,
        platform: str = "",
        executable: str = "",
        is_dlc: bool = False,
    ) -> None:
        """
        Initializes a new HeroicGame instance.

        Args:
            app_name (str): The internal app name used by Heroic.
            name (str): The display name of the game.
            install_path (Path): The directory where the game is installed.
            runner (str): The store backend that manages the game.
            heroic_path (Path): The Heroic root directory.
            developer (str): The developer of the game.
            store_url (str): URL of the game's store page.
            art_cover (str): URL of the game's cover art.
            art_square (str): URL of the game's square art.
            is_installed (bool): Whether the game is installed.
            platform (str): The platform of the installed version.
            executable (str): The main executable of the game.
            is_dlc (bool): Whether the game is DLC.
        """
        super().__init__(app_name, name, "", install_path)
        self.app_name = app_name
        self.runner = runner
        self.developer = developer
        self.store_url = store_url
        self.art_cover = art_cover
        self.art_square = art_square
        self.is_installed = is_installed
        self.platform = platform
        self.executable = executable
        self.is_dlc = is_dlc
        self.wine_bin = ""
        self.wine_type = ""
        self.wine_prefix = ""
        self.heroic_path = heroic_path

    def get_game_config(self) -> dict[str, Any]:
        """
        Returns the per-game configuration of this game.

        Returns:
            dict: The game's configuration as stored by Heroic.
        """
        return get_heroic_game_config(self.heroic_path, self.app_name)


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

    def __init__(self, name: str, root_path: Path, install_mode: InstallMode) -> None:
        super().__init__(name, root_path, install_mode)

        self._cached_game_list: list[HeroicGame] = []

    def get_compatibility_tools_path(self, tool_type: CompatToolType) -> Path:
        if tool_type not in self.supported_tools_folders:
            raise ValueError(
                "HeroicLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders}, got {tool_type}"
            )

        path = self.root_path / self.supported_tools_folders[tool_type]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_game_list(self, cached: bool = True) -> Sequence[HeroicGame]:
        """
        Returns a list of games installed in this launcher.

        Games are read from Heroic's library and installed metadata files.
        A missing or broken store (e.g. Nile, which requires an Amazon
        account) does not prevent the other stores from being listed.

        Args:
            cached (bool): Whether to use the cached game list if available.

        Returns:
            Sequence[HeroicGame]: A list of installed Heroic games.

        Raises:
            ValueError: If the Heroic root directory is invalid.
        """
        if not self.root_path.is_dir():
            raise ValueError(f"Heroic directory does not exist: {self.root_path}")

        if cached and self._cached_game_list:
            return self._cached_game_list

        default_install_path = self._get_default_install_path()

        games: list[HeroicGame] = []
        sources: tuple[tuple[str, GameSourceLoader], ...] = (
            ("sideload", get_heroic_sideload_games),
            ("gog", get_heroic_gog_games),
            ("legendary", get_heroic_legendary_games),
            ("nile", get_heroic_nile_games),
        )
        for runner, fetch in sources:
            try:
                entries = fetch(self.root_path)
            except Exception as e:
                print(f"Warning: Could not load the {runner} game list: {e}")
                continue
            for entry in entries:
                game = self._build_game(entry, runner, default_install_path)
                if game is None or not game.is_installed:
                    continue
                self._enrich_game_from_config(game)
                games.append(game)

        games.sort(key=lambda game: game.name)
        self._cached_game_list = games
        return games

    def set_games_tools(self, game_tool_map: Mapping[Game, str | None]) -> None:
        """
        Sets the compatibility tool for the given games by writing the
        wineVersion into each game's Heroic configuration file.

        Args:
            game_tool_map (Mapping[Game, str | None]):
                Maps a game to a compatibility tool name or None to reset the
                game to Heroic's default Wine.

        Raises:
            RuntimeError: If updating the game configurations failed.
        """
        try:
            tools_by_name = {tool.full_name: tool for tool in self.get_installed_tools()}
            updates: list[tuple[HeroicGame, dict[str, str]]] = []
            for game, tool_name in game_tool_map.items():
                if not isinstance(game, HeroicGame):
                    raise ValueError(f"Game {game.name} is not managed by Heroic")

                if tool_name:
                    tool = tools_by_name.get(tool_name)
                    if tool is None:
                        raise ValueError(f"Compatibility tool not found: {tool_name}")
                    updates.append((game, self._get_wine_version(tool)))
                else:
                    updates.append((game, {"bin": "", "name": DEFAULT_WINE_NAME, "type": "wine"}))

            for game, wine_version in updates:
                config_file = self.root_path / "GamesConfig" / f"{game.app_name}.json"
                self._write_wine_version(config_file, game.app_name, wine_version)
        except Exception as e:
            raise RuntimeError(f"Setting the compatibility tools for games failed: {e}") from e

        self._cached_game_list = []

    def get_global_tool(self, tool_type: CompatToolType) -> CompatTool | None:
        if tool_type not in (CompatToolType.PROTON, CompatToolType.WINE):
            raise ValueError(
                "HeroicLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders}, got {tool_type}"
            )

        settings = get_heroic_default_settings(self.root_path)
        wine = settings.get("wineVersion")
        if not isinstance(wine, dict):
            return None
        wine_name = wine.get("name")
        if not isinstance(wine_name, str) or wine_name == DEFAULT_WINE_NAME:
            return None

        for tool in self.get_installed_tools([tool_type]):
            if tool.full_name == wine_name:
                return tool
        return None

    def set_global_tool(self, tool: CompatTool) -> None:
        if tool.tool_type not in (CompatToolType.PROTON, CompatToolType.WINE):
            raise ValueError(
                "HeroicLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders}, got {tool.tool_type}"
            )

        config_file = self.root_path / "config.json"
        try:
            data: dict[str, Any] = {"defaultSettings": {}, "version": "v0"}
            if config_file.is_file():
                try:
                    data = json_safe_load(config_file)
                except ValueError:
                    data = {"defaultSettings": {}, "version": "v0"}

            settings = data.get("defaultSettings")
            if not isinstance(settings, dict):
                settings = {}
                data["defaultSettings"] = settings
            settings["wineVersion"] = self._get_wine_version(tool)

            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Setting the global compatibility tool failed: {e}") from e

    def _get_default_install_path(self) -> Path | None:
        """
        Returns Heroic's default install directory from config.json.

        Returns:
            Path | None: The default install directory, or None if not set.
        """
        settings = get_heroic_default_settings(self.root_path)
        default_install = settings.get("defaultInstallPath")
        if isinstance(default_install, str) and default_install:
            return Path(default_install).expanduser()
        return None

    def _build_game(
        self, entry: dict[str, Any], runner: str, default_install_path: Path | None
    ) -> HeroicGame | None:
        """
        Builds a HeroicGame from a raw Heroic library or installed entry.

        Args:
            entry (dict): Raw JSON entry describing the game.
            runner (str): The store backend of the entry.
            default_install_path (Path | None): Heroic's default install
                directory, used to resolve relative folder names.

        Returns:
            HeroicGame | None: The built game, or None if the entry is invalid.
        """
        app_name = entry.get("app_name")
        title = entry.get("title")
        if not isinstance(app_name, str) or not app_name:
            return None
        if not isinstance(title, str):
            title = ""

        install = entry.get("install")
        install_entry = install if isinstance(install, dict) else {}

        install_path = resolve_heroic_install_path(entry, default_install_path)
        if install_path is None:
            install_path = Path("?")

        is_installed = _get_bool(entry, "is_installed", True)
        platform = _get_str(entry, "platform", _get_str(install_entry, "platform", ""))
        executable = _get_str(entry, "executable", _get_str(install_entry, "executable", ""))
        is_dlc = _get_bool(entry, "is_dlc", _get_bool(install_entry, "is_dlc", False))

        return HeroicGame(
            app_name=app_name,
            name=title,
            install_path=install_path,
            runner=runner,
            heroic_path=self.root_path,
            developer=_get_str(entry, "developer", ""),
            store_url=_get_str(entry, "store_url", ""),
            art_cover=_get_str(entry, "art_cover", ""),
            art_square=_get_str(entry, "art_square", ""),
            is_installed=is_installed,
            platform=platform,
            executable=executable,
            is_dlc=is_dlc,
        )

    def _enrich_game_from_config(self, game: HeroicGame) -> None:
        """
        Enriches a game with information from its per-game configuration file,
        such as the assigned compatibility tool and wine prefix.

        Args:
            game (HeroicGame): The game to enrich.
        """
        config = get_heroic_game_config(self.root_path, game.app_name)
        wine = config.get("wineVersion")
        if isinstance(wine, dict):
            game.wine_bin = _get_str(wine, "bin", "")
            game.wine_type = _get_str(wine, "type", "")
            wine_name = _get_str(wine, "name", "")
            if wine_name and wine_name != DEFAULT_WINE_NAME:
                game.compat_tool_name = wine_name

        wine_prefix = config.get("winePrefix")
        if isinstance(wine_prefix, str):
            game.wine_prefix = wine_prefix

        if game.runner == "gog":
            game.executable = get_heroic_gog_executable(
                game.install_path,
                game.app_name,
                wine if isinstance(wine, dict) else {},
                game.platform,
            )

    def _get_wine_version(self, tool: CompatTool) -> dict[str, str]:
        """
        Computes the Heroic wineVersion entry for a compatibility tool.

        Args:
            tool (CompatTool): The compatibility tool to map.

        Returns:
            dict[str, str]: The wineVersion entry with bin, name and type.

        Raises:
            ValueError: If the tool type is not supported by Heroic's
                per-game tool mapping.
        """
        if tool.tool_type == CompatToolType.PROTON:
            return {
                "bin": str(tool.install_dir / "proton"),
                "name": tool.full_name,
                "type": "proton",
            }
        if tool.tool_type == CompatToolType.WINE:
            return {
                "bin": str(tool.install_dir / "bin" / "wine"),
                "name": tool.full_name,
                "type": "wine",
            }
        raise ValueError(
            "Heroic only supports Proton and Wine as game compatibility tools, "
            f"got {tool.tool_type}"
        )

    def _write_wine_version(
        self, config_file: Path, app_name: str, wine_version: dict[str, str]
    ) -> None:
        """
        Writes the wineVersion into a game's Heroic configuration file,
        preserving unrelated keys.

        Args:
            config_file (Path): Path to the game's GamesConfig file.
            app_name (str): The game's app name.
            wine_version (dict): The wineVersion entry to write.
        """
        data: dict[str, Any] = {app_name: {}, "version": "v0", "explicit": True}
        if config_file.is_file():
            try:
                data = json_safe_load(config_file)
            except ValueError:
                data = {app_name: {}, "version": "v0", "explicit": True}

        game_config = data.get(app_name)
        if not isinstance(game_config, dict):
            game_config = {}
            data[app_name] = game_config
        game_config["wineVersion"] = wine_version

        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
