# Manage Games (Library)

Managing games is currently supported for the following launchers: <span class="badge steam">Steam</span> <span class="badge heroic">Heroic</span>

## Basics

### List installed games

Get a list of all installed games for a launcher using `get_game_list()`.
This returns a sequence of `Game` objects containing metadata about each game, including the game ID, name, install path, and assigned compatibility tool.

```python
from protondl.launchers.steam import SteamLauncher

launcher = SteamLauncher.discover()[0]
games = launcher.get_game_list()

for game in games:
    print(f"{game.id}: {game.name} ({game.compat_tool_name})")
```

### Set compatibility tool for a specific game

Set a specific compatibility tool for one or more games using `set_games_tools()`.
This method accepts a mapping of games to tool names. Pass `None` to use the global compatibility tool.

```python
from protondl.launchers.steam import SteamLauncher

launcher = SteamLauncher.discover()[0]
games = launcher.get_game_list()

# Find a specific game and change its tool
game_to_update = next(g for g in games if g.name == "My Game")

# Set a specific tool
launcher.set_games_tools({game_to_update: "Proton-8.0"})

# Or use the global tool
launcher.set_games_tools({game_to_update: None})
```

### Read Steam Deck compatibility metadata

`SteamGame` objects expose `get_steamdeck_compatibility()` to return the recommended runtime and compatibility category.

```python
from protondl.launchers.steam import SteamDeckCompatType, SteamLauncher

launcher = SteamLauncher.discover()[0]

for game in launcher.get_game_list():
    recommended_runtime, status = game.get_steamdeck_compatibility()
    if status == SteamDeckCompatType.VERIFIED:
        print(f"{game.name} is VERIFIED (recommended runtime: {recommended_runtime or 'none'})")
```

### Heroic

`HeroicLauncher` lists installed games across all Heroic stores (GOG, Epic via legendary, Amazon via nile, and sideloaded apps). Only games that are installed are returned; DLC entries are included.

```python
from protondl.launchers.heroic import HeroicLauncher

launcher = HeroicLauncher.discover()[0]
games = launcher.get_game_list()

for game in games:
    print(f"{game.id}: {game.name} (store: {game.runner}, tool: {game.compat_tool_name or 'default'})")
```

`HeroicGame` objects expose additional attributes: `runner`, `is_dlc`, `is_installed`, `install_path`, `wine_type`, and `platform`. Assign a tool the same way as with Steam via `set_games_tools()`; pass `None` to reset a game to the global tool.

```python
from protondl.launchers.heroic import HeroicLauncher

launcher = HeroicLauncher.discover()[0]
game = launcher.get_game_list()[0]

launcher.set_games_tools({game: "GE-Proton10-14"})  # set a specific tool
launcher.set_games_tools({game: None})               # reset to the global tool
```

The per-game and global tools in Heroic correspond to Proton and Wine installers only (DXVK and vkd3d-proton do not have a matching Heroic `wineVersion` entry). `set_global_tool()` raises a `ValueError` for unsupported tool types; `set_games_tools()` raises a `RuntimeError`.

Service-based online lookups such as AWACY and ProtonDB are documented in
`Library_API/40_external_services_api.md`.

## Helper functions

### Batch update games

Update the compatibility tool for multiple games at once using `batch_update_games_tools()`.
You can match games by an exact tool name (using a `CompatTool` instance) or by a partial string match.

```python
from protondl.launchers.steam import SteamLauncher
from protondl.util.helpers import batch_update_games_tools
from protondl.core.models import CompatTool, CompatToolType
from pathlib import Path

launcher = SteamLauncher.discover()[0]

# Get the new tool to assign
new_tool = CompatTool("Proton-9.0", CompatToolType.PROTON, Path("/path/to/tool"))

# Update all games using tools with "GE-Proton" in the name
count = batch_update_games_tools(launcher, "GE-Proton", new_tool)
print(f"Updated {count} games")

# Or update games using an exact tool
old_tool = CompatTool("Proton-8.0", CompatToolType.PROTON, Path("/path/to/tool"))
count = batch_update_games_tools(launcher, old_tool, new_tool)
print(f"Updated {count} games")
```
