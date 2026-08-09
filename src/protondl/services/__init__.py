"""Public service clients for external online APIs."""

from protondl.services.awacy import (
    AWACYGameEntry,
    AWACYIndex,
    AWACYStatus,
    fetch_awacy_index,
    get_awacy_status_by_id,
    get_awacy_status_by_slug,
)
from protondl.services.protondb import (
    PROTONDB_SUMMARY_API_URL,
    ProtonDBSummary,
    ProtonDBTier,
    SupportsProtonDBLookup,
    fetch_protondb_summary,
    fetch_protondb_tier,
    fetch_protondb_tiers,
    parse_protondb_summary,
    parse_protondb_tier,
    resolve_steam_appid,
)

__all__ = [
    "AWACYGameEntry",
    "AWACYStatus",
    "AWACYIndex",
    "fetch_awacy_index",
    "get_awacy_status_by_id",
    "get_awacy_status_by_slug",
    "PROTONDB_SUMMARY_API_URL",
    "ProtonDBSummary",
    "ProtonDBTier",
    "SupportsProtonDBLookup",
    "fetch_protondb_summary",
    "fetch_protondb_tier",
    "fetch_protondb_tiers",
    "parse_protondb_summary",
    "parse_protondb_tier",
    "resolve_steam_appid",
]
