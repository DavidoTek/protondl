# Copilot Instructions for protondl

You are helping develop the `protondl` library.

## Project Purpose

The goal of this project is to provide a modern Python library for downloading and managing Linux gaming compatibility tools (such as GE-Proton, Wine, DXVK, and VKD3D) across different launchers, including Steam, Lutris, and Heroic Games Launcher.

The library API should be easy to integrate into other applications (for example GUI apps), while also serving the `protondl` CLI in this repository.

## Repository Structure

Use and preserve this project layout when adding or modifying code:

- `src/protondl/`: Main library package (source of truth for runtime code).
- `src/protondl/core/`: Shared base abstractions and data models used by all launchers/installers.
- `src/protondl/launchers/`: Launcher-specific integrations (for example Steam, Lutris, Heroic).
- `src/protondl/installers/`: Tool-specific installer implementations (for example GE-Proton, DXVK, VKD3D).
- `src/protondl/util/`: Cross-cutting helpers (archive, download, Steam parsing helpers, etc.).
- `src/protondl/services/`: Integrations with optional online services (for example AWACY anti-cheat status).
- `src/protondl/cli/`: CLI entrypoints and CLI helpers; keep thin and delegate logic to library modules.
- `tests/`: Unit tests and test fixtures (for example `config.vdf`, `libraryfolders.vdf`).
- `docs/`: MkDocs source documentation.
- `.github/workflows/`: CI workflows.

When implementing changes:

- Put business logic in `src/protondl/` modules, not in CLI glue code.
- Add launcher behavior to the corresponding file in `src/protondl/launchers/`.
- Add installer behavior to `src/protondl/installers/` and keep each tool focused in its own module.
- Put reusable helpers in `src/protondl/util/` only when they are genuinely cross-cutting.
- Keep tests close to observable behavior and use fixture files in `tests/` where realistic parser inputs help.
    - Do not write tests for the CLI.
- Update docs in `docs/` when public behavior or APIs change.

## Development Standards

- Prefer clear, maintainable, strongly typed Python code.
- Keep public APIs simple and predictable.
- Favor small, focused changes over broad refactors.
- Maintain compatibility with existing behavior unless a change is explicitly intended.

## Docstring Requirements

All functions should include concise but complete docstrings that describe:

- What the function does.
- Parameter names and parameter types.
- Return value and return type.
- Raised exceptions.

Docstrings should be short, practical, and sufficient for both CLI and library consumers.

Example:

```python
def example_function(param1: int, param2: str) -> bool:
    """
    Determines if the length of param2 is greater than param1.

    Args:
        param1 (int): The first parameter, which should be an integer.
        param2 (str): The second parameter, which should be a string.

    Returns:
        bool: True if the parameters meet the condition, False otherwise.

    Raises:
        ValueError: If param1 is negative or if param2 is empty.
    """
    if param1 < 0:
        raise ValueError("param1 must be non-negative")
    if not param2:
        raise ValueError("param2 must be a non-empty string")
    
    return len(param2) > param1
```

## Verification Commands

Before considering a change complete, run and fix issues from the following commands:

1. `uv run ruff format .`
2. `uv run ruff check --fix .`
3. `uv run mypy src tests --config-file=./pyproject.toml`
4. `uv run pytest tests`

You may run these commands in a different order, and run them multiple times if needed.

## Testing Expectations

- Add or update tests for behavior changes.
- Prefer deterministic tests using fixtures and targeted mocking where appropriate.
- Keep tests readable and focused on observable behavior.

## Safety and Workflow

- Do not use destructive git operations unless explicitly requested.
- Do not revert unrelated changes.
- Keep edits scoped to the task at hand.
