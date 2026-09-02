# Manage Tools

A core functionality of protondl is management of compatibility tools.

Managing tools is currently supported for the following launchers: <span class="badge steam">Steam</span> <span class="badge lutris">Lutris</span> <span class="badge heroic">Heroic</span> <span class="badge bottles">Bottles</span>

All commands below take a launcher argument, written as `<launcher>`. It accepts either the numeric ID of a
detected launcher from [`list-launchers`](./index.md#list-installed-launchers) or a `<type>:<path>` spec to
target a launcher at a custom installation path (see [Target a custom launcher path](./index.md#target-a-custom-launcher-path)).


## List tools available for a specific launcher

Run the following commands to list all compatibility tools supported by a specific launcher.

```bash
protondl list-tools <launcher>
```

The commands returns a list of supported compatibility tools, a description, and a URL with more information about the specific tool.
It also contains an ID for each compatibility tool, required by other commands.

## Fetch available tool versions

Before installing a compatibility tool, you may want to list available versions.
You need to provide either the tool name or the numeric tool ID from [`list-tools`](#list-tools-available-for-a-specific-launcher).

```bash
protondl list-versions <tool id or name>

# Optional pagination
protondl list-versions GE-Proton --count 30 --page 1
```

Tools that provide builds for multiple architectures (e.g. GE-Proton ships `x86_64`
and `aarch64` builds) show an additional `Architectures` column with a comma-separated
list of the architectures each version provides.

You can restrict the output to versions shipping a specific architecture:

```bash
protondl list-versions GE-Proton --arch aarch64
```

Passing an architecture that the tool does not support at all (e.g. `--arch aarch64`
for an x86_64-only tool) results in an error.

## Installing a compatibility tool

To install a compatibility tool for a launcher, run the following command.
You need to specify the launcher ID and compatibility tool ID or name, then the exact version string.

```bash
protondl install <launcher> <tool id/name> <tool version name>

# Example
protondl install 1 GE-Proton GE-Proton10-10
```

By default protondl installs a build matching the architecture of the current host,
falling back to `x86_64` if the tool does not provide a build for the host architecture.
Use `--arch` to select a specific architecture:

```bash
protondl install 1 GE-Proton GE-Proton11-3 --arch aarch64
```

If the requested architecture is not available for the tool, the installation fails
with an error. After a successful installation, the CLI prints the installed
architecture (e.g. `Successfully installed GE-Proton (aarch64)!`).

If the requested version and architecture are already installed, the installation
is skipped and protondl prints a notice (e.g. `GE-Proton11-3 (x86_64) is already
installed.`), exiting with code 2. The check is architecture-aware: an x86_64 and
an aarch64 build of the same version are independent, so installing the other
architecture is allowed.

Use `--force` (or `-f`) to re-install a version that is already installed. This
removes the existing build of the same version and architecture before
downloading and extracting it again:

```bash
protondl install 1 GE-Proton GE-Proton11-3 --arch aarch64 --force
```

When protondl installs a compatibility tool, it writes a `protondl_version.json` file into the
tool's folder that stores metadata about the installation, including the compatibility tool's
name, version, install timestamp, and the installed architecture with translation details.
See the [Library API](../Library_API/10_launcher_api.md#protondl_versionjson) docs for details.

Press `Ctrl+C` during the download or extraction to cancel the installation. protondl removes
the partially downloaded archive and any files already extracted, so no half-installed tool is
left behind, prints `Installation cancelled.` and exits with code 130. Cancellation is
cooperative and takes effect within a fraction of a second; press `Ctrl+C` a second time to
abort immediately without cleanup.

## List installed compatibility tools

If you want to see, which compatibility tools are installed for a specific launcher, run the following command:

```bash
protondl list-installed <launcher>
```

## Remove an installed compatibility tool

To remove a compatibility tool from a launcher, specify the launcher ID and the tool's index
from [`list-installed`](#list-installed-compatibility-tools) or its exact name.

```bash
protondl remove <launcher> <tool index or name>

# Examples
protondl remove 1 GE-Proton10-12
protondl remove 1 2
```

Removal is immediate and does not ask for confirmation.
Tools that are managed by the launcher itself (e.g. Proton installed as a Steam app) cannot be
removed and are rejected with an error message.

## Set global compatibility tool

Set the launcher's global/default compatibility tool using a tool name or the index from `list-installed`.

```bash
protondl set-global-tool <launcher> <tool name or index>

# Examples
protondl set-global-tool 1 GE-Proton10-10
protondl set-global-tool 1 2
```

Global tool configuration is currently implemented for Steam launchers.

## Update all compatibility tools

Check all installed compatibility tools of a launcher for updates and install them:

```bash
protondl update-all <launcher>
```

The command lists the available updates in a table with the architecture, the installed
versions and the latest version of each compatibility tool, then asks for confirmation
before installing. Compatibility tools that are already at the newest version are shown
as up to date. After a successful update it asks whether the compatibility tool of all
games should be switched to the newest version.

Updates are checked per (compatibility tool, architecture, build variant): each installed
architecture and variant is updated to the newest release that provides a build for it, so
the two architectures or variants of a tool can be updated to different versions when the
newest release only ships some of them. Games are moved to the new build of the same
architecture and variant.

By default, older versions of a compatibility tool are deleted after the new version was
installed successfully and the batch update of all games runs without asking.
The behavior can be adjusted with the following options:

```bash
# Keep older versions of the compatibility tools and ask before the batch update
protondl update-all 1 --keep-old

# Run the whole update without any prompts
protondl update-all 1 --yes-install --yes-batch-update

# Skip only the install confirmation
protondl update-all 1 --yes-install
```

Options:

- `--keep-old`: Keep older versions of the compatibility tools instead of deleting them.
- `--yes-install`: Install all available updates without prompting.
- `--yes-batch-update`: Update the compatibility tool of all games without prompting.

Note: Tools that could not be mapped to an installer (e.g. tools not installed by protondl)
are reported but skipped.

Press `Ctrl+C` while the tools are being updated to cancel the run. Tools already updated
before the cancel stay installed, the current tool's partial download and extraction are
cleaned up, and protondl prints `Update cancelled.` and exits with code 130 without running
the batch update of games. Press `Ctrl+C` a second time to abort immediately.
