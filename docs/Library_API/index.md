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

## API sections

- [Launcher API](10_launcher_api.md): Discover launchers, detect/delete installed tools.
- [Manage Tools API](20_manage_tools_api.md): Install and update compatibility tools.
- [Manage Games API](30_manage_games_api.md): List installed games, set tool a game uses.
- [External Services API](40_external_services_api.md): Interface AWACY and ProtonDB.
- [Errors](50_errors.md): The exception hierarchy raised by the library.
