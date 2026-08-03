import json
from pathlib import Path

from protondl.core.models import CompatToolVersionInfo

FILENAME = "protondl_version.json"


def write_version_file(install_dir: Path, info: CompatToolVersionInfo) -> None:
    """
    Writes the compatibility tool metadata into the tool's installation directory.

    Args:
        install_dir (Path): The directory where the compatibility tool is installed.
        info (CompatToolVersionInfo): The metadata to store.
    """
    with open(install_dir / FILENAME, "w", encoding="utf-8") as f:
        json.dump(
            {
                "compat_tool": info.compat_tool,
                "version": info.version,
                "installed_at": info.installed_at,
            },
            f,
            indent=2,
        )


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
        data = json.loads(version_file.read_text(encoding="utf-8"))
        return CompatToolVersionInfo(
            compat_tool=str(data["compat_tool"]),
            version=str(data["version"]),
            installed_at=int(data["installed_at"]),
        )
    except (ValueError, KeyError, TypeError):
        return None
