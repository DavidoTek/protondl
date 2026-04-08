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

## Verification Commands

Before considering a change complete, run and fix issues from the following commands:

1. `uv run mypy src tests`
2. `uv run pytest tests`
3. `uv run ruff format .`
4. `uv run ruff check --fix .`

You may run these commands in a different order, and run them multiple times if needed.

## Testing Expectations

- Add or update tests for behavior changes.
- Prefer deterministic tests using fixtures and targeted mocking where appropriate.
- Keep tests readable and focused on observable behavior.

## Safety and Workflow

- Do not use destructive git operations unless explicitly requested.
- Do not revert unrelated changes.
- Keep edits scoped to the task at hand.
