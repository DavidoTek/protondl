import binascii
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import vdf
from steam.utils.appcache import parse_appinfo


class CompatToolUsage(TypedDict):
    """Represents the compatibility tool configuration for a specific game."""

    name: str
    config: str
    priority: str


class CompatToolInfo(TypedDict):
    """Information about an installed Steam compatibility tool."""

    name: str
    from_oslist: str


def vdf_safe_load(vdf_file: Path) -> dict:  # type: ignore
    """
    Loads a vdf file and returns its contents as a dict.

    Args:
        vdf_file (Path): Path to the vdf file

    Returns:
        dict: Content of the vdf file

    Raises:
        ValueError: In case loading the vdf fails
    """
    data = {}

    try:
        # Replace Unicode errors, see https://github.com/DavidoTek/ProtonUp-Qt/issues/424
        with open(vdf_file, encoding="utf-8", errors="replace") as f:
            data = vdf.loads(f.read())
    except Exception as e:
        raise ValueError(f"Loading {vdf_file} failed: {e}") from e

    if not isinstance(data, dict):
        # Apparently, vdf.loads() can return None (issue #481)
        raise ValueError(f"Loading {vdf_file} did not return a dict, but {type(data)}: {data}")

    return data


def get_steam_vdf_compat_tool_mapping(config_data: dict) -> dict[str, CompatToolUsage]:  # type: ignore
    """
    Get the game compatibility tool mapping from the Steam configuration.
    Maps the appid to the compatibility tool used by that game.

    Args:
        config_data (dict): Data from config.vdf. Load it using vdf_safe_load first.

    Returns:
        dict[str, CompatToolUsage]: Game compatibility tool mapping

    Raises:
        ValueError: If the configuration does not contain the 'valve' key
    """
    s = config_data.get("InstallConfigStore", {}).get("Software", {})

    # Key may be 'Valve' or 'valve', see https://github.com/DavidoTek/ProtonUp-Qt/issues/226
    c = s.get("Valve") or s.get("valve")
    if not c:
        raise ValueError("Steam config does not contain the 'valve' key (ignore case)")

    m = c.get("Steam", {}).get("CompatToolMapping", {})

    return m  # type: ignore


def get_steam_ctool_info(steam_root: Path) -> dict[str, CompatToolInfo]:
    """
    Get a map with information about the compatibility tools.
    Maps the appid of the tool to information about that tool.

    Args:
        steam_root (Path): Steam root directory

    Returns:
        dict[str, CompatToolInfo]: Maps the appid to compatibility tool info

    Raises:
        ValueError: If fetching Steam compatibilty tool info failed.
    """
    appinfo_file = steam_root / "appcache" / "appinfo.vdf"
    if not appinfo_file.is_file():
        raise ValueError(f"Steam app info does not exist: {appinfo_file}")

    ctool_map = {}
    compat_tools = {}
    try:
        with open(appinfo_file, "rb") as f:
            _, apps = parse_appinfo(f, mapper=dict)
            for steam_app in apps:
                if steam_app.get("appid") == 891390:
                    compat_tools = (
                        steam_app.get("data", {})
                        .get("appinfo", {})
                        .get("extended", {})
                        .get("compat_tools", {})
                    )
                    break
    except Exception as e:
        raise ValueError(f"Error getting compatibility tool map from appinfo.vdf: {e}") from e
    else:
        for t in compat_tools:
            ctool_map[str(compat_tools.get(t, {}).get("appid", ""))] = CompatToolInfo(
                name=t, from_oslist=compat_tools.get(t, {}).get("from_oslist", "")
            )

    return ctool_map


@dataclass
class SteamUser:
    """
    Represents a Steam user account.

    Attributes:
        long_id (int): The 64-bit SteamID.
        account_name (str): The user's account name.
        persona_name (str): The user's display name.
        most_recent (bool): True if the user was logged in most recently.
        timestamp (int): Timestamp of the last login.
    """

    long_id: int
    account_name: str
    persona_name: str
    most_recent: bool
    timestamp: int

    @property
    def short_id(self) -> int:
        """
        Returns the short (32-bit) SteamID, used as the userdata folder name.

        Returns:
            int: The short SteamID.
        """
        return self.long_id & 0xFFFFFFFF


