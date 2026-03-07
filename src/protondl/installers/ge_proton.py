import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.launchers.steam import SteamLauncher
from protondl.util.archive import extract_tar
from protondl.util.download import (
    calculate_sha512,
    fetch_project_release_data,
    fetch_project_releases,
)


class GEProtonInstaller(CtInstaller):
    name = "GE-Proton"
    description = "A community-built version of Proton with additional features and fixes."
    # Using the class type as requested, though you might prefer strings for slugs
    supported_launchers = [SteamLauncher]
    info_url = "https://github.com/GloriousEggroll/proton-ge-custom"
    release_info_url = "https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/{version}"
    release_format = ".tar.gz"

    # GitHub API endpoint
    _API_URL = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[str]:
        """Fetches release tags from the GitHub API."""
        return await fetch_project_releases(
            releases_url=self._API_URL,
            config=self.request_config,
            count=count,
            page=page,
        )

    async def install(
        self,
        version: str,
        launcher: Launcher,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        release_data = await fetch_project_release_data(
            release_url=self._API_URL,
            release_format=self.release_format,
            config=self.request_config,
            tag=version,
            checksum_suffix=".sha512sum",
        )

        if not release_data.download:
            raise ValueError(f"No downloadable asset found for version '{version}'")

        async with httpx.AsyncClient(
            headers=self.request_config.get_headers(), follow_redirects=True
        ) as client:
            with tempfile.NamedTemporaryFile(suffix=self.release_format, delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

                async with client.stream("GET", release_data.download) as response:
                    response.raise_for_status()
                    total_size = (
                        release_data.size
                        if release_data.size and release_data.size > 0
                        else int(response.headers.get("Content-Length", 0))
                    )

                    async for chunk in response.aiter_bytes():
                        tmp_file.write(chunk)
                        if progress_callback:
                            progress_callback(len(chunk), total_size)

                    tmp_file.flush()

            if release_data.checksum:
                sha_resp = await client.get(release_data.checksum)
                sha_resp.raise_for_status()

                expected_sha = sha_resp.text.split()[0].strip()
                actual_sha = calculate_sha512(tmp_path, self.buffer_size)

                if actual_sha != expected_sha:
                    tmp_path.unlink()
                    raise ValueError("Checksum verification failed! The file may be corrupted.")

            try:
                install_dir = launcher.get_compatibility_tools_path()
                extract_tar(tmp_path, install_dir, compression=self.release_format.split(".")[-1])
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
