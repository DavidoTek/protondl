# Manage Compatibility Tools (Library)

Managing compatibility tools is currently supported for the following launchers:
<span class="badge steam">Steam</span> <span class="badge lutris">Lutris</span>
<span class="badge heroic">Heroic</span> <span class="badge bottles">Bottles</span>

This page documents the high-level helpers for updating compatibility tools:
`check_for_updates()`, `update_compatibility_tools()`, and `batch_update_games_tools()`.
All three live in `protondl.util.helpers`.

## Check for updates

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

- `updates`: A list of `ToolUpdate` objects, one per compatibility tool class that has
  an available update. Each entry contains the tool name (`compat_tool_name`), the newest
  available version (`latest_version`), the currently installed versions
  (`installed_versions`), and the installed `CompatTool` objects (`installed_tools`).
- `up_to_date`: A list of names of compatibility tools that are already at the newest
  available version.
- `unchecked`: A list of names of installed tools for which no update check was possible.

Things to consider:

- Only tools that carry a `protondl_version.json` file (i.e. tools installed by protondl)
  can be checked. All other installed tools are reported in `unchecked`.
- Multiple installed versions of the same tool class are grouped, and the newest version
  is fetched only once per tool class.
- If fetching the newest version fails (e.g. the remote API is unreachable), the affected
  tools are reported in `unchecked` instead of raising.
- Pass an optional `RequestConfig` (e.g. configured with a GitHub token) as
  `request_config` to authenticate API requests and raise the rate limits. A
  `RequestConfig()` created without arguments picks up the `GITHUB_TOKEN` environment
  variable automatically.

## Install updates

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
        progress_callback=lambda completed, total: print(f"{completed} of {total}"),
    )
)
```

The function is async and accepts the following arguments:

- `launcher`: The launcher the tools are installed for.
- `updates`: The `ToolUpdate` list from `check_for_updates()`.
- `keep_old`: Whether to keep older versions of the tools. If `False` (the default),
  all older versions are deleted after the new version was installed successfully.
- `progress_callback`: An optional callback receiving the number of completed tools and
  the total number of tools to update.
- `request_config`: An optional `RequestConfig` for authenticated API requests.

Things to consider:

- Each compatibility tool is installed using the architecture resolved from the host
  system (same behavior as `CtInstaller.install()`).
- If `keep_old=False`, the old versions are deleted. Games of the launcher that still
  reference an old version would then point to a missing tool, so follow up with
  `batch_update_games_tools()` (see below). With `keep_old=True` the batch update is
  optional because the old versions remain usable.
- A `ValueError` is raised if no `CtInstaller` exists for one of the tools.

## Batch update games

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

## End-to-end example

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
    def on_progress(completed: int, total: int) -> None:
        print(f"Updated {completed} of {total} compatibility tools")

    await update_compatibility_tools(
        launcher, result.updates, keep_old=False, progress_callback=on_progress
    )

    # 3. Point all games to the newest version. As the old versions were deleted
    #    in step 2, games still referencing them would break without this step.
    installed_tools = launcher.get_installed_tools()
    for update in result.updates:
        new_tool = next(tool for tool in installed_tools if tool.full_name == update.latest_version)
        count = batch_update_games_tools(launcher, update.compat_tool_name, new_tool)
        print(f"Updated {count} games to {update.latest_version}")


asyncio.run(main())
```

The three functions play together as follows: `check_for_updates()` determines *what*
can be updated and returns the `ToolUpdate` list. `update_compatibility_tools()`
installs those updates, and optionally removes the old versions. `batch_update_games_tools()`
then reconciles the games with the new state. When old versions are deleted
(`keep_old=False`), running the batch update is strongly recommended so that no game
references a deleted tool.
