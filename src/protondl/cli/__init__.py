import logging

from rich.console import Console
from rich.logging import RichHandler
from typer import Option, Typer

from protondl.core.config import RequestConfig

app = Typer(help="Proton Compatibility Tool Manager")
state = {"request_config": RequestConfig()}
console = Console()


def _configure_logging(*, verbose: bool, quiet: bool) -> None:
    level = logging.WARNING
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.ERROR

    logger = logging.getLogger("protondl")
    logger.setLevel(level)
    logger.handlers = [h for h in logger.handlers if not isinstance(h, RichHandler)]
    logger.addHandler(RichHandler(console=console, show_time=False, show_path=False, markup=True))


@app.callback()
def main(
    github_token: str | None = Option(
        None, "--github-token", "-t", help="GitHub API Token", envvar="GITHUB_TOKEN"
    ),
    gitlab_token: str | None = Option(
        None, "--gitlab-token", help="GitLab API Token", envvar="GITLAB_TOKEN"
    ),
    verbose: bool = Option(False, "--verbose", "-v", help="Enable debug logging"),
    quiet: bool = Option(False, "--quiet", "-q", help="Only show error logging"),
) -> None:
    """
    protondl compatibility tool downloader.
    """
    _configure_logging(verbose=verbose, quiet=quiet)
    state["request_config"] = RequestConfig(github_token=github_token, gitlab_token=gitlab_token)
