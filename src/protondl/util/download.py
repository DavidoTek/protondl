import hashlib
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx

from protondl.core.config import RequestConfig
from protondl.core.errors import (
    APIRateLimitError,
    NetworkError,
    raise_for_httpx_error,
    raise_for_os_error,
)
from protondl.core.models import (
    Arch,
    CancelToken,
    GitHubArtifactResponse,
    InstallProgress,
    InstallStep,
    ProgressCallback,
    ReleaseData,
    ReleaseVersion,
)

GITHUB_API = "https://api.github.com/"
GITLAB_APIS = ["https://gitlab.com/api/"]
GITEA_APIS = ["https://codeberg.org/api/v1/", "https://dawn.wine/api/v1/"]

GITLAB_RATELIMIT_MSGS = ["Retry later", "rate limit exceeded"]

#: Backwards-compatible alias. Use :class:`protondl.core.errors.APIRateLimitError`.
RateLimitError = APIRateLimitError


@asynccontextmanager
async def _translate_network_errors() -> AsyncIterator[None]:
    """
    Async context manager that converts raw :mod:`httpx` errors into protondl
    :class:`~protondl.core.errors.NetworkError` subclasses.

    Raises:
        NoInternetConnectionError: On connection failures and timeouts.
        LinkNotFoundError: On HTTP 404 responses.
        APIRateLimitError: On HTTP 403/429 responses (rate limiting).
        DownloadError: On any other httpx error.
    """
    try:
        yield
    except NetworkError:
        raise
    except httpx.HTTPError as e:
        raise_for_httpx_error(e)


def is_gitlab_instance(url: str) -> bool:
    """
    Checks if the given URL belongs to a GitLab instance.

    Args:
        url: The URL to check.

    Returns:
        True if the URL is associated with GitLab, False otherwise.
    """
    return any(instance in url for instance in GITLAB_APIS)


def is_gitea_instance(url: str) -> bool:
    """
    Checks if the given URL belongs to a Gitea (or Forgejo) instance.

    Args:
        url: The URL to check.

    Returns:
        True if the URL is associated with a known Gitea instance, False otherwise.
    """
    return any(instance in url for instance in GITEA_APIS)


async def is_online(host: str = "https://api.github.com/rate_limit", timeout: int = 5) -> bool:
    """
    Async check if the host is reachable.

    Args:
        host: The URL to check connectivity against.
        timeout: The maximum time to wait for a response in seconds.

    Returns:
        True if the host is reachable, False otherwise.
    """
    try:
        async with httpx.AsyncClient() as client:
            await client.get(host, timeout=timeout)
            return True
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def check_rate_limits(response_json: Any) -> Any:
    """
    Checks API responses for rate limit errors and raises RateLimitError if limits are exceeded.

    Args:
        response_json: The JSON response from the API call.

    Returns:
        The original response_json if no rate limit issues are detected.

    Raises:
        RateLimitError: If the API response indicates that rate limits have been exceeded.
    """
    if not isinstance(response_json, dict):
        return response_json

    message = str(response_json.get("message", ""))

    # GitHub check
    if "rate limit exceeded" in message.lower():
        raise RateLimitError("GitHub API rate limit exceeded. Provide a token to increase limits.")

    # GitLab check
    if any(msg in message for msg in GITLAB_RATELIMIT_MSGS):
        raise RateLimitError("GitLab API rate limit exceeded.")

    return response_json


