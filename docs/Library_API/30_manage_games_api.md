# Manage Games (Library)

Managing games is currently supported for the following launchers: <span class="badge steam">Steam</span> <span class="badge lutris">Lutris</span> <span class="badge heroic">Heroic</span>

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

> **Blocking I/O:** `get_game_list()` reads and parses the launcher's
> configuration and database files (e.g. Steam's `appinfo.vdf`, Lutris' `pga.db`)
> on the calling thread. From an async or GUI event loop, offload it to a thread
> pool with `await asyncio.to_thread(launcher.get_game_list)` (or
> `loop.run_in_executor(None, launcher.get_game_list)`) so the UI stays
> responsive.

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

## Manage Steam shortcuts

Non-Steam games and applications can be added to the Steam library as shortcuts. Shortcuts are stored in
the binary `shortcuts.vdf` file in the config directory of each Steam user.

`SteamLauncher` provides `get_shortcuts()`, `add_shortcut()`, `update_shortcuts()` and `remove_shortcuts()`
to manage them. Shortcuts are represented as `SteamGame` objects with the shortcut-specific attributes
`shortcut_id`, `shortcut_exe`, `shortcut_startdir`, `shortcut_icon` and `shortcut_user`.

### List shortcuts

```python
from protondl.launchers.steam import SteamLauncher

launcher = SteamLauncher.discover()[0]

for shortcut in launcher.get_shortcuts():
    print(
        f"{shortcut.name}: {shortcut.shortcut_exe} "
        f"(user {shortcut.shortcut_user}, sid {shortcut.shortcut_id})"
    )
```

Shortcuts are also included in `get_game_list()` (unless called with `shortcuts=False`).

### Add a shortcut

`add_shortcut()` creates a new custom entry. The shortcut is added to the Steam user with the most
existing shortcuts, or to the most recently logged in user if there are none. Use the `user` parameter
to target a specific user (the userdata folder name).

```python
from protondl.launchers.steam import SteamLauncher

launcher = SteamLauncher.discover()[0]

shortcut = launcher.add_shortcut(
    name="My Game",
    exe="/opt/games/my-game/MyGame.sh",
    startdir="/opt/games/my-game",
    icon="/opt/games/my-game/icon.png",
)

# Assign a compatibility tool to the new shortcut like any other game
launcher.set_games_tools({shortcut: "GE-Proton10-14"})
```

`add_shortcut()` raises a `ValueError` if `name` or `exe` is empty, or if no Steam user can be determined.
The returned `SteamGame` carries the shortcut's appid, user and sid.

### Update shortcuts

Mutate the shortcut's `name`, `shortcut_exe`, `shortcut_startdir` or `shortcut_icon` attributes and write
the changes with `update_shortcuts()`. Only these four fields are updated.

```python
from protondl.launchers.steam import SteamLauncher

launcher = SteamLauncher.discover()[0]

shortcut = launcher.get_shortcuts()[0]
shortcut.name = "Renamed Game"
shortcut.shortcut_exe = "/opt/games/my-game/MyGame"
launcher.update_shortcuts([shortcut])
```

### Remove shortcuts

```python
from protondl.launchers.steam import SteamLauncher

launcher = SteamLauncher.discover()[0]

shortcuts = launcher.get_shortcuts()
launcher.remove_shortcuts(shortcuts)  # remove all shortcuts
```

Note that Steam needs to be restarted to pick up changes to the shortcuts.

### Heroic

`HeroicLauncher` lists installed games across all Heroic stores (GOG, Epic via legendary, Amazon via nile, and sideloaded apps). Only games that are installed are returned; DLC entries are included.

```python
from protondl.launchers.heroic import HeroicLauncher

launcher = HeroicLauncher.discover()[0]
games = launcher.get_game_list()

for game in games:
    print(
        f"{game.id}: {game.name} (store: {game.runner}, tool: {game.compat_tool_name or 'default'})"
    )
```

`HeroicGame` objects expose additional attributes: `runner`, `is_dlc`, `is_installed`, `install_path`, `wine_type`, and `platform`. Assign a tool the same way as with Steam via `set_games_tools()`; pass `None` to reset a game to the global tool.

```python
from protondl.launchers.heroic import HeroicLauncher

launcher = HeroicLauncher.discover()[0]
game = launcher.get_game_list()[0]

launcher.set_games_tools({game: "GE-Proton10-14"})  # set a specific tool
launcher.set_games_tools({game: None})  # reset to the global tool
```

The per-game and global tools in Heroic correspond to Proton and Wine installers only (DXVK and vkd3d-proton do not have a matching Heroic `wineVersion` entry). `set_global_tool()` raises a `ValueError` for unsupported tool types; `set_games_tools()` raises a `RuntimeError`.

### Lutris

`LutrisLauncher` lists installed games read from Lutris' `pga.db` database, enriched with the assigned compatibility tool and install directory from each game's YAML configuration file. Games added manually to Lutris (without an install directory in the database) get their install directory resolved from the game's configuration.

```python
from protondl.launchers.lutris import LutrisLauncher

launcher = LutrisLauncher.discover()[0]
games = launcher.get_game_list()

for game in games:
    print(
        f"{game.id}: {game.name} (runner: {game.runner}, tool: {game.compat_tool_name or 'default'})"
    )
```

`LutrisGame` objects expose additional attributes: `slug`, `runner` (e.g. `wine` or `steam`), `installer_slug`, and `installed_at`. `install_path` is set to the game's install directory or `?` if it cannot be determined. Setting per-game tools via `set_games_tools()` is not implemented yet for Lutris.

Service-based online lookups such as AWACY and ProtonDB are documented in
`Library_API/40_external_services_api.md`.

## Helper functions

### Batch update games

Update the compatibility tool for multiple games at once using `batch_update_games_tools()`.
You can match games by an exact tool name (using a `CompatTool` instance) or by a partial string match.
This helper is also an essential part of the update workflow, see
[Manage Compatibility Tools](20_manage_tools_api.md#automatic-tool-updates) for more details.