from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from protondl.core.models import Arch, CompatToolVersionInfo

if TYPE_CHECKING:
    from protondl.core.base_installer import CtInstaller


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
