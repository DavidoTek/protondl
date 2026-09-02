# Manage Compatibility Tools (Library)

Managing compatibility tools is currently supported for the following launchers:
<span class="badge steam">Steam</span> <span class="badge lutris">Lutris</span>
<span class="badge heroic">Heroic</span> <span class="badge bottles">Bottles</span>

This page documents the API for fetching compatibility tools releases, installing tools, and updating tools.

## List available compatibility tools

After determining the available launchers, the next step is to determine which compatibility tools
can be installed for a specific launcher.
The function `get_tools_for_launcher` returns all compatibility tools supported by the launcher.

```python
from protondl.installers import get_tools_for_launcher

compatible_tools = get_tools_for_launcher(launchers[0])

for tool_installer in compatible_tools:
    print(f"{tool_installer.name}: {tool_installer.description}")
```

## Fetch versions for a tool and install

Once you pick an installer, fetch available versions and install one into a selected launcher.

```python
import asyncio
from protondl.installers import get_tools_for_launcher
from protondl.launchers import detect_all_launchers

launchers = detect_all_launchers()
if not launchers:
    raise RuntimeError("No supported launcher found")

compatible_tools = get_tools_for_launcher(launchers[0])
if not compatible_tools:
    raise RuntimeError("No installers available for selected launcher")

tool_installer = compatible_tools[0]

versions = asyncio.run(tool_installer.fetch_releases(count=30, page=1))

print(f"Available versions of {tool_installer.name}:")

for release in versions:
    print(f"  {release.version} ({', '.join(arch.value for arch in release.archs)})")

if not versions:
    raise RuntimeError("No releases returned")

if not tool_installer.supports_launcher(launchers[0]):
    raise RuntimeError("Selected launcher is not supported by this installer")

# Install the newest release for the given architecture.
# Omitting `arch` selects the host architecture if supported, else x86_64.
from protondl.core.models import Arch

asyncio.run(
    tool_installer.install(
        versions[0].version,
        launchers[0],
        arch=Arch.AARCH64,  # Optional
        # force=True removes an already installed build of the same version
        # and architecture before re-installing it (default: False)
        force=False,
        # Optional: receive step-based progress (fetch, download, verify, extract)
        progress_callback=lambda event: print(
            f"{event.step.value}: {event.current} / {event.total}"
        ),
        # Optional: a CancelToken to abort the download/extraction (see below)
        cancel_token=None,
    )
)
```

`fetch_releases()` returns a list of `ReleaseVersion` objects with a `version` string and an
`archs` tuple of `Arch` values. `install()` returns the `CompatToolVersionInfo` written to the
tool's `protondl_version.json`, which includes the installed architecture.

If the requested version and architecture are already installed for the launcher,
`install()` raises `AlreadyInstalledError` instead of downloading and extracting it
again. The check is architecture-aware, so installing a different architecture of an
already installed version is allowed. Pass `force=True` to remove the existing build
of the same version and architecture and re-install it.

For a complete workflow with launcher/tool selection, see the CLI implementation in `src/protondl/cli/main.py`.

### Threading and the progress callback

