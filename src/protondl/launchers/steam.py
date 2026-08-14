from collections import Counter
from collections.abc import Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import TypedDict

import vdf
from steam.utils.appcache import parse_appinfo

from protondl.core.base_launcher import Game, Launcher
from protondl.core.models import CompatTool, CompatToolType, InstallMode
from protondl.util.steam import (
    CompatToolInfo,
    CompatToolUsage,
    calc_shortcut_app_id,
    determine_most_recent_steam_user,
    get_steam_ctool_info,
    get_steam_shortcuts,
    get_steam_users,
    get_steam_vdf_compat_tool_mapping,
    vdf_safe_load,
    write_steam_shortcuts,
)

PROTON_NEXT_APPID = 2230260
PROTON_EAC_RUNTIME_APPID = 1826330
PROTON_BATTLEYE_RUNTIME_APPID = 1161040
STEAMLINUXRUNTIME_APPID = 1070560
STEAMLINUXRUNTIME_SOLDIER_APPID = 1391110
STEAMLINUXRUNTIME_SNIPER_APPID = 1628350


class SteamRuntimeType(Enum):
    """
    Represents the types of Steam runtimes, primarily used for
    identifying required Anti-Cheat runtimes for games.
    """

    EAC = PROTON_EAC_RUNTIME_APPID  # ProtonEasyAntiCheatRuntime
    BATTLEYE = PROTON_BATTLEYE_RUNTIME_APPID  # ProtonBattlEyeRuntime
    STEAMLINUXRUNTIME = STEAMLINUXRUNTIME_APPID  # Steam Linux Runtime 1.0 (scout)


class SteamAppType(Enum):
    """
    Represents the category of a Steam application, which can be
    a game, a runtime, a compatibility tool, etc.
    """

    GAME = 0
    RUNTIME = 1
    ANTICHEAT_RUNTIME = 2
    STEAMWORKS = 3
    PROTON_NEXT = 4
    COMPAT_TOOL = 5


class SteamDeckCompatType(Enum):
    """
    Represents the compatibility status of a game on the Steam Deck.
    """

    UNKNOWN = 0
    UNSUPPORTED = 1
    PLAYABLE = 2
    VERIFIED = 3


