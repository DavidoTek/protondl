# Launchers (Library)

## Get and set global compatibility tools

Get the global compatibility tool for a launcher using `get_global_tool()`.
This returns the default compatibility tool that applies to all games unless they have a game-specific override.
Set a new global tool using `set_global_tool()`.

```python
from protondl.launchers.steam import SteamLauncher
from protondl.core.models import CompatToolType

launcher = SteamLauncher.discover()[0]

# Get the current global Proton tool
current_tool = launcher.get_global_tool(CompatToolType.PROTON)
if current_tool:
    print(f"Global tool: {current_tool.full_name}")
else:
    print("No global tool set")

# Set a new global tool
available_tools = launcher.get_installed_tools([CompatToolType.PROTON])
if available_tools:
    launcher.set_global_tool(available_tools[0])
```
