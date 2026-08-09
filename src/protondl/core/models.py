import os
from dataclasses import dataclass, field
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
class RequestConfig:
    github_token: str | None = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))

    def get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        return headers


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
