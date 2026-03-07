import tarfile
import zipfile
from pathlib import Path

import zstandard


class ArchiveError(Exception):
    """Custom exception for archive-related failures."""

    pass


def _validate_paths(archive_path: Path, extract_path: Path) -> None:
    """
    Validates that the archive exists and the destination parent is writable.

    Args:
        archive_path: The path to the archive file.
        extract_path: The path where the archive should be extracted.

    Raises:
        ArchiveError: If the archive file does not exist or if the destination
            parent directory does not exist.
    """
    if not archive_path.is_file():
        raise ArchiveError(f"Archive file does not exist: {archive_path}")

    if not extract_path.parent.exists():
        raise ArchiveError(f"Destination parent directory does not exist: {extract_path.parent}")


def extract_zip(zip_path: Path, extract_path: Path) -> None:
    """
    Extracts a Zip archive to the specified path.

    Args:
        zip_path: The path to the Zip archive file.
        extract_path: The path where the archive should be extracted.

    Raises:
        ArchiveError: If the archive file is invalid or if extraction fails.
    """
    _validate_paths(zip_path, extract_path)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_path)
    except zipfile.BadZipFile as e:
        raise ArchiveError(f"Zip file '{zip_path}' is invalid or corrupted.") from e
    except Exception as e:
        raise ArchiveError(f"Failed to extract zip '{zip_path}': {e}") from e


def extract_tar(tar_path: Path, extract_path: Path, compression: str = "") -> None:
    """
    Extracts a Tar archive.

    Args:
        tar_path: The path to the Tar archive file.
        extract_path: The path where the archive should be extracted.
        compression: The compression format (e.g., 'gz', 'bz2', 'xz').
                    Defaults to "" (auto-detect or regular tar).

    Raises:
        ArchiveError: If the archive file is invalid or if extraction fails.
    """
    _validate_paths(tar_path, extract_path)

    mode = f"r:{compression}" if compression else "r:*"

    try:
        with tarfile.open(tar_path, mode=mode) as tf:  # type: ignore
            tf.extractall(extract_path, filter="data")
    except tarfile.ReadError as e:
        raise ArchiveError(f"Could not read tar file '{tar_path}': {e}") from e
    except Exception as e:
        raise ArchiveError(f"Failed to extract tar '{tar_path}': {e}") from e


def extract_tar_zst(zst_path: Path, extract_path: Path) -> None:
    """
    Extracts a .tar.zst file using zstandard.

    Args:
        zst_path: The path to the .tar.zst file.
        extract_path: The path where the archive should be extracted.

    Raises:
        ArchiveError: If the archive file is invalid or if extraction fails.
    """
    _validate_paths(zst_path, extract_path)

    try:
        with open(zst_path, "rb") as zf:
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_reader(zf) as reader:
                with tarfile.open(fileobj=reader, mode="r|") as tf:
                    tf.extractall(extract_path, filter="data")
    except Exception as e:
        raise ArchiveError(f"Could not extract .zst archive '{zst_path}': {e}") from e
