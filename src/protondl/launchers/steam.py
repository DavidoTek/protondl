from collections.abc import Sequence
from enum import Enum
from pathlib import Path

import vdf
from steam.utils.appcache import parse_appinfo

from protondl.core.base_launcher import Game, Launcher
from protondl.core.models import CompatToolType, InstallMode
from protondl.util.steam import (
    CompatToolInfo,
    CompatToolUsage,
    get_steam_ctool_info,
    get_steam_vdf_compat_tool_mapping,
    vdf_safe_load,
)

PROTON_NEXT_APPID = 2230260
PROTON_EAC_RUNTIME_APPID = 1826330
PROTON_BATTLEYE_RUNTIME_APPID = 1161040
STEAMLINUXRUNTIME_APPID = 1070560
STEAMLINUXRUNTIME_SOLDIER_APPID = 1391110
STEAMLINUXRUNTIME_SNIPER_APPID = 1628350


class SteamRuntimeType(Enum):
    EAC = PROTON_EAC_RUNTIME_APPID  # ProtonEasyAntiCheatRuntime
    BATTLEYE = PROTON_BATTLEYE_RUNTIME_APPID  # ProtonBattlEyeRuntime
    STEAMLINUXRUNTIME = STEAMLINUXRUNTIME_APPID  # Steam Linux Runtime 1.0 (scout)


class SteamAppType(Enum):
    GAME = 0
    RUNTIME = 1
    ANTICHEAT_RUNTIME = 2
    STEAMWORKS = 3
    PROTON_NEXT = 4
    COMPAT_TOOL = 5


class SteamGame(Game):
    """
    Represents a game managed by the Steam launcher.

    This class extends the base `Game` class to include Steam-specific metadata
    extracted from VDF manifests and user shortcuts. It tracks AppIDs,
    compatibility tool overrides, and Anti-Cheat runtime requirements.

    Attributes:
        appid (int): The unique Steam Application ID.
        libraryfolder_id (str): The ID of the Steam library folder where the game resides.
        libraryfolder_path (Path): The root path of the library folder containing the game.
        anticheat_runtimes (dict[SteamRuntimeType, bool]): Status of required
            Anti-Cheat runtimes (e.g., BattlEye, EAC; true if required).
        compat_tool_name (str): The compatibility tool name.
        ctool_from_oslist (str): Operating system whose executables can be run
            by this compatibility tool, for example windows for Proton.
        deck_compatibility (dict[str, str]): Steam Deck verification status and flags.
        app_type (SteamAppType): Category of the application (Game, Tool, Media, etc.).
        shortcut_id (str): ID for non-Steam shortcuts, if applicable.
        shortcut_startdir (str): Working directory for the game execution.
        shortcut_exe (str): Path to the game's executable file.
        shortcut_icon (str): Path to the icon used for the game entry.
        shortcut_user (str): The Steam User ID associated with the shortcut.
    """

    __slots__ = (
        "appid",
        "libraryfolder_id",
        "libraryfolder_path",
        "anticheat_runtimes",
        "compat_tool_name",
        "ctool_from_oslist",
        "deck_compatibility",
        "app_type",
        "shortcut_id",
        "shortcut_startdir",
        "shortcut_exe",
        "shortcut_icon",
        "shortcut_user",
    )

    def __init__(self, appid: int, name: str, install_path: Path) -> None:
        """
        Initializes a new SteamGame instance.

        Args:
            appid (int): The Steam AppID.
            name (str): The display name of the game.
            install_path (Path): The directory where the game is installed.
        """
        super().__init__(str(appid), name, "", install_path)
        self.appid = appid
        self.libraryfolder_id = ""
        self.libraryfolder_path = install_path.parent
        self.anticheat_runtimes: dict[SteamRuntimeType, bool] = {}
        self.compat_tool_name = ""
        self.ctool_from_oslist = ""
        self.deck_compatibility: dict[str, str] = {}
        self.app_type = SteamAppType.GAME

        self.shortcut_id = ""
        self.shortcut_startdir = ""
        self.shortcut_exe = ""
        self.shortcut_icon = ""
        self.shortcut_user = ""


