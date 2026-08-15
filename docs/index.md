# protondl

Welcome to the documentation of protondl, a modern, headless, and async-first Python library for downloading and managing compatibility tools such as GE-Proton, Proton-Tkg, DXVK, and vkd3d-proton for Steam, Lutris, Heroic, Bottles, and other Linux game launchers.

## ✨ Features

- **Launcher Discovery**: Automatically detects Native, Flatpak, and Snap installations of Steam and other launchers.
- **Modular Architecture**: Easily extendable for new compatibility tools or launchers.
- **Async-First**: Built with httpx and asyncio for non-blocking downloads.
- **Headless by Design**: No Qt/GUI dependencies in the core library.
- **Modern Tooling**: Powered by uv, ruff, and mypy for a rock-solid developer experience.

### Supported Launchers

Tool Type | [Steam](https://store.steampowered.com/) | [Lutris](https://github.com/lutris/lutris) | [Heroic Games Launcher](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher) | [Bottles](https://usebottles.com/)
----------|-------|--------|--------|--------
⚛️ Proton | ✅    | ✅     | ✅     | ✅
🍷 Wine   | ❌    | ✅     | ✅     | ✅
🇽 VKD3D  | ❌    | ✅     | ✅     | ❌
9️⃣ DXVK   | ❌    | ✅     | ✅     | ❌

### Supported Tools

- [GE-Proton](https://github.com/GloriousEggroll/proton-ge-custom) (Proton)
- [Proton-Tkg](https://github.com/Frogging-Family/wine-tkg-git) (Proton)
- [Proton-Tkg (Wine Master)](https://github.com/Frogging-Family/wine-tkg-git) (Proton)
- [Proton-Tkg (Valve Wine)](https://github.com/Frogging-Family/wine-tkg-git) (Proton)
- [Proton-Tkg (Wine Master NTSYNC)](https://github.com/Frogging-Family/wine-tkg-git) (Proton)
- [Wine-Tkg (Wine Master)](https://github.com/Frogging-Family/wine-tkg-git) (Wine)
- [Boxtron](https://github.com/dreamer/boxtron) (Proton)
- [Roberta](https://github.com/dreamer/roberta) (Proton)
- [Proton-EM](https://github.com/Etaash-mathamsetty/Proton) (Proton)
- [RTSP Proton](https://github.com/SpookySkeletons/proton-ge-rtsp) (Proton)
- [Lutris-Wine](https://github.com/lutris/wine) (Wine)
- [Kron4ek Wine-Builds Vanilla](https://github.com/Kron4ek/Wine-Builds) (Wine)
- [DXVK](https://github.com/doitsujin/dxvk) (DXVK)
- [DXVK Async](https://gitlab.com/Ph42oN/dxvk-gplasync) (DXVK)
- [DXVK (nightly)](https://github.com/doitsujin/dxvk) (DXVK)
- [vkd3d-proton](https://github.com/HansKristian-Work/vkd3d-proton) (VKD3D)
- [vkd3d-lutris](https://github.com/lutris/vkd3d) (VKD3D)

### Current Scope

- Launcher discovery: Steam, Lutris, Heroic, and Bottles (native/flatpak; Steam also snap).
- Tool management (install/list tools): Steam, Lutris, Heroic, and Bottles.
- Game management (list games, set game tools, Steam Deck status): Steam, Heroic (list and set tools), and Lutris (list games).
- Global/default compatibility tool management: Steam and Heroic.

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
Show game SteamDeck rating     | ✅       | ✅              | ⬜             | ⬜
Show game AWACY[^4] rating     | ✅       | ✅              | ✅             | ⬜
Show game ProtonDB [^5] rating | ✅       | ✅              | ✅             | ⬜
Programming language           | Python   | Python          | Vala           | Rust
GUI/TUI                        | typer, rich | Qt           | GTK            | clap, indicatif

The table may be out-of-date. Please create an issue or pull request if that is the case.

[^1]: https://github.com/DavidoTek/ProtonUp-Qt
[^2]: https://github.com/Vysp3r/ProtonPlus
[^3]: https://github.com/auyer/Protonup-rs
[^4]: https://areweanticheatyet.com/
[^5]: https://www.protondb.com/
