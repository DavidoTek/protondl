from typing import Any

import pytest

from protondl.core.config import RequestConfig
from protondl.core.models import Arch, ReleaseData, ReleaseVersion
from protondl.installers.dxvk import DXVKInstaller
from protondl.installers.ge_proton import GEProtonInstaller
from protondl.util.download import fetch_project_release_data, fetch_project_releases

RELEASE_URL = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"


class FakeResponse:
    def __init__(self, data: Any) -> None:
        self._data = data

    def json(self) -> Any:
        return self._data

    def raise_for_status(self) -> None:
        pass


class FakeClient:
    def __init__(self, data: Any) -> None:
        self._data = data

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def get(self, url: str, params: dict[str, Any] | None = None) -> FakeResponse:
        return FakeResponse(self._data)


def _fake_async_client(monkeypatch: pytest.MonkeyPatch, data: Any) -> None:
    def make_client(*args: Any, **kwargs: Any) -> FakeClient:
        return FakeClient(data)

    monkeypatch.setattr("protondl.util.download.httpx.AsyncClient", make_client)


class ParamsCapturingClient(FakeClient):
    def __init__(self, data: Any) -> None:
        super().__init__(data)
        self.params: dict[str, Any] | None = None

    async def get(self, url: str, params: dict[str, Any] | None = None) -> FakeResponse:
        self.params = params
        return FakeResponse(self._data)


def _fake_async_client_capturing(
    monkeypatch: pytest.MonkeyPatch, data: Any
) -> ParamsCapturingClient:
    client = ParamsCapturingClient(data)

    def make_client(*args: Any, **kwargs: Any) -> ParamsCapturingClient:
        return client

    monkeypatch.setattr("protondl.util.download.httpx.AsyncClient", make_client)
    return client


GE_PROTON_RELEASE = {
    "tag_name": "GE-Proton11-3",
    "published_at": "2026-08-03T12:00:00Z",
    "assets": [
        {
            "name": "GE-Proton11-3.tar.gz",
            "size": 100,
            "browser_download_url": "https://example.com/GE-Proton11-3.tar.gz",
        },
        {
            "name": "GE-Proton11-3.sha512sum",
            "size": 10,
            "browser_download_url": "https://example.com/GE-Proton11-3.sha512sum",
        },
        {
            "name": "GE-Proton11-3-aarch64.tar.gz",
            "size": 200,
            "browser_download_url": "https://example.com/GE-Proton11-3-aarch64.tar.gz",
        },
        {
            "name": "GE-Proton11-3-aarch64.sha512sum",
            "size": 20,
            "browser_download_url": "https://example.com/GE-Proton11-3-aarch64.sha512sum",
        },
    ],
}


def test_fetch_project_releases_returns_archs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(
        monkeypatch,
        [
            {
                "tag_name": "GE-Proton11-3",
                "published_at": "2026-08-03T12:00:00Z",
                "assets": GE_PROTON_RELEASE["assets"],
            },
            {
                "tag_name": "GE-Proton11-2",
                "published_at": "2026-07-01T12:00:00Z",
                "assets": [{"name": "GE-Proton11-2.tar.gz"}],
            },
        ],
    )

    installer = GEProtonInstaller()
    releases = asyncio_run(
        fetch_project_releases(
            RELEASE_URL,
            RequestConfig(),
            release_archs=installer._release_archs_from_assets,
        )
    )

    assert releases == [
        ReleaseVersion("GE-Proton11-3", (Arch.X86_64, Arch.AARCH64)),
        ReleaseVersion("GE-Proton11-2", (Arch.X86_64,)),
    ]


def test_fetch_project_releases_default_archs(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(
        monkeypatch,
        [{"tag_name": "GE-Proton11-3", "assets": GE_PROTON_RELEASE["assets"]}],
    )

    releases = asyncio_run(fetch_project_releases(RELEASE_URL, RequestConfig()))

    assert releases == [ReleaseVersion("GE-Proton11-3", (Arch.X86_64,))]


def test_fetch_project_release_data_selects_x86_64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, GE_PROTON_RELEASE)

    installer = GEProtonInstaller()
    release_data = asyncio_run(
        fetch_project_release_data(
            RELEASE_URL,
            installer.release_format,
            RequestConfig(),
            tag="GE-Proton11-3",
            checksum_suffix=installer.checksum_suffix,
            asset_condition=lambda asset: installer._asset_matches_arch(
                asset["name"], Arch.X86_64, installer.release_format
            ),
            checksum_condition=lambda asset: installer._asset_matches_arch(
                asset["name"], Arch.X86_64, installer.checksum_suffix
            ),
        )
    )

    assert release_data == ReleaseData(
        version="GE-Proton11-3",
        date="2026-08-03",
        download="https://example.com/GE-Proton11-3.tar.gz",
        size=100,
        checksum="https://example.com/GE-Proton11-3.sha512sum",
        original_filename="GE-Proton11-3.tar.gz",
    )