class SteamLauncher(Launcher):
    supported_tools_folders = {
        CompatToolType.PROTON: Path("compatibilitytools.d"),
    }

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

    def __init__(self, name: str, root_path: Path, install_mode: InstallMode) -> None:
        super().__init__(name, root_path, install_mode)

        self._cached_game_list: list[SteamGame] = []
        self._cached_ctool_map: dict[str, CompatToolInfo] = {}

    def get_compatibility_tools_path(self, tool_type: CompatToolType) -> Path:
        if tool_type not in self.supported_tools_folders:
            raise ValueError(
                "SteamLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders}, got {tool_type}"
            )

        path = self.root_path / self.supported_tools_folders[tool_type]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_game_list(self, shortcuts: bool = True, cached: bool = True) -> Sequence[SteamGame]:
        """
        Returns a list of games installed in this launcher.

        Args:
            shortcuts (bool): Also return shortcuts.
            cached (bool): Whether to use cached tools if the list was fetched before.

        Returns:
            Sequence[SteamGame]: A list of Steam apps.

        Raises:
            ValueError: If loading the game list failed.
        """
        if cached and self._cached_game_list:
            return self._cached_game_list

        games: list[SteamGame] = []

        libraryfolders_vdf_file: Path = self.root_path / "config" / "libraryfolders.vdf"
        config_vdf_file: Path = self.root_path / "config" / "config.vdf"

        libraryfolders_data = {}
        try:
            libraryfolders_data = vdf_safe_load(libraryfolders_vdf_file)
        except Exception as e:
            raise ValueError(f"Could not load library data: {e}") from e

        compat_tool_mapping = {}
        try:
            config_data = vdf_safe_load(config_vdf_file)
            compat_tool_mapping = get_steam_vdf_compat_tool_mapping(config_data)
        except Exception as e:
            print(f"Warning: Could not load the compatibility tool mapping: {e}")

        for fid in libraryfolders_data.get("libraryfolders", {}):
            fentry = libraryfolders_data.get("libraryfolders", {}).get(fid)
            if not fentry or "apps" not in fentry:
                continue
            fentry_path = Path(fentry.get("path", ""))
            fentry_libraryfolders_path = fentry_path
            if fid == "0":
                fentry_path = fentry_path / "steamapps" / "common"
            for appid in fentry.get("apps", {}):
                fid_steamapps_path = fentry_libraryfolders_path / "steamapps"
                appmanifest_path = fid_steamapps_path / f"appmanifest_{appid}.acf"
                full_path = Path("?")
                if appmanifest_path.is_file():
                    try:
                        appmanifest_data = vdf_safe_load(appmanifest_path)
                        appmanifest_install_path = appmanifest_data.get("AppState", {}).get(
                            "installdir", None
                        )
                        if not appmanifest_install_path:
                            continue
                        full_path = fid_steamapps_path / "common" / Path(appmanifest_install_path)
                        if not full_path.is_dir():
                            continue
                    except Exception as e:
                        print(f"Error: Could not load the app manifest for {appid}: {e}")
                        continue

                game = SteamGame(int(appid), full_path.name, full_path)
                game.libraryfolder_id = fid
                if ct := compat_tool_mapping.get(appid):
                    game.compat_tool_name = ct.get("name", "")
                games.append(game)

        if shortcuts:
            try:
                games.extend(self._get_steam_shortcuts_list(compat_tool_mapping))
            except Exception as e:
                print(f"Warning: Could not fetch the shortcut list: {e}")

        try:
            games = self._update_steam_game_list_with_app_info(games)
        except Exception as e:
            print(f"Warning: Could not update the game info: {e}")

        self._cached_game_list = games
        return games

    def _update_steam_game_list_with_app_info(self, games: list[SteamGame]) -> list[SteamGame]:
        """
        Enrich existing SteamGame entries with appinfo.vdf metadata.

        The function keeps a map of `appid` to `SteamGame` and only processes
        entries that already exist in the initial `games` list. If appinfo file
        does not exist, it raises `ValueError`.

        Args:
            games (list[SteamGame]): List of games.

        Returns:
            list[SteamGame]: List of games with updated metadata.

        Raises:
            ValueError: If the appinfo file is missing or if applying appinfo data fails.
        """
        appinfo_file = self.root_path / "appcache" / "appinfo.vdf"

        if not appinfo_file.is_file():
            raise ValueError(f"Steam app info does not exist: {appinfo_file}")

        game_map: dict[str, SteamGame] = {str(game.appid): game for game in games}
        cnt = 0

        try:
            if not self._cached_ctool_map:
                self._cached_ctool_map = get_steam_ctool_info(self.root_path)
            with open(appinfo_file, "rb") as f:
                _, apps = parse_appinfo(f, mapper=dict)
                for app in apps:
                    appid_str = str(app.get("appid"))
                    if game := game_map.get(appid_str):
                        app_appinfo = app.get("data", {}).get("appinfo", {})
                        app_appinfo_common = app_appinfo.get("common", {})

                        game.name = str(app_appinfo_common.get("name", ""))
                        game.deck_compatibility = app_appinfo_common.get(
                            "steam_deck_compatibility", {}
                        )

                        # Dictionary of Dictionaries with dependency info,
                        # primarily Proton anti-cheat runtimes
                        # Example: {
                        #   '0': {
                        #     'src_os': 'windows',
                        #     'dest_os': 'linux',
                        #     'appid': 1826330,
                        #     'comment': 'EAC runtime'
                        #   }
                        # }
                        app_additional_dependencies = app_appinfo.get("extended", {}).get(
                            "additional_dependencies", {}
                        )
                        for dep in app_additional_dependencies.values():
                            game.anticheat_runtimes[SteamRuntimeType.EAC] = (
                                dep.get("appid", -1) == PROTON_EAC_RUNTIME_APPID
                            )
                            game.anticheat_runtimes[SteamRuntimeType.BATTLEYE] = (
                                dep.get("appid", -1) == PROTON_BATTLEYE_RUNTIME_APPID
                            )

                        # Configure app types
                        if game.appid in [PROTON_EAC_RUNTIME_APPID, PROTON_BATTLEYE_RUNTIME_APPID]:
                            game.app_type = SteamAppType.ANTICHEAT_RUNTIME
                        elif game.appid in [
                            STEAMLINUXRUNTIME_APPID,
                            STEAMLINUXRUNTIME_SOLDIER_APPID,
                            STEAMLINUXRUNTIME_SNIPER_APPID,
                        ]:
                            game.app_type = SteamAppType.RUNTIME
                        elif "Steamworks" in game.name:
                            game.app_type = SteamAppType.STEAMWORKS
                        elif ct := self._cached_ctool_map.get(str(app.get("appid", ""))):
                            game.compat_tool_name = ct.get("name", "")
                            game.ctool_from_oslist = ct.get("from_oslist", "")
                            game.app_type = SteamAppType.COMPAT_TOOL
                        elif game.appid == PROTON_NEXT_APPID:
                            # See https://github.com/DavidoTek/ProtonUp-Qt/pull/280
                            game.app_type = SteamAppType.PROTON_NEXT
                        else:
                            game.app_type = SteamAppType.GAME
                        cnt += 1
                    if cnt == len(game_map):
                        break

        except Exception as e:
            raise ValueError(f"Updating the Steam game list with app info failed: {e}") from e

        return list(game_map.values())

    def _get_steam_shortcuts_list(
        self, compat_tool_mapping: dict[str, CompatToolUsage]
    ) -> list[SteamGame]:
        """
        Fetches a list of non-Steam user shortcuts.

        Args:
            compat_tool_mapping(dict): Compatibility tool to appid map.

        Returns:
            list[SteamGame]: List of shortcuts.

        Raises:
            ValueError: If fetching the shortcuts failed.
        """
        userdata_dir = self.root_path / "userdata"

        games = []

        try:
            for user_dir in userdata_dir.iterdir():
                if not user_dir.is_dir():
                    continue

                shortcuts_file = user_dir / "config" / "shortcuts.vdf'"
                if not shortcuts_file.is_file():
                    continue

                shortcuts_data = vdf.binary_load(open(shortcuts_file, "rb"))
                if "shortcuts" not in shortcuts_data:
                    continue

                for sid, svalue in shortcuts_data.get("shortcuts", {}).items():
                    appid = svalue.get("appid", 0)
                    if appid < 0:
                        appid = appid + (1 << 32)  # convert to unsigned
                    name = svalue.get("AppName") or svalue.get("appname", "")
                    game = SteamGame(appid, name, install_path=user_dir)

                    game.app_type = SteamAppType.GAME
                    if ct := compat_tool_mapping.get(str(appid)):
                        game.compat_tool_name = ct.get("name", "")

                    game.shortcut_id = str(sid)
                    game.shortcut_startdir = svalue.get("StartDir", "")
                    game.shortcut_exe = svalue.get("Exe", "")
                    game.shortcut_icon = svalue.get("icon", "")
                    game.shortcut_user = user_dir.name

                    games.append(game)
        except Exception as e:
            raise ValueError(f"Fetching Steam shortcuts failed: {e}") from e

        return games