async def fetch_project_release_data(
    release_url: str,
    release_format: str,
    config: RequestConfig,
    tag: str,
    checksum_suffix: str = "",
    asset_condition: Callable[[dict[str, Any]], bool] | None = None,
    checksum_condition: Callable[[dict[str, Any]], bool] | None = None,
    asset_priority: Callable[[dict[str, Any]], int] | None = None,
) -> ReleaseData:
    """
    Unified fetch for release metadata across GitHub and GitLab.

    Args:
        release_url (str): The API URL for the release (e.g., GitHub or GitLab).
        release_format (str): The expected file format for the main asset (e.g., ".tar.gz").
        config (RequestConfig): Configuration for API requests, including auth tokens.
        tag (str): Specific tag to fetch. If empty, fetches the latest release.
        checksum_suffix (str): Suffix to identify checksum assets (e.g., ".sha512").
        asset_condition (Callable[[dict], bool], optional): Additional filter for assets.
        checksum_condition (Callable[[dict], bool], optional):
            Additional filter for checksum assets.
        asset_priority (Callable[[dict], int], optional):
            Returns a priority for a matching asset. When a release provides
            multiple matching assets, the one with the highest priority is
            selected. Assets of equal priority keep the last one seen.

    Returns:
        ReleaseData: A dataclass containing release metadata and asset URLs.

    Raises:
        NoInternetConnectionError: If the release API host is unreachable.
        LinkNotFoundError: If the release/tag does not exist (HTTP 404).
        APIRateLimitError: If the GitHub/GitLab API rate limit was exceeded.
        DownloadError: If the request fails for any other HTTP reason.
        ValueError: If the release URL is not a supported GitHub/GitLab/Gitea API URL.
    """
    is_gl = is_gitlab_instance(release_url)
    is_gitea = is_gitea_instance(release_url)
    api_tag = tag if tag not in ["", "latest"] else "latest"

    if is_gl:
        fetch_url = f"{release_url}/{api_tag}"
        date_key, tag_key = "released_at", "name"
    else:
        fetch_url = f"{release_url}/tags/{api_tag}" if tag else f"{release_url}/latest"
        date_key, tag_key = "published_at", "tag_name"

    headers = config.get_headers(fetch_url)
    async with (
        _translate_network_errors(),
        httpx.AsyncClient(headers=headers, follow_redirects=True) as client,
    ):
        resp = await client.get(fetch_url)
        data = check_rate_limits(resp.json())

        release_data = ReleaseData(
            version=data.get(tag_key, "unknown"), date=data.get(date_key, "unknown").split("T")[0]
        )

        if GITHUB_API in release_url or is_gitea:
            assets = data.get("assets", [])
        elif is_gitlab_instance(release_url):
            assets = data.get("assets", {}).get("links", [])
        else:
            raise ValueError("Unsupported release URL format.")

        selected_priority = 0
        for asset in assets:
            name = asset.get("name", "")
            download_url = asset.get("browser_download_url") if not is_gl else asset.get("url")

            if name.endswith(release_format):
                if not asset_condition or asset_condition(asset):
                    priority = asset_priority(asset) if asset_priority else 0
                    if priority >= selected_priority:
                        selected_priority = priority
                        release_data.download = download_url
                        release_data.size = int(asset.get("size", -1))
                        release_data.original_filename = name

            if checksum_suffix and name.endswith(checksum_suffix):
                if not checksum_condition or checksum_condition(asset):
                    release_data.checksum = download_url

    return release_data


async def fetch_project_releases(
    releases_url: str,
    config: RequestConfig,
    count: int = 100,
    page: int = 1,
    release_archs: Callable[[list[dict[str, Any]]], Sequence[Arch]] | None = None,
) -> list[ReleaseVersion]:
    """
    Lists available release tags/names for a given project URL (GitHub or GitLab).

    Args:
        releases_url (str): The API URL for the releases (e.g., GitHub or GitLab).
        config (RequestConfig): Configuration for API requests, including auth tokens.
        count (int): Number of releases to fetch per page.
        page (int): Page number for paginated APIs.
        release_archs (Callable[[list[dict]], Sequence[Arch]], optional):
            A function that receives the release's asset list and returns the
            architectures for which the release provides a build.

    Returns:
        list[ReleaseVersion]: A list of release versions with their supported
            architectures, sorted by newest first.

    Raises:
        NoInternetConnectionError: If the release API host is unreachable.
        LinkNotFoundError: If the releases endpoint does not exist (HTTP 404).
        APIRateLimitError: If the GitHub/GitLab API rate limit was exceeded.
        DownloadError: If the request fails for any other HTTP reason.
    """
    is_gl = is_gitlab_instance(releases_url)
    tag_key = "name" if is_gl else "tag_name"

    params = (
        {"limit": count, "page": page}
        if is_gitea_instance(releases_url)
        else {"per_page": count, "page": page}
    )

    headers = config.get_headers(releases_url)
    async with (
        _translate_network_errors(),
        httpx.AsyncClient(headers=headers, follow_redirects=True) as client,
    ):
        response = await client.get(releases_url, params=params)

        data = check_rate_limits(response.json())

        if not isinstance(data, list):
            return []

        releases_list: list[ReleaseVersion] = []
        for release in data:
            tag_name = release.get(tag_key)
            if not tag_name:
                continue

            if is_gl:
                assets = release.get("assets", {}).get("links", [])
            else:
                assets = release.get("assets", [])

            archs = tuple(release_archs(assets)) if release_archs else (Arch.X86_64,)
            releases_list.append(ReleaseVersion(version=tag_name, archs=archs))

        return releases_list


