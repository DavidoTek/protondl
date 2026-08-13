from rich.console import Console
from typer import Option, Typer

from protondl.core.config import RequestConfig

app = Typer(help="Proton Compatibility Tool Manager")
state = {"request_config": RequestConfig()}
console = Console()


@app.callback()
def main(
    github_token: str | None = Option(
        None, "--github-token", "-t", help="GitHub API Token", envvar="GITHUB_TOKEN"
    ),
    gitlab_token: str | None = Option(
        None, "--gitlab-token", help="GitLab API Token", envvar="GITLAB_TOKEN"
    ),
) -> None:
    """
    protondl compatibility tool downloader.
    """
    state["request_config"] = RequestConfig(github_token=github_token, gitlab_token=gitlab_token)
