import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.launchers.steam import SteamLauncher


class GEProtonInstaller(CtInstaller):
    name = "GE-Proton"
    description = "A community-built version of Proton with additional features and fixes."
    # Using the class type as requested, though you might prefer strings for slugs
    supported_launchers = [SteamLauncher]
    info_url = "https://github.com/GloriousEggroll/proton-ge-custom"
    release_info_url = "https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/{version}"

    # GitHub API endpoint
    _API_URL = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"

    async def fetch_releases(self, count: int = 30, page: int = 1) -> list[str]:
        """Fetches release tags from the GitHub API."""
        params = {"per_page": count, "page": page}
        headers = self.request_config.get_headers()

        async with httpx.AsyncClient(headers=headers) as client:
            response = await client.get(self._API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            return [release["tag_name"] for release in data]

    async def install(
        self,
        version: str,
        launcher: Launcher,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        headers = self.request_config.get_headers()

        # 1. Get Release Data
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            if version == "latest":
                url = f"{self._API_URL}/latest"
            else:
                url = f"{self._API_URL}/tags/{version}"

            resp = await client.get(url)
            resp.raise_for_status()
            release_data = resp.json()

            # 2. Find the .tar.gz asset
            asset = next(
                (a for a in release_data["assets"] if a["name"].endswith(".tar.gz")),
                None,
            )
            if not asset:
                raise ValueError(f"No tar.gz asset found for version {version}")

            download_url = asset["browser_download_url"]
            install_dir = launcher.get_compatibility_tools_path()

            # 3. Download to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

                async with client.stream("GET", download_url) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get("Content-Length", 0))

                    # REMOVED the second 'with tempfile...' line here
                    async for chunk in response.aiter_bytes():
                        tmp_file.write(chunk)
                        if progress_callback:
                            progress_callback(len(chunk), total_size)

                    # Critical: Ensure all data is flushed to disk before extraction
                    tmp_file.flush()

            # 4. Extract
            try:
                self._extract_tool(tmp_path, install_dir)
            finally:
                # Always clean up the temp file
                if tmp_path.exists():
                    tmp_path.unlink()

    def _extract_tool(self, archive_path: Path, extract_to: Path) -> None:
        """Standard tar extraction logic."""
        with tarfile.open(archive_path, "r:gz") as tar:
            # We use filter='data' for security if using Python 3.12+
            tar.extractall(path=extract_to, filter="data")

    def supports_launcher(self, launcher: Launcher) -> bool:
        """Matches based on the class type provided in supported_launchers."""
        return any(isinstance(launcher, cls) for cls in self.supported_launchers)
