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

### Discover launchers and list installed tools

The main entrypoint for launcher discovery is `detect_all_launchers()`.
Each launcher object contains the launcher name, install directory, and install mode (native, flatpak, ...).
You can then query installed compatibility tools directly from the launcher instance.

```python
from protondl.launchers import detect_all_launchers

launchers = detect_all_launchers()

if not launchers:
    raise RuntimeError("No supported launcher found")

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

compatible_tools = get_tools_for_launcher(launchers[0])

for tool_installer in compatible_tools:
    print(f"{tool_installer.name}: {tool_installer.description}")
```

### Fetch versions for a tool and install

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

print(f"Available versions of {tool_installer.name}: {versions}")

if not versions:
    raise RuntimeError("No releases returned")

if not tool_installer.supports_launcher(launchers[0]):
    raise RuntimeError("Selected launcher is not supported by this installer")

asyncio.run(
    tool_installer.install(
        versions[0],
        launchers[0],
        lambda p, t: print(f"Progress: {p} / {t}")  # Optional progress callback (current bytes, total size)
    )
)
```

For a complete workflow with launcher/tool selection, see the CLI implementation in `src/protondl/cli/main.py`.

## API sections

- [Manage Games](20_manage_games_api.md)
- [Launchers](30_launcher_api.md)
- [External Services](40_external_services_api.md)
