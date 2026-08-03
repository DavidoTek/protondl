"""Modal screen for installing a new compatibility tool."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ProgressBar, Select

from protondl.core.base_installer import CtInstaller
from protondl.core.base_launcher import Launcher
from protondl.installers import CT_INSTALLERS, get_tools_for_launcher


class InstallToolScreen(ModalScreen[None]):
    """
    Modal screen to select a compatibility tool and version and install it.

    The tool dropdown lists all installers compatible with the launcher. Choosing a
    tool fetches its available versions and fills the version dropdown. Installing
    runs in a worker and reports progress through a progress bar.
    """

    BINDINGS = [
        Binding("escape", "pop_screen", "Close"),
    ]

    def __init__(self, launcher: Launcher) -> None:
        """
        Initializes the install dialog.

        Args:
            launcher: The launcher the new tool should be installed for.
        """
        self._launcher = launcher
        self._installers: list[CtInstaller] = []
        self._versions: list[str] = []
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="install-dialog"):
            yield Label("Add new compatibility tool", id="install-title")
            yield Label("Tool:")
            yield Select([], id="tool-select", prompt="Select a tool")
            yield Label("Version:")
            yield Select([], id="version-select", prompt="Select a tool first")
            yield ProgressBar(total=1, id="install-progress")
            yield Label("", id="install-status")
            with Horizontal(id="install-actions"):
                yield Button("Cancel", id="cancel-button")
                yield Button("Install", id="install-button", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self._installers = sorted(
            get_tools_for_launcher(self._launcher), key=lambda tool: CT_INSTALLERS.index(tool)
        )
        tool_select = self.query_one("#tool-select", Select)
        tool_select.set_options([(tool.name, i) for i, tool in enumerate(self._installers)])
        if self._installers:
            tool_select.value = 0
        else:
            tool_select.disabled = True

    def _current_tool(self) -> CtInstaller | None:
        tool_select = self.query_one("#tool-select", Select)
        value = tool_select.value
        if isinstance(value, int) and 0 <= value < len(self._installers):
            return self._installers[value]
        return None

    def _current_version(self) -> str | None:
        version_select = self.query_one("#version-select", Select)
        value = version_select.value
        if isinstance(value, str) and value in self._versions:
            return value
        return None

    @on(Select.Changed, "#tool-select")
    def _on_tool_changed(self) -> None:
        version_select = self.query_one("#version-select", Select)
        install_button = self.query_one("#install-button", Button)
        tool = self._current_tool()
        self._versions = []
        install_button.disabled = True
        if tool is None:
            version_select.set_options([])
            version_select.disabled = True
            return
        version_select.set_options([("Fetching versions...", "")])
        version_select.disabled = True
        self._fetch_versions(tool)

    @work(exclusive=True, group="versions", exit_on_error=False)
    async def _fetch_versions(self, tool: CtInstaller) -> None:
        version_select = self.query_one("#version-select", Select)
        try:
            versions = await tool.fetch_releases(count=30)
        except Exception as e:
            self.app.notify(f"Failed to fetch versions for {tool.name}: {e}", severity="error")
            version_select.set_options([("Failed to fetch versions", "")])
            version_select.disabled = True
            return
        self._versions = versions
        if versions:
            version_select.set_options([(version, version) for version in versions])
            version_select.value = versions[0]
            version_select.disabled = False
        else:
            version_select.set_options([("No versions found", "")])
            version_select.disabled = True

    @on(Select.Changed, "#version-select")
    def _on_version_changed(self) -> None:
        install_button = self.query_one("#install-button", Button)
        install_button.disabled = self._current_version() is None

    @on(Button.Pressed, "#cancel-button")
    def _on_cancel(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#install-button")
    def _on_install(self) -> None:
        tool = self._current_tool()
        version = self._current_version()
        if tool is None or version is None:
            return
        self._run_install(tool, version)

    @work(exclusive=True, group="install", exit_on_error=False)
    async def _run_install(self, tool: CtInstaller, version: str) -> None:
        tool_select = self.query_one("#tool-select", Select)
        version_select = self.query_one("#version-select", Select)
        install_button = self.query_one("#install-button", Button)
        cancel_button = self.query_one("#cancel-button", Button)
        progress_bar = self.query_one("#install-progress", ProgressBar)
        status = self.query_one("#install-status", Label)

        tool_select.disabled = True
        version_select.disabled = True
        install_button.disabled = True
        cancel_button.disabled = True
        progress_bar.styles.display = "block"
        status.styles.display = "block"
        status.update(f"Installing {tool.name} {version}...")
        progress_bar.total = 1
        progress_bar.progress = 0

        def update_progress(chunk_size: int, total_size: int) -> None:
            if total_size > 0:
                progress_bar.update(total=total_size, advance=chunk_size)
            else:
                progress_bar.update(advance=chunk_size)

        try:
            await tool.install(version, self._launcher, progress_callback=update_progress)
        except Exception as e:
            status.update("Installation failed.")
            self.app.notify(f"Installation of {tool.name} {version} failed: {e}", severity="error")
            tool_select.disabled = False
            cancel_button.disabled = False
            return

        status.update("Installation finished.")
        self.app.notify(f"Successfully installed {tool.name} {version}.")
        self.dismiss()
