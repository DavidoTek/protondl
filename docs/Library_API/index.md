# Library Usage

This section documents protondl's library API interface.

protondl also provides a [CLI wrapper](../CLI/index.md) for the library API.
Please take a look at its implementation for reference usage of the library.

## Install from GitHub

Run the following command to install the latest version of protondl from GitHub.
This installs protondl *without* optional CLI dependencies (rich, typer).

```bash
pip install "protondl @ git+https://github.com/DavidoTek/protondl@main"
```

## Basics

### Fetch launchers and installed tools

The main method for interacting with launchers and installed compatibility tools, is via the Launcher implementations.
A Launcher object contains the launcher's name, install directory, and install mode (native, Flatpak, ...).
Each launcher inherits from the base Launcher class to implement the functionality for the specific launcher.
Below, you find the code for fetching a list of installed launchers and fetching installed compatibility tools for the first launcher.

```python
from protondl.cli.helpers import get_launchers

launchers = get_launchers()

for launcher in launchers:
    print(f"{launcher.name}: {str(launcher.root_path)}")

for tool in launchers[0].get_installed_tools():
    print(f"{tool.full_name}: {tool.install_dir}")
```

### List available compatibility tools

The next step is to determine which compatibility tools can be installed for a specific launcher.
The function `get_tools_for_launcher` returns all compatibility tools supported by the launcher.

```python
from protondl.installers import get_tools_for_launcher

compatible_tools = get_tools_for_launcher(launcher)

for tool_installer in compatible_tools:
    print(f"{tool_installer.name}: {tool_installer.description}")
```

### Fetch versions for a tool

Once we have decided which tool should be installed, we list available versions of the tool and install a version.

```python
versions = asyncio.run(tool_installer.fetch_releases(count=count, page=page))

print(f"Available versions of {tool_installer.name}: {versions}")

if not installer.supports_launcher(launchers[0]):
    exit()

asyncio.run(
    installer.install(
        versions[0],
        launchers[0],
        lambda p, t: print(f"Progress: {p} / {t}")  # Optional progress callback (current bytes, total size)
    )
)
```
