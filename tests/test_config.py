from protondl.core.config import RequestConfig

GITHUB_ACCEPT = "application/vnd.github.v3+json"
GITLAB_ACCEPT = "application/json"


def _config(github: str = "gh-token", gitlab: str = "gl-token") -> RequestConfig:
    return RequestConfig(github_token=github, gitlab_token=gitlab)


def test_get_headers_github_host_sends_github_token() -> None:
    headers = _config().get_headers("https://api.github.com/repos/foo/bar/releases")

    assert headers == {
        "Accept": GITHUB_ACCEPT,
        "Authorization": "token gh-token",
    }


def test_get_headers_githubusercontent_host_sends_github_token() -> None:
    headers = _config().get_headers("https://raw.githubusercontent.com/foo/bar/main/x.tar.gz")

    assert headers == {
        "Accept": GITHUB_ACCEPT,
        "Authorization": "token gh-token",
    }


def test_get_headers_gitlab_host_sends_gitlab_token() -> None:
    headers = _config().get_headers("https://gitlab.com/api/v4/projects")

    assert headers == {
        "Accept": GITLAB_ACCEPT,
        "Authorization": "Bearer gl-token",
    }


def test_get_headers_gitlab_subdomain_sends_gitlab_token() -> None:
    headers = _config().get_headers("https://gitlab.example.gitlab.com/foo")

    assert headers == {"Accept": GITLAB_ACCEPT, "Authorization": "Bearer gl-token"}


def test_get_headers_github_host_does_not_send_gitlab_token() -> None:
    headers = _config().get_headers("https://api.github.com/repos/foo/bar/releases")

    assert "Bearer gl-token" not in headers.values()


def test_get_headers_gitlab_host_does_not_send_github_token() -> None:
    headers = _config().get_headers("https://gitlab.com/api/v4/projects")

    assert "token gh-token" not in headers.values()


def test_get_headers_unrelated_host_sends_no_token() -> None:
    for url in ("https://nightly.link/foo/bar/1234", "https://example.com/dl/x.tar.gz"):
        headers = _config().get_headers(url)

        assert headers == {"Accept": GITHUB_ACCEPT}


def test_get_headers_lookalike_host_sends_no_token() -> None:
    for url in ("https://notgitlab.com/foo", "https://evil-github.com/foo"):
        headers = _config().get_headers(url)

        assert headers == {"Accept": GITHUB_ACCEPT}


def test_get_headers_host_is_case_insensitive() -> None:
    headers = _config().get_headers("https://GITLAB.com/api/v4/projects")

    assert headers == {"Accept": GITLAB_ACCEPT, "Authorization": "Bearer gl-token"}


def test_get_headers_url_none_uses_github_style() -> None:
    headers = _config().get_headers()

    assert headers == {
        "Accept": GITHUB_ACCEPT,
        "Authorization": "token gh-token",
    }


def test_get_headers_no_tokens_omits_authorization() -> None:
    config = RequestConfig(github_token=None, gitlab_token=None)

    assert config.get_headers("https://api.github.com/repos/foo/bar") == {"Accept": GITHUB_ACCEPT}
    assert config.get_headers("https://gitlab.com/api/v4/projects") == {"Accept": GITLAB_ACCEPT}
