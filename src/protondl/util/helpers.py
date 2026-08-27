from __future__ import annotations

import json
import platform
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from protondl.core.config import RequestConfig
from protondl.core.models import (
    AlreadyInstalledError,
    Arch,
    CancelToken,
    CompatTool,
    CompatToolVersionInfo,
    InstallProgress,
    InstallStep,
    ProgressCallback,
    ReleaseVersion,
    ToolUpdate,
    UpdateCheckResult,
)

if TYPE_CHECKING:
    from protondl.core.base_installer import CtInstaller
    from protondl.core.base_launcher import Launcher

MAX_UPDATE_RELEASES_PAGES = 5
UPDATE_RELEASES_PAGE_SIZE = 30


def detect_host_arch() -> Arch:
    """
    Detects the CPU architecture of the current host.

    Returns:
        Arch: The detected host architecture. Unknown architectures default to Arch.X86_64.
    """
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return Arch.X86_64
    if machine in ("aarch64", "arm64"):
        return Arch.AARCH64
    return Arch.X86_64


def read_cpu_flags() -> frozenset[str]:
    """
    Reads the CPU feature flags of the host from /proc/cpuinfo.

    Returns:
        frozenset[str]: The set of CPU feature flags, or an empty set if
            /proc/cpuinfo is unavailable (e.g. on non-Linux systems).
    """
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo:
            for line in cpuinfo:
                if line.startswith("flags"):
                    return frozenset(line.split(":")[1].strip().split())
    except OSError:
        pass
    return frozenset()


def detect_hwcaps() -> frozenset[str]:
    """
    Detects the x86-64 micro-architecture levels (hwcaps) supported by the host CPU.

    The flag sets follow the x86-64 psABI as used by pupgui2:
    - x86_64_v2: SSE4.1, SSE4.2, SSSE3
    - x86_64_v3: x86_64_v2 plus AVX, AVX2
    - x86_64_v4: x86_64_v3 plus AVX-512 (F, BW, CD, DQ, VL)

    Returns:
        frozenset[str]: The set of supported levels, always containing "x86_64".
    """
    flags = read_cpu_flags()
    flags_v2 = {"sse4_1", "sse4_2", "ssse3"}
    flags_v3 = {*flags_v2, "avx", "avx2"}
    flags_v4 = {*flags_v3, "avx512f", "avx512bw", "avx512cd", "avx512dq", "avx512vl"}

    hwcaps = {"x86_64"}
    levels = (
        ("x86_64_v4", flags_v4),
        ("x86_64_v3", flags_v3),
        ("x86_64_v2", flags_v2),
    )
    for name, required in levels:
        if required.issubset(flags):
            hwcaps.add(name)
    return frozenset(hwcaps)


def json_safe_load(json_file: Path) -> dict[str, Any]:
    """
    Loads a JSON file and returns its contents as a dict.

    Args:
        json_file (Path): Path to the JSON file.

    Returns:
        dict: Content of the JSON file.

    Raises:
        ValueError: In case loading the JSON file fails.
    """
    try:
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"Loading {json_file} failed: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Loading {json_file} did not return a dict, but {type(data)}: {data}")

    return cast(dict[str, Any], data)


def batch_update_games_tools(
    launcher: Launcher, from_tool: CompatTool | str, to_tool: CompatTool
) -> int:
    """
    Updates the compatibility tool for multiple games in batch.
    The from_tool can be specified as a CompatTool instance (exact version match)
    or as a string (matches any tool name containing the string).

    Args:
        launcher: The game launcher instance to operate on.
        from_tool: The compatibility tool to replace.
            Can be a CompatTool instance (exact version) or a string (tool name, e.g., "GE-Proton").
        to_tool: The new compatibility tool to set for the affected games.

    Returns:
        int: The number of games that were updated.

    Raises:
        RuntimeError: If updating the games' compatibility tools failed.
    """
    games = launcher.get_game_list()

    if isinstance(from_tool, str):
        games_to_update = [game for game in games if from_tool in game.compat_tool_name]
    else:
        games_to_update = [game for game in games if game.compat_tool_name == from_tool.full_name]

    game_tool_map = {game: to_tool.full_name for game in games_to_update}

    try:
        launcher.set_games_tools(game_tool_map)
    except RuntimeError as e:
        raise RuntimeError(f"Batch update of games' compatibility tools failed: {e}") from e

    return len(games_to_update)


