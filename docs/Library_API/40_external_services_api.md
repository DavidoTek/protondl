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

## ProtonDB compatibility rating

Use `protondl.services.protondb` to query the Linux compatibility rating from [protondb.com](https://www.protondb.com/).

`fetch_protondb_summary()` downloads the report summary for a single Steam AppID.
Use `fetch_protondb_tier()` to get only the compatibility tier, and `fetch_protondb_tiers()`
to batch-lookup multiple targets in parallel (bounded by the `max_concurrency` argument,
10 by default). `resolve_steam_appid()` converts a game object or identifier into a Steam AppID.

In the batch lookup, targets without a ProtonDB report are mapped to `ProtonDBTier.UNKNOWN`,
while targets whose lookup failed due to a network error are mapped to `None`.

```python
import asyncio

from protondl.services.protondb import (
    ProtonDBTier,
    fetch_protondb_summary,
    fetch_protondb_tier,
    fetch_protondb_tiers,
    resolve_steam_appid,
)

game = launcher.get_game_list()[0]
appid = resolve_steam_appid(game)

summary: ProtonDBSummary = asyncio.run(fetch_protondb_summary(appid))
tier: ProtonDBTier = asyncio.run(fetch_protondb_tier(appid))

tiers: dict[str, ProtonDBTier | None] = asyncio.run(fetch_protondb_tiers(launcher.get_game_list()))

print(summary.tier.value)
print(tier.value)
```
