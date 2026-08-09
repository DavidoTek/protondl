import json
from pathlib import Path

from protondl.core.models import Arch, CompatToolVersionInfo, TranslationDetails
from protondl.util.helpers import json_safe_load

FILENAME = "protondl_version.json"


def write_version_file(install_dir: Path, info: CompatToolVersionInfo) -> None:
    """
    Writes the compatibility tool metadata into the tool's installation directory.

    Args:
        install_dir (Path): The directory where the compatibility tool is installed.
        info (CompatToolVersionInfo): The metadata to store.
    """
    data: dict[str, object] = {
        "compat_tool": info.compat_tool,
        "version": info.version,
        "installed_at": info.installed_at,
    }
    if info.arch is not None:
        data["arch"] = info.arch.value
    if info.translation_details is not None:
        data["translation_details"] = {
            "from_os": info.translation_details.from_os,
            "from_arch": info.translation_details.from_arch,
            "to_os": info.translation_details.to_os,
            "to_arch": info.translation_details.to_arch,
        }

    with open(install_dir / FILENAME, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_version_file(install_dir: Path) -> CompatToolVersionInfo | None:
    """
    Reads the compatibility tool metadata from the tool's installation directory.

    Args:
        install_dir (Path): The directory where the compatibility tool is installed.

    Returns:
        CompatToolVersionInfo | None: The stored metadata, or None if the file
            is missing or contains invalid data.
    """
    version_file = install_dir / FILENAME
    if not version_file.is_file():
        return None

    try:
        data = json_safe_load(version_file)

        arch = Arch(data["arch"]) if isinstance(data.get("arch"), str) else None

        translation_details = None
        if isinstance(data.get("translation_details"), dict):
            td = data["translation_details"]
            translation_details = TranslationDetails(
                from_os=str(td["from_os"]),
                from_arch=str(td["from_arch"]),
                to_os=str(td["to_os"]),
                to_arch=str(td["to_arch"]),
            )

        return CompatToolVersionInfo(
            compat_tool=str(data["compat_tool"]),
            version=str(data["version"]),
            installed_at=int(data["installed_at"]),
            arch=arch,
            translation_details=translation_details,
        )
    except (ValueError, KeyError, TypeError):
        return None
