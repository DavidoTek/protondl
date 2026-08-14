# CLI Usage

This section documents protondl's command-line interface (CLI).

The CLI generates human-readable output. For integration into other tools, use the [Library API (Python)](../Library_API/index.md).

## Install from GitHub

Run the following command to install the latest version of protondl from GitHub.
This installs protondl, including optional dependencies ([rich](https://github.com/Textualize/rich), [typer](https://github.com/fastapi/typer)) required by the CLI.

```bash
pip install "protondl[cli] @ git+https://github.com/DavidoTek/protondl@main"
```

## Basics

Below is a documentation of basic commands.
Run the following command to get an overview of all commands:

```bash
protondl --help
```

### List installed launchers

Run the following command to list all installed launchers.
It will provide an overview, including the install mode (native, Flatpak, ...) and the launcher's root path.
Some commands require you to specify a launcher. Use the ID from the list to reference the launcher.

```bash
protondl list-launchers
```

After running the command, you should get an output like this:

```
                                        Detected Launchers                                        
┏━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID ┃ Launcher Name  ┃ Mode    ┃ Root Path                                                     ┃
┡━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1  │ Steam          │ native  │ /home/user/.local/share/Steam                                 │
│ 2  │ Lutris Flatpak │ flatpak │ /home/user/.var/app/net.lutris.Lutris/data/lutris             │
│ 3  │ Heroic Flatpak │ flatpak │ /home/user/.var/app/com.heroicgameslauncher.hgl/config/heroic │
└────┴────────────────┴─────────┴───────────────────────────────────────────────────────────────┘
```

### Target a custom launcher path

Commands that require a launcher accept either the ID from `list-launchers` or a `<type>:<path>` spec to target
a launcher installed at a non-standard location (e.g. a Steam installation in `~/mySteam` instead of
`~/.steam/root`). The supported types are `steam`, `lutris`, `heroic` and `bottles`.

```bash
protondl list-installed steam:~/mySteam
protondl install steam:~/mySteam GE-Proton GE-Proton10-10
```

Commands that read launcher data (e.g. `list-installed`, `list-games`) validate the path: it must exist
and look like a data directory of the given launcher type, otherwise the command fails with a clear
error. Only the `install` command accepts a path that does not exist yet; it creates the required
directories on demand.

### GitHub API Token

Many of the compatibility tools supported by protondl rely on GitHub for hosting their releases.
If you are installing many tools or use a shared internet connection, you may run into GitHub's API usage limit.
A way to circumvent this problem is to use an Access Token to identify with GitHub using your account.

See here for more information: [https://github.com/DavidoTek/ProtonUp-Qt/wiki/GitHub-and-GitLab-API-Tokens](https://github.com/DavidoTek/ProtonUp-Qt/wiki/GitHub-and-GitLab-API-Tokens)

You may specify your API token like this:

```bash
protondl --github-token <your GitHub token> install 1 GE-Proton GE-Proton10-10

# Alternative: Environmental variable
export GITHUB_TOKEN=<your GitHub token>
protondl install 1 GE-Proton GE-Proton10-10
```
