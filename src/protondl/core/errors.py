"""
Exception hierarchy for protondl.

Every error protondl raises on purpose derives from :class:`ProtondlError`, so a
caller can catch that one base class to handle "anything protondl did wrong".
More specific subclasses let callers (CLIs, GUIs) react to individual failure
modes - no internet, a missing release, a hit rate limit, a read-only or full
disk - without inspecting error messages.

Several subclasses also inherit from the matching built-in exception
(``ValueError``, ``PermissionError``, ``OSError``) so that code written against
the standard library keeps working.
"""

from __future__ import annotations

import errno
from typing import TYPE_CHECKING, NoReturn

import httpx

if TYPE_CHECKING:
    from protondl.core.models import Arch


class ProtondlError(Exception):
    """Base class for all errors raised on purpose by protondl."""


# ---------------------------------------------------------------------------
# Operation lifecycle errors
# ---------------------------------------------------------------------------


class InstallCancelledError(ProtondlError):
    """
    Raised when a compatibility tool install or update was cancelled.

    Cancellation is requested through a CancelToken passed to
    CtInstaller.install() or update_compatibility_tools(). Partially
    downloaded and extracted files are cleaned up before this is raised.
    """

    def __init__(self, message: str = "The operation was cancelled.") -> None:
        super().__init__(message)


class AlreadyInstalledError(ProtondlError):
    """
    Raised when a compatibility tool version is already installed.

    The requested version and architecture are already installed for the
    launcher. Use the force option of install() to re-install the tool.

    Attributes:
        tool_name (str): The name of the compatibility tool.
        version (str): The already installed version.
        arch (Arch): The already installed architecture.
    """

    def __init__(self, tool_name: str, version: str, arch: Arch) -> None:
        self.tool_name = tool_name
        self.version = version
        self.arch = arch
        super().__init__(f"{tool_name} {version} ({arch.value}) is already installed.")


# ---------------------------------------------------------------------------
# Network / remote API errors
# ---------------------------------------------------------------------------


class NetworkError(ProtondlError):
    """Base class for failures while talking to a remote host or API."""


class NoInternetConnectionError(NetworkError):
    """
    Raised when a remote host cannot be reached.

    Covers a missing internet connection, DNS failures and connection/read
    timeouts.
    """

    def __init__(
        self,
        message: str = "No internet connection or the remote host is unreachable.",
    ) -> None:
        super().__init__(message)


class LinkNotFoundError(NetworkError, ValueError):
    """
    Raised when a requested release, tag, asset or download URL does not exist.

    Typically the result of an HTTP 404 response from a release API or download
    mirror. Also a :class:`ValueError` for backwards compatibility.
    """


class APIRateLimitError(NetworkError):
    """
    Raised when the GitHub or GitLab API rate limit has been exceeded.

    Pass a ``GITHUB_TOKEN`` / ``GITLAB_TOKEN`` (see
    :class:`protondl.core.config.RequestConfig`) to raise the limits.
    """


class DownloadError(NetworkError):
    """
    Raised when a download or API request fails for a reason other than
    connectivity, a missing link, or a rate limit (for example an HTTP 5xx
    response or a malformed response body).
    """


# ---------------------------------------------------------------------------
# Local filesystem errors
# ---------------------------------------------------------------------------


class FileSystemError(ProtondlError):
    """Base class for local filesystem failures during install/update/remove."""


class NoWritePermissionError(FileSystemError, PermissionError):
    """
    Raised when protondl lacks permission to write to a target directory or
    file (for example the launcher's compatibility tools directory).

    Also a :class:`PermissionError` for backwards compatibility.
    """


class NoDiskSpaceError(FileSystemError, OSError):
    """
    Raised when a write fails because the filesystem is full (``ENOSPC``).

    Also an :class:`OSError` for backwards compatibility.
    """


# ---------------------------------------------------------------------------
# Content / integrity errors
# ---------------------------------------------------------------------------


class ChecksumMismatchError(ProtondlError, ValueError):
    """
    Raised when a downloaded file's checksum does not match the value published
    alongside the release. The partially downloaded file is removed before this
    is raised. Also a :class:`ValueError` for backwards compatibility.
    """


class ArchiveExtractionError(ProtondlError):
    """Raised when a downloaded archive cannot be read or extracted."""


# ---------------------------------------------------------------------------
# Translation helpers
# ---------------------------------------------------------------------------

_PERMISSION_ERRNOS = frozenset({errno.EACCES, errno.EPERM, errno.EROFS})


def raise_for_os_error(exc: OSError) -> NoReturn:
    """
    Translates a low-level :class:`OSError` into a protondl error and raises it.

    Args:
        exc (OSError): The original filesystem error.

    Raises:
        NoWritePermissionError: If the error is a permission error
            (``EACCES``, ``EPERM`` or ``EROFS``).
        NoDiskSpaceError: If the error is ``ENOSPC`` (no space left on device).
        OSError: The original error, if it is neither of the above.
    """
    if isinstance(exc, NoWritePermissionError | NoDiskSpaceError):
        raise exc
    if isinstance(exc, PermissionError) or exc.errno in _PERMISSION_ERRNOS:
        raise NoWritePermissionError(
            exc.errno or errno.EACCES, exc.strerror or "Permission denied", exc.filename
        ) from exc
    if exc.errno == errno.ENOSPC:
        raise NoDiskSpaceError(
            errno.ENOSPC, exc.strerror or "No space left on device", exc.filename
        ) from exc
    raise exc


def raise_for_httpx_error(exc: httpx.HTTPError) -> NoReturn:
    """
    Translates an :mod:`httpx` error into a protondl :class:`NetworkError` and
    raises it.

    Args:
        exc (httpx.HTTPError): The original httpx error, for example from
            ``client.get()`` or ``response.raise_for_status()``.

    Raises:
        NoInternetConnectionError: On connection failures and timeouts.
        LinkNotFoundError: On HTTP 404 responses.
        APIRateLimitError: On HTTP 403/429 responses (rate limiting).
        DownloadError: On any other HTTP error.
    """
    if isinstance(exc, httpx.TimeoutException | httpx.ConnectError | httpx.NetworkError):
        raise NoInternetConnectionError() from exc
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 404:
            raise LinkNotFoundError(f"Not found: {exc.request.url}") from exc
        if status in (403, 429):
            raise APIRateLimitError(
                f"GitHub/GitLab API rate limit exceeded (HTTP {status}). "
                "Provide a token to increase the limits."
            ) from exc
        raise DownloadError(f"Request to {exc.request.url} failed with HTTP {status}.") from exc
    raise DownloadError(str(exc) or exc.__class__.__name__) from exc