async def fetch_github_project_workflows(
    ct_workflow_url: str,
    package_name: str,
    config: RequestConfig,
    count: int = 30,
    page: int = 1,
) -> list[str]:
    """
    Fetches workflow run IDs for a given GitHub Actions workflow
    that match the specified package name.

    Args:
        ct_workflow_url (str): The API URL for the GitHub Actions workflows.
        package_name (str): The name of the package to filter workflows by.
        config (RequestConfig): Configuration for API requests, including auth tokens.
        count (int): The number of workflow runs to fetch per page.
        page (int): The page number for paginated API requests.

    Returns:
        list[str]: A list of workflow run IDs that match
            the specified package name, sorted by newest first.

    Raises:
        NoInternetConnectionError: If the GitHub API host is unreachable.
        LinkNotFoundError: If the workflow endpoint does not exist (HTTP 404).
        APIRateLimitError: If the GitHub API rate limit was exceeded.
        DownloadError: If the request fails for any other HTTP reason.
    """
    headers = config.get_headers(ct_workflow_url)
    async with (
        _translate_network_errors(),
        httpx.AsyncClient(headers=headers, follow_redirects=True) as client,
    ):
        tags = []
        wf_resp = await client.get(f"{ct_workflow_url}?per_page={str(count)}&page={str(page)}")
        for wf in wf_resp.json().get("workflows", []):
            if wf["state"] != "active" or package_name not in wf["path"]:
                continue
            page = 1
            while page != -1 and page < 5:
                # fetch more (up to 5 pages) if first releases all failed
                # ensure the reason that len(tags)=0 is that releases failed
                at_least_one_failed = False
                runs_resp = await client.get(
                    f"{wf['url']}/runs?per_page={str(count)}&page={str(page)}"
                )
                for run in runs_resp.json().get("workflow_runs", []):
                    if run["conclusion"] == "success":
                        tags.append(str(run["id"]))
                    elif run["conclusion"] == "failure":
                        at_least_one_failed = True
                if len(tags) == 0 and at_least_one_failed:
                    page += 1
                else:
                    page = -1

        return tags