async def check_for_updates(
    launcher: Launcher, request_config: RequestConfig | None = None
) -> UpdateCheckResult:
    """
    Checks all installed compatibility tools of a launcher for available updates.

    The newest available version is determined per (compatibility tool,
    architecture, build variant): for each installed architecture and variant
    of a tool, the release history is walked back until a release providing a
    build of that variant and architecture is found. This handles releases
    that only ship a subset of the tool's architectures (e.g. an
    architecture-specific patch) and tools that ship multiple build variants
    per architecture (e.g. fshack or wow64 builds); it means the
    architectures and variants of a tool may be updated to different versions.

    Args:
        launcher: The game launcher instance to operate on.
        request_config: Optional configuration for API requests, including auth tokens.

    Returns:
        UpdateCheckResult: The compatibility tools with an available update
            (one entry per architecture and build variant, including the newest
            version providing that architecture and variant), the tools that
            are already at the newest version, and the tools that could not be
            checked.
    """
    from protondl.installers import get_installer_by_name
    from protondl.util.version_file import read_version_file

    installed_tools = launcher.get_installed_tools()
    unchecked: list[str] = []
    groups: dict[tuple[str, Arch, str], list[CompatTool]] = {}
    versions_by_group: dict[tuple[str, Arch, str], list[str]] = {}
    installers: dict[str, CtInstaller] = {}
    installer_order: list[str] = []

    for tool in installed_tools:
        info = read_version_file(tool.install_dir)
        if info is None:
            unchecked.append(tool.full_name)
            continue

        installer = get_installer_by_name(info.compat_tool, request_config=request_config)
        if installer is None:
            unchecked.append(tool.full_name)
            continue

        arch = _resolve_tool_arch(installer, info)
        variant = installer.variant_of(info.version)
        group = (installer.name, arch, variant)
        if installer.name not in installers:
            installers[installer.name] = installer
            installer_order.append(installer.name)
        groups.setdefault(group, []).append(tool)
        versions_by_group.setdefault(group, []).append(info.version)

    updates: list[ToolUpdate] = []
    up_to_date: list[str] = []
    for tool_name in installer_order:
        installer = installers[tool_name]
        group_variants = [(arch, variant) for (name, arch, variant) in groups if name == tool_name]

        try:
            candidates = await _newest_releases_for_archs(installer, group_variants)
        except Exception:
            unchecked.extend(tool.full_name for tool in _group_tools(groups, tool_name))
            continue

        for arch, variant in group_variants:
            candidate = candidates.get((arch, variant))
            tools = groups[(tool_name, arch, variant)]
            if candidate is None:
                unchecked.extend(tool.full_name for tool in tools)
                continue

            latest_version = candidate.version
            installed_versions = versions_by_group[(tool_name, arch, variant)]
            if latest_version in installed_versions:
                up_to_date.append(_tool_label(installer, arch, variant))
            else:
                updates.append(
                    ToolUpdate(
                        compat_tool_name=tool_name,
                        latest_version=latest_version,
                        installed_versions=installed_versions,
                        installed_tools=tools,
                        arch=arch,
                        variant=variant,
                    )
                )

    return UpdateCheckResult(updates=updates, up_to_date=up_to_date, unchecked=unchecked)


async def _newest_releases_for_archs(
    installer: CtInstaller, arch_variants: Sequence[tuple[Arch, str]]
) -> dict[tuple[Arch, str], ReleaseVersion]:
    """
    Finds the newest release providing a build for each of the given
    (architecture, variant) combinations.

    The release history is walked back page by page until a release providing
    each requested combination is found or the release history is exhausted
    (bounded by MAX_UPDATE_RELEASES_PAGES).

    Args:
        installer: The compatibility tool installer to query.
        arch_variants: The (architecture, variant) combinations to find the
            newest release for.

    Returns:
        dict[tuple[Arch, str], ReleaseVersion]: The newest release providing a
            build for each requested combination, keyed by the combination.
            Combinations without a matching release within the fetched history
            are omitted.
    """
    arch_variants = [
        (arch, variant) for arch, variant in arch_variants if arch in installer.supported_archs
    ]
    if not arch_variants:
        return {}
    found: dict[tuple[Arch, str], ReleaseVersion] = {}
    for page in range(1, MAX_UPDATE_RELEASES_PAGES + 1):
        releases = await installer.fetch_releases(count=UPDATE_RELEASES_PAGE_SIZE, page=page)
        for release in releases:
            release_variant = installer.variant_of(release.version)
            for arch, variant in arch_variants:
                key = (arch, variant)
                if key not in found and arch in release.archs and release_variant == variant:
                    found[key] = release
        if len(found) == len(arch_variants):
            break
        if len(releases) < UPDATE_RELEASES_PAGE_SIZE:
            break
    return found


def _resolve_tool_arch(installer: CtInstaller, info: CompatToolVersionInfo) -> Arch:
    """
    Resolves the architecture of an installed compatibility tool.

    The version file's arch field takes precedence, followed by the host-side
    architecture recorded in its translation details (legacy version files),
    and finally the installer's default architecture resolution.

    Args:
        installer: The compatibility tool installer of the installed tool.
        info: The metadata of the installed tool.

    Returns:
        Arch: The architecture of the installed tool.
    """
    if info.arch is not None:
        return info.arch
    if info.translation_details is not None:
        try:
            return Arch(info.translation_details.to_arch)
        except ValueError:
            pass
    return installer.resolve_arch(None)


