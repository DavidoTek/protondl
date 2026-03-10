import tempfile
from abc import ABC
from collections.abc import Callable
from pathlib import Path

import httpx

from protondl.core.base_launcher import Launcher
from protondl.core.models import CompatToolType, ReleaseData, RequestConfig
from protondl.util.archive import extract_tar, extract_tar_zst, extract_zip
from protondl.util.download import (
    calculate_sha512,
    download_file,
    fetch_project_release_data,
    fetch_project_releases,
)


class CtInstaller(ABC):
    """
    Abstract base class for compatibility tool installers.

    This class defines the interface for fetching and installing external
    compatibility tools (like GE-Proton, Boxtron, or Luxtorpeda) into various
    game launchers. Concrete subclasses must implement the logic for communicating
    with specific backends (e.g., GitHub API).

    Attributes:
        name (str): The human-readable name of the compatibility tool.
        description (str): A brief summary of what the tool does.
        tool_type (CompatToolType): The type/category of the compatibility tool.
        advanced (bool): Whether this tool is considered "advanced".
        info_url (str): The official website or repository URL for the tool.
        release_info_url (str): URL to the releases page.
            Formatted with {version} for specific release details.
        api_url (str): The API endpoint URL to fetch release data (e.g., GitHub or GitLab).
        release_format (str): The expected file format of the release asset (e.g., ".tar.gz").
        checksum_suffix (str): The suffix used to identify checksum assets (e.g., ".sha512sum").
    """

    name: str
    description: str
    tool_type: CompatToolType
    advanced: bool
    info_url: str
    release_info_url: str
    api_url: str
    release_format: str
    checksum_suffix: str

    def __init__(self) -> None:
        self.request_config: RequestConfig = RequestConfig()
        self.buffer_size = 65536

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[str]:
        """
        Fetches a list of available versions/releases from the remote source.

        Returns:
            list[str]: A list of version strings (e.g., ["GE-Proton9-1", "GE-Proton9-2"])
                sorted by newest first.
            count (int): The maximum number of versions to fetch.
            page (int): The page number for paginated APIs.

        Raises:
            ConnectionError: If the remote API or source is unreachable.
        """
        return await fetch_project_releases(
            releases_url=self.api_url,
            config=self.request_config,
            count=count,
            page=page,
        )

    async def install(
        self,
        version: str,
        launcher: Launcher,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """
        Downloads and extracts a specific version of the tool into the launcher's directory.

        Args:
            version (str): The specific version string to install.
            launcher (Launcher): The Launcher instance where the tool should be installed.
            progress_callback (Callable[[int, int], None], optional):
                A callback function to report download/extraction progress.

        Raises:
            ValueError: If the version string is invalid.
            PermissionError: If the library lacks write access to the launcher's
                compatibility tools directory.
        """
        release_data = await self._fetch_release_data(version)

        if not release_data.download:
            raise ValueError(f"No downloadable asset found for version '{version}'")

        async with httpx.AsyncClient(
            headers=self.request_config.get_headers(), follow_redirects=True
        ) as client:
            suffix = release_data.original_filename or self.release_format
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

                try:
                    await download_file(
                        url=release_data.download,
                        destination=tmp_path,
                        client=client,
                        progress_callback=progress_callback,
                        known_size=release_data.size or 0,
                    )

                    await self._verify_checksum(client, release_data, tmp_path)

                    install_dir = self._get_extract_dir(launcher)
                    self._extract_archive(tmp_path, install_dir)
                except Exception as e:
                    if tmp_path.exists():
                        tmp_path.unlink()
                    raise e
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

    def supports_launcher(self, launcher: Launcher) -> bool:
        """
        Determines if the given launcher is compatible with this tool.

        Args:
            launcher (Launcher): The Launcher instance to check compatibility against.

        Returns:
            bool: True if the tool supports the launcher, False otherwise.
        """
        return self.tool_type in launcher.supported_tools_folders

    def _get_extract_dir(self, launcher: Launcher) -> Path:
        """
        Helper method to determine the extraction directory for the given launcher.

        Args:
            launcher (Launcher): The Launcher instance for which to determine the path.

        Returns:
            Path: The path to the extraction directory.
        """
        return launcher.get_compatibility_tools_path(self.tool_type)

    async def _fetch_release_data(self, version: str) -> ReleaseData:
        """
        Fetches detailed release data for a specific version.

        Args:
            version (str): The version string for which to fetch release data.

        Returns:
            ReleaseData: The fetched release data.
        """
        return await fetch_project_release_data(
            release_url=self.api_url,
            release_format=self.release_format,
            config=self.request_config,
            tag=version,
            checksum_suffix=self.checksum_suffix,
        )

    async def _verify_checksum(
        self, client: httpx.AsyncClient, release_data: ReleaseData, file_path: Path
    ) -> None:
        """
        Verifies the checksum of a downloaded file against the expected checksum.

        Args:
            client (httpx.AsyncClient): The HTTP client for making requests.
            release_data (ReleaseData): The release data containing the checksum.
            file_path (Path): The path to the downloaded file.

        Raises:
            ValueError: If the checksum verification fails.
        """
        if release_data.checksum:
            sha_resp = await client.get(release_data.checksum)
            sha_resp.raise_for_status()

            expected_sha = sha_resp.text.split()[0].strip()
            actual_sha = calculate_sha512(file_path, self.buffer_size)

            if actual_sha != expected_sha:
                raise ValueError("Checksum verification failed! File corrupted.")

    def _extract_archive(self, archive_path: Path, extract_to: Path) -> None:
        """
        Helper method to extract an archive file to the specified directory.

        Args:
            archive_path (Path): The path to the archive file.
            extract_to (Path): The directory where the contents should be extracted.

        Raises:
            ValueError: If the archive format is unsupported.
        """
        if self.release_format.endswith(".tar.zst"):
            extract_tar_zst(archive_path, extract_to)
        elif ".tar." in self.release_format:
            extract_tar(
                archive_path, extract_to, compression=self.release_format.split(".tar.")[-1]
            )
        elif self.release_format.endswith(".zip"):
            extract_zip(archive_path, extract_to)
        else:
            raise ValueError(f"Unsupported archive format: {self.release_format}")
