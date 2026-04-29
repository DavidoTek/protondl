from dataclasses import dataclass
from enum import Enum
from typing import Any, TypedDict

import httpx

AWACY_GAME_LIST_URL = (
    "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/master/games.json"
)


class AWACYStatus(Enum):
    """
    Status values from areweanticheatyet.com.

    The values represent the anti-cheat support state for a game on Linux.
    """

    BROKEN = "Broken"
    DENIED = "Denied"
    PLANNED = "Planned"
    RUNNING = "Running"
    SUPPORTED = "Supported"
    UNKNOWN = "Unknown"


class AWACYGameEntry(TypedDict):
    """Single game entry from the AWACY games list."""

    url: str
    name: str
    logo: str
    native: bool
    status: AWACYStatus
    reference: str
    anticheats: list[str]
    notes: list[list[str]]
    storeIds: dict[str, str | dict[str, str]]
    slug: str
    dateChanged: str


@dataclass
class AWACYIndex:
    """
    Lookup index for AWACY game status data.

    Provides maps keyed by normalized game name and Steam AppID.
    """

    by_slug: dict[str, AWACYGameEntry]
    by_store_id: dict[str, AWACYGameEntry]


def _build_awacy_index(payload: list[AWACYGameEntry]) -> AWACYIndex:
    """
    Build lookup maps from AWACY JSON payload data.

    Args:
        payload (list[AWACYGameEntry]): Parsed games list from AWACY.

    Returns:
        AWACYIndex: Lookup index keyed by normalized game name and AppID.
    """
    by_slug: dict[str, AWACYGameEntry] = {}
    by_store_id: dict[str, AWACYGameEntry] = {}

    for item in payload:
        if isinstance(item.get("status"), str):
            if item["status"] in AWACYStatus._value2member_map_:
                item["status"] = AWACYStatus(item["status"])
            else:
                item["status"] = AWACYStatus.UNKNOWN

        if "slug" in item:
            by_slug[item["slug"]] = item

        if store_ids := item.get("storeIds"):
            if steam_id := store_ids.get("steam"):
                if not isinstance(steam_id, str):
                    continue
                by_store_id[steam_id] = item
            if epic_id := store_ids.get("epic"):
                if not isinstance(epic_id, dict):
                    continue
                if epic_namespace := epic_id.get("namespace"):
                    by_store_id[epic_namespace] = item
                if epic_slug := epic_id.get("slug"):
                    by_slug[epic_slug] = item

    return AWACYIndex(by_slug=by_slug, by_store_id=by_store_id)


async def fetch_awacy_index(
    url: str = AWACY_GAME_LIST_URL,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> AWACYIndex:
    """
    Fetch anti-cheat compatibility status data from AWACY.

    Args:
        url (str): AWACY JSON endpoint.
        timeout (float): Request timeout in seconds.
        client (httpx.AsyncClient | None): Optional injected client.

    Returns:
        AWACYIndex: AWACY lookup index.

    Raises:
        ValueError: If the JSON payload is not a list.
        httpx.HTTPError: If the request fails.
    """

    async def _fetch(active_client: httpx.AsyncClient) -> AWACYIndex:
        response = await active_client.get(url, timeout=timeout)
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, list):
            raise ValueError("AWACY payload is not a list of games")
        return _build_awacy_index(payload)

    if client is not None:
        return await _fetch(client)

    async with httpx.AsyncClient() as created_client:
        return await _fetch(created_client)


def get_awacy_status_by_id(
    game_id: str,
    index: AWACYIndex,
) -> AWACYStatus:
    """
    Get AWACY status for a game by its ID.

    Args:
        game_id (str): Game ID.
        index (AWACYIndex): Pre-built AWACY lookup index.

    Returns:
        AWACYStatus: The anti-cheat support status for the game, or UNKNOWN if not found.
    """
    entry = index.by_store_id.get(game_id)
    if entry:
        return entry["status"]

    return AWACYStatus.UNKNOWN


def get_awacy_status_by_slug(
    slug: str,
    index: AWACYIndex,
) -> AWACYStatus:
    """
    Get AWACY status for a game by its slug.

    Args:
        slug (str): Game slug.
        index (AWACYIndex): Pre-built AWACY lookup index.

    Returns:
        AWACYStatus: The anti-cheat support status for the game, or UNKNOWN if not found.
    """
    entry = index.by_slug.get(slug)
    if entry:
        return entry["status"]

    return AWACYStatus.UNKNOWN
