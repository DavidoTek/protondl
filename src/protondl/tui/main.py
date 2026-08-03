"""Textual application entry point for the protondl TUI."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from protondl.tui.screens.main_screen import MainScreen


class ProtondlApp(App[None]):
    """Textual application for managing compatibility tools."""

    TITLE = "protondl"
    SUB_TITLE = "Compatibility Tool Manager"
    CSS_PATH = "main.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    def on_mount(self) -> None:
        self.push_screen(MainScreen())

    def action_refresh(self) -> None:
        """Refresh the installed tools list."""
        if isinstance(self.screen, MainScreen):
            self.screen.refresh_installed_tools()


def app() -> None:
    """Run the protondl TUI."""
    ProtondlApp().run()