def get_steam_users(steam_root: Path) -> list[SteamUser]:
    """
    Returns a list of Steam users from the loginusers.vdf file.

    Args:
        steam_root (Path): Steam root directory.

    Returns:
        list[SteamUser]: The Steam users, or an empty list if the file does
            not exist or cannot be loaded.
    """
    loginusers_file = steam_root / "config" / "loginusers.vdf"
    if not loginusers_file.is_file():
        return []

    users = []
    try:
        data = vdf_safe_load(loginusers_file)
    except ValueError:
        return []

    for uid, uvalue in data.get("users", {}).items():
        if not isinstance(uvalue, dict):
            continue
        users.append(
            SteamUser(
                long_id=int(uid),
                account_name=str(uvalue.get("AccountName", "")),
                persona_name=str(uvalue.get("PersonaName", "")),
                most_recent=bool(int(uvalue.get("MostRecent", "0"))),
                timestamp=int(uvalue.get("Timestamp", "-1")),
            )
        )

    return users


def determine_most_recent_steam_user(steam_users: Sequence[SteamUser]) -> SteamUser | None:
    """
    Returns the Steam user that was logged in most recently.

    Returns the first user with most_recent=True, otherwise the first user.

    Args:
        steam_users (Sequence[SteamUser]): List of Steam users,
            from get_steam_users().

    Returns:
        SteamUser | None: The most recent user, or None if the list is empty.
    """
    for user in steam_users:
        if user.most_recent:
            return user
    return steam_users[0] if steam_users else None


def calc_shortcut_app_id(appname: str, exe: str) -> int:
    """
    Calculates the appid for a shortcut based on the app name and executable.

    Based on
    https://github.com/SteamGridDB/steam-rom-manager/blob/master/src/lib/helpers/steam/generate-app-id.ts

    Args:
        appname (str): The name of the shortcut.
        exe (str): The executable of the shortcut.

    Returns:
        int: The calculated appid.
    """
    key = exe + appname
    return (binascii.crc32(key.encode()) | 0x80000000) - 0x100000000


def get_steam_shortcuts(steam_root: Path) -> list[dict[str, Any]]:
    """
    Returns the Steam shortcuts (non-Steam games) from all users.

    Shortcuts are read from the binary shortcuts.vdf files in each user's
    config directory. The returned entries use the following keys:
    'user' (userdata folder name), 'sid' (key in the shortcuts VDF),
    'appid' (unsigned), 'name', 'exe', 'startdir' and 'icon'.

    Args:
        steam_root (Path): Steam root directory.

    Returns:
        list[dict]: The Steam shortcuts.

    Raises:
        ValueError: If a shortcuts.vdf file exists but cannot be loaded.
    """
    users_folder = steam_root / "userdata"
    if not users_folder.is_dir():
        return []

    entries = []
    for user_dir in users_folder.iterdir():
        if not user_dir.is_dir():
            continue

        shortcuts_file = user_dir / "config" / "shortcuts.vdf"
        if not shortcuts_file.is_file():
            continue

        try:
            with open(shortcuts_file, "rb") as f:
                shortcuts_data = vdf.binary_load(f)
        except Exception as e:
            raise ValueError(f"Loading Steam shortcuts failed: {e}") from e

        for sid, svalue in shortcuts_data.get("shortcuts", {}).items():
            if not isinstance(svalue, dict):
                continue
            appid = svalue.get("appid", 0)
            if not isinstance(appid, int):
                appid = 0
            if appid < 0:
                appid = appid + (1 << 32)  # convert to unsigned
            entries.append(
                {
                    "user": user_dir.name,
                    "sid": str(sid),
                    "appid": appid,
                    "name": str(svalue.get("AppName") or svalue.get("appname", "")),
                    "exe": str(svalue.get("Exe", "")),
                    "startdir": str(svalue.get("StartDir", "")),
                    "icon": str(svalue.get("icon", "")),
                }
            )

    return entries


