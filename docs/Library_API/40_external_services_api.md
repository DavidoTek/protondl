# External Services (Library)

Network-bound integrations are available in the dedicated `protondl.services` package.
These APIs are optional and can be used by any app integrating protondl.

## AWACY anti-cheat status

Use `protondl.services.awacy` to query Linux anti-cheat compatibility from [areweanticheatyet.com](https://areweanticheatyet.com/).

`fetch_awacy_index()` downloads the AWACY game list into an `AWACYIndex`.
Use `get_awacy_status_by_id()` and `get_awacy_status_by_slug()` to read a game's status from that index.


```python
import asyncio

from protondl.services.awacy import (
    fetch_awacy_index,
    get_awacy_status_by_id,
    get_awacy_status_by_slug,
)


game = launcher.get_game_list()[0]

index: AWACYIndex = asyncio.run(fetch_awacy_index())

steam_status: AWACYStatus = get_awacy_status_by_id(game.id, index)
slug_status: AWACYStatus = get_awacy_status_by_slug("game-slug", index)

print(steam_status.value)
print(slug_status.value)
```
