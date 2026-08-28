# AGENTS.md

Guidance for AI agents and human contributors working on **protondl**.
Read this before making changes. It describes what the project is, how it is
structured, the standards it holds code to, and when to ask before acting.

---

## 1. What protondl is

protondl is a **modern, headless, async-first Python library** (plus a thin CLI)
for managing Linux gaming compatibility tools such as GE-Proton, Proton-Tkg,
Wine, DXVK and vkd3d-proton across game launchers (Steam, Lutris, Heroic,
Bottles).

"Managing" means:

- **Compatibility tools**: discover available tools, list released versions,
  install, update (single and batch), and remove them for a launcher.
- **Games**: list a launcher's games, read and set the compatibility tool a game
  uses, batch-migrate games from one tool to another.
- **External services**: look up anti-cheat status (areweanticheatyet.com) and
  Linux compatibility ratings (ProtonDB), plus Steam Deck compatibility.

### Design goals — keep these in mind for every change

- **Library first.** The public API is the product. The CLI is one consumer of
  it; future GUIs (drop-downs of tool versions, editable game/tool tables,
  install progress bars, cancel buttons) will be others. Anything a GUI would
  need belongs in the library, not the CLI.
- **Headless.** No Qt/GUI, no TUI, no interactive prompts in the library. The
  core must work from plain Python, a CLI, or any async GUI framework.
- **Few dependencies.** The library depends only on `httpx`, `pyyaml`, `steam`,
  `vdf`, `zstandard`. CLI-only dependencies (`rich`, `typer`) live behind the
  `cli` optional-dependency group and must never be imported from library code.
- **Async-first.** All network I/O is `async` (`httpx.AsyncClient`). Do not add
  blocking network calls or hidden threads to the library.
- **Strongly typed.** The package ships `py.typed` and passes `mypy --strict`.
- **Explicitly documented behavior.** Every public function documents its
  arguments, return value, and the exceptions it raises. Callers should never be
  surprised by an exception type. See [`src/protondl/core/errors.py`](src/protondl/core/errors.py).

---

## 2. Repository structure

Preserve this layout. Put logic where it belongs:

| Path | Contents |
|------|----------|
| `src/protondl/core/` | Shared abstractions and data models: `CtInstaller`, `Launcher`, `Game` base classes, dataclasses/enums (`models.py`), the exception hierarchy (`errors.py`), `RequestConfig` (`config.py`). |
| `src/protondl/installers/` | One module per compatibility tool (`ge_proton.py`, `dxvk.py`, …). Each subclasses `CtInstaller` and is registered in `installers/__init__.py`. |
| `src/protondl/launchers/` | One module per launcher (`steam.py`, `lutris.py`, `heroic.py`, `bottles.py`). Each subclasses `Launcher`; discovery/factory helpers live in `launchers/__init__.py`. |
| `src/protondl/services/` | Optional online services independent of launchers/installers (`awacy.py`, `protondb.py`). |
| `src/protondl/util/` | Genuinely cross-cutting helpers: `download.py` (GitHub/GitLab/Gitea release APIs, downloads), `archive.py` (tar/zip/zst extraction), `version_file.py` (`protondl_version.json`), `helpers.py` (arch/hwcaps detection, update orchestration), launcher-specific parsers (`steam.py`, `lutris.py`, `heroic.py`). |
| `src/protondl/cli/` | `typer`/`rich` CLI. Thin: parses args, calls the library, renders output. No business logic. |
| `tests/` | `pytest` unit tests and fixtures (`config.vdf`, `libraryfolders.vdf`, …). Mirrors the `src` layout. |
| `docs/` | MkDocs (Material) sources. `Library_API/` and `CLI/` sections. Published to GitHub Pages. |
| `.github/workflows/` | CI (`ci.yml`: ruff + mypy + pytest) and docs deploy (`docs.yml`). |

When adding behavior:

- Business logic → `src/protondl/` modules, **never** in `cli/`.
- New tool → new module in `installers/`, registered in `installers/__init__.py`.
- New launcher → new module in `launchers/`, registered in `launchers/__init__.py`.
- New helper → `util/` only if it is truly cross-cutting; otherwise keep it local.
- Update `docs/` whenever public API or observable behavior changes.

