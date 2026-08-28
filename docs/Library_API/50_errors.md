# Errors

Every error protondl raises on purpose derives from a single base class,
`ProtondlError`, defined in `protondl.core.errors`. A consumer (CLI, GUI, script)
can catch that one class to handle "anything protondl did wrong", or catch a more
specific subclass to react to an individual failure mode.

```python
from protondl.core.errors import ProtondlError, NoInternetConnectionError

try:
    await installer.install(version, launcher)
except NoInternetConnectionError:
    ...  # show "you are offline"
except ProtondlError as e:
    ...  # generic "install failed: {e}"
```

## Hierarchy

```
ProtondlError
├── NetworkError
│   ├── NoInternetConnectionError   # no connection, DNS failure, timeout
│   ├── LinkNotFoundError           # release/tag/asset/URL missing (HTTP 404); also ValueError
│   ├── APIRateLimitError           # GitHub/GitLab API rate limit hit (HTTP 403/429)
│   └── DownloadError               # other HTTP failures (5xx, malformed response)
├── FileSystemError
│   ├── NoWritePermissionError      # target dir/file not writable; also PermissionError
│   └── NoDiskSpaceError            # filesystem full (ENOSPC); also OSError
├── ChecksumMismatchError           # downloaded archive failed checksum; also ValueError
├── ArchiveExtractionError          # archive missing/corrupt/unextractable
├── InstallCancelledError           # a CancelToken aborted the operation
└── AlreadyInstalledError           # version+arch already installed and force=False
```

Some classes also inherit from a matching built-in exception (`ValueError`,
`PermissionError`, `OSError`) so that code written against the standard library
keeps working.

## Which functions raise what

| Operation | Can raise |
|-----------|-----------|
| `CtInstaller.fetch_releases()` | `NoInternetConnectionError`, `LinkNotFoundError`, `APIRateLimitError`, `DownloadError` |
| `CtInstaller.install()` | all of the above, plus `ChecksumMismatchError`, `ArchiveExtractionError`, `NoWritePermissionError`, `NoDiskSpaceError`, `AlreadyInstalledError`, `InstallCancelledError`, `ValueError` (bad version / unsupported arch) |
| `CtInstaller.remove()` / `Launcher.remove_tool()` | `FileNotFoundError`, `NoWritePermissionError`, `ValueError` (Steam-managed / outside tools dir) |
| `check_for_updates()` | *nothing* — network/API failures are reported in `UpdateCheckResult.unchecked` |
| `update_compatibility_tools()` | everything `install()` can raise, plus `ValueError` if a tool has no installer |
| `batch_update_games_tools()` / `Launcher.set_games_tools()` | `RuntimeError` if the launcher cannot set game tools |
| `Launcher.get_game_list()` | `ValueError` if the launcher's config/game data cannot be loaded |

## External services

The `protondl.services` package (AWACY, ProtonDB) deliberately surfaces
`httpx.HTTPError` and `ValueError` directly rather than wrapping them, since those
integrations are optional and often used with a caller-provided `httpx` client.
See each function's `Raises:` section. The batch helper `fetch_protondb_tiers()`
never raises for per-game lookup failures; it maps them to `None`.
