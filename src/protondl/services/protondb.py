import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import httpx

PROTONDB_SUMMARY_API_URL = "https://www.protondb.com/api/v1/reports/summaries/{game_id}.json"


class ProtonDBTier(Enum):
    """
    ProtonDB compatibility tiers reported for a game.

    The values are the tier names returned by the ProtonDB API.
    """

    BORKED = "borked"
    BRONZE = "bronze"
    GOLD = "gold"
    PENDING = "pending"
    PLATINUM = "platinum"
    SILVER = "silver"
    UNKNOWN = "unknown"


class SupportsProtonDBLookup(Protocol):
    """Objects that can be resolved to a Steam AppID for ProtonDB lookups."""

    id: str


_PROTONDB_TIER_LOOKUP: dict[str, ProtonDBTier] = {}


@dataclass
class ProtonDBSummary:
    """Normalized ProtonDB summary data for a Steam AppID."""

    appid: int
    tier: ProtonDBTier
    confidence: str
    trending_tier: ProtonDBTier
    reports_count: int | None = field(default=None)
    raw: dict[str, Any] = field(default_factory=dict)


def _build_tier_lookup() -> dict[str, ProtonDBTier]:
    """
    Build the case-insensitive ProtonDB tier lookup table.

    Returns:
        dict[str, ProtonDBTier]: Mapping of lowercase tier names to enum values.
    """
    return {tier.value.lower(): tier for tier in ProtonDBTier}


def resolve_steam_appid(target: SupportsProtonDBLookup | int | str) -> int:
    """
    Resolve a ProtonDB lookup target to a Steam AppID.

    Args:
        target (SupportsProtonDBLookup | int | str): Steam AppID or object exposing `id`.

    Returns:
        int: Resolved Steam AppID.

    Raises:
        ValueError: If the target cannot be converted into an integer AppID.
    """
    if isinstance(target, int):
        return target

    if isinstance(target, str):
        return int(target)

    appid = getattr(target, "appid", None)
    if appid is not None:
        return int(appid)

    if (game_id := getattr(target, "id", None)) is not None:
        return int(game_id)

    raise ValueError(f"Cannot resolve {target!r} to a Steam AppID")


def parse_protondb_tier(tier_text: str) -> ProtonDBTier:
    """
    Convert a ProtonDB tier string into the matching enum value.

    Args:
        tier_text (str): ProtonDB tier string.

    Returns:
        ProtonDBTier: Normalized ProtonDB tier.
    """
    normalized_tier = tier_text.strip().lower()

    if not _PROTONDB_TIER_LOOKUP:
        _PROTONDB_TIER_LOOKUP.update(_build_tier_lookup())

    return _PROTONDB_TIER_LOOKUP.get(normalized_tier, ProtonDBTier.UNKNOWN)


def parse_protondb_summary(appid: int, payload: dict[str, Any]) -> ProtonDBSummary:
    """
    Normalize a ProtonDB summary payload into a dataclass.

    Args:
        appid (int): Steam AppID the payload belongs to.
        payload (dict[str, Any]): ProtonDB JSON response payload.

    Returns:
        ProtonDBSummary: Normalized ProtonDB summary.

    Raises:
        ValueError: If the payload is missing required tier fields.
    """
    tier_text = payload.get("tier", "")
    trending_tier_text = payload.get("trendingTier", "")
    confidence = payload.get("confidence", "")

    if not isinstance(tier_text, str) or not tier_text:
        raise ValueError("ProtonDB summary payload is missing a tier")
    if not isinstance(trending_tier_text, str) or not trending_tier_text:
        raise ValueError("ProtonDB summary payload is missing a trending tier")

    total = payload.get("total")
    reports_count = int(total) if total is not None else None

    return ProtonDBSummary(
        appid=appid,
        tier=parse_protondb_tier(tier_text),
        confidence=str(confidence),
        trending_tier=parse_protondb_tier(trending_tier_text),
        reports_count=reports_count,
        raw=payload,
    )


