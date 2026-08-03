# TUI Usage

protondl ships a small terminal user interface (TUI) built on [Textual](https://textual.textualize.io/).
It offers a mouse- and keyboard-driven way to manage compatibility tools without having to type commands.

## Install

The TUI is an optional extra. Install it together with the [CLI dependencies](./index.md#install-from-github):

```bash
pip install "protondl[tui] @ git+https://github.com/DavidoTek/protondl@main"
```

## Start

```bash
protondl-tui
```

## Layout

The main screen shows a launcher dropdown, the list of compatibility tools installed for the
selected launcher, and buttons to remove or add tools.

```
┌──────────────────────────────────────────────────────────────┐
│ ■ protondl — Compatibility Tool Manager                      │
├──────────────────────────────────────────────────────────────┤
│ Launcher: [ ▼ Steam (native)                 ]               │
│                                                              │
│ Installed compatibility tools                                │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ GE-Proton10-13               proton                      │ │
│ │ vkd3d-proton-2.16            vkd3d                       │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│     [ ✕ Remove selected ]      [ + Add new tool ]            │
├──────────────────────────────────────────────────────────────┤
│ q quit │ tab cycle │ enter select                            │
└──────────────────────────────────────────────────────────────┘
```

## Features

- **Selecting a launcher**: Pick a detected launcher from the dropdown to list its installed
  compatibility tools. The list refreshes automatically when the launcher changes.
- **Removing a tool**: Select an installed tool in the list and press *Remove selected*.
  A confirmation dialog asks before the tool is deleted.
- **Adding a tool**: Press *Add new tool* to open a dialog. Select the compatibility tool and
  the version to install, then press *Install*. The download and extraction progress is shown
  in the dialog, and the installed-tools list refreshes once the installation finishes.

## Key bindings

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Cycle focus between widgets |
| `Enter` | Activate the focused widget / select |
| `Esc` | Close the current dialog |
| `q` | Quit the TUI |
| `Ctrl+R` | Refresh the installed-tools list |

## GitHub API Token

Fetching tool versions relies on the GitHub API. If you hit the API rate limit, provide a token
via the `GITHUB_TOKEN` environment variable as described in the
[CLI docs](./index.md#github-api-token).
