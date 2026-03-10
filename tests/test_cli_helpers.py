import pytest
import typer

from protondl.cli.helpers import resolve_installer, select_launcher
from protondl.installers import CT_INSTALLERS


def test_select_launcher_invalid_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("protondl.cli.helpers.get_launchers", lambda: [])
    with pytest.raises(typer.Exit):
        select_launcher(1)


def test_resolve_installer_by_name() -> None:
    assert resolve_installer(CT_INSTALLERS[0].name) is CT_INSTALLERS[0]


def test_resolve_installer_global_index() -> None:
    # numeric IDs correspond to CT_INSTALLERS order and are independent of launcher
    assert resolve_installer("1") is CT_INSTALLERS[0]
    assert resolve_installer(str(len(CT_INSTALLERS))) is CT_INSTALLERS[-1]
    # out-of-range returns None
    assert resolve_installer(str(len(CT_INSTALLERS) + 1)) is None