async def fetch_protondb_summary(
    target: SupportsProtonDBLookup | int | str,
    url_template: str = PROTONDB_SUMMARY_API_URL,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> ProtonDBSummary:
    """
    Fetch a ProtonDB summary for a Steam AppID.

    Args:
        target (SupportsProtonDBLookup | int | str): Steam AppID or lookup object.
        url_template (str): URL template used to query ProtonDB.
        timeout (float): Request timeout in seconds.
        client (httpx.AsyncClient | None): Optional injected HTTP client.

    Returns:
        ProtonDBSummary: Parsed ProtonDB summary response.

    Raises:
        ValueError: If ProtonDB returns an unexpected payload shape.
        httpx.HTTPError: If the request fails.
    """

    async def _fetch(active_client: httpx.AsyncClient) -> ProtonDBSummary:
        game_id = resolve_steam_appid(target)
        response = await active_client.get(url_template.format(game_id=game_id), timeout=timeout)
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, dict):
            raise ValueError("ProtonDB summary payload is not an object")
        return parse_protondb_summary(game_id, payload)

    if client is not None:
        return await _fetch(client)

    async with httpx.AsyncClient() as created_client:
        return await _fetch(created_client)


async def fetch_protondb_tier(
    target: SupportsProtonDBLookup | int | str,
    url_template: str = PROTONDB_SUMMARY_API_URL,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> ProtonDBTier:
    """
    Fetch only the normalized ProtonDB tier for a Steam AppID.

    Args:
        target (SupportsProtonDBLookup | int | str): Steam AppID or lookup object.
        url_template (str): URL template used to query ProtonDB.
        timeout (float): Request timeout in seconds.
        client (httpx.AsyncClient | None): Optional injected HTTP client.

    Returns:
        ProtonDBTier: Parsed ProtonDB tier.
    """
    summary = await fetch_protondb_summary(target, url_template, timeout, client)
    return summary.tier


async def fetch_protondb_tiers(
    targets: Iterable[SupportsProtonDBLookup | int | str],
    url_template: str = PROTONDB_SUMMARY_API_URL,
    timeout: float = 10.0,
    max_concurrency: int = 10,
    client: httpx.AsyncClient | None = None,
) -> dict[str, ProtonDBTier | None]:
    """
    Fetch ProtonDB tiers for multiple targets in parallel.

    Targets that cannot be resolved to a Steam AppID are skipped. Targets
    without a ProtonDB report (HTTP 404) are mapped to `ProtonDBTier.UNKNOWN`.
    Targets whose lookup fails for any other reason (network errors, malformed
    responses) are mapped to `None` so callers can distinguish them from a
    missing report.

    Lookups are bounded to `max_concurrency` simultaneous requests so that
    libraries with hundreds or thousands of games do not flood the ProtonDB
    API.

    Args:
        targets (Iterable[SupportsProtonDBLookup | int | str]): Lookup targets.
        url_template (str): URL template used to query ProtonDB.
        timeout (float): Request timeout in seconds.
        max_concurrency (int): Maximum number of simultaneous lookups.
        client (httpx.AsyncClient | None): Optional injected HTTP client.

    Returns:
        dict[str, ProtonDBTier | None]: Mapping of Steam AppID strings to
            ProtonDB tiers, or `None` if the lookup failed.
    """

    async def _run(active_client: httpx.AsyncClient) -> dict[str, ProtonDBTier | None]:
        resolved_targets: list[tuple[str, SupportsProtonDBLookup | int | str]] = []
        for target in targets:
            try:
                appid = resolve_steam_appid(target)
            except ValueError:
                continue
            resolved_targets.append((str(appid), target))

        semaphore = asyncio.Semaphore(max_concurrency)

        async def _limited(target: SupportsProtonDBLookup | int | str) -> ProtonDBTier | None:
            async with semaphore:
                return await _fetch_tier_safe(target, url_template, timeout, active_client)

        results = await asyncio.gather(*(_limited(target) for _, target in resolved_targets))
        return dict(zip((appid for appid, _ in resolved_targets), results, strict=True))

    if client is not None:
        return await _run(client)

    async with httpx.AsyncClient() as created_client:
        return await _run(created_client)


async def _fetch_tier_safe(
    target: SupportsProtonDBLookup | int | str,
    url_template: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> ProtonDBTier | None:
    """
    Fetch a single ProtonDB tier, reporting lookup failures.

    Returns `ProtonDBTier.UNKNOWN` for AppIDs without a report (HTTP 404) and
    `None` for any other lookup failure (network errors, malformed responses).

    Args:
        target (SupportsProtonDBLookup | int | str): Lookup target.
        url_template (str): URL template used to query ProtonDB.
        timeout (float): Request timeout in seconds.
        client (httpx.AsyncClient): HTTP client to use.

    Returns:
        ProtonDBTier | None: ProtonDB tier, UNKNOWN if there is no report,
            or None if the lookup failed.
    """
    try:
        return await fetch_protondb_tier(target, url_template, timeout, client)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return ProtonDBTier.UNKNOWN
        return None
    except (httpx.HTTPError, ValueError):
        return None