`install()` keeps the event loop responsive: the network download runs on the loop,
and the CPU/disk-bound work (checksum hashing, archive extraction, and the scans of
the launcher's installed-tool directories) is offloaded to a thread pool via
`asyncio.to_thread()`. You do not need to wrap `install()` yourself.

One consequence: `progress_callback` is invoked from a **worker thread** for the
`VERIFYING` and `EXTRACTING` steps, and from the calling thread for the others. The
callback must be thread-safe and must not block. A GUI callback must marshal the
update onto the UI thread (e.g. `GLib.idle_add` for GTK, a queued signal for Qt).
The same applies to `update_compatibility_tools()`.

### Cancelling an installation

Pass a `CancelToken` to `install()` to make a running installation abortable, e.g. from a
GUI's cancel button next to a progress bar.

```python
import asyncio
import threading

from protondl.core.models import CancelToken
from protondl.core.errors import InstallCancelledError

cancel_token = CancelToken()

# Cancel from anywhere - another thread, a signal handler, a GUI callback.
# Here: cancel automatically after 10 seconds.
threading.Timer(10.0, cancel_token.cancel).start()

try:
    asyncio.run(
        tool_installer.install(
            versions[0].version,
            launchers[0],
            progress_callback=lambda event: print(
                f"{event.step.value}: {event.current}/{event.total}"
            ),
            cancel_token=cancel_token,
        )
    )
except InstallCancelledError:
    print("Installation cancelled.")
```

Things to consider:

- Cancellation is **cooperative**: the token is checked between the install steps and during
  the two long-running steps - the download (before every downloaded chunk) and the
  extraction (before every extracted archive member). `cancel()` therefore takes effect
  within a fraction of a second, not instantly.
- On cancellation, the partially downloaded archive and any files already extracted into the
  launcher's compatibility tools directory are removed before `InstallCancelledError` is
  raised, so no half-installed tool is left behind.
- `CancelToken` is single use. Once `cancel()` has been called the token stays cancelled;
  create a new token for each installation.
- `cancel()` and the `cancelled` property are safe to call from a different thread than the
  one running `install()`.
- A token that is already cancelled when passed to `install()` aborts it before the release
  info is fetched.

## Automatic tool updates

protondl provides helper functions that check whether updates are available for currently installed
tools, installing the newest version of the tools and optionally removing old versions, and finally,
changing the compatibility tool a game uses to the latest installed version.

### Check for updates

`check_for_updates(launcher)` scans all compatibility tools installed for a launcher,
determines the corresponding `CtInstaller` for each of them, and fetches the newest
available version using that installer.

```python
import asyncio

from protondl.launchers import detect_all_launchers
from protondl.util.helpers import check_for_updates

launcher = detect_all_launchers()[0]

result = asyncio.run(check_for_updates(launcher))

for update in result.updates:
    print(
        f"{update.compat_tool_name}: "
        f"{', '.join(update.installed_versions)} -> {update.latest_version}"
    )

print(f"Could not check: {', '.join(result.unchecked)}")
```

The function is async and returns an `UpdateCheckResult` with three fields:

Field | Type | Description
------|------|------------
`updates` | `list[ToolUpdate]` | A list of `ToolUpdate` objects, one per (compatibility tool, architecture, build variant) that has an available update. Each entry contains the tool name (`compat_tool_name`), the newest available version providing that architecture and variant (`latest_version`), the currently installed versions of that architecture and variant (`installed_versions`), the installed `CompatTool` objects (`installed_tools`), the architecture (`arch`), and the build variant (`variant`).
`up_to_date` | `list[str]` | A list of compatibility tools that are already at the newest available version. Tools providing multiple architectures or build variants are labeled with them (e.g. `GE-Proton (x86_64)`, `GE-Proton (x86_64) (fshack)`).
`unchecked` | `list[str]` | A list of names of installed tools for which no update check was possible.

Things to consider:

- Only tools that carry a `protondl_version.json` file (i.e. tools installed by protondl)
  can be checked. All other installed tools are reported in `unchecked`.
- Installed tools are grouped by compatibility tool class, architecture and build
  variant. For each (architecture, variant) combination the release history is walked
  back (up to a few pages) until a release providing a build of that variant and
  architecture is found. The architecture is taken from the tool's version file (`arch`,
  falling back to its translation details), and finally from the installer's default
  resolution.
- A release may only ship a subset of a tool's architectures (e.g. an architecture-specific
  patch). The newest release for each architecture is therefore determined independently,
  so the two architectures of one tool can be updated to *different* versions when the
  newest release does not provide both.
- Tools that ship multiple build variants per architecture (e.g. fshack or wow64 builds)
  are handled the same way: each installed variant is updated to the newest release that
  provides it, so the variants of a tool may also be updated to different versions.
- The release history is fetched once per compatibility tool class; it is only paginated
  further when an installed (architecture, variant) combination has not found a matching
  release yet.
- If fetching the newest version fails (e.g. the remote API is unreachable), the affected
  tools are reported in `unchecked` instead of raising.
