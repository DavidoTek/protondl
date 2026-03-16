import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from protondl.core.models import GitHubArtifactResponse, ReleaseData, RequestConfig

GITHUB_API = "https://api.github.com/"
GITLAB_APIS = ["https://gitlab.com/api/"]

GITLAB_RATELIMIT_MSGS = ["Retry later", "rate limit exceeded"]


class RateLimitError(Exception):
    """Raised when GitHub or GitLab API rate limits are hit."""

    pass


def is_gitlab_instance(url: str) -> bool:
    """
    Checks if the given URL belongs to a GitLab instance.

    Args:
        url: The URL to check.

    Returns:
        True if the URL is associated with GitLab, False otherwise.
    """
    return any(instance in url for instance in GITLAB_APIS)


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

    Returns:
        ReleaseData: A dataclass containing release metadata and asset URLs.
    """
    is_gl = is_gitlab_instance(release_url)
    api_tag = tag if tag not in ["", "latest"] else "latest"

    if is_gl:
        fetch_url = f"{release_url}/{api_tag}"
        date_key, tag_key = "released_at", "name"
    else:
        fetch_url = f"{release_url}/tags/{api_tag}" if tag else f"{release_url}/latest"
        date_key, tag_key = "published_at", "tag_name"

    async with httpx.AsyncClient(headers=config.get_headers(), follow_redirects=True) as client:
        resp = await client.get(fetch_url)
        data = check_rate_limits(resp.json())

        release_data = ReleaseData(
            version=data.get(tag_key, "unknown"), date=data.get(date_key, "unknown").split("T")[0]
        )

        if GITHUB_API in release_url:
            assets = data.get("assets", [])
        elif is_gitlab_instance(release_url):
            assets = data.get("assets", {}).get("links", [])
        else:
            raise ValueError("Unsupported release URL format.")

        for asset in assets:
            name = asset.get("name", "")
            download_url = asset.get("browser_download_url") if not is_gl else asset.get("url")

            if name.endswith(release_format):
                if not asset_condition or asset_condition(asset):
                    release_data.download = download_url
                    release_data.size = int(asset.get("size", -1))
                    release_data.original_filename = name

            if checksum_suffix and name.endswith(checksum_suffix):
                release_data.checksum = download_url

    return release_data


async def fetch_project_releases(
    releases_url: str,
    config: RequestConfig,
    count: int = 100,
    page: int = 1,
    include_extra_asset: Callable[[dict[str, Any]], list[str]] | None = None,
) -> list[str]:
    """
    Lists available release tags/names for a given project URL (GitHub or GitLab).

    Args:
        releases_url (str): The API URL for the releases (e.g., GitHub or GitLab).
        config (RequestConfig): Configuration for API requests, including auth tokens.
        count (int): Number of releases to fetch per page.
        page (int): Page number for paginated APIs.
        include_extra_asset (Callable[[dict], list[str]], optional):
            A function to extract additional version strings from a release dict.

    Returns:
        list[str]: A list of release tags/names sorted by newest first.
    """
    is_gl = is_gitlab_instance(releases_url)
    tag_key = "name" if is_gl else "tag_name"

    params = {"per_page": count, "page": page}

    async with httpx.AsyncClient(headers=config.get_headers(), follow_redirects=True) as client:
        response = await client.get(releases_url, params=params)

        data = check_rate_limits(response.json())

        if not isinstance(data, list):
            return []

        releases_list: list[str] = []
        for release in data:
            if tag_name := release.get(tag_key):
                releases_list.append(tag_name)

            assets = release.get("assets", [])
            if assets and include_extra_asset:
                releases_list.extend(include_extra_asset(release))

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
    """
    async with httpx.AsyncClient(headers=config.get_headers(), follow_redirects=True) as client:
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
    """
    async with httpx.AsyncClient(headers=config.get_headers()) as client:
        resp = await client.get(f"{ct_artifact_url.format(version)}?per_page=100")
        artifact_info: GitHubArtifactResponse = resp.json()
        if artifact_info.get("total_count") != 1:
            raise ValueError(f"No artifact found for version '{version}'")

        artifact = artifact_info["artifacts"][0]

        if artifact:
            return ReleaseData(
                version=artifact["workflow_run"]["head_sha"],
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
    progress_callback: Callable[[int, int], None] | None = None,
    known_size: int = 0,
    buffer_size: int = 65536,
) -> None:
    """
    Downloads a file from the specified URL to the given destination path.

    Args:
        url (str): The URL of the file to download.
        destination (Path): The destination path where the file should be saved.
        client (httpx.AsyncClient): An instance of httpx.AsyncClient to use for the download.
        progress_callback (Callable[[int, int], None], optional): An optional callback function
            that receives the number of bytes downloaded and total size.
        known_size (int): The known size of the file, if available.
            If 0, it will attempt to determine the size from the response headers.
        buffer_size (int): The size of the buffer to use when reading the file in bytes.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    async with client.stream("GET", url) as response:
        response.raise_for_status()

        total_size = known_size
        if not total_size:
            total_size = int(response.headers.get("Content-Length", 0))

        with open(destination, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=buffer_size):
                f.write(chunk)
                if progress_callback:
                    progress_callback(len(chunk), total_size)
            f.flush()
