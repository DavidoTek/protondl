# protondl

Welcome to the documentation of protondl, a modern, headless, and async-first Python library for downloading and managing Proton compatibility tools such as GE-Proton, Luxtorpeda, and Boxtron for Steam, Lutris, and other Linux game launchers.

## ✨ Features

- **Launcher Discovery**: Automatically detects Native, Flatpak, and Snap installations of Steam and other launchers.
- **Modular Architecture**: Easily extendable for new compatibility tools or launchers.
- **Async-First**: Built with httpx and asyncio for non-blocking downloads.
- **Headless by Design**: No Qt/GUI dependencies in the core library.
- **Modern Tooling**: Powered by uv, ruff, and mypy for a rock-solid developer experience.

### Supported Launchers

Tool Type | [Steam](https://store.steampowered.com/) | [Lutris](https://github.com/lutris/lutris) | [Heroic Games Launcher](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher)
----------|-------|--------|--------
⚛️ Proton | ✅    | ✅     | ✅
🍷 Wine   | ❌    | ✅     | ✅
🇽 VKD3D  | ❌    | ✅     | ✅
9️⃣ DXVK   | ❌    | ✅     | ✅

### Supported Tools

- [GE-Proton](https://github.com/GloriousEggroll/proton-ge-custom) (Proton)
- [Wine-Tkg](https://github.com/Frogging-Family/wine-tkg-git) (Wine)
- [Proton-Tkg](https://github.com/Frogging-Family/wine-tkg-git) (Proton)
- [DXVK](https://github.com/doitsujin/dxvk) (DXVK)
- [DXVK Async](https://gitlab.com/Ph42oN/dxvk-gplasync) (DXVK)
- [DXVK (nightly)](https://github.com/doitsujin/dxvk) (DXVK)
- [vkd3d-proton](https://github.com/HansKristian-Work/vkd3d-proton) (VKD3D)

### Comparison

Below, you can find a comparison chart of different compatibility tool installer tools.

Feature                        | protondl | ProtonUp-Qt[^1] | ProtonPlus[^2] | Protonup-rs[^3]
-------------------------------|----------|-----------------|----------------|------------
GUI                            | ⬜       | ✅              | ✅             | ⬜
CLI                            | ✅       | ⬜              | ⬜             | ✅
Library                        | ✅       | ⬜              | ⬜             | ✅
Install compatibility tools    | ✅       | ✅              | ✅             | ✅
Fetch available tool versions  | ✅       | ✅              | ✅             | ✅
List installed tools           | ✅       | ✅              | ✅             | ⬜
List installed games           | ✅       | ✅              | ✅             | ⬜
Get tool used by a game        | ✅       | ✅              | ✅             | ⬜
Set tool used by a game        | ✅       | ✅              | ✅             | ⬜
Show game SteamDeck rating     | ⬜       | ✅              | ⬜             | ⬜
Show game AWACY[^4] rating     | ⬜       | ✅              | ✅             | ⬜
Programming language           | Python   | Python          | Vala           | Rust
GUI/TUI                        | typer, rich | Qt           | GTK            | clap, indicatif

The table may be out-of-date. Please create an issue or pull request if that is the case.

[^1]: https://github.com/DavidoTek/ProtonUp-Qt
[^2]: https://github.com/Vysp3r/ProtonPlus
[^3]: https://github.com/auyer/Protonup-rs
[^4]: https://areweanticheatyet.com/
