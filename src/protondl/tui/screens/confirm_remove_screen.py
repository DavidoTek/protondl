"""Confirmation dialog for removing an installed compatibility tool."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from protondl.core.models import CompatTool


class ConfirmRemoveScreen(ModalScreen[bool]):
    """
    Modal screen that asks for confirmation before a tool is removed.

    Dismisses with ``True`` when the user confirms the removal and ``False`` otherwise.
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel"),
    ]

    def __init__(self, tool: CompatTool) -> None:
        """
        Initializes the confirmation dialog.

        Args:
            tool: The installed compatibility tool that would be removed.
        """
        self._tool = tool
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(f"Remove {self._tool.full_name}?", id="confirm-label")
            yield Label(
                "This will delete the compatibility tool from the launcher. "
                "This action cannot be undone.",
                id="confirm-subtitle",
            )
            with Horizontal(id="confirm-actions"):
                yield Button("Cancel", id="confirm-cancel-button")
                yield Button("Remove", id="confirm-remove-button", variant="error")

    def action_dismiss_modal(self) -> None:
        """Cancel the removal when the Escape key is pressed."""
        self.dismiss(False)

    @on(Button.Pressed, "#confirm-cancel-button")
    def _on_cancel(self) -> None:
        """Dismiss the dialog without removing the tool."""
        self.dismiss(False)

    @on(Button.Pressed, "#confirm-remove-button")
    def _on_confirm(self) -> None:
        """Dismiss the dialog and confirm the removal."""
        self.dismiss(True)
