from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypedDict


class InstallMode(Enum):
    NATIVE = "native"
    FLATPAK = "flatpak"
    SNAP = "snap"


class CompatToolType(Enum):
    PROTON = "proton"
    WINE = "wine"
    DXVK = "dxvk"
    VKD3D = "vkd3d"


class Arch(Enum):
    X86_64 = "x86_64"
    AARCH64 = "aarch64"


@dataclass
class CompatTool:
    """
    Represents a compatibility tool (like Proton or VKD3D) installed for a specific launcher.

    Attributes:
        full_name: The full name of the installed tool, often including version information.
        tool_type: The type of compatibility tool (e.g., PROTON, VKD3D).
        install_dir: The directory where the tool is installed.
    """

    full_name: str
    tool_type: CompatToolType
    install_dir: Path


@dataclass
class ToolUpdate:
    """
    A compatibility tool that can be updated to a newer version.

    One ToolUpdate is created per (compatibility tool, architecture, build
    variant): the latest_version is the newest release that provides a build
    of the update's variant and architecture. When both architectures or both
    variants of a tool are installed, multiple updates are produced which may
    target different versions.

    Attributes:
        compat_tool_name: The name of the compatibility tool (CtInstaller.name).
        latest_version: The newest available version string that provides a
            build of the update's variant and architecture.
        installed_versions: The versions of the tool currently installed for
            the update's variant and architecture, as recorded in the tools'
            version files.
        installed_tools: The installed compatibility tools of the update's
            variant and architecture to be replaced.
        arch: The architecture this update applies to, or None to resolve
            the architecture during installation (host architecture if
            supported, else x86_64).
        variant: The build variant this update applies to, or an empty string
            for tools that do not ship multiple variants.
    """

    compat_tool_name: str
    latest_version: str
    installed_versions: list[str]
    installed_tools: list[CompatTool]
    arch: Arch | None = None
    variant: str = ""


@dataclass
class UpdateCheckResult:
    """
    Result of checking a launcher for available compatibility tool updates.

    Attributes:
        updates: Compatibility tools for which an update is available,
            including the latest available version.
        up_to_date: Names of compatibility tools that are already at the
            newest available version.
        unchecked: Names of installed tools for which no update check was
            possible (e.g. because no matching CtInstaller was found).
    """

    updates: list[ToolUpdate]
    up_to_date: list[str]
    unchecked: list[str]


@dataclass
class TranslationDetails:
    """
    Describes the game/host translation performed by a compatibility tool build.

    The "from" side is the guest software (e.g. Windows games) the tool runs,
    the "to" side is the host platform the tool runs on.

    Attributes:
        from_os: The guest operating system (e.g. "windows").
        from_arch: The guest architecture (e.g. "x86_64").
        to_os: The host operating system (e.g. "linux").
        to_arch: The host architecture (e.g. "aarch64").
    """

    from_os: str
    from_arch: str
    to_os: str
    to_arch: str


@dataclass
class CompatToolVersionInfo:
    """
    Metadata stored by protondl inside a compatibility tool's directory.

    Attributes:
        compat_tool: The name of the compatibility tool installer (CtInstaller.name).
        version: The installed version as returned by CtInstaller.fetch_releases.
        installed_at: UNIX timestamp (in seconds) when the tool was installed.
        arch: The architecture of the installed build, if known.
        translation_details: Details about the game/host translation performed
            by the installed build, if known.
    """

    compat_tool: str
    version: str
    installed_at: int
    arch: Arch | None = None
    translation_details: TranslationDetails | None = None


@dataclass
class ReleaseVersion:
    """
    A single release version and the architectures it ships.

    Attributes:
        version: The release version string (e.g. "GE-Proton11-3").
        archs: The architectures for which this release provides a build.
    """

    version: str
    archs: tuple[Arch, ...] = (Arch.X86_64,)


@dataclass
class ReleaseData:
    version: str
    date: str
    download: str | None = None
    size: int | None = None
    checksum: str | None = None
    original_filename: str | None = None


class GitHubWorkflowRun(TypedDict):
    """Represents a GitHub Actions workflow run associated with an artifact."""

    id: int
    head_sha: str


class GitHubArtifact(TypedDict):
    """Represents an artifact from a GitHub Actions workflow run."""

    name: str
    size_in_bytes: int
    updated_at: str
    workflow_run: GitHubWorkflowRun


class GitHubArtifactResponse(TypedDict):
    """Represents the response from the GitHub API when querying for artifacts."""

    total_count: int
    artifacts: list[GitHubArtifact]


class InstallStep(Enum):
    """The current step of a compatibility tool install or update."""

    FETCHING_RELEASE = "fetching release info"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying checksum"
    EXTRACTING = "extracting"
    FINISHING = "finalizing"
    COMPLETED = "installed"


@dataclass(frozen=True)
class InstallProgress:
    """
    A progress event reported during a compatibility tool install or update.

    Attributes:
        step: The current step of the operation.
        current: The progress within the step. For DOWNLOADING this is the number
            of bytes downloaded, for EXTRACTING the number of files extracted.
            0 for steps without measurable progress.
        total: The total of the step. 0 if the step's total is unknown.
        tool: The name of the tool being installed, set when the event is part
            of a multi-tool update run.
        tool_index: The 1-based index of the tool within an update run.
        tool_total: The total number of tools in the update run.
    """

    step: InstallStep
    current: int = 0
    total: int = 0
    tool: str | None = None
    tool_index: int = 0
    tool_total: int = 0


ProgressCallback = Callable[[InstallProgress], None]
