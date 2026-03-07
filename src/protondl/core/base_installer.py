from abc import ABC, abstractmethod
from collections.abc import Callable

from protondl.core.base_launcher import Launcher
from protondl.core.models import RequestConfig


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
        supported_launchers (list[Launcher]): A collection of launcher identifiers compatible
            with this tool.
        info_url (str): The official website or repository URL for the tool.
        release_info_url (str): URL to the releases page.
            Formatted with {version} for specific release details.
        release_format (str): The expected file format of the release asset (e.g., ".tar.gz").
    """

    name: str
    description: str
    supported_launchers: list[type[Launcher]]
    info_url: str
    release_info_url: str
    release_format: str

    def __init__(self) -> None:
        self.request_config: RequestConfig = RequestConfig()
        self.buffer_size = 65536

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    def supports_launcher(self, launcher: Launcher) -> bool:
        """
        Determines if the given launcher is compatible with this tool.

        Args:
            launcher (Launcher): The Launcher instance to check compatibility against.

        Returns:
            bool: True if the tool supports the launcher, False otherwise.
        """
        return isinstance(launcher, tuple(self.supported_launchers))
