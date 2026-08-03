from pathlib import Path

from protondl.core.models import CompatToolVersionInfo
from protondl.util.version_file import FILENAME, read_version_file, write_version_file


def test_write_and_read_version_file(tmp_path: Path) -> None:
    info = CompatToolVersionInfo(
        compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=1785769458
    )

    write_version_file(tmp_path, info)

    assert (tmp_path / FILENAME).is_file()
    assert read_version_file(tmp_path) == info


def test_read_version_file_missing(tmp_path: Path) -> None:
    assert read_version_file(tmp_path) is None


def test_read_version_file_malformed_json(tmp_path: Path) -> None:
    (tmp_path / FILENAME).write_text("{not valid json", encoding="utf-8")
    assert read_version_file(tmp_path) is None


def test_read_version_file_incomplete_data(tmp_path: Path) -> None:
    (tmp_path / FILENAME).write_text('{"compat_tool": "GE-Proton"}', encoding="utf-8")
    assert read_version_file(tmp_path) is None
