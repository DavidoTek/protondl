import shutil
import tempfile
import time
from abc import ABC
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx

from protondl.core.base_launcher import Launcher
from protondl.core.config import RequestConfig
from protondl.core.errors import (
    AlreadyInstalledError,
    ChecksumMismatchError,
    InstallCancelledError,
    raise_for_httpx_error,
    raise_for_os_error,
)
from protondl.core.models import (
    Arch,
    CancelToken,
    CompatTool,
    CompatToolType,
    CompatToolVersionInfo,
    InstallProgress,
    InstallStep,
    ProgressCallback,
    ReleaseData,
    ReleaseVersion,
    TranslationDetails,
)
from protondl.util.archive import extract_tar, extract_tar_zst, extract_zip
from protondl.util.download import (
    calculate_sha512,
    download_file,
    fetch_project_release_data,
    fetch_project_releases,
)
from protondl.util.helpers import _resolve_tool_arch, detect_host_arch
from protondl.util.version_file import read_version_file, write_version_file


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
        supported_archs (tuple[Arch, ...]): The architectures the tool can provide
            builds for. Defaults to x86_64 only.
        arch_release_suffixes (Mapping[Arch, str]): Maps an architecture to the filename
            suffix identifying its release asset (e.g. {"aarch64": "-aarch64"}).
            x86_64 assets default to no suffix. An empty mapping means every
            architecture uses the same (arch-agnostic) release asset.
        from_os (str): The guest operating system the tool runs games from (e.g. "windows").
        from_arch (str): The guest architecture of the games (e.g. "x86_64").
        to_os (str): The host operating system the tool runs on (e.g. "linux").
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

    supported_archs: tuple[Arch, ...] = (Arch.X86_64,)
    arch_release_suffixes: Mapping[Arch, str] = {}

    from_os: str = "windows"
    from_arch: str = "x86_64"
    to_os: str = "linux"

    def __init__(self, request_config: RequestConfig | None = None) -> None:
        self.request_config: RequestConfig = request_config or RequestConfig()
        self.buffer_size = 65536

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        """
        Fetches a list of available versions/releases from the remote source.

        Returns:
            list[ReleaseVersion]: A list of release versions (e.g.,
                ReleaseVersion("GE-Proton9-1", (Arch.X86_64,))) with the architectures
                each release provides, sorted by newest first.
            count (int): The maximum number of versions to fetch.
            page (int): The page number for paginated APIs.

        Raises:
            NoInternetConnectionError: If the remote API or source is unreachable.
            LinkNotFoundError: If the releases endpoint returns HTTP 404.
            APIRateLimitError: If the GitHub/GitLab API rate limit was exceeded.
            DownloadError: If the request fails for any other HTTP reason.
        """
        return await fetch_project_releases(
            releases_url=self.api_url,
            config=self.request_config,
            count=count,
            page=page,
            release_archs=self._release_archs_from_assets,
        )

    async def install(
        self,
        version: str,
        launcher: Launcher,
        arch: Arch | None = None,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CompatToolVersionInfo:
        """
        Downloads and extracts a specific version of the tool into the launcher's directory.

        If the requested version and architecture are already installed, the
        installation is cancelled by raising AlreadyInstalledError, unless
        force is True. The check is architecture-aware: x86_64 and aarch64
        builds of the same version are tracked independently.

        Args:
            version (str): The specific version string to install.
            launcher (Launcher): The Launcher instance where the tool should be installed.
            arch (Arch | None): The architecture to install. Defaults to the host
                architecture if supported by the tool, otherwise to x86_64.
            force (bool): Whether to remove an already installed build of the
                same version and architecture and re-install it. Defaults to False.
            progress_callback (ProgressCallback | None, optional):
                A callback function to report progress as InstallProgress events,
                covering the fetch, download, verification, extraction and
                finalization steps.
            cancel_token (CancelToken | None, optional): A token whose cancel()
                method aborts the installation. It is checked between the steps
                and during the download (per chunk) and extraction (per archive
                member). On cancellation, the partially downloaded archive and
                any files extracted so far are removed and InstallCancelledError
                is raised.

        Returns:
            CompatToolVersionInfo: The metadata written to the tool's version file,
                including the installed architecture.

        Raises:
            AlreadyInstalledError: If the requested version and architecture are
                already installed for the launcher and force is False.
            InstallCancelledError: If the cancel_token is cancelled before the
                installation completes.
            ValueError: If the version string is invalid or no build exists for the
                requested architecture.
            LinkNotFoundError: If the requested version/release cannot be found
                on the remote source (HTTP 404).
            NoInternetConnectionError: If the remote source is unreachable.
            APIRateLimitError: If the GitHub/GitLab API rate limit was exceeded.
            DownloadError: If fetching the release info or the download fails for
                another HTTP reason.
            ChecksumMismatchError: If the downloaded archive fails checksum
                verification.
            ArchiveExtractionError: If the downloaded archive cannot be extracted.
            NoWritePermissionError: If the library lacks write access to the
                launcher's compatibility tools directory. Also a PermissionError
                for backwards compatibility.
            NoDiskSpaceError: If the filesystem runs out of space during download
                or extraction.
        """
        arch = self.resolve_arch(arch)

        self._check_not_installed(launcher, version, arch, force)

        def report(step: InstallStep, current: int = 0, total: int = 0) -> None:
            if progress_callback is not None:
                progress_callback(InstallProgress(step=step, current=current, total=total))

        def check_cancelled() -> None:
            if cancel_token is not None:
                cancel_token.raise_if_cancelled()

        check_cancelled()

        report(InstallStep.FETCHING_RELEASE)
        release_data = await self._fetch_release_data(version, arch)

        if not release_data.download:
            raise ValueError(f"No {arch.value} asset found for version '{version}' of {self.name}.")

        self._check_not_installed(launcher, release_data.version, arch, force)

        info = CompatToolVersionInfo(
            compat_tool=self.name,
            version=release_data.version,
            installed_at=int(time.time()),
            arch=arch,
            translation_details=self.get_translation_details(arch),
        )

        async with httpx.AsyncClient(
            headers=self.request_config.get_headers(release_data.download), follow_redirects=True
        ) as client:
            suffix = release_data.original_filename or self.release_format
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

                try:
                    check_cancelled()
                    await download_file(
                        url=release_data.download,
                        destination=tmp_path,
                        client=client,
                        progress_callback=progress_callback,
                        known_size=release_data.size or 0,
                        cancel_token=cancel_token,
                    )

                    check_cancelled()
                    report(InstallStep.VERIFYING)
                    await self._verify_checksum(client, release_data, tmp_path)

                    check_cancelled()
                    if force:
                        self._remove_installed_tool(launcher, release_data.version, arch)

                    try:
                        install_dir = self._get_extract_dir(launcher)
                        before = set(install_dir.iterdir())
                    except OSError as e:
                        raise_for_os_error(e)
                    report(InstallStep.EXTRACTING)
                    try:
                        self._extract_archive(
                            tmp_path,
                            install_dir,
                            progress_callback=progress_callback,
                            cancel_token=cancel_token,
                        )
                    except InstallCancelledError:
                        self._cleanup_partial_extraction(install_dir, before)
                        raise

                    installed_dir = self._find_installed_dir(
                        install_dir, before, release_data.version
                    )
                    report(InstallStep.FINISHING)
                    if installed_dir is None:
                        print(
                            f"Warning: Could not determine the installation directory of "
                            f"{self.name}; skipping version file creation."
                        )
                    else:
                        try:
                            write_version_file(installed_dir, info)
                        except OSError as e:
                            print(f"Warning: Could not write the version file for {self.name}: {e}")
                except Exception as e:
                    if tmp_path.exists():
                        tmp_path.unlink()
                    raise e
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

        return info

    def supports_launcher(self, launcher: Launcher) -> bool:
        """
        Determines if the given launcher is compatible with this tool.

        Args:
            launcher (Launcher): The Launcher instance to check compatibility against.

        Returns:
            bool: True if the tool supports the launcher, False otherwise.
        """
        return self.tool_type in launcher.supported_tools_folders

    def variant_of(self, version: str) -> str:
        """
        Returns the build variant a version string belongs to.

        Tools that ship multiple distinct build variants under the same
        architecture and version-string space (e.g. Lutris-Wine's fshack
        builds or Kron4ek's wow64 builds) must override this so that update
        checks group the variants separately instead of treating them as
        interchangeable builds.

        Args:
            version (str): The version string as returned by fetch_releases.

        Returns:
            str: The variant identifier of the version, or an empty string
                for the default variant.
        """
        return ""

    def find_installed_tool(
        self, launcher: Launcher, version: str, arch: Arch
    ) -> CompatTool | None:
        """
        Finds an installed build of the given version and architecture.

        A build is considered installed if its protondl_version.json matches the
        installer's name, the given version and architecture. For legacy version
        files without an arch field, the host-side architecture recorded in the
        translation details is used as a fallback.

        The lookup is best-effort: if the launcher's installed tools cannot be
        enumerated (e.g. missing launcher configuration files), None is returned
        and the caller proceeds without a check.

        Args:
            launcher (Launcher): The launcher to search for installed tools.
            version (str): The version to look for.
            arch (Arch): The architecture to look for.

        Returns:
            CompatTool | None: The installed tool, or None if no build of the
                given version and architecture is installed.
        """
        try:
            installed_tools = launcher.get_installed_tools()
        except Exception:
            return None
        for tool in installed_tools:
            info = read_version_file(tool.install_dir)
            if info is None:
                continue
            if info.compat_tool != self.name or info.version != version:
                continue
            if _resolve_tool_arch(self, info) != arch:
                continue
            return tool
        return None

    def _check_not_installed(
        self, launcher: Launcher, version: str, arch: Arch, force: bool
    ) -> None:
        """
        Cancels the installation if the given version and architecture are already installed.

        Args:
            launcher (Launcher): The launcher to search for installed tools.
            version (str): The version to check.
            arch (Arch): The architecture to check.
            force (bool): Whether the installation will re-install the build.

        Raises:
            AlreadyInstalledError: If the build is already installed and force is False.
        """
        if not force and self.find_installed_tool(launcher, version, arch) is not None:
            raise AlreadyInstalledError(self.name, version, arch)

    def _remove_installed_tool(self, launcher: Launcher, version: str, arch: Arch) -> None:
        """
        Removes an already installed build of the given version and architecture.

        Args:
            launcher (Launcher): The launcher to search for installed tools.
            version (str): The version of the build to remove.
            arch (Arch): The architecture of the build to remove.
        """
        existing = self.find_installed_tool(launcher, version, arch)
        if existing is not None:
            launcher.remove_tool(existing)

    def remove(self, tool: CompatTool, launcher: Launcher) -> None:
        """
        Removes an installed compatibility tool.

        The default implementation deletes the tool's installation directory.
        Subclasses may override this method to perform additional cleanup,
        e.g. removing launcher configuration that references the tool.

        Args:
            tool (CompatTool): The installed compatibility tool to remove.
            launcher (Launcher): The launcher instance the tool is installed for.

        Raises:
            FileNotFoundError: If the tool's installation directory does not exist.
            NoWritePermissionError: If the tool's installation directory cannot be
                deleted. Also a PermissionError for backwards compatibility.
        """
        try:
            shutil.rmtree(tool.install_dir)
        except OSError as e:
            raise_for_os_error(e)

    def _get_extract_dir(self, launcher: Launcher) -> Path:
        """
        Helper method to determine the extraction directory for the given launcher.

        Args:
            launcher (Launcher): The Launcher instance for which to determine the path.

        Returns:
            Path: The path to the extraction directory.
        """
        return launcher.get_compatibility_tools_path(self.tool_type)

    async def _fetch_release_data(self, version: str, arch: Arch) -> ReleaseData:
        """
        Fetches detailed release data for a specific version and architecture.

        Args:
            version (str): The version string for which to fetch release data.
            arch (Arch): The architecture whose build should be selected.

        Returns:
            ReleaseData: The fetched release data.
        """
        return await fetch_project_release_data(
            release_url=self.api_url,
            release_format=self.release_format,
            config=self.request_config,
            tag=version,
            checksum_suffix=self.checksum_suffix,
            asset_condition=lambda asset: self._asset_matches_arch(
                asset.get("name", ""), arch, self.release_format
            ),
            checksum_condition=lambda asset: self._asset_matches_arch(
                asset.get("name", ""), arch, self.checksum_suffix
            ),
            asset_priority=self._asset_priority,
        )

    def resolve_arch(self, arch: Arch | None) -> Arch:
        """
        Resolves the architecture to install.

        An explicitly requested architecture must be supported by the tool.
        Otherwise, the host architecture is used if supported by the tool,
        falling back to x86_64.

        Args:
            arch (Arch | None): The requested architecture, or None to auto-detect.

        Returns:
            Arch: The resolved architecture.

        Raises:
            ValueError: If the requested architecture is not supported by the tool.
        """
        if arch is not None:
            if arch not in self.supported_archs:
                supported = ", ".join(a.value for a in self.supported_archs)
                raise ValueError(
                    f"{self.name} does not support architecture '{arch.value}'. "
                    f"Supported: {supported}."
                )
            return arch

        host_arch = detect_host_arch()
        if host_arch in self.supported_archs:
            return host_arch
        return Arch.X86_64

    def get_translation_details(self, arch: Arch) -> TranslationDetails:
        """
        Returns the translation details for a build of the given architecture.

        Args:
            arch (Arch): The architecture of the installed build.

        Returns:
            TranslationDetails: The game/host translation performed by the build.
        """
        return TranslationDetails(
            from_os=self.from_os,
            from_arch=self.from_arch,
            to_os=self.to_os,
            to_arch=arch.value,
        )

    def _asset_matches_arch(self, name: str, arch: Arch, file_suffix: str) -> bool:
        """
        Determines whether an asset filename belongs to a build of the given architecture.

        An asset matches if its name ends with the architecture's release suffix
        followed by the file suffix, and it does not end with a *different*
        other-architecture suffix (e.g. "GE-Proton11-3-aarch64.tar.gz" is not
        considered an x86_64 asset).

        Args:
            name (str): The asset filename.
            arch (Arch): The architecture to check against.
            file_suffix (str): The expected file suffix (e.g. ".tar.gz" or a checksum suffix).

        Returns:
            bool: True if the asset belongs to the given architecture, False otherwise.
        """
        arch_suffix = self.arch_release_suffixes.get(arch, "")
        if not name.endswith(arch_suffix + file_suffix):
            return False

        for other_arch, other_suffix in self.arch_release_suffixes.items():
            if other_arch == arch or not other_suffix or other_suffix == arch_suffix:
                continue
            if name.endswith(other_suffix + file_suffix):
                return False

        return True

    def _asset_priority(self, asset: Mapping[str, Any]) -> int:
        """
        Returns the priority of an asset matching the release format.

        When a release provides multiple matching assets, the asset with the
        highest priority is selected. Subclasses may override this to prefer
        specific builds (e.g. ignoring "native" variant builds).

        Args:
            asset (Mapping): The release asset (from the API response).

        Returns:
            int: The priority of the asset (higher is preferred).
        """
        return 0

    def _release_archs_from_assets(self, assets: Sequence[dict[str, Any]]) -> list[Arch]:
        """
        Determines which architectures a release's assets provide builds for.

        Args:
            assets (Sequence[dict]): The release's asset list (from the API response).

        Returns:
            list[Arch]: The architectures supported by the release's assets.
        """
        return [
            arch
            for arch in self.supported_archs
            if any(
                self._asset_matches_arch(asset.get("name", ""), arch, self.release_format)
                for asset in assets
            )
        ]

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
            ChecksumMismatchError: If the checksum verification fails. Also a
                ValueError for backwards compatibility.
            NoInternetConnectionError: If the checksum file cannot be downloaded.
            DownloadError: If downloading the checksum file fails for another reason.
        """
        if release_data.checksum:
            try:
                sha_resp = await client.get(release_data.checksum)
                sha_resp.raise_for_status()
            except httpx.HTTPError as e:
                raise_for_httpx_error(e)

            expected_sha = sha_resp.text.split()[0].strip()
            actual_sha = calculate_sha512(file_path, self.buffer_size)

            if actual_sha != expected_sha:
                raise ChecksumMismatchError("Checksum verification failed! File corrupted.")

    def _extract_archive(
        self,
        archive_path: Path,
        extract_to: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> None:
        """
        Helper method to extract an archive file to the specified directory.

        Args:
            archive_path (Path): The path to the archive file.
            extract_to (Path): The directory where the contents should be extracted.
            progress_callback (ProgressCallback | None, optional): A callback to
                receive EXTRACTING progress events with per-file progress.
            cancel_token (CancelToken | None, optional): A token checked before each
                extracted archive member.

        Raises:
            ValueError: If the archive format is unsupported.
            InstallCancelledError: If the cancel_token is cancelled during extraction.
        """
        if self.release_format.endswith(".tar.zst"):
            extract_tar_zst(
                archive_path,
                extract_to,
                progress_callback=progress_callback,
                cancel_token=cancel_token,
            )
        elif ".tar." in self.release_format:
            extract_tar(
                archive_path,
                extract_to,
                compression=self.release_format.split(".tar.")[-1],
                progress_callback=progress_callback,
                cancel_token=cancel_token,
            )
        elif self.release_format.endswith(".zip"):
            extract_zip(
                archive_path,
                extract_to,
                progress_callback=progress_callback,
                cancel_token=cancel_token,
            )
        else:
            raise ValueError(f"Unsupported archive format: {self.release_format}")

    def _cleanup_partial_extraction(self, install_dir: Path, before: set[Path]) -> None:
        """
        Removes files and directories created by an aborted extraction.

        Any entry in install_dir that was not present before extraction started
        is deleted. Used to undo a partial extraction after cancellation.

        Args:
            install_dir (Path): The directory the archive was extracted into.
            before (set[Path]): The contents of install_dir before extraction.
        """
        try:
            entries = list(install_dir.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry in before:
                continue
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)

    def _find_installed_dir(
        self, install_dir: Path, before: set[Path], version: str
    ) -> Path | None:
        """
        Determines the directory of the newly extracted compatibility tool.

        Args:
            install_dir (Path): The directory into which the archive was extracted.
            before (set[Path]): The contents of install_dir before extraction.
            version (str): The installed version, used to disambiguate if multiple
                directories were created by the extraction.

        Returns:
            Path | None: The path to the installed tool's directory, or None if
                no new directory was created.
        """
        new_dirs = [d for d in install_dir.iterdir() if d.is_dir() and d not in before]
        if not new_dirs:
            return None
        if len(new_dirs) == 1:
            return new_dirs[0]
        for d in new_dirs:
            if d.name == version:
                return d
        return new_dirs[0]
