# Manage Games

protondl allows listing and managing installed games.

Managing games is currently supported for the following launchers: <span class="badge steam">Steam</span> <span class="badge lutris">Lutris</span> <span class="badge heroic">Heroic</span>

## List installed games

You may list the installed games of a launcher by running the following command.
It displays the launcher's game ID, the name of the game, the install directory, and the compatibility tool the game uses.

```bash
protondl list-games <launcher id>
```

Add `--awacy` to include the AWACY anti-cheat status for each game.
Add `--protondb` to include the ProtonDB compatibility rating for each game.
Add `--deck-status` to include the Steam Deck compatibility status for each game.
All flags can be combined.

```bash
protondl list-games <launcher id> --awacy
protondl list-games <launcher id> --protondb
protondl list-games <launcher id> --deck-status
protondl list-games <launcher id> --awacy --protondb --deck-status
```

Games without a Steam AppID or without a ProtonDB report are shown as `Unknown`.
The Steam Deck status is read from the local Steam metadata and is only available
for Steam games; it is shown as `VERIFIED`, `PLAYABLE`, `UNSUPPORTED`, or `UNKNOWN`,
followed by the recommended runtime if one is set (e.g. `VERIFIED (proton_9)`).
Steam shortcuts (non-Steam games) are skipped in all status columns. If the status data
could not be fetched (for example, the service is unreachable), the affected column
shows `Network Error` instead; the table is still printed and the command exits with
code 3. If the installed game list cannot be read, the command exits with code 2.

## Show Steam Deck compatibility for a game

For Steam games, you can inspect the Steam Deck compatibility category and the recommended runtime.

```bash
protondl get-steam-deck-status <launcher id> <game id>
```

The command prints the Steam Deck status as one of `UNKNOWN`, `UNSUPPORTED`, `PLAYABLE`, or `VERIFIED`.

## Set compatibility tool for a specific game

Run the following command to force that a specific game uses a specific compatibility tool.
Use the game id from [`list-games`](#list-installed-games) and the tool name from [`list-installed`](./10_manage_tools.md#list-installed-compatibility-tools).

```bash
protondl set-tool <launcher id> <game id> <tool name>

# Reset game-specific override and use global tool
protondl set-tool <launcher id> <game id> none
```

`set-tool` currently requires a Steam or Heroic launcher. For Heroic, only Proton and Wine tools are supported, and listing includes installed DLC.