async def fetch_github_artifact_data(
    api_url: str, ct_artifact_url: str, ct_nightly_link: str, version: str, config: RequestConfig
) -> ReleaseData:
    """
    Fetches release data for a given version by first attempting to find an artifact from
    the workflow run ID (which is the version), and if not found, falls back to fetching
    release data from the GitHub API using the version as a tag.

    Args:
        api_url: The base API URL for fetching release data (e.g., GitHub releases API).
        ct_artifact_url: The API URL template for fetching artifacts associated with a workflow run.
        ct_nightly_link: The URL template for downloading nightly builds based
            on workflow run ID and artifact name.
        version: The version string to fetch release data for.
        config: Configuration for API requests, including auth tokens.

    Returns:
        A ReleaseData object containing the release information.

    Raises:
        NoInternetConnectionError: If the GitHub API host is unreachable.
        APIRateLimitError: If the GitHub API rate limit was exceeded.
        DownloadError: If the request fails for any other HTTP reason.
        ValueError: If no artifact and no matching release asset exists for the version.
    """
    async with (
        _translate_network_errors(),
        httpx.AsyncClient(headers=config.get_headers(api_url)) as client,
    ):
        resp = await client.get(f"{ct_artifact_url.format(version)}?per_page=100")
        artifact_info: GitHubArtifactResponse = resp.json()
        if artifact_info.get("total_count") != 1:
            raise ValueError(f"No artifact found for version '{version}'")

        artifact = artifact_info["artifacts"][0]

        if artifact:
            return ReleaseData(
                version=version,
                date=artifact["updated_at"].split("T")[0],
                download=ct_nightly_link.format(version=version, artifact_name=artifact["name"]),
                size=artifact["size_in_bytes"],
                original_filename=f"{artifact['name']}.zip",
            )

        url = f"{api_url}/tags/{version}" if version else f"{api_url}/latest"
        resp = await client.get(url)
        data = resp.json()

        if "tag_name" not in data:
            raise ValueError(f"Release with version '{version}' not found.")

        download_url = None
        size = 0
        for asset in data.get("assets", []):
            if "proton" in asset["name"]:
                download_url = asset["browser_download_url"]
                size = asset["size"]
                break

        if not download_url:
            raise ValueError(f"No suitable asset found for version '{version}'.")

        return ReleaseData(
            version=data["tag_name"],
            date=data["published_at"].split("T")[0],
            download=download_url,
            size=size,
        )


def calculate_sha512(filepath: Path, buffer_size: int) -> str:
    """
    Calculates the SHA-512 hash of a file.

    Args:
        filepath: The path to the file for which to calculate the hash.
        buffer_size: The size of the buffer to use when reading the file.

    Returns:
        The SHA-512 hash as a hexadecimal string.
    """
    sha512 = hashlib.sha512()
    with open(filepath, "rb") as f:
        while chunk := f.read(buffer_size):
            sha512.update(chunk)
    return sha512.hexdigest()


async def download_file(
    url: str,
    destination: Path,
    client: httpx.AsyncClient,
    progress_callback: ProgressCallback | None = None,
    known_size: int = 0,
    buffer_size: int = 65536,
    cancel_token: CancelToken | None = None,
) -> None:
    """
    Downloads a file from the specified URL to the given destination path.

    Args:
        url (str): The URL of the file to download.
        destination (Path): The destination path where the file should be saved.
        client (httpx.AsyncClient): An instance of httpx.AsyncClient to use for the download.
        progress_callback (ProgressCallback | None, optional): An optional callback function
            that receives InstallProgress events with the cumulative number of bytes
            downloaded and the total size.
        known_size (int): The known size of the file, if available.
            If 0, it will attempt to determine the size from the response headers.
        buffer_size (int): The size of the buffer to use when reading the file in bytes.
        cancel_token (CancelToken | None, optional): An optional token checked before
            every written chunk. The partially downloaded file is left in place for
            the caller to clean up.

    Raises:
        InstallCancelledError: If the cancel_token is cancelled during the download.
        NoInternetConnectionError: If the connection drops or times out.
        LinkNotFoundError: If the download URL returns HTTP 404.
        APIRateLimitError: If the host responds with HTTP 403/429.
        DownloadError: If the download fails for any other HTTP reason.
        NoWritePermissionError: If the destination cannot be written to.
        NoDiskSpaceError: If the filesystem runs out of space during the download.
    """
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise_for_os_error(e)

    async with _translate_network_errors():
        async with client.stream("GET", url) as response:
            response.raise_for_status()

            total_size = known_size
            if not total_size:
                total_size = int(response.headers.get("Content-Length", 0))

            try:
                with open(destination, "wb") as f:
                    downloaded = 0
                    async for chunk in response.aiter_bytes(chunk_size=buffer_size):
                        if cancel_token is not None:
                            cancel_token.raise_if_cancelled()
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(
                                InstallProgress(
                                    step=InstallStep.DOWNLOADING,
                                    current=downloaded,
                                    total=total_size,
                                )
                            )
                    f.flush()
            except OSError as e:
                raise_for_os_error(e)
