# External Services

This page covers CLI commands that query optional online services.

## Show AWACY anti-cheat status for a game

You can query the [areweanticheatyet.com](https://areweanticheatyet.com/) status for a game by Steam AppID or AWACY slug.

```bash
protondl get-awacy-status <game id>
protondl get-awacy-status --slug <awacy slug>
```

The command prints the AWACY status as `Broken`, `Denied`, `Planned`, `Running`, `Supported`, or `Unknown`.

## Show ProtonDB compatibility rating for a game

You can query the [protondb.com](https://www.protondb.com/) compatibility rating for a game by Steam AppID.

```bash
protondl get-protondb-status <steam appid>
```

The command prints the ProtonDB tier as `Borked`, `Bronze`, `Gold`, `Pending`, `Platinum`, `Silver`, or `Unknown`.
It prints `Unknown` when ProtonDB has no report for the given AppID, and exits with an error
when the data cannot be fetched. A non-numeric AppID is rejected up front as `Invalid Steam AppID`.
