from pathlib import Path

from protondl.core.models import Arch, CompatToolVersionInfo, TranslationDetails
from protondl.util.version_file import FILENAME, read_version_file, write_version_file


def test_write_and_read_version_file(tmp_path: Path) -> None:
    info = CompatToolVersionInfo(
        compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=1785769458
    )

    write_version_file(tmp_path, info)

    assert (tmp_path / FILENAME).is_file()
    assert read_version_file(tmp_path) == info


def test_write_and_read_version_file_with_arch(tmp_path: Path) -> None:
    info = CompatToolVersionInfo(
        compat_tool="GE-Proton",
        version="GE-Proton11-3",
        installed_at=1785769458,
        arch=Arch.AARCH64,
        translation_details=TranslationDetails(
            from_os="windows",
            from_arch="x86_64",
            to_os="linux",
            to_arch="aarch64",
        ),
    )

    write_version_file(tmp_path, info)

    assert read_version_file(tmp_path) == info


def test_read_version_file_without_arch_fields(tmp_path: Path) -> None:
    (tmp_path / FILENAME).write_text(
        '{"compat_tool": "GE-Proton", "version": "GE-Proton11-3", "installed_at": 1785769458}',
        encoding="utf-8",
    )

    info = read_version_file(tmp_path)
    assert info is not None
    assert info.compat_tool == "GE-Proton"
    assert info.version == "GE-Proton11-3"
    assert info.installed_at == 1785769458
    assert info.arch is None
    assert info.translation_details is None


def test_read_version_file_missing(tmp_path: Path) -> None:
    assert read_version_file(tmp_path) is None


def test_read_version_file_malformed_json(tmp_path: Path) -> None:
    (tmp_path / FILENAME).write_text("{not valid json", encoding="utf-8")
    assert read_version_file(tmp_path) is None


def test_read_version_file_incomplete_data(tmp_path: Path) -> None:
    (tmp_path / FILENAME).write_text('{"compat_tool": "GE-Proton"}', encoding="utf-8")
    assert read_version_file(tmp_path) is None
