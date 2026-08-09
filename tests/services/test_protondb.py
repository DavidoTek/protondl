import asyncio
from dataclasses import dataclass

import httpx
import pytest

from protondl.services.protondb import (
    ProtonDBSummary,
    ProtonDBTier,
    fetch_protondb_summary,
    fetch_protondb_tier,
    fetch_protondb_tiers,
    parse_protondb_summary,
    parse_protondb_tier,
    resolve_steam_appid,
)


@dataclass
class _DummyGame:
    id: str
    appid: int | None = None


@pytest.mark.parametrize(
    ("target", "expected_appid"),
    [
        (42, 42),
        ("43", 43),
        (_DummyGame(id="44", appid=45), 45),
        (_DummyGame(id="46"), 46),
    ],
)
def test_resolve_steam_appid(
    target: _DummyGame | int | str,
    expected_appid: int,
) -> None:
    assert resolve_steam_appid(target) == expected_appid


@pytest.mark.parametrize(
    "target",
    ["not-an-appid", _DummyGame(id="not-an-appid"), 12.5],
)
def test_resolve_steam_appid_raises_for_unresolvable_target(target: object) -> None:
    with pytest.raises(ValueError):
        resolve_steam_appid(target)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("tier_text", "expected_tier"),
    [
        ("platinum", ProtonDBTier.PLATINUM),
        ("GOLD", ProtonDBTier.GOLD),
        (" Silver ", ProtonDBTier.SILVER),
        ("bronze", ProtonDBTier.BRONZE),
        ("borked", ProtonDBTier.BORKED),
        ("pending", ProtonDBTier.PENDING),
        ("unknown", ProtonDBTier.UNKNOWN),
        ("does-not-exist", ProtonDBTier.UNKNOWN),
    ],
)
def test_parse_protondb_tier(tier_text: str, expected_tier: ProtonDBTier) -> None:
    assert parse_protondb_tier(tier_text) is expected_tier


def test_parse_protondb_summary() -> None:
    payload = {
        "bestReportedTier": "platinum",
        "confidence": "strong",
        "score": 0.82,
        "tier": "gold",
        "total": 1678,
        "trendingTier": "platinum",
    }

    summary = parse_protondb_summary(123, payload)

    assert summary.appid == 123
    assert summary.tier is ProtonDBTier.GOLD
    assert summary.trending_tier is ProtonDBTier.PLATINUM
    assert summary.confidence == "strong"
    assert summary.reports_count == 1678
    assert summary.raw == payload


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"tier": "gold"},
        {"trendingTier": "platinum"},
        {"tier": "", "trendingTier": ""},
    ],
)
def test_parse_protondb_summary_raises_for_missing_tier_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="ProtonDB summary payload is missing a"):
        parse_protondb_summary(123, payload)


def _make_mock_client(payload_by_path: dict[str, object]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = payload_by_path.get(request.url.path)
        if payload is None:
            return httpx.Response(404, request=request)
        return httpx.Response(200, json=payload, request=request)

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="https://www.protondb.com")


def test_fetch_protondb_summary_and_tier_from_mocked_http() -> None:
    payload = {
        "bestReportedTier": "platinum",
        "confidence": "strong",
        "score": 0.82,
        "tier": "gold",
        "total": 1678,
        "trendingTier": "platinum",
    }

    async def _run() -> tuple[ProtonDBSummary, ProtonDBTier]:
        async with _make_mock_client({"/api/v1/reports/summaries/123.json": payload}) as client:
            summary = await fetch_protondb_summary(123, client=client)
            tier = await fetch_protondb_tier("123", client=client)
        return summary, tier

    summary, tier = asyncio.run(_run())

    assert summary.tier is ProtonDBTier.GOLD
    assert summary.trending_tier is ProtonDBTier.PLATINUM
    assert summary.confidence == "strong"
    assert tier is ProtonDBTier.GOLD


def test_fetch_protondb_summary_raises_for_unknown_appid() -> None:
    async def _run() -> None:
        async with _make_mock_client({}) as client:
            await fetch_protondb_summary(999999, client=client)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(_run())


def test_fetch_protondb_summary_raises_for_non_object_payload() -> None:
    async def _run() -> None:
        async with _make_mock_client({"/api/v1/reports/summaries/123.json": ["gold"]}) as client:
            await fetch_protondb_summary(123, client=client)

    with pytest.raises(ValueError, match="ProtonDB summary payload is not an object"):
        asyncio.run(_run())


def test_fetch_protondb_tiers_maps_failures_to_unknown() -> None:
    payload = {
        "bestReportedTier": "platinum",
        "confidence": "strong",
        "score": 0.82,
        "tier": "gold",
        "total": 1678,
        "trendingTier": "platinum",
    }

    async def _run() -> dict[str, ProtonDBTier | None]:
        async with _make_mock_client(
            {
                "/api/v1/reports/summaries/123.json": payload,
                "/api/v1/reports/summaries/999999.json": None,
            }
        ) as client:
            return await fetch_protondb_tiers(
                [123, 999999, _DummyGame(id="not-an-appid")],
                client=client,
            )

    tiers = asyncio.run(_run())

    assert tiers == {"123": ProtonDBTier.GOLD, "999999": ProtonDBTier.UNKNOWN}


def test_fetch_protondb_tiers_maps_network_errors_to_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/999999.json"):
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(404, request=request)

    async def _run() -> dict[str, ProtonDBTier | None]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://www.protondb.com",
        ) as client:
            return await fetch_protondb_tiers([123, 999999], client=client)

    tiers = asyncio.run(_run())

    assert tiers == {"123": ProtonDBTier.UNKNOWN, "999999": None}


def test_fetch_protondb_tiers_maps_server_errors_to_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    async def _run() -> dict[str, ProtonDBTier | None]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://www.protondb.com",
        ) as client:
            return await fetch_protondb_tiers([123], client=client)

    tiers = asyncio.run(_run())

    assert tiers == {"123": None}


def test_fetch_protondb_tiers_respects_max_concurrency() -> None:
    active = 0
    max_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        try:
            await asyncio.sleep(0.05)
        finally:
            active -= 1
        return httpx.Response(404, request=request)

    async def _run() -> dict[str, ProtonDBTier | None]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://www.protondb.com",
        ) as client:
            return await fetch_protondb_tiers(
                list(range(1, 21)),
                client=client,
                max_concurrency=4,
            )

    tiers = asyncio.run(_run())

    assert max_active <= 4
    assert tiers == {str(i): ProtonDBTier.UNKNOWN for i in range(1, 21)}
