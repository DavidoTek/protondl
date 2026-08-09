import httpx
import pytest
from typer.testing import CliRunner

from protondl.cli import app
from protondl.services.protondb import ProtonDBTier

runner = CliRunner()


def test_get_protondb_status(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_protondb_tier(target: str) -> ProtonDBTier:
        return ProtonDBTier.GOLD

    monkeypatch.setattr(
        "protondl.cli.services.fetch_protondb_tier",
        fake_fetch_protondb_tier,
    )

    result = runner.invoke(app, ["get-protondb-status", "221380"])

    assert result.exit_code == 0
    assert "ProtonDB status of 221380 is Gold" in result.stdout


def test_get_protondb_status_fetch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_protondb_tier(target: str) -> ProtonDBTier:
        request = httpx.Request("GET", target)
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("500 Internal Server Error", request=request, response=response)

    monkeypatch.setattr(
        "protondl.cli.services.fetch_protondb_tier",
        fake_fetch_protondb_tier,
    )

    result = runner.invoke(app, ["get-protondb-status", "221380"])

    assert result.exit_code == 1
    assert "Failed to fetch ProtonDB data" in result.stdout


def test_get_protondb_status_no_report(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_protondb_tier(target: str) -> ProtonDBTier:
        request = httpx.Request("GET", target)
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("404 Not Found", request=request, response=response)

    monkeypatch.setattr(
        "protondl.cli.services.fetch_protondb_tier",
        fake_fetch_protondb_tier,
    )

    result = runner.invoke(app, ["get-protondb-status", "221380"])

    assert result.exit_code == 0
    assert "ProtonDB status of 221380 is Unknown" in result.stdout


def test_get_protondb_status_invalid_appid(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_protondb_tier(target: str) -> ProtonDBTier:
        raise AssertionError("must not be called for an invalid AppID")

    monkeypatch.setattr(
        "protondl.cli.services.fetch_protondb_tier",
        fake_fetch_protondb_tier,
    )

    result = runner.invoke(app, ["get-protondb-status", "abc"])

    assert result.exit_code == 1
    assert "Invalid Steam AppID: abc" in result.stdout
