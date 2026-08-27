from pathlib import Path

from protondl.core.base_installer import CtInstaller
from protondl.core.models import (
    Arch,
    CancelToken,
    CompatToolType,
    ProgressCallback,
    ReleaseData,
    ReleaseVersion,
)
from protondl.util.archive import extract_zip_with_tar
from protondl.util.download import fetch_github_artifact_data, fetch_github_project_workflows


class DXVKNightlyInstaller(CtInstaller):
    name = "DXVK (nightly)"
    description = (
        "Nightly version of DXVK (master branch), "
        "a Vulkan based implementation of Direct3D 8, 9, 10 and 11 for Linux/Wine."
    )
    tool_type = CompatToolType.DXVK
    advanced = True

    info_url = "https://github.com/doitsujin/dxvk"
    release_info_url = "https://github.com/doitsujin/dxvk/releases/tag/{version}"
    api_url = "https://api.github.com/repos/doitsujin/dxvk/releases"
    release_format = ".zip"  # GitHub artifact downloads are always .zip
    checksum_suffix = ""

    ct_workflow_url = "https://api.github.com/repos/doitsujin/dxvk/actions/workflows"
    ct_artifact_url = "https://api.github.com/repos/doitsujin/dxvk/actions/runs/{}/artifacts"
    ct_info_url_ci = "https://github.com/doitsujin/dxvk/actions/runs/"
    ct_nightly_link = (
        "https://nightly.link/doitsujin/dxvk/actions/runs/{version}/{artifact_name}.zip"
    )
    package_name = "artifacts"

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[ReleaseVersion]:
        workflow_ids = await fetch_github_project_workflows(
            self.ct_workflow_url, self.package_name, self.request_config, count, page
        )
        return [ReleaseVersion(version=workflow_id) for workflow_id in workflow_ids]

    async def _fetch_release_data(self, version: str, arch: Arch) -> ReleaseData:
        return await fetch_github_artifact_data(
            self.api_url, self.ct_artifact_url, self.ct_nightly_link, version, self.request_config
        )

    def _extract_archive(
        self,
        archive_path: Path,
        extract_to: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> None:
        extract_to = extract_to / ("dxvk-" + archive_path.stem.split("-")[-1])
        super()._extract_archive(
            archive_path,
            extract_to,
            progress_callback=progress_callback,
            cancel_token=cancel_token,
        )
        for item in extract_to.iterdir():
            # remove DXVK native archive
            if item.is_file() and item.suffix == ".gz":
                extract_zip_with_tar(
                    item, extract_to, progress_callback=progress_callback, cancel_token=cancel_token
                )
                item.unlink()