def test_fetch_project_release_data_selects_aarch64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, GE_PROTON_RELEASE)

    installer = GEProtonInstaller()
    release_data = asyncio_run(
        fetch_project_release_data(
            RELEASE_URL,
            installer.release_format,
            RequestConfig(),
            tag="GE-Proton11-3",
            checksum_suffix=installer.checksum_suffix,
            asset_condition=lambda asset: installer._asset_matches_arch(
                asset["name"], Arch.AARCH64, installer.release_format
            ),
            checksum_condition=lambda asset: installer._asset_matches_arch(
                asset["name"], Arch.AARCH64, installer.checksum_suffix
            ),
        )
    )

    assert release_data == ReleaseData(
        version="GE-Proton11-3",
        date="2026-08-03",
        download="https://example.com/GE-Proton11-3-aarch64.tar.gz",
        size=200,
        checksum="https://example.com/GE-Proton11-3-aarch64.sha512sum",
        original_filename="GE-Proton11-3-aarch64.tar.gz",
    )


DXVK_RELEASE = {
    "tag_name": "v3.0.2",
    "published_at": "2026-08-01T12:00:00Z",
    "assets": [
        {
            "name": "dxvk-3.0.2.tar.gz",
            "size": 100,
            "browser_download_url": "https://example.com/dxvk-3.0.2.tar.gz",
        },
        {
            "name": "dxvk-native-3.0.2-steamrt-sniper.tar.gz",
            "size": 200,
            "browser_download_url": ("https://example.com/dxvk-native-3.0.2-steamrt-sniper.tar.gz"),
        },
    ],
}


def test_fetch_project_release_data_selects_non_native_with_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, DXVK_RELEASE)

    release_data = asyncio_run(
        fetch_project_release_data(
            "https://api.github.com/repos/doitsujin/dxvk/releases",
            ".tar.gz",
            RequestConfig(),
            tag="v3.0.2",
            asset_priority=lambda asset: 0 if "native" in asset["name"] else 1,
        )
    )

    assert release_data.download == "https://example.com/dxvk-3.0.2.tar.gz"
    assert release_data.original_filename == "dxvk-3.0.2.tar.gz"


def test_fetch_project_release_data_last_match_wins_without_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, DXVK_RELEASE)

    release_data = asyncio_run(
        fetch_project_release_data(
            "https://api.github.com/repos/doitsujin/dxvk/releases",
            ".tar.gz",
            RequestConfig(),
            tag="v3.0.2",
        )
    )

    assert release_data.download == ("https://example.com/dxvk-native-3.0.2-steamrt-sniper.tar.gz")


def test_fetch_project_release_data_last_match_wins_when_priorities_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, DXVK_RELEASE)

    release_data = asyncio_run(
        fetch_project_release_data(
            "https://api.github.com/repos/doitsujin/dxvk/releases",
            ".tar.gz",
            RequestConfig(),
            tag="v3.0.2",
            asset_priority=lambda asset: 0,
        )
    )

    assert release_data.download == ("https://example.com/dxvk-native-3.0.2-steamrt-sniper.tar.gz")


def test_dxvk_fetch_release_data_selects_non_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_async_client(monkeypatch, DXVK_RELEASE)

    installer = DXVKInstaller()
    release_data = asyncio_run(installer._fetch_release_data("v3.0.2", Arch.X86_64))

    assert release_data.download == "https://example.com/dxvk-3.0.2.tar.gz"
    assert release_data.original_filename == "dxvk-3.0.2.tar.gz"


