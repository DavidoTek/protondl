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
