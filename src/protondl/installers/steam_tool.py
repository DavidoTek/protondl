from pathlib import Path

from protondl.core.base_installer import CtInstaller


class SteamToolInstaller(CtInstaller):
    """
    Base class for Steam Play compatibility tools that are not distributed as
    versioned builds (e.g. Boxtron, Roberta, Luxtorpeda).

    Such tools always extract into a fixed directory name instead of a
    version-specific one. The installed directory is therefore the fixed
    directory, independent of the installed version.
    """

    fixed_dir_name: str = ""

    def _find_installed_dir(
        self, install_dir: Path, before: set[Path], version: str
    ) -> Path | None:
        target = install_dir / self.fixed_dir_name
        return target if target.is_dir() else None
