import os
from dataclasses import dataclass, field
from urllib.parse import urlparse


def _is_host(host: str, domain: str) -> bool:
    """
    Check if the given host is exactly the domain or one of its subdomains.

    Args:
        host: The (lowercased) host to check.
        domain: The domain to match against (e.g. "github.com").

    Returns:
        True if the host matches the domain or a subdomain of it.
    """
    return host == domain or host.endswith(f".{domain}")


@dataclass
class RequestConfig:
    github_token: str | None = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    gitlab_token: str | None = field(default_factory=lambda: os.getenv("GITLAB_TOKEN"))

    def get_headers(self, url: str | None = None) -> dict[str, str]:
        """
        Build the HTTP headers for a request to the given URL.

        The matching token is selected based on the host: the GitHub token is sent to
        GitHub hosts, the GitLab token to GitLab hosts. Tokens are never sent to
        unrelated hosts (e.g. download mirrors).

        Args:
            url: The request URL. If None, GitHub-style headers are used.

        Returns:
            dict[str, str]: The headers to send with the request.
        """
        if url is not None:
            host = urlparse(url).netloc.lower()
            is_github = _is_host(host, "github.com") or _is_host(host, "githubusercontent.com")
            is_gitlab = _is_host(host, "gitlab.com")
        else:
            is_github = is_gitlab = True

        headers: dict[str, str]
        if is_gitlab and not is_github:
            headers = {"Accept": "application/json"}
            if self.gitlab_token:
                headers["Authorization"] = f"Bearer {self.gitlab_token}"
        else:
            headers = {"Accept": "application/vnd.github.v3+json"}
            if is_github and self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
        return headers
