# Manage Games

protondl allows listing and managing installed games.

Managing games is currently supported for the following launchers: <span class="badge steam">Steam</span>

## List installed games

You may list the installed games of a launcher by running the following command.
It displays the launcher's game ID, the name of the game, the install directory, and the compatibilty tools the game uses.

```bash
protondl list-games <launcher id>
```

## Set compatibility tool for a specific game

Run the following command to force that a specific game uses a specific compatibility tool.
Use the game id from [`list-games`](#list-installed-games) and the tool name from [`list-installed`](./10_manage_tools.md#list-installed-compatibility-tools).

```bash
protondl list-games <launcher id> <game id> <tool name>
```