---

## 3. Coding standards

### Tooling (all enforced in CI and by pre-commit)

Run and fix all of these before considering a change done — order does not
matter, and re-run as needed:

```bash
uv run ruff format .
uv run ruff check --fix .
uv run mypy src tests --config-file=./pyproject.toml
uv run pytest tests
```

`uv run pre-commit install` sets these up as a git hook.

### Style

- **Formatter/linter:** Ruff. Line length **100**. Target Python **3.10+**
  (`requires-python = ">=3.10"`). Enabled rule sets: `E`, `F`, `I` (isort),
  `N` (pep8-naming), `UP` (pyupgrade), `B` (bugbear).
- **Typing:** `mypy` strict. Fully annotate every function signature. Use
  modern syntax (`X | None`, `list[str]`, `from __future__ import annotations`
  where it helps). Do not add `# type: ignore` without a reason next to it.
- **Naming:** `snake_case` functions/variables, `PascalCase` classes,
  `UPPER_SNAKE_CASE` module-level constants. Installer classes end in
  `Installer`, launcher classes end in `Launcher`. Private helpers are prefixed
  with `_`.
- **Imports:** absolute (`from protondl.core.models import ...`). Import order is
  managed by Ruff's isort. Lazy imports inside functions are used deliberately to
  break import cycles (e.g. `installers` ↔ `launchers`) — keep that pattern where
  it exists.
- **Async:** library network code is `async`. Bound concurrent requests with a
  semaphore (see `fetch_protondb_tiers`). Never block the event loop.
- **No prints for control flow.** Library code may emit `print("Warning: …")`
  for best-effort/degraded paths (existing convention), but errors that the
  caller must handle are raised, not printed.

### Docstrings — required on every public function/method/class

Google-style sections. Keep them short, practical, and complete for both CLI and
library consumers:

```python
def example_function(param1: int, param2: str) -> bool:
    """
    Determines if the length of param2 is greater than param1.

    Args:
        param1 (int): The first parameter.
        param2 (str): The second parameter.

    Returns:
        bool: True if the parameters meet the condition, False otherwise.

    Raises:
        ValueError: If param1 is negative or if param2 is empty.
    """
```

The **`Raises:` section is mandatory** whenever a function can raise. Document the
specific exception types from `protondl.core.errors` (or the standard-library
exceptions) that a caller can reasonably expect. If a function is explicitly
best-effort (catches and degrades instead of raising), say so.

---

## 4. Test policy

- **Framework:** `pytest`. Tests live in `tests/`, mirroring `src/protondl/`.
- **Add or update tests for every behavior change.** New public function → new
  test. Bug fix → regression test.
- **Do not write tests for the CLI** (`src/protondl/cli/`). The CLI is covered
  by exercising the library it calls. (Some `tests/test_cli_*.py` files exist
  from earlier work; do not expand CLI test coverage — test the library API
  instead.)
- **Determinism:** no real network, no real `$HOME`. Use `tmp_path`, fixture
  files (`tests/launchers/*.vdf`), and targeted monkeypatching
  (`monkeypatch.setattr("protondl.util.download.httpx.AsyncClient", …)`,
  fake async clients). Follow the existing fake-client patterns in
  `tests/util/test_download.py` and `tests/services/`.
- **Focus on observable behavior**, not implementation details. Assert on return
  values, written files, and raised exception types/messages.
- Keep tests readable; prefer small, named test functions over parametrized
  mega-tests unless the cases are genuinely uniform.

---

## 5. Domain glossary

