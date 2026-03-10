import glob
from pathlib import Path

import httpx

from protondl.core.base_installer import CtInstaller
from protondl.core.models import CompatToolType, GitHubArtifact, GitHubArtifactResponse, ReleaseData
from protondl.util.archive import extract_tar, extract_tar_zst, extract_zip


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
    proton_package_name = "proton-valvexbe-arch-nopackage"

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[str]:
        """
        Fetches a list of available release versions. For Proton-Tkg, this involves fetching
        workflow runs from GitHub Actions and extracting the run IDs as version identifiers.
        """
        async with httpx.AsyncClient() as client:
            return await self._fetch_workflows(client, count)

        # Note: Old (pre-2022) GitHub releases are not fetched

    async def _fetch_workflows(self, client: httpx.AsyncClient, count: int = 30) -> list[str]:
        tags = []
        wf_resp = await client.get(f"{self.ct_workflow_url}?per_page={str(count)}")
        for wf in wf_resp.json().get("workflows", []):
            if wf["state"] != "active" or self.proton_package_name not in wf["path"]:
                continue
            page = 1
            while page != -1 and page < 5:
                # fetch more (up to 5 pages) if first releases all failed
                # ensure the reason that len(tags)=0 is that releases failed
                at_least_one_failed = False
                runs_resp = await client.get(
                    f"{wf['url']}/runs?per_page={str(count)}&page={str(page)}"
                )
                for run in runs_resp.json().get("workflow_runs", []):
                    if run["conclusion"] == "success":
                        tags.append(str(run["id"]))
                    elif run["conclusion"] == "failure":
                        at_least_one_failed = True
                if len(tags) == 0 and at_least_one_failed:
                    page += 1
                else:
                    page = -1

        return tags

    async def _fetch_release_data(self, version: str) -> ReleaseData:
        """
        Fetches release data for a given version. First attempts to find an artifact from
        the workflow run ID (which is the version), and if not found, falls back to fetching
        release data from the GitHub API using the version as a tag.

        Args:
            version: The version string to fetch release data for.

        Returns:
            A ReleaseData object containing the release information.
        """
        async with httpx.AsyncClient() as client:
            artifact = await self._get_artifact_from_id(client, version)
            if artifact:
                return ReleaseData(
                    version=artifact["workflow_run"]["head_sha"],
                    date=artifact["updated_at"].split("T")[0],
                    download=f"https://nightly.link/Frogging-Family/wine-tkg-git/actions/runs/{artifact['workflow_run']['id']}/{artifact['name']}.zip",
                    size=artifact["size_in_bytes"],
                    original_filename=f"{artifact['name']}.zip",
                )

            url = f"{self.api_url}/tags/{version}" if version else f"{self.api_url}/latest"
            resp = await client.get(url)
            data = resp.json()

            if "tag_name" not in data:
                raise ValueError(f"Release with version '{version}' not found.")

            download_url = None
            size = 0
            for asset in data.get("assets", []):
                if "proton" in asset["name"]:
                    download_url = asset["browser_download_url"]
                    size = asset["size"]
                    break

            if not download_url:
                raise ValueError(f"No suitable asset found for version '{version}'.")

            return ReleaseData(
                version=data["tag_name"],
                date=data["published_at"].split("T")[0],
                download=download_url,
                size=size,
            )

    async def _get_artifact_from_id(
        self, client: httpx.AsyncClient, version: str
    ) -> GitHubArtifact | None:
        """
        Get artifact from workflow run id.

        Args:
            client: An instance of httpx.AsyncClient to make the API request.
            version: The workflow run id to search for.

        Returns:
            The artifact information if found, otherwise None.
        """
        resp = await client.get(f"{self.ct_artifact_url.format(version)}?per_page=100")
        artifact_info: GitHubArtifactResponse = resp.json()
        if artifact_info.get("total_count") == 1:
            return artifact_info["artifacts"][0]
        return None

    def _extract_archive(self, archive_path: Path, extract_to: Path) -> None:
        """
        Extracts the downloaded archive, which is a .zip containing either a .tar.zst or .tar.
        """
        archive_str = str(archive_path)

        if archive_str.endswith(".tar.gz"):
            extract_tar(archive_path, extract_to, compression="gz")
        elif archive_str.endswith(".zip"):
            tmp_dir = extract_to / "tkg_extract_tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            extract_zip(archive_path, tmp_dir)

            if zst_files := glob.glob(f"{tmp_dir}/*.tar.zst"):
                zst_file = Path(zst_files[0])
                extract_tar_zst(zst_file, extract_to)
                (extract_to / "usr").rename(extract_to / zst_file.stem.replace(".tar", ""))
                for dotfile in [".BUILDINFO", ".INSTALL", ".MTREE", ".PKGINFO"]:
                    (extract_to / dotfile).unlink(missing_ok=True)
                zst_file.unlink(missing_ok=True)
            elif tar_files := glob.glob(f"{tmp_dir}/*.tar"):
                tar_file = Path(tar_files[0])
                extract_tar(tar_file, extract_to)
                tar_file.unlink(missing_ok=True)

            tmp_dir.rmdir()
