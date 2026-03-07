import os
from dataclasses import dataclass, field
from enum import Enum


class InstallMode(Enum):
    NATIVE = "native"
    FLATPAK = "flatpak"
    SNAP = "snap"


@dataclass
class RequestConfig:
    github_token: str | None = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))

    def get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        return headers