def _tool_label(installer: CtInstaller, arch: Arch, variant: str = "") -> str:
    """
    Returns the display label of a tool for a given architecture.

    For tools that provide multiple architectures the label includes the
    architecture, single-architecture tools keep their plain name. A non-empty
    build variant is appended to the label.

    Args:
        installer: The compatibility tool installer of the tool.
        arch: The architecture to label.
        variant: The build variant of the tool, or an empty string for the
            default variant.

    Returns:
        str: The display label.
    """
    if len(installer.supported_archs) > 1:
        label = f"{installer.name} ({arch.value})"
    else:
        label = installer.name
    if variant:
        return f"{label} ({variant})"
    return label


def _group_tools(
    groups: dict[tuple[str, Arch, str], list[CompatTool]], tool_name: str
) -> list[CompatTool]:
    """Returns all installed tools of the given compatibility tool name."""
    return [tool for (name, _, _), tools in groups.items() if name == tool_name for tool in tools]


async def update_compatibility_tools(
    launcher: Launcher,
    updates: list[ToolUpdate],
    keep_old: bool = False,
    progress_callback: ProgressCallback | None = None,
    request_config: RequestConfig | None = None,
    cancel_token: CancelToken | None = None,
) -> dict[tuple[str, Arch | None, str], CompatTool]:
    """
    Installs the newest version of all given compatibility tools.

    Each update is installed for its own architecture (the architecture of the
    installed builds it replaces). If keep_old is False, all older versions of
    the compatibility tool for that architecture and build variant are removed
    after the new version was installed successfully.

    Args:
        launcher: The game launcher instance to operate on.
        updates: The compatibility tools to update, including the latest version.
        keep_old: Whether to keep older versions of the compatibility tools.
        progress_callback: Optional callback receiving InstallProgress events of the
            currently installed tool, enriched with the tool's name and its index
            within the update run (tool, tool_index, tool_total).
        request_config: Optional configuration for API requests, including auth tokens.
        cancel_token: Optional token whose cancel() method aborts the update run.
            It is checked before each tool and forwarded to the running
            installation (see CtInstaller.install()), so a cancel takes effect
            during the current download or extraction. Tools already updated
            before the cancel stay installed; the current tool's partial
            download and extraction are removed.

    Returns:
        dict[(str, Arch | None, str), CompatTool]: A mapping of compatibility
            tool name, architecture and build variant to the newly installed
            tool for every update whose installation directory could be
            determined.

    Raises:
        ValueError: If no CtInstaller exists for one of the compatibility tools.
        InstallCancelledError: If the cancel_token is cancelled before the
            update run completes.
    """
    from protondl.installers import get_installer_by_name

    installed_new_tools: dict[tuple[str, Arch | None, str], CompatTool] = {}
    total = len(updates)
    for index, update in enumerate(updates):
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()

        installer = get_installer_by_name(update.compat_tool_name, request_config=request_config)
        if installer is None:
            raise ValueError(
                f"No installer found for compatibility tool '{update.compat_tool_name}'."
            )

        def report_progress(
            event: InstallProgress,
            tool_name: str = update.compat_tool_name,
            tool_index: int = index + 1,
        ) -> None:
            if progress_callback is not None:
                progress_callback(
                    InstallProgress(
                        step=event.step,
                        current=event.current,
                        total=event.total,
                        tool=tool_name,
                        tool_index=tool_index,
                        tool_total=total,
                    )
                )

        try:
            info = await installer.install(
                update.latest_version,
                launcher,
                arch=update.arch,
                progress_callback=report_progress,
                cancel_token=cancel_token,
            )
        except AlreadyInstalledError:
            report_progress(InstallProgress(step=InstallStep.COMPLETED))
            continue

        if not keep_old:
            for tool in update.installed_tools:
                launcher.remove_tool(tool)

        new_tool = _find_installed_tool(launcher, info)
        if new_tool is not None:
            installed_new_tools[(update.compat_tool_name, update.arch, update.variant)] = new_tool

        report_progress(InstallProgress(step=InstallStep.COMPLETED))

    return installed_new_tools


def _find_installed_tool(launcher: Launcher, info: CompatToolVersionInfo) -> CompatTool | None:
    """
    Finds the installed tool matching the given version file metadata.

    The tool's installation directory is identified by the metadata written to
    its protondl_version.json (compat tool name, version, installed_at and
    architecture), which is independent of the directory name.

    Args:
        launcher: The game launcher instance to search.
        info: The metadata of the installed tool to find.

    Returns:
        CompatTool | None: The matching installed tool, or None if no installed
            tool carries the given metadata.
    """
    from protondl.util.version_file import read_version_file

    for tool in launcher.get_installed_tools():
        installed_info = read_version_file(tool.install_dir)
        if installed_info is None:
            continue
        if (
            installed_info.compat_tool == info.compat_tool
            and installed_info.version == info.version
            and installed_info.installed_at == info.installed_at
            and installed_info.arch == info.arch
        ):
            return tool
    return None
