# protondl 🧬

protondl is a modern, headless Python library for downloading and managing Proton compatibility tools (like GE-Proton, Luxtorpeda, and Boxtron) for Steam, Lutris, and other Linux game launchers.

Inspired by the logic of ProtonUp-Qt, protondl decouples the core management logic from the GUI, providing a modular and developer-friendly API for automation, CLI tools, or custom integrations.

## 🏗️ This library is Work in Progress!

The goal of this project is to port all functionality from ProtonUp-Qt into a headless library that is indepenent from the Qt GUI to allow for future use in different projects.
This is more of a side project that I will work on here and there. Please use [ProtonUp-Qt](https://github.com/DavidoTek/ProtonUp-Qt) instead for managing your compatibility tools!


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

## 🚀 Quick Start

### Installation (for users)

```bash
uv tool install "protondl[cli] @ git+https://github.com/DavidoTek/protondl@main"
uvx run protondl
```

### Basic Usage (CLI)

1. List your launchers to find your target ID:

    ```bash
    protondl list-launchers
    ```

2. List compatibilty tools available for the launcher:

    ```bash
    protondl list-tools 1
    ```

3. Find available versions for a tool:

    ```bash
    protondl list-versions GE-Proton
    ```

4. Install it:

    ```bash
    protondl install 1 GE-Proton GE-Proton10-10
    ```


5. List installed games and the compatibility tools used by them:

    ```bash
    protondl list-games 1
    ```

### Basic Usage (Library API)

```python
import asyncio
from protondl.launchers import detect_all_launchers
from protondl.installers.ge_proton import GEProtonInstaller

async def main():
    # Detect Steam -> add more checks here since there can be multiple launchers
    launchers = detect_all_launchers()
    steam = launchers[0] 

    # Initialize Installer
    ge = GEProtonInstaller()
    
    # Install latest GE-Proton
    await ge.install(version="latest", launcher=steam)

asyncio.run(main())
```

## 🛠 Development Setup

protondl uses the [uv](https://docs.astral.sh/uv/) package manager for high-performance dependency management.

1. **Clone and Install**

    ```bash
    git clone https://github.com/DavidoTek/protondl.git
    cd protondl

    uv sync

    uv run protondl --help
    ```

2. **Code Quality & Standards**

    We use Ruff for linting/formatting and Mypy for strict type checking.
    - Format code: `uv run ruff format .`
    - Lint code: `uv run ruff check --fix .`
    - Type check: `uv run mypy src tests`
    - Unit tests: `uv run pytest tests`

3. **Pre-commit Hooks**

    Ensure your code is compliant before every commit:
    ```bash
    uv run pre-commit install
    ```

## 🏗 Project Structure

```
src/protondl/
├── cli/            # Rich-powered terminal interface
├── core/           # Abstract Base Classes and Enums (The Contract)
├── installers/     # Tool-specific logic (GE-Proton, Luxtorpeda)
├── launchers/      # Launcher discovery (Steam, Lutris, etc.)
└── util/           # Utility functions (downloads, etc.)
```

## 📸 Credits & Story

The project was originally inspired by AUNaseef's [protonup](https://github.com/AUNaseef/protonup) for which I created an [initial GUI](https://github.com/AUNaseef/protonup/pull/9). Since the library didn't have the necessary features and upstreaming was slow, I started with the development of [ProtonUp-Qt](https://github.com/DavidoTek/ProtonUp-Qt).
Thanks to the many [ProtonUp-Qt contributers](https://github.com/DavidoTek/ProtonUp-Qt/graphs/contributors), the project was able to grow and become as feature rich as it is today.
While ProtonUp-Qt is well working, the original idea of having a headless library and a separate GUI was lost. This is where protondl comes in. The idea is to port the features of ProtonUp-Qt into a headless library, featuring modern CLI and API interfaces.
