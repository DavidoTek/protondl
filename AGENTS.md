# AGENTS.md

Guidance for AI agents working on protondl. Also see `.github/copilot-instructions.md`.

## Project

protondl is a modern Python library and CLI for downloading and managing Linux gaming
compatibility tools (GE-Proton, Wine, DXVK, vkd3d-proton, ...) for Steam, Lutris, Heroic,
and Bottles. It is inspired by ProtonUp-Qt but headless, async-first, and library-first:
the CLI is a thin wrapper around the library API.

- Python `>=3.10`, built with `uv` (see `pyproject.toml` / `uv.lock`).
- Async downloads via `httpx`/`asyncio`.

## Structure

```
src/protondl/
├── core/         # ABCs & data models (Launcher, CtInstaller, CompatTool, enums)
├── launchers/    # Launcher integrations (Steam, Lutris, Heroic, Bottles)
├── installers/   # Tool installers (GE-Proton, DXVK, ...); registry in __init__.py
├── services/     # Optional online services (e.g. AWACY)
├── util/         # Cross-cutting helpers (archive, download, version_file, steam)
├── tui/          # Textual TUI; one file per screen in tui/screens/
└── cli/          # Typer CLI; keep thin, delegate logic to library modules
tests/            # pytest tests + fixtures (config.vdf, libraryfolders.vdf)
docs/             # MkDocs source (CLI/ and Library_API/)
```

### API vs CLI

- **API**: users import launchers/installers and call methods directly (e.g.
  `launcher.get_installed_tools()`, `await installer.install(version, launcher)`). This is the
  source of truth for all business logic.
- **CLI**: Typer commands registered on `app` in `src/protondl/cli/` (`main.py`, `tools.py`,
  `games.py`, `services.py`). Commands resolve IDs/names, print via `rich`, and delegate all
  logic to library modules. No business logic in CLI glue.

## Coding style

- Ruff (format + lint) and strict mypy are enforced; keep both clean.
- Strongly typed code; avoid `Any` unless necessary.
- Follow existing patterns: prefer small, focused changes over broad refactors.
- Public API should be simple and predictable.
- Docstrings: every function/class documents what it does, params with types, return value,
  and raised exceptions (Google style).
- Preserve the project layout above; no comments unless asked.
- Launcher behavior goes in `src/protondl/launchers/<name>.py`, installer behavior in
  `src/protondl/installers/<name>.py`, reusable helpers in `src/protondl/util/` only when
  genuinely cross-cutting.

## Test policy

- `pytest` tests live in `tests/`, close to observable behavior.
- Do **not** write tests for the CLI; test the library API.
- Use fixture files (`tests/launchers/config.vdf`, `libraryfolders.vdf`) where realistic parser
  inputs help; prefer targeted mocking (`monkeypatch`) and deterministic tests.
- Update `tests/` when changing behavior, and update `docs/` when public behavior/APIs change.

## Verification

Run before considering a change complete:

```bash
uv run ruff format .
uv run ruff check --fix .
uv run mypy src tests --config-file=./pyproject.toml
uv run pytest tests
```