| Term | Meaning |
|------|---------|
| **Compatibility tool / compat tool** | Software that runs Windows (or DOS) games on Linux: Proton, Wine, DXVK, vkd3d-proton, Boxtron, etc. Categorized by `CompatToolType` (`PROTON`, `WINE`, `DXVK`, `VKD3D`). |
| **Proton** | Valve's Wine-based compatibility tool. **GE-Proton** is Glorious Eggroll's community build; **Proton-Tkg**, **Proton-CachyOS**, **Proton-EM** are other community builds. |
| **Wine** | The underlying Windows compatibility layer. Managed standalone for Lutris/Heroic/Bottles. |
| **DXVK / vkd3d-proton** | Translation layers: Direct3D 9/10/11 → Vulkan (DXVK) and Direct3D 12 → Vulkan (vkd3d-proton). |
| **Launcher** | A game manager protondl integrates with: Steam, Lutris, Heroic Games Launcher, Bottles. |
| **Install mode** | How a launcher is installed: `NATIVE`, `FLATPAK`, or `SNAP` (`InstallMode`). Affects filesystem paths. |
| **`CtInstaller`** | Abstract base for a compatibility-tool installer (`core/base_installer.py`). Knows an API URL, release format, checksum suffix, supported archs; implements `fetch_releases()` and `install()`. |
| **`Launcher`** | Abstract base for a launcher (`core/base_launcher.py`). Discovers installs, resolves the compat-tools directory, lists/updates games and installed tools. |
| **`Game`** | A game known to a launcher. Subclasses add launcher-specific metadata (`SteamGame`, `LutrisGame`, `HeroicGame`). |
| **Release / version** | A published build of a tool (e.g. `GE-Proton11-3`). `ReleaseVersion` pairs a version string with the architectures it ships. |
| **Build variant** | Distinct builds sharing a tool's version space (e.g. Lutris-Wine `fshack`, Kron4ek `wow64`). Grouped separately for update checks via `CtInstaller.variant_of()`. |
| **Arch** | CPU architecture of a build: `x86_64` or `aarch64` (`Arch`). |
| **`protondl_version.json`** | Metadata file protondl writes into each tool directory it installs (tool name, version, install time, arch, translation details). Used to identify and update protondl-managed tools. |
| **Translation details** | The guest→host mapping a build performs (`from_os`/`from_arch` → `to_os`/`to_arch`), e.g. Windows/x86_64 → Linux/aarch64. |
| **`CancelToken`** | Cooperative cancellation token passed to `install()` / `update_compatibility_tools()`; `cancel()` aborts and cleans up partial files, raising `InstallCancelledError`. |
| **`ProgressCallback`** | `Callable[[InstallProgress], None]` invoked during install with step (`InstallStep`), byte/file counts, and multi-tool run position. |
| **`RequestConfig`** | Holds optional GitHub/GitLab API tokens (from args or `GITHUB_TOKEN`/`GITLAB_TOKEN` env vars). Tokens are sent only to their matching host. |
| **AWACY** | areweanticheatyet.com — crowd-sourced Linux anti-cheat support tracker (`services/awacy.py`). |
| **ProtonDB** | protondb.com — crowd-sourced Linux game compatibility ratings, tiers `borked`…`platinum` (`services/protondb.py`). |
| **Steam Deck compatibility** | Valve's per-game verification status (`SteamDeckCompatType`: unknown/unsupported/playable/verified). |
| **Global / default tool** | The compatibility tool a launcher applies to games with no per-game override (Steam AppID `"0"`). |
| **Shortcut / non-Steam game** | A user-added Steam entry for a non-Steam executable, stored in `shortcuts.vdf`. |
| **hwcaps** | x86-64 micro-architecture levels (`x86_64_v2`/`v3`/`v4`) derived from CPU flags; used to pick optimized builds. |

Upstream reference project: **ProtonUp-Qt** (same author). protondl is the effort
to extract ProtonUp-Qt's logic into a GUI-independent library.

---

## 6. Security & compliance

- **Secrets:** the only secrets are `GITHUB_TOKEN` / `GITLAB_TOKEN`. They come
  from `RequestConfig` (explicit args or environment). **Never** log, print, or
  write them to disk, and never send a token to a host it does not belong to —
  `RequestConfig.get_headers(url)` already scopes tokens per host; keep that
  guarantee. Do not add new credential inputs without a strong reason.