- Pass an optional `RequestConfig` as `request_config` to authenticate API requests and
  raise the rate limits (see [API tokens](#api-tokens)). A `RequestConfig()` created
  without arguments picks up the `GITHUB_TOKEN` and `GITLAB_TOKEN` environment variables
  automatically; an explicitly passed config takes precedence.

### Install updates

`update_compatibility_tools(launcher, updates)` installs the newest version of each
compatibility tool in the given list of updates. The list returned by
`check_for_updates()` can be passed directly.

```python
import asyncio

from protondl.launchers import detect_all_launchers
from protondl.util.helpers import check_for_updates, update_compatibility_tools

launcher = detect_all_launchers()[0]
result = asyncio.run(check_for_updates(launcher))

asyncio.run(
    update_compatibility_tools(
        launcher,
        result.updates,
        keep_old=False,
        progress_callback=lambda event: print(
            f"[{event.tool_index}/{event.tool_total}] {event.tool}: "
            f"{event.step.value} {event.current}/{event.total}"
        ),
    )
)
```

The function is async and accepts the following arguments:

Argument | Type | Description
---------|------|------------
`launcher` | `Launcher` |  The launcher the tools are installed for.
`updates` | `list[ToolUpdate]` |  The `ToolUpdate` list from `check_for_updates()`.
`keep_old` | `bool` |  Whether to keep older versions of the tools. If `False` (the default), all older versions are deleted after the new version was installed successfully.
`progress_callback` | `ProgressCallback \| None` |  An optional callback receiving `InstallProgress` events for the currently installed tool. Each event carries the current `step` (`InstallStep`: fetching release info, downloading, verifying checksum, extracting, finalizing, installed) with the progress within that step (`current`/`total`, e.g. downloaded bytes or extracted files), plus the tool's name and its index within the update run (`tool`, `tool_index`, `tool_total`). A `COMPLETED` step with `tool_index`/`tool_total` marks a tool as fully processed (after old versions were removed). As with `install()`, `VERIFYING`/`EXTRACTING` events are delivered from a worker thread (see [Threading and the progress callback](#threading-and-the-progress-callback)).
`request_config` | `RequestConfig \| None` |  An optional `RequestConfig` for authenticated API requests. Takes precedence over the `GITHUB_TOKEN`/`GITLAB_TOKEN` environment variables; see [API tokens](#api-tokens).
`cancel_token` | `CancelToken \| None` |  An optional `CancelToken` to abort the update run. It is checked before each tool and forwarded to the running `install()` (see [Cancelling an installation](#cancelling-an-installation)), so a cancel also takes effect during the current download or extraction. Raises `InstallCancelledError` when cancelled.

Things to consider:

- Each update is installed for its own architecture (`ToolUpdate.arch`) and build variant
  (`ToolUpdate.variant`), i.e. the architecture and variant of the installed builds it
  replaces. When both architectures or both variants of a tool are installed and updated,
  multiple builds (one per combination) are installed, possibly at different versions.
- The function returns a dict mapping `(compat_tool_name, arch, variant)` to the newly
  installed `CompatTool` for every update whose installation directory could be determined.
  Use these to point games at the new build (see `batch_update_games_tools()` below).
- If `keep_old=False`, the old versions are deleted. Games of the launcher that still
  reference an old version would then point to a missing tool, so follow up with
  `batch_update_games_tools()` (see below). With `keep_old=True` the batch update is
  optional because the old versions remain usable.
- A `ValueError` is raised if no `CtInstaller` exists for one of the tools.
- When cancelled through `cancel_token`, tools already updated before the cancel stay
  installed, the current tool's partial download and extraction are cleaned up, and
  `InstallCancelledError` propagates out of `update_compatibility_tools()`.

### Batch update games

`batch_update_games_tools(launcher, from_tool, to_tool)` changes the compatibility tool
of all games that currently use `from_tool` to `to_tool`.

```python
from protondl.launchers import detect_all_launchers
from protondl.util.helpers import batch_update_games_tools

launcher = detect_all_launchers()[0]

new_tool = next(
    tool for tool in launcher.get_installed_tools() if tool.full_name == "GE-Proton11-3"
)

# Match all games whose compatibility tool name contains "GE-Proton"
count = batch_update_games_tools(launcher, "GE-Proton", new_tool)
print(f"Updated {count} games")
```

`from_tool` can be:

- A `CompatTool` instance to match games using that exact tool, or
- A string to match all games whose tool name contains the string (e.g. `"GE-Proton"`
  matches every installed GE-Proton version).

The function returns the number of games that were updated. It raises a `RuntimeError`
if updating the games' compatibility tools failed (e.g. for launchers that do not
implement `set_games_tools()`, such as Lutris).

### End-to-end example

The following example combines all three functions to update every compatibility tool of
a launcher and move all games to the newest versions:

```python
import asyncio

from protondl.launchers import detect_all_launchers
from protondl.util.helpers import (
    batch_update_games_tools,
    check_for_updates,
    update_compatibility_tools,
)


async def main() -> None:
    launcher = detect_all_launchers()[0]

    # 1. Check which compatibility tools can be updated
    result = await check_for_updates(launcher)

    if result.unchecked:
        print(f"Could not check: {', '.join(result.unchecked)}")

    if result.up_to_date:
        print(f"Up to date: {', '.join(result.up_to_date)}")

    if not result.updates:
        print("No updates available.")
        return

    # 2. Install the newest versions and delete the old ones
    def on_progress(event) -> None:
        print(
            f"[{event.tool_index}/{event.tool_total}] {event.tool}: "
            f"{event.step.value} {event.current}/{event.total}"
        )

    new_tools = await update_compatibility_tools(
        launcher, result.updates, keep_old=False, progress_callback=on_progress
    )

    # 3. Point all games to the newest version. As the old versions were deleted
    #    in step 2, games still referencing them would break without this step.
    #    Each update is migrated to its own architecture- and variant-specific new build.
    for update in result.updates:
        new_tool = new_tools.get((update.compat_tool_name, update.arch, update.variant))
        if new_tool is None:
            print(f"Could not find the newly installed {update.compat_tool_name}; skipping")
            continue
        for old_tool in update.installed_tools:
            count = batch_update_games_tools(launcher, old_tool, new_tool)
            print(f"Updated {count} games to {new_tool.full_name}")


asyncio.run(main())
```

The three functions play together as follows: `check_for_updates()` determines *what*
can be updated and returns the `ToolUpdate` list. `update_compatibility_tools()`
installs those updates, and optionally removes the old versions. `batch_update_games_tools()`
then reconciles the games with the new state. When old versions are deleted
(`keep_old=False`), running the batch update is strongly recommended so that no game
references a deleted tool.

The user should be presented with a list of available updates and for which compatibility tools no
updates could be fetched. The user should optionally be able to select which of the compatibility
tools should be updated. Furthermore, the user should have the choice whether old compatibility
tools are deleted and whether a batch update for the installed games should be performed.

## API tokens

protondl queries GitHub's API to fetch releases and artifacts.
Unauthenticated requests are subject to API rate limits; a token raises them.

API requests are configured via a `RequestConfig`:

- `RequestConfig()` reads the `GITHUB_TOKEN` and `GITLAB_TOKEN` environment variables automatically.
- `RequestConfig(github_token="...", gitlab_token="...")` sets the tokens explicitly.

The token is only sent to the matching host, as an `Authorization` header (`token ...` for GitHub,
`Bearer ...` for GitLab). Set it via an environment variable:

```bash
export GITHUB_TOKEN=<your GitHub token>
export GITLAB_TOKEN=<your GitLab token>
```

or directly in code:

```python
import asyncio

from protondl.core.config import RequestConfig

config = RequestConfig(github_token="<your GitHub token>")

# For tool installers:
installer.request_config = config  # used by fetch_releases()/install()

# For the update helpers:
result = asyncio.run(check_for_updates(launcher, request_config=config))
```
