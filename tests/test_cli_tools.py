import os
import signal

import pytest
from typer.testing import CliRunner

from protondl.cli import app
from protondl.core.base_launcher import Launcher
from protondl.core.models import (
    AlreadyInstalledError,
    Arch,
    CancelToken,
    CompatToolVersionInfo,
    InstallProgress,
    InstallStep,
    ProgressCallback,
)

runner = CliRunner()


class _FakeLauncher:
    name = "Steam"


class _FakeInstaller:
    name = "GE-Proton"
    supported_archs = (Arch.X86_64, Arch.AARCH64)

    def __init__(self) -> None:
        self.calls: list[tuple[str, Arch | None, bool]] = []
        self.cancel_tokens: list[CancelToken | None] = []
        self.already_installed = False

    def supports_launcher(self, launcher: Launcher) -> bool:
        return True

    async def install(
        self,
        version: str,
        launcher: Launcher,
        arch: Arch | None = None,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CompatToolVersionInfo:
        self.calls.append((version, arch, force))
        self.cancel_tokens.append(cancel_token)
        if progress_callback is not None:
            progress_callback(InstallProgress(step=InstallStep.FINISHING, current=1, total=1))
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        if self.already_installed:
            raise AlreadyInstalledError(self.name, version, arch or Arch.X86_64)
        return CompatToolVersionInfo(
            compat_tool=self.name,
            version=version,
            installed_at=1,
            arch=arch,
        )


def _patch_cli(monkeypatch: pytest.MonkeyPatch) -> _FakeInstaller:
    installer = _FakeInstaller()
    monkeypatch.setattr(
        "protondl.cli.tools.select_launcher", lambda launcher_id, **_: _FakeLauncher()
    )
    monkeypatch.setattr(
        "protondl.cli.tools.resolve_installer", lambda tool_name, request_config=None: installer
    )
    return installer


def test_install_exits_2_when_version_already_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = _patch_cli(monkeypatch)
    installer.already_installed = True

    result = runner.invoke(app, ["install", "1", "GE-Proton", "GE-Proton11-3"])

    assert result.exit_code == 2
    assert "GE-Proton11-3 (x86_64) is already installed." in result.stdout
    assert "Successfully installed" not in result.stdout


def test_install_passes_force_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    installer = _patch_cli(monkeypatch)

    result = runner.invoke(
        app, ["install", "1", "GE-Proton", "GE-Proton11-3", "--arch", "aarch64", "--force"]
    )

    assert result.exit_code == 0
    assert installer.calls == [("GE-Proton11-3", Arch.AARCH64, True)]
    assert "Successfully installed GE-Proton (aarch64)" in result.stdout


def test_install_defaults_to_host_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    installer = _patch_cli(monkeypatch)

    result = runner.invoke(app, ["install", "1", "GE-Proton", "GE-Proton11-3"])

    assert result.exit_code == 0
    assert installer.calls[0][1] is None
    assert installer.calls[0][2] is False


def test_install_failure_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    installer = _patch_cli(monkeypatch)

    async def failing_install(*args: object, **kwargs: object) -> CompatToolVersionInfo:
        raise ConnectionError("network down")

    installer.install = failing_install  # type: ignore[method-assign]

    result = runner.invoke(app, ["install", "1", "GE-Proton", "GE-Proton11-3"])

    assert result.exit_code == 1
    assert "Installation failed: network down" in result.stdout


def test_install_passes_cancel_token(monkeypatch: pytest.MonkeyPatch) -> None:
    installer = _patch_cli(monkeypatch)

    result = runner.invoke(app, ["install", "1", "GE-Proton", "GE-Proton11-3"])

    assert result.exit_code == 0
    assert installer.cancel_tokens and isinstance(installer.cancel_tokens[0], CancelToken)
    assert not installer.cancel_tokens[0].cancelled


def test_install_cancelled_on_sigint(monkeypatch: pytest.MonkeyPatch) -> None:
    installer = _patch_cli(monkeypatch)

    async def cancelling_install(
        version: str,
        launcher: Launcher,
        arch: Arch | None = None,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CompatToolVersionInfo:
        # Simulate the user pressing Ctrl+C during the installation.
        os.kill(os.getpid(), signal.SIGINT)
        assert cancel_token is not None
        cancel_token.raise_if_cancelled()
        raise AssertionError("install should have been cancelled")

    installer.install = cancelling_install  # type: ignore[method-assign]

    result = runner.invoke(app, ["install", "1", "GE-Proton", "GE-Proton11-3"])

    assert result.exit_code == 130
    assert "Installation cancelled." in result.stdout


def test_install_restores_sigint_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cli(monkeypatch)
    original = signal.getsignal(signal.SIGINT)

    result = runner.invoke(app, ["install", "1", "GE-Proton", "GE-Proton11-3"])

    assert result.exit_code == 0
    assert signal.getsignal(signal.SIGINT) is original
