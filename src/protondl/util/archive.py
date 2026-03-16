import glob
import shutil
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


def extract_zip_with_tar(zip_path: Path, extract_path: Path) -> None:
    """
    Extracts a .zip file that contains either a .tar.zst or .tar archive.
    Renames the extracted "usr" directory to match the archive name (without .tar extension).
    Dotfiles like .BUILDINFO, .INSTALL, .MTREE, and .PKGINFO are removed after extraction.

    Args:
        zip_path: The path to the .zip file.
        extract_path: The path where the archive should be extracted.
    Raises:
        ArchiveError: If the archive file is invalid or if extraction fails.
    """
    archive_str = str(zip_path)

    if archive_str.endswith(".tar.gz"):
        extract_tar(zip_path, extract_path, compression="gz")
    elif archive_str.endswith(".zip"):
        tmp_dir = extract_path / "extract_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            extract_zip(zip_path, tmp_dir)

            if zst_files := glob.glob(f"{tmp_dir}/*.tar.zst"):
                zst_file = Path(zst_files[0])
                extract_tar_zst(zst_file, extract_path)
                if (extract_path / "usr").exists():
                    (extract_path / "usr").rename(extract_path / zst_file.stem.replace(".tar", ""))
                for dotfile in [".BUILDINFO", ".INSTALL", ".MTREE", ".PKGINFO"]:
                    (extract_path / dotfile).unlink(missing_ok=True)
                zst_file.unlink(missing_ok=True)
            elif tar_files := glob.glob(f"{tmp_dir}/*.tar*"):
                tar_file = Path(tar_files[0])
                extract_tar(tar_file, extract_path)
                tar_file.unlink(missing_ok=True)
        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ArchiveError(f"Failed to extract zip with tar '{zip_path}': {e}") from e
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    else:
        raise ArchiveError(f"Unsupported archive format for file: {zip_path}")