- **No telemetry / no PII.** protondl does not collect analytics. It reads local
  launcher config (Steam users, game lists, install paths) only to perform the
  requested operation and never transmits it anywhere except the necessary
  ProtonDB AppID / AWACY slug lookups. Do not add outbound reporting.
- **Downloading third-party code:** protondl downloads community-built
  executables from GitHub/GitLab/Gitea/Codeberg release APIs. Always:
  - Use HTTPS APIs only; `follow_redirects=True` is expected for asset CDNs.
  - **Verify checksums** when the release provides one (`_verify_checksum`);
    a mismatch must raise `ChecksumMismatchError`, never install silently.
  - Extract archives with `filter="data"` (path-traversal protection) — never
    remove that. Clean up partial downloads/extractions on any failure or cancel.
  - protondl is not affiliated with and not liable for the tools it downloads
    (see README "Services"). Do not add tools from untrusted/unofficial hosts.
- **Filesystem:** only write inside the target launcher's directories and the
  system temp dir. `Launcher.remove_tool()` refuses to delete anything outside a
  launcher's compat-tools directory — preserve that check. Never follow symlinks
  out of the target tree.
- **Audit / reproducibility:** every installed tool gets a `protondl_version.json`
  recording what was installed and when. Keep writing it.

---

## 7. Workflow rules

- **Branches:** never commit directly to `main`. Branch from `main`
  (`feat/…`, `fix/…`, `refactor/…`, `doc/…`, `test/…`).
- **Commits:** **Conventional Commits**, matching the existing history:
  `type(scope): summary`, e.g.
  - `feat(cli): cancel install/update-all on Ctrl+C`
  - `fix(test): include build variant in cli update-all`
  - `refactor(installers): replace CT_INSTALLERS singleton with factory function`
  - `doc: describe build variant`

  Common types: `feat`, `fix`, `refactor`, `doc`, `test`, `chore`, `ci`.
  Scope is usually a package name (`cli`, `installers`, `launchers`, `services`,
  `core`, `util`) or `test`/`docs`. Split unrelated changes into separate
  commits.
- **Before every commit:** the four verification commands in §3 must pass.
- **Pull requests:** target `main`. Describe what changed and why, note any
  public-API or behavior change, and confirm ruff/mypy/pytest pass. Update
  `docs/` in the same PR as the code it documents.
- **Keep changes scoped.** Prefer small, focused diffs over broad refactors.
  Do not revert or reformat unrelated code. Maintain backward compatibility of
  the public API unless the change is the explicit point of the work.
- **Git safety:** no destructive git operations (`push --force`, hard resets,
  history rewrites, branch deletion) unless the user explicitly asks.

---

## 8. Consultation policy — when to ask vs. when to act

**Act without asking** when the task is clear and the change is low-risk and
reversible:

- Implementing a requested feature or fix within the described scope.
- Adding/adjusting tests, docstrings, type annotations, docs.
- Following an established pattern (new installer like the existing ones, new
  `Raises:` section, new fixture-based test).
- Running the verification commands and fixing what they report.

**Ask the user first** when:

- The request is ambiguous, underspecified, or self-contradictory.
- A change would break or alter the **public API** or documented behavior in a
  way not obviously intended.
- A new runtime dependency (especially a library-level one) seems necessary.
- The work implies a larger refactor, a new architectural layer, or touching
  many modules beyond the stated scope.
- A destructive or hard-to-reverse action is involved (deleting user data,
  git history rewrites, removing a public symbol).
- Adding a new downloaded tool, launcher integration, or outbound network call
  not already discussed.
- Tests or CI fail for a reason that looks pre-existing or environmental and the
  fix is unclear.

When you proceed on a reasonable assumption, state the assumption in your
response so the user can correct course early.

---

## 9. Quick reference

```bash
uv sync                              # install deps
uv run protondl --help               # run the CLI
uv run ruff format .                 # format
uv run ruff check --fix .            # lint
uv run mypy src tests --config-file=./pyproject.toml   # type check
uv run pytest tests                  # test
uv run mkdocs serve                  # preview docs locally
```