class SteamDeckCompatInfo(TypedDict):
    """
    Represents the Steam Deck compatibility information for a game, including
    the recommended compatibility tool and the compatibility category as defined
    in the appinfo.vdf metadata.
    """

    configuration: dict[str, str]
    category: int


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

    __slots__ = Game.__slots__ + (
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
        self.deck_compatibility: SteamDeckCompatInfo = {"configuration": {}, "category": 0}
        self.app_type = SteamAppType.GAME

        self.shortcut_id = ""
        self.shortcut_startdir = ""
        self.shortcut_exe = ""
        self.shortcut_icon = ""
        self.shortcut_user = ""

    def get_steamdeck_compatibility(self) -> tuple[str, SteamDeckCompatType]:
        """
        Returns the Steam Deck compatibility status for this game.

        Returns:
            tuple[str, SteamDeckCompatType]:
                A tuple containing the recommended compatibility tool (e.g., "proton_7")
                and the SteamDeckCompatType enum value representing the compatibility category.
        """
        recommended_runtime = self.deck_compatibility.get("configuration", {}).get(
            "recommended_runtime", ""
        )
        try:
            compat_type = SteamDeckCompatType(self.deck_compatibility.get("category"))
        except (TypeError, ValueError):
            compat_type = SteamDeckCompatType.UNKNOWN
        return recommended_runtime, compat_type


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

    def get_installed_tools(
        self, tool_types: list[CompatToolType] | None = None
    ) -> list[CompatTool]:
        """
        Returns a list of installed compatibility tools for this launcher by checking the
        compatibility tools directory and installed official Proton versions.

        Args:
            tool_types (list[CompatToolType] | None):
                An optional list of tool types to filter by.
                If None, all supported tool types are checked.

        Returns:
            list[CompatTool]: A list of installed compatibility tools.
        """
        installed_tools = super().get_installed_tools(tool_types)

        if not tool_types or CompatToolType.PROTON in tool_types:
            installed_tools.extend(
                [
                    CompatTool(app.name, CompatToolType.PROTON, app.install_path)
                    for app in self.get_game_list()
                    if app.app_type == SteamAppType.COMPAT_TOOL
                ]
            )

        return installed_tools

    def remove_tool(self, tool: CompatTool) -> None:
        """
        Removes an installed compatibility tool from this launcher.

        Tools that are managed by Steam (e.g. Proton installed as a Steam app)
        cannot be removed and raise a ValueError instead.

        Args:
            tool (CompatTool): The installed compatibility tool to remove.

        Raises:
            ValueError: If the tool is managed by Steam or its directory is not
                inside a supported compatibility tools directory.
            FileNotFoundError: If the tool's directory does not exist.
            PermissionError: If the tool's directory cannot be deleted.
        """
        steam_managed_paths = {
            app.install_path.resolve()
            for app in self.get_game_list()
            if app.app_type == SteamAppType.COMPAT_TOOL
        }
        if tool.install_dir.resolve() in steam_managed_paths:
            raise ValueError(
                f"{tool.full_name} is managed by Steam and cannot be removed with protondl. "
                "Uninstall it in Steam instead."
            )
        super().remove_tool(tool)

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

    def set_games_tools(self, game_tool_map: Mapping[Game, str | None]) -> None:
        config_vdf_file: Path = self.root_path / "config" / "config.vdf"

        try:
            config_data = vdf_safe_load(config_vdf_file)
            compat_tool_mapping = get_steam_vdf_compat_tool_mapping(config_data)

            for game, compat_tool_name in game_tool_map.items():
                if game.id in compat_tool_mapping:
                    if not compat_tool_name:
                        compat_tool_mapping.pop(game.id)
                    elif game_entry := compat_tool_mapping.get(game.id):
                        game_entry["name"] = compat_tool_name
                elif compat_tool_name:
                    compat_tool_mapping[game.id] = {
                        "name": compat_tool_name,
                        "config": "",
                        "priority": "75" if game.id == "0" else "250",
                    }

            vdf.dump(config_data, open(config_vdf_file, "w"), pretty=True)
        except Exception as e:
            raise RuntimeError(f"Setting the compatibility tools for games failed: {e}") from e

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
        games = []

        for entry in get_steam_shortcuts(self.root_path):
            appid = entry["appid"]
            game = SteamGame(appid, entry["name"], self.root_path / "userdata" / entry["user"])

            game.app_type = SteamAppType.GAME
            if ct := compat_tool_mapping.get(str(appid)):
                game.compat_tool_name = ct.get("name", "")

            game.shortcut_id = entry["sid"]
            game.shortcut_startdir = entry["startdir"]
            game.shortcut_exe = entry["exe"]
            game.shortcut_icon = entry["icon"]
            game.shortcut_user = entry["user"]

            games.append(game)

        return games

    def get_shortcuts(self) -> Sequence[SteamGame]:
        """
        Returns a list of non-Steam shortcuts (custom game entries).

        Shortcuts are read from the shortcuts.vdf files of all Steam users.

        Returns:
            Sequence[SteamGame]: A list of Steam shortcuts.

        Raises:
            ValueError: If fetching the shortcuts failed.
        """
        compat_tool_mapping = self._get_compat_tool_mapping()
        return self._get_steam_shortcuts_list(compat_tool_mapping)

    def add_shortcut(
        self,
        name: str,
        exe: str,
        startdir: str = "",
        icon: str = "",
        user: str = "",
    ) -> SteamGame:
        """
        Adds a new non-Steam shortcut to Steam.

        The shortcut is added to the most common user of existing shortcuts,
        or to the most recently logged in user if there are no shortcuts yet.
        Use the 'user' parameter to override the target user (userdata folder
        name).

        Args:
            name (str): The display name of the shortcut.
            exe (str): The executable to launch.
            startdir (str): The working directory for the launch.
            icon (str): The path to the icon used for the shortcut.
            user (str): The userdata folder name of the Steam user the
                shortcut should be added to. Auto-detected if empty.

        Returns:
            SteamGame: The newly added shortcut.

        Raises:
            ValueError: If 'name' or 'exe' is empty, no Steam user can be
                determined, or writing the shortcut failed.
        """
        if not name or not exe:
            raise ValueError("Shortcut name and executable are required")

        if not user:
            user = self._determine_shortcut_user()

        shortcuts = get_steam_shortcuts(self.root_path)
        user_sids = [int(entry["sid"]) for entry in shortcuts if entry["user"] == user]
        next_sid = max(user_sids, default=-1) + 1

        appid = calc_shortcut_app_id(name, exe)
        if appid < 0:
            appid = appid + (1 << 32)  # convert to unsigned

        write_steam_shortcuts(
            self.root_path,
            [
                {
                    "user": user,
                    "sid": str(next_sid),
                    "appid": appid,
                    "name": name,
                    "exe": exe,
                    "startdir": startdir,
                    "icon": icon,
                }
            ],
        )

        game = SteamGame(appid, name, self.root_path / "userdata" / user)
        game.app_type = SteamAppType.GAME
        game.shortcut_id = str(next_sid)
        game.shortcut_startdir = startdir
        game.shortcut_exe = exe
        game.shortcut_icon = icon
        game.shortcut_user = user

        self._cached_game_list = []
        return game

    def update_shortcuts(self, shortcuts: Sequence[SteamGame]) -> None:
        """
        Updates the given non-Steam shortcuts in the Steam configuration.

        Only the name, executable, start directory and icon are updated.

        Args:
            shortcuts (Sequence[SteamGame]): The shortcuts to update.

        Raises:
            ValueError: If a shortcut has no shortcut_id or writing the
                shortcuts failed.
        """
        entries = []
        for shortcut in shortcuts:
            if not shortcut.shortcut_id:
                raise ValueError(f"Shortcut '{shortcut.name}' has no shortcut_id")
            entries.append(
                {
                    "user": shortcut.shortcut_user,
                    "sid": str(shortcut.shortcut_id),
                    "appid": shortcut.appid,
                    "name": shortcut.name,
                    "exe": shortcut.shortcut_exe,
                    "startdir": shortcut.shortcut_startdir,
                    "icon": shortcut.shortcut_icon,
                }
            )

        write_steam_shortcuts(self.root_path, entries)
        self._cached_game_list = []

    def remove_shortcuts(self, shortcuts: Sequence[SteamGame]) -> None:
        """
        Removes the given non-Steam shortcuts from the Steam configuration.

        Args:
            shortcuts (Sequence[SteamGame]): The shortcuts to remove.

        Raises:
            ValueError: If writing the shortcuts failed.
        """
        delete: dict[str, list[str]] = {}
        for shortcut in shortcuts:
            delete.setdefault(shortcut.shortcut_user, []).append(str(shortcut.shortcut_id))

        write_steam_shortcuts(self.root_path, [], delete)
        self._cached_game_list = []

    def _get_compat_tool_mapping(self) -> dict[str, CompatToolUsage]:
        """
        Returns the game compatibility tool mapping from config.vdf,
        or an empty dict if it cannot be loaded.
        """
        config_vdf_file: Path = self.root_path / "config" / "config.vdf"
        try:
            config_data = vdf_safe_load(config_vdf_file)
            return get_steam_vdf_compat_tool_mapping(config_data)
        except Exception as e:
            print(f"Warning: Could not load the compatibility tool mapping: {e}")
            return {}

    def _determine_shortcut_user(self) -> str:
        """
        Determines the user a new shortcut should be added to.

        Returns the most common user of existing shortcuts, otherwise the
        most recently logged in user.

        Returns:
            str: The userdata folder name of the Steam user.

        Raises:
            ValueError: If no Steam user can be determined.
        """
        shortcuts = get_steam_shortcuts(self.root_path)
        if shortcuts:
            users: list[str] = [str(entry["user"]) for entry in shortcuts]
            return Counter(users).most_common(1)[0][0]

        user = determine_most_recent_steam_user(get_steam_users(self.root_path))
        if user is None:
            raise ValueError("No Steam user found to add the shortcut to")
        return str(user.short_id)

    def get_global_tool(self, tool_type: CompatToolType) -> CompatTool | None:
        if tool_type not in self.supported_tools_folders:
            raise ValueError(
                "SteamLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders.keys()}, got {tool_type}"
            )
        tools = self.get_installed_tools([tool_type])

        config_vdf_file: Path = self.root_path / "config" / "config.vdf"
        try:
            config_data = vdf_safe_load(config_vdf_file)
            compat_tool_mapping = get_steam_vdf_compat_tool_mapping(config_data)
            for tool in tools:
                if tool.full_name in compat_tool_mapping.get("0", {}).get("name", ""):  # type: ignore
                    return tool
        except Exception as e:
            print(f"Warning: Could not load the compatibility tool mapping: {e}")

        return None

    def set_global_tool(self, tool: CompatTool) -> None:
        if tool.tool_type not in self.supported_tools_folders:
            raise ValueError(
                "SteamLauncher only supports the following tool types: "
                + f"{self.supported_tools_folders.keys()}, got {tool.tool_type}"
            )
        self.set_games_tools({SteamGame(0, "", Path("")): tool.full_name})