def test_fetch_project_release_data_missing_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(
        monkeypatch,
        {
            "tag_name": "GE-Proton11-3",
            "published_at": "2026-08-03T12:00:00Z",
            "assets": [{"name": "GE-Proton11-3.tar.gz", "browser_download_url": "url"}],
        },
    )

    installer = GEProtonInstaller()
    release_data = asyncio_run(
        fetch_project_release_data(
            RELEASE_URL,
            installer.release_format,
            RequestConfig(),
            tag="GE-Proton11-3",
            checksum_suffix=installer.checksum_suffix,
            asset_condition=lambda asset: installer._asset_matches_arch(
                asset["name"], Arch.AARCH64, installer.release_format
            ),
            checksum_condition=lambda asset: installer._asset_matches_arch(
                asset["name"], Arch.AARCH64, installer.checksum_suffix
            ),
        )
    )

    assert release_data.download is None
    assert release_data.checksum is None


LUXTORPEDA_RELEASE_URL = "https://codeberg.org/api/v1/repos/luxtorpeda/luxtorpeda/releases"

LUXTORPEDA_RELEASE = {
    "tag_name": "v77.1.0",
    "published_at": "2026-05-27T02:35:32+02:00",
    "assets": [
        {
            "name": "luxtorpeda-v77.1.0.tar.xz",
            "size": 100,
            "browser_download_url": "https://example.com/luxtorpeda-v77.1.0.tar.xz",
        },
        {
            "name": "luxtorpeda-v77.1.0.tar.xz.sha512",
            "size": 10,
            "browser_download_url": "https://example.com/luxtorpeda-v77.1.0.tar.xz.sha512",
        },
    ],
}


def test_fetch_project_release_data_gitea_codeberg(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, LUXTORPEDA_RELEASE)

    release_data = asyncio_run(
        fetch_project_release_data(
            LUXTORPEDA_RELEASE_URL,
            ".tar.xz",
            RequestConfig(),
            tag="v77.1.0",
            checksum_suffix=".sha512",
        )
    )

    assert release_data == ReleaseData(
        version="v77.1.0",
        date="2026-05-27",
        download="https://example.com/luxtorpeda-v77.1.0.tar.xz",
        size=100,
        checksum="https://example.com/luxtorpeda-v77.1.0.tar.xz.sha512",
        original_filename="luxtorpeda-v77.1.0.tar.xz",
    )


DWPROTON_RELEASE_URL = "https://dawn.wine/api/v1/repos/dawn-winery/dwproton/releases"

DWPROTON_RELEASE = {
    "tag_name": "dwproton-11.0-11",
    "published_at": "2026-08-07T23:32:56+01:00",
    "assets": [
        {
            "name": "dwproton-11.0-11-x86_64.sha512sum",
            "size": 20,
            "browser_download_url": "https://example.com/dwproton-11.0-11-x86_64.sha512sum",
        },
        {
            "name": "dwproton-11.0-11-x86_64.tar.xz",
            "size": 200,
            "browser_download_url": "https://example.com/dwproton-11.0-11-x86_64.tar.xz",
        },
        {
            "name": "dwproton-11.0-11-x86_64.tar.xz.torrent",
            "size": 30,
            "browser_download_url": "https://example.com/dwproton-11.0-11-x86_64.tar.xz.torrent",
        },
    ],
}


def test_fetch_project_release_data_gitea_dawnwine(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_async_client(monkeypatch, DWPROTON_RELEASE)

    release_data = asyncio_run(
        fetch_project_release_data(
            DWPROTON_RELEASE_URL,
            ".tar.xz",
            RequestConfig(),
            tag="dwproton-11.0-11",
            checksum_suffix=".sha512sum",
        )
    )

    assert release_data == ReleaseData(
        version="dwproton-11.0-11",
        date="2026-08-07",
        download="https://example.com/dwproton-11.0-11-x86_64.tar.xz",
        size=200,
        checksum="https://example.com/dwproton-11.0-11-x86_64.sha512sum",
        original_filename="dwproton-11.0-11-x86_64.tar.xz",
    )


def test_fetch_project_releases_gitea_uses_limit_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _fake_async_client_capturing(
        monkeypatch,
        [
            {"tag_name": "v77.1.0", "assets": LUXTORPEDA_RELEASE["assets"]},
            {"tag_name": "v77.0.0", "assets": LUXTORPEDA_RELEASE["assets"]},
        ],
    )

    releases = asyncio_run(fetch_project_releases(LUXTORPEDA_RELEASE_URL, RequestConfig()))

    assert client.params == {"limit": 100, "page": 1}
    assert releases == [
        ReleaseVersion("v77.1.0", (Arch.X86_64,)),
        ReleaseVersion("v77.0.0", (Arch.X86_64,)),
    ]


def asyncio_run(coro: Any) -> Any:
    import asyncio

    return asyncio.run(coro)
