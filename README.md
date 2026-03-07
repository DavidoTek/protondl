# protondl 🧬

## 🏗️ This library is Work in Progress!

protondl is a modern, headless Python library for downloading and managing Proton compatibility tools (like GE-Proton, Luxtorpeda, and Boxtron) for Steam, Lutris, and other Linux game launchers.

Inspired by the logic of ProtonUp-Qt, protondl decouples the core management logic from the GUI, providing a modular and developer-friendly API for automation, CLI tools, or custom integrations.

## ✨ Features

- **Launcher Discovery**: Automatically detects Native, Flatpak, and Snap installations of Steam and other launchers.
- **Modular Architecture**: Easily extendable for new compatibility tools or launchers.
- **Async-First**: Built with httpx and asyncio for non-blocking downloads.
- **Headless by Design**: No Qt/GUI dependencies in the core library.
- **Modern Tooling**: Powered by uv, ruff, and mypy for a rock-solid developer experience.

## 🚀 Quick Start

### Installation (for users)

```bash
uv tool install protondl
```

### Basic Usage (CLI)

1. List your launchers to find your target ID:

    ```bash
    protondl list-launchers
    ```

2. List compatibilty tools available for the launcher:

    ```bash
    protondl list-tools 0
    ```

3. Find available versions for a tool:

    ```bash
    protondl list-versions GE-Proton
    ```

4. Install it:

    ```bash
    protondl install 0 GE-Proton GE-Proton10-10
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
    - Type check: `uv run mypy src`

3. **Pre-commit Hooks**

    Ensure your code is compliant before every commit:
    ```bash
    uv run pre-commit install
    ```

## 🏗 Project Structure

```
src/protondl/
├── core/           # Abstract Base Classes and Enums (The Contract)
├── launchers/      # Launcher discovery (Steam, Lutris, etc.)
├── installers/     # Tool-specific logic (GE-Proton, Luxtorpeda)
└── cli/            # Rich-powered terminal interface
```
