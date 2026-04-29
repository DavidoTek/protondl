import asyncio

import pytest

from protondl.services.awacy import (
    AWACY_GAME_LIST_URL,
    AWACYIndex,
    AWACYStatus,
    fetch_awacy_index,
    get_awacy_status_by_id,
    get_awacy_status_by_slug,
)


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.requested_url: str | None = None
        self.requested_timeout: float | None = None

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get(self, url: str, timeout: float) -> _FakeResponse:
        self.requested_url = url
        self.requested_timeout = timeout
        return _FakeResponse(self._payload)


def test_fetch_awacy_index_builds_lookup_index(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "slug": "game-one",
            "status": "Supported",
            "storeIds": {"steam": "12345"},
        },
        {
            "slug": "game-two",
            "status": "Broken",
            "storeIds": {"epic": {"namespace": "epic-namespace", "slug": "epic-game-two"}},
        },
    ]
    fake_client = _FakeAsyncClient(payload)

    monkeypatch.setattr("protondl.services.awacy.httpx.AsyncClient", lambda: fake_client)

    index = asyncio.run(fetch_awacy_index())

    assert fake_client.requested_url == AWACY_GAME_LIST_URL
    assert fake_client.requested_timeout == 10.0
    assert index.by_store_id["12345"]["status"] is AWACYStatus.SUPPORTED
    assert index.by_slug["game-one"]["status"] is AWACYStatus.SUPPORTED
    assert index.by_slug["epic-game-two"]["status"] is AWACYStatus.BROKEN
    assert index.by_store_id["epic-namespace"]["slug"] == "game-two"


def test_fetch_awacy_index_raises_value_error_for_non_list_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeAsyncClient({"status": "ok"})

    monkeypatch.setattr("protondl.services.awacy.httpx.AsyncClient", lambda: fake_client)

    with pytest.raises(ValueError, match="AWACY payload is not a list of games"):
        asyncio.run(fetch_awacy_index())


@pytest.mark.parametrize(
    ("game_id", "expected_status"),
    [("12345", AWACYStatus.SUPPORTED), ("missing", AWACYStatus.UNKNOWN)],
)
def test_get_awacy_status_by_id(
    game_id: str,
    expected_status: AWACYStatus,
) -> None:
    index = AWACYIndex(
        by_slug={},
        by_store_id={"12345": {"status": AWACYStatus.SUPPORTED}},  # type: ignore
    )

    assert get_awacy_status_by_id(game_id, index) is expected_status


@pytest.mark.parametrize(
    ("slug", "expected_status"),
    [("game-one", AWACYStatus.RUNNING), ("missing", AWACYStatus.UNKNOWN)],
)
def test_get_awacy_status_by_slug(
    slug: str,
    expected_status: AWACYStatus,
) -> None:
    index = AWACYIndex(
        by_slug={"game-one": {"status": AWACYStatus.RUNNING}},  # type: ignore
        by_store_id={},
    )

    assert get_awacy_status_by_slug(slug, index) is expected_status
