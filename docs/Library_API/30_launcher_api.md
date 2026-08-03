# Launchers (Library)

## Discover launchers

Use `detect_all_launchers()` to discover all supported launcher installations on the current system.

```python
from protondl.launchers import detect_all_launchers

launchers = detect_all_launchers()

for launcher in launchers:
    print(launcher.name, launcher.install_mode.value, launcher.root_path)
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
    "installed_at": 1785769458
}
```

- `compat_tool`: The name of the compatibility tool installer (`CtInstaller.name`).
- `version`: The installed version as returned by `CtInstaller.fetch_releases`.
- `installed_at`: The UNIX timestamp in seconds when the tool was installed.

The file is read by `get_installed_tools()` to resolve the correct tool type of an
installed tool. Tools without the file are still detected and fall back to the type of
their parent folder. This disambiguates launchers that share a folder across tool types
(e.g., Lutris stores Proton and Wine runners in `runners/wine`).

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
- `LutrisLauncher`: launcher discovery and compatibility-tool filesystem management.
- `HeroicLauncher`: launcher discovery and compatibility-tool filesystem management.
- `BottlesLauncher`: launcher discovery and compatibility-tool filesystem management.

Game management and global tool APIs are currently implemented for Steam launchers.
