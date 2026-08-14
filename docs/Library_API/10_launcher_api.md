# Launchers (Library)

## Discover launchers

Use `detect_all_launchers()` to discover all supported launcher installations on the current system.

```python
from protondl.launchers import detect_all_launchers

launchers = detect_all_launchers()

for launcher in launchers:
    print(launcher.name, launcher.install_mode.value, launcher.root_path)
```

## Custom launcher paths

Launchers installed at non-standard locations (e.g. a Steam installation in `~/mySteam` instead of
`~/.steam/root`) are not picked up by `detect_all_launchers()`, since discovery only scans the default
installation paths. Use `create_launcher_from_path()` to construct a launcher instance directly from a
custom root path.

```python
from pathlib import Path
from protondl.launchers import create_launcher_from_path

launcher = create_launcher_from_path("steam", Path("~/mySteam").expanduser())
```

The supported types are `steam`, `lutris`, `heroic` and `bottles`. The returned launcher behaves exactly
like a discovered one: the compatibility tools directory, game list, and global tool configuration are all
resolved relative to the given root path. The path may not exist yet; installers create the required
directories on demand. An unknown launcher type raises a `ValueError`.

Equivalent to calling the launcher class constructor directly:

```python
from pathlib import Path
from protondl.launchers.steam import SteamLauncher
from protondl.core.models import InstallMode

launcher = SteamLauncher("Steam", Path("~/mySteam").expanduser(), InstallMode.NATIVE)
```

## List installed compatibility tools

Query all installed tools or restrict by tool type.

```python
from protondl.core.models import CompatToolType
from protondl.launchers import detect_all_launchers

launcher = detect_all_launchers()[0]

# All installed tools
all_tools = launcher.get_installed_tools()

# Only Proton tools
proton_tools = launcher.get_installed_tools([CompatToolType.PROTON])
```

## protondl_version.json

When a compatibility tool is installed via an installer (see the installers API),
protondl writes a `protondl_version.json` file into the tool's installation directory:

```json
{
    "compat_tool": "GE-Proton",
    "version": "GE-Proton11-3",
    "installed_at": 1785769458,
    "arch": "aarch64",
    "translation_details": {
        "from_os": "windows",
        "from_arch": "x86_64",
        "to_os": "linux",
        "to_arch": "aarch64"
    }
}
```

- `compat_tool`: The name of the compatibility tool installer (`CtInstaller.name`).
- `version`: The installed version as returned by `CtInstaller.fetch_releases`.
- `installed_at`: The UNIX timestamp in seconds when the tool was installed.
- `arch`: The architecture of the installed build (e.g. `x86_64` or `aarch64`).
- `translation_details`: Describes the game/host translation the build performs.
  - `from_os`/`from_arch`: The guest side, i.e. the games the tool runs
    (e.g. Windows `x86_64` games).
  - `to_os`/`to_arch`: The host side the tool runs on (e.g. Linux `aarch64`).

For example, the `aarch64` build of GE-Proton runs x86_64 Windows games on
ARM Linux (via Fex), hence `from_arch: "x86_64"` and `to_arch: "aarch64"`.

`arch` and `translation_details` may be absent for tools installed by older
versions of protondl; the file is read accordingly.

The file is read by `get_installed_tools()` to resolve the correct tool type of an
installed tool. Tools without the file are still detected and fall back to the type of
their parent folder. This disambiguates launchers that share a folder across tool types
(e.g., Lutris stores Proton and Wine runners in `runners/wine`).

## Remove installed compatibility tools

Remove an installed compatibility tool using `remove_tool()`.
The tool is located by name or index from `list-installed`, then its directory is deleted.

```python
from protondl.launchers import detect_all_launchers

launcher = detect_all_launchers()[0]

tools = launcher.get_installed_tools()
if tools:
    launcher.remove_tool(tools[0])
```

`Launcher.remove_tool()` refuses to delete directories outside the launcher's compatibility
tools directories and tools that are managed by the launcher itself (e.g. Proton installed
as a Steam app). If the tool was installed by a protondl installer, the matching
`CtInstaller.remove()` is called instead of a plain folder deletion, allowing installers to
perform additional cleanup. Installers can override the default `remove()` implementation,
which deletes the tool's installation directory.

## Get and set global compatibility tools

Get the global compatibility tool for a launcher using `get_global_tool()`.
This returns the default compatibility tool that applies to all games unless they have a game-specific override.
Set a new global tool using `set_global_tool()`.

```python
from protondl.launchers.steam import SteamLauncher
from protondl.core.models import CompatToolType

launcher = SteamLauncher.discover()[0]

# Get the current global Proton tool
current_tool = launcher.get_global_tool(CompatToolType.PROTON)
if current_tool:
    print(f"Global tool: {current_tool.full_name}")
else:
    print("No global tool set")

# Set a new global tool
available_tools = launcher.get_installed_tools([CompatToolType.PROTON])
if available_tools:
    launcher.set_global_tool(available_tools[0])
```

## Current implementation status

- `SteamLauncher`: game list, per-game tool mapping, global tool management, Steam Deck compatibility metadata.
- `LutrisLauncher`: launcher discovery, compatibility-tool filesystem management, and game list.
- `HeroicLauncher`: launcher discovery, game list, per-game tool mapping, and global tool management.
- `BottlesLauncher`: launcher discovery and compatibility-tool filesystem management.

Game management APIs are currently implemented for Steam and Heroic launchers, and listing
games is implemented for Lutris.