def write_steam_shortcuts(
    steam_root: Path,
    shortcuts: Sequence[dict[str, Any]],
    delete: Mapping[str, Sequence[str]] | None = None,
) -> None:
    """
    Updates the Steam shortcuts.vdf files with the provided shortcuts.

    Existing shortcuts (matching the sid) are updated in place, new ones are
    added and the shortcuts given in 'delete' are removed. The shortcuts are
    grouped by their 'user' key (userdata folder name) and written to the
    matching user's shortcuts.vdf file.

    Args:
        steam_root (Path): Steam root directory.
        shortcuts (Sequence[dict]): Shortcuts to add or update. Each entry
            uses the same keys as get_steam_shortcuts().
        delete (Mapping[str, Sequence[str]] | None): Maps a user to the
            list of sids to remove.

    Raises:
        ValueError: If writing a shortcuts.vdf file failed.
    """
    shortcuts_by_user: dict[str, dict[str, dict[str, Any]]] = {}
    for shortcut in shortcuts:
        user = str(shortcut.get("user", ""))
        sid = str(shortcut.get("sid", ""))
        shortcuts_by_user.setdefault(user, {})[sid] = shortcut

    users_folder = steam_root / "userdata"
    users = set(shortcuts_by_user.keys())
    if delete:
        users.update(delete.keys())

    for user in users:
        user_shortcuts = shortcuts_by_user.get(user, {})
        shortcuts_file = users_folder / user / "config" / "shortcuts.vdf"

        shortcuts_data: dict[str, Any] = {}
        if shortcuts_file.is_file():
            try:
                with open(shortcuts_file, "rb") as f:
                    shortcuts_data = vdf.binary_load(f)
            except Exception as e:
                raise ValueError(f"Loading Steam shortcuts failed: {e}") from e

        current_shortcuts = shortcuts_data.get("shortcuts", {})
        if not isinstance(current_shortcuts, dict):
            current_shortcuts = {}

        for sid, shortcut in user_shortcuts.items():
            if sid in current_shortcuts and isinstance(current_shortcuts[sid], dict):
                svalue = current_shortcuts[sid]
                svalue["AppName"] = shortcut.get("name", "")
                svalue["Exe"] = shortcut.get("exe", "")
                svalue["StartDir"] = shortcut.get("startdir", "")
                svalue["icon"] = shortcut.get("icon", "")
            else:
                current_shortcuts[sid] = _new_shortcut_vdf_entry(shortcut)

        for sid in (delete or {}).get(user, []):
            current_shortcuts.pop(sid, None)

        shortcuts_data["shortcuts"] = current_shortcuts

        try:
            shortcuts_file.parent.mkdir(parents=True, exist_ok=True)
            with open(shortcuts_file, "wb") as f:
                f.write(vdf.binary_dumps(shortcuts_data))
        except Exception as e:
            raise ValueError(f"Writing Steam shortcuts failed: {e}") from e


def _new_shortcut_vdf_entry(shortcut: dict[str, Any]) -> dict[str, Any]:
    """
    Builds the binary VDF entry for a new shortcut.

    Args:
        shortcut (dict): The shortcut data, using the same keys as
            get_steam_shortcuts().

    Returns:
        dict: The entry as stored in the shortcuts VDF.
    """
    return {
        "appid": _to_signed_appid(shortcut.get("appid", 0)),
        "AppName": shortcut.get("name", ""),
        "Exe": shortcut.get("exe", ""),
        "StartDir": shortcut.get("startdir", ""),
        "icon": shortcut.get("icon", ""),
        "ShortcutPath": "",
        "LaunchOptions": "",
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": "",
        "DevkitOverrideAppID": 0,
        "LastPlayTime": 0,
        "FlatpakAppID": "",
        "tags": {},
    }


def _to_signed_appid(appid: Any) -> Any:
    """
    Converts an unsigned 32-bit appid to its signed representation.

    The shortcuts VDF stores appids as signed 32-bit integers, while
    get_steam_shortcuts() returns them as unsigned values.

    Args:
        appid (Any): The appid.

    Returns:
        Any: The signed appid.
    """
    if isinstance(appid, int) and appid >= 1 << 31:
        return appid - (1 << 32)
    return appid
