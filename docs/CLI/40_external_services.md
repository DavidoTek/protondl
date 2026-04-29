# External Services

This page covers CLI commands that query optional online services.

## Show AWACY anti-cheat status for a game

You can query the [areweanticheatyet.com](https://areweanticheatyet.com/) status for a game by Steam AppID or AWACY slug.

```bash
protondl get-awacy-status <game id>
protondl get-awacy-status --slug <awacy slug>
```

The command prints the AWACY status as `Broken`, `Denied`, `Planned`, `Running`, `Supported`, or `Unknown`.
