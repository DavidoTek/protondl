from typing import Any

import pytest

from protondl.core.models import Arch, ReleaseData, ReleaseVersion, RequestConfig
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


def asyncio_run(coro: Any) -> Any:
    import asyncio

    return asyncio.run(coro)
