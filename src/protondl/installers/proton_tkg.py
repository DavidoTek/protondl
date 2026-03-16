from pathlib import Path

from protondl.core.base_installer import CtInstaller
from protondl.core.models import CompatToolType, ReleaseData
from protondl.util.archive import extract_zip_with_tar
from protondl.util.download import fetch_github_artifact_data, fetch_github_project_workflows


class ProtonTkgInstaller(CtInstaller):
    name = "Proton-Tkg"
    description = (
        "Custom Proton build for running Windows games, built with the Wine-tkg build system."
    )
    tool_type = CompatToolType.PROTON
    advanced = False
    info_url = "https://github.com/Frogging-Family/wine-tkg-git"
    release_info_url = "https://github.com/Frogging-Family/wine-tkg-git/releases/tag/{version}"
    api_url = "https://github.com/Frogging-Family/wine-tkg-git/releases"
    # release format is .tar.gz but the pipeline artifact is .zip containing a .tar.zst or .tar
    release_format = ".tar.gz"
    checksum_suffix = ""

    ct_workflow_url = "https://api.github.com/repos/Frogging-Family/wine-tkg-git/actions/workflows"
    ct_artifact_url = (
        "https://api.github.com/repos/Frogging-Family/wine-tkg-git/actions/runs/{}/artifacts"
    )
    ct_info_url_ci = "https://github.com/Frogging-Family/wine-tkg-git/actions/runs/"
    ct_nightly_link = "https://nightly.link/Frogging-Family/wine-tkg-git/actions/runs/{version}/{artifact_name}.zip"
    package_name = "proton-valvexbe-arch-nopackage"

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[str]:
        return await fetch_github_project_workflows(
            self.ct_workflow_url, self.package_name, self.request_config, count, page
        )

        # Note: Old (pre-2022) GitHub releases are not fetched

    async def _fetch_release_data(self, version: str) -> ReleaseData:
        return await fetch_github_artifact_data(
            self.api_url, self.ct_artifact_url, self.ct_nightly_link, version, self.request_config
        )

    def _extract_archive(self, archive_path: Path, extract_to: Path) -> None:
        """
        Extracts the downloaded archive, which is a .zip containing either a .tar.zst or .tar.
        """
        extract_zip_with_tar(archive_path, extract_to)
