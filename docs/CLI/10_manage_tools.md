# Manage Tools

A core functionality of protondl is management of compatibility tools.

Managing tools is currently supported for the following launchers: <span class="badge steam">Steam</span> <span class="badge lutris">Lutris</span> <span class="badge heroic">Heroic</span>


## List tools available for a specific launcher

Run the following commands to list all compatibility tools supported by a specific launcher.
Replace `<launcher id>` with the ID of the launcher from [`list-launchers`](./index.md#list-installed-launchers).

```bash
protondl list-tools <launcher id>
```

The commands returns a list of supported compatibility tools, a description, and a URL with more information about the specific tool.
It also contains an ID for each compatibility tool, required by other commands.

## Fetch available tool versions

Before installing a compatibility tool, you may want to list available versions.
You need to provide the tool ID from the [`list-tools` command](#list-tools-available-for-a-specific-launcher)

```bash
protondl list-versions <tools id>
```

## Installing a compatibility tool

To install a compatibility tool for a launcher, run the following command.
You need to specify the launcher ID and compatibility tool ID or name.

```bash
protondl install <launcher id> <tool id/name> <tool version name>

# Example
protondl install 1 GE-Proton GE-Proton10-10
```

## List installed compatibility tools

If you want to see, which compatibility tools are installed for a specific launcher, run the following command:

```bash
protondl list-installed <launcher id>
```
