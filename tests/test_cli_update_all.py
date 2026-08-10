from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from protondl.cli import app
from protondl.core.base_launcher import Launcher
from protondl.core.models import (
    CompatTool,
    CompatToolType,
    RequestConfig,
    ToolUpdate,
    UpdateCheckResult,
)

runner = CliRunner()


class _FakeLauncher:
    name = "Steam"

    def get_installed_tools(self) -> list[CompatTool]:
        return [CompatTool("GE-Proton11-3", CompatToolType.PROTON, Path("/tools/GE-Proton11-3"))]


def _update() -> ToolUpdate:
    return ToolUpdate(
        compat_tool_name="GE-Proton",
        latest_version="GE-Proton11-3",
        installed_versions=["GE-Proton10-5"],
        installed_tools=[
            CompatTool("GE-Proton10-5", CompatToolType.PROTON, Path("/tools/GE-Proton10-5"))
        ],
    )


def _make_result() -> UpdateCheckResult:
    return UpdateCheckResult(updates=[_update()], up_to_date=["DXVK"], unchecked=[])


def _patch_cli(
    monkeypatch: pytest.MonkeyPatch,
    result: UpdateCheckResult,
) -> list[str]:
    monkeypatch.setattr("protondl.cli.tools.select_launcher", lambda launcher_id: _FakeLauncher())

    async def fake_check_for_updates(
        launcher: Launcher, request_config: RequestConfig | None = None
    ) -> UpdateCheckResult:
        return result

    monkeypatch.setattr("protondl.cli.tools.check_for_updates", fake_check_for_updates)

    installed: list[str] = []

    async def fake_update_compatibility_tools(
        launcher: Launcher,
        updates: list[ToolUpdate],
        keep_old: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
        request_config: RequestConfig | None = None,
    ) -> None:
        for update in updates:
            installed.append(update.latest_version)
        if progress_callback:
            progress_callback(len(updates), len(updates))

    monkeypatch.setattr(
        "protondl.cli.tools.update_compatibility_tools", fake_update_compatibility_tools
    )

    monkeypatch.setattr(
        "protondl.cli.tools.batch_update_games_tools",
        lambda launcher, from_tool, to_tool: 3,
    )
    return installed


def test_update_all_no_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.tools.select_launcher", lambda launcher_id: _FakeLauncher())

    async def fake_check_for_updates(
        launcher: Launcher, request_config: RequestConfig | None = None
    ) -> UpdateCheckResult:
        return UpdateCheckResult(updates=[], up_to_date=["GE-Proton"], unchecked=["SomeTool"])

    monkeypatch.setattr("protondl.cli.tools.check_for_updates", fake_check_for_updates)

    result = runner.invoke(app, ["update-all", "1"])

    assert result.exit_code == 0
    assert "No updates available" in result.stdout
    assert "Could not check for updates for: SomeTool" in result.stdout
    assert "Up to date: GE-Proton" in result.stdout


def test_update_all_yes_flags_installs_and_batch_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = _patch_cli(monkeypatch, _make_result())

    result = runner.invoke(
        app, ["update-all", "1", "--yes-install", "--yes-batch-update"], input=""
    )

    assert result.exit_code == 0
    assert installed == ["GE-Proton11-3"]
    assert "Compatibility tools updated successfully" in result.stdout
    assert "Updated 3 games to GE-Proton11-3" in result.stdout


def test_update_all_default_deletes_old_and_always_batch_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = _patch_cli(monkeypatch, _make_result())

    result = runner.invoke(app, ["update-all", "1", "--yes-install"], input="")

    assert result.exit_code == 0
    assert installed == ["GE-Proton11-3"]
    assert "Updated 3 games to GE-Proton11-3" in result.stdout


def test_update_all_keep_old_prompts_batch_update_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = _patch_cli(monkeypatch, _make_result())

    result = runner.invoke(app, ["update-all", "1", "--keep-old", "--yes-install"], input="n\n")

    assert result.exit_code == 0
    assert installed == ["GE-Proton11-3"]
    assert "Updated 3 games" not in result.stdout


def test_update_all_keep_old_batch_update_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = _patch_cli(monkeypatch, _make_result())

    result = runner.invoke(app, ["update-all", "1", "--keep-old", "--yes-install"], input="y\n")

    assert result.exit_code == 0
    assert installed == ["GE-Proton11-3"]
    assert "Updated 3 games to GE-Proton11-3" in result.stdout


def test_update_all_install_declined(monkeypatch: pytest.MonkeyPatch) -> None:
    installed = _patch_cli(monkeypatch, _make_result())

    result = runner.invoke(app, ["update-all", "1"], input="n\n")

    assert result.exit_code == 0
    assert installed == []
    assert "Do you want to install the updates?" in result.stdout


def test_update_all_check_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.tools.select_launcher", lambda launcher_id: _FakeLauncher())

    async def fake_check_for_updates(
        launcher: Launcher, request_config: RequestConfig | None = None
    ) -> UpdateCheckResult:
        raise RuntimeError("boom")

    monkeypatch.setattr("protondl.cli.tools.check_for_updates", fake_check_for_updates)

    result = runner.invoke(app, ["update-all", "1"])

    assert result.exit_code == 1
    assert "Failed to check for updates: boom" in result.stdout
