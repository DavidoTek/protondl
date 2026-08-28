import errno
from pathlib import Path
from typing import Any

import httpx
import pytest

from protondl.core.errors import (
    AlreadyInstalledError,
    APIRateLimitError,
    ArchiveExtractionError,
    ChecksumMismatchError,
    DownloadError,
    InstallCancelledError,
    LinkNotFoundError,
    NoDiskSpaceError,
    NoInternetConnectionError,
    NoWritePermissionError,
    ProtondlError,
    raise_for_httpx_error,
    raise_for_os_error,
)


def test_lifecycle_errors_are_protondl_errors() -> None:
    assert issubclass(InstallCancelledError, ProtondlError)
    assert issubclass(AlreadyInstalledError, ProtondlError)
    assert issubclass(ArchiveExtractionError, ProtondlError)


def test_builtin_compatibility() -> None:
    assert issubclass(LinkNotFoundError, ValueError)
    assert issubclass(ChecksumMismatchError, ValueError)
    assert issubclass(NoWritePermissionError, PermissionError)
    assert issubclass(NoDiskSpaceError, OSError)
    for cls in (LinkNotFoundError, NoWritePermissionError, NoDiskSpaceError, ChecksumMismatchError):
        assert issubclass(cls, ProtondlError)


def test_raise_for_os_error_permission() -> None:
    exc = PermissionError(errno.EACCES, "Permission denied", "/opt/tool")
    with pytest.raises(NoWritePermissionError):
        raise_for_os_error(exc)


def test_raise_for_os_error_disk_full() -> None:
    exc = OSError(errno.ENOSPC, "No space left on device", "/opt/tool")
    with pytest.raises(NoDiskSpaceError):
        raise_for_os_error(exc)


def test_raise_for_os_error_passthrough() -> None:
    exc = FileNotFoundError(errno.ENOENT, "No such file or directory", "/opt/tool")
    with pytest.raises(FileNotFoundError):
        raise_for_os_error(exc)


def test_raise_for_httpx_error_connection() -> None:
    with pytest.raises(NoInternetConnectionError):
        raise_for_httpx_error(httpx.ConnectError("nope"))
    with pytest.raises(NoInternetConnectionError):
        raise_for_httpx_error(httpx.ConnectTimeout("nope"))


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com/x")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


def test_raise_for_httpx_error_status_codes() -> None:
    with pytest.raises(LinkNotFoundError):
        raise_for_httpx_error(_status_error(404))
    with pytest.raises(APIRateLimitError):
        raise_for_httpx_error(_status_error(429))
    with pytest.raises(APIRateLimitError):
        raise_for_httpx_error(_status_error(403))
    with pytest.raises(DownloadError):
        raise_for_httpx_error(_status_error(500))


def test_download_file_translates_connection_error() -> None:
    from protondl.util.download import download_file

    class _FailingClient:
        def stream(self, *args: Any, **kwargs: Any) -> "_FailingClient":
            return self

        async def __aenter__(self) -> "_FailingClient":
            raise httpx.ConnectError("no route to host")

        async def __aexit__(self, *args: Any) -> bool:
            return False

    import asyncio

    client: Any = _FailingClient()
    with pytest.raises(NoInternetConnectionError):
        asyncio.run(download_file("https://example.com/f", Path("/tmp/x"), client))


def test_extract_tar_translates_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tarfile

    from protondl.util import archive

    archive_file = tmp_path / "a.tar"
    with tarfile.open(archive_file, "w") as tf:
        member = tarfile.TarInfo("file.txt")
        data = b"x"
        member.size = len(data)
        from io import BytesIO

        tf.addfile(member, BytesIO(data))

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise PermissionError(errno.EACCES, "Permission denied", str(tmp_path))

    monkeypatch.setattr(tarfile.TarFile, "extract", _boom)

    with pytest.raises(NoWritePermissionError):
        archive.extract_tar(archive_file, tmp_path / "out")
