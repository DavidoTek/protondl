"""Main screen of the protondl TUI."""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Select, Static

from protondl.core.base_launcher import Launcher
from protondl.core.models import CompatTool
from protondl.launchers import detect_all_launchers
from protondl.tui.screens.confirm_remove_screen import ConfirmRemoveScreen
from protondl.tui.screens.install_screen import InstallToolScreen


class MainScreen(Screen[None]):
    """
    Main screen showing the selected launcher, its installed tools and the
    actions to add or remove tools.
    """

    def __init__(self) -> None:
        self._launchers: list[Launcher] = []
        self._current_launcher: Launcher | None = None
        self._installed_tools: list[CompatTool] = []
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-container"):
            yield Label("Launcher:")
            yield Select([], id="launcher-select", prompt="Select a launcher")
            yield Label("Installed compatibility tools", classes="section-title")
            yield Static("", id="empty-hint")
            yield ListView(id="installed-tools")
            with Horizontal(id="actions"):
                yield Button("Remove selected", id="remove-button", variant="error", disabled=True)
                yield Button("Add new tool", id="add-button", variant="primary", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self._launchers = detect_all_launchers()
        launcher_select = self.query_one("#launcher-select", Select)
        launcher_select.set_options(
            [
                (f"{launcher.name} ({launcher.install_mode.value})", i)
                for i, launcher in enumerate(self._launchers)
            ]
        )
        if self._launchers:
            launcher_select.value = 0
        else:
            launcher_select.disabled = True
            self.refresh_installed_tools()

    def _selected_tool(self) -> CompatTool | None:
        list_view = self.query_one("#installed-tools", ListView)
        index = list_view.index
        if index is not None and 0 <= index < len(self._installed_tools):
            return self._installed_tools[index]
        return None

    @on(Select.Changed, "#launcher-select")
    def _on_launcher_selected(self, event: Select.Changed) -> None:
        value = event.value
        if isinstance(value, int) and 0 <= value < len(self._launchers):
            self._current_launcher = self._launchers[value]
        else:
            self._current_launcher = None
        self.refresh_installed_tools()

    @work(exclusive=True, group="refresh", exit_on_error=False)
    async def refresh_installed_tools(self) -> None:
        """Scan and display the tools installed for the current launcher."""
        launcher = self._current_launcher
        list_view = self.query_one("#installed-tools", ListView)
        hint = self.query_one("#empty-hint", Static)
        remove_button = self.query_one("#remove-button", Button)
        add_button = self.query_one("#add-button", Button)

        list_view.clear()
        self._installed_tools = []
        if launcher is None:
            hint.update("No launchers detected on your system.")
            hint.styles.display = "block"
            remove_button.disabled = True
            add_button.disabled = True
            return

        try:
            tools = await asyncio.to_thread(launcher.get_installed_tools)
        except Exception as e:
            hint.update(f"Failed to scan installed tools: {e}")
            hint.styles.display = "block"
            remove_button.disabled = True
            add_button.disabled = True
            return

        self._installed_tools = sorted(tools, key=lambda tool: tool.full_name)
        for tool in self._installed_tools:
            list_view.append(ListItem(Label(f"{tool.full_name}   ({tool.tool_type.value})")))

        add_button.disabled = False
        remove_button.disabled = not self._installed_tools
        if self._installed_tools:
            hint.styles.display = "none"
        else:
            hint.update(f"No compatibility tools installed for {launcher.name}.")
            hint.styles.display = "block"

    @on(Button.Pressed, "#remove-button")
    def _on_remove(self) -> None:
        tool = self._selected_tool()
        if tool is None:
            return

        def handle(confirmed: bool | None) -> None:
            if confirmed:
                self._remove_tool(tool)

        self.app.push_screen(ConfirmRemoveScreen(tool), handle)

    @work(exclusive=True, group="remove", exit_on_error=False)
    async def _remove_tool(self, tool: CompatTool) -> None:
        launcher = self._current_launcher
        if launcher is None:
            return
        try:
            await asyncio.to_thread(launcher.remove_tool, tool)
        except Exception as e:
            self.app.notify(f"Failed to remove {tool.full_name}: {e}", severity="error")
            return
        self.app.notify(f"Removed {tool.full_name}.")
        self.refresh_installed_tools()

    @on(Button.Pressed, "#add-button")
    def _on_add(self) -> None:
        if self._current_launcher is None:
            return

        def handle(_: None) -> None:
            self.refresh_installed_tools()

        self.app.push_screen(InstallToolScreen(self._current_launcher), handle)
