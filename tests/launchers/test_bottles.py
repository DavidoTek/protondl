from pathlib import Path

import pytest

from protondl.core.models import CompatToolType, InstallMode
from protondl.launchers import SUPPORTED_LAUNCHER_CLASSES
from protondl.launchers.bottles import BottlesLauncher


def test_get_compatibility_tools_path(tmp_path: Path) -> None:
    """
    Test that the Bottles compatibility tools path is resolved and created.
    """
    launcher = BottlesLauncher("Bottles", tmp_path, InstallMode.NATIVE)

    proton_path = launcher.get_compatibility_tools_path(CompatToolType.PROTON)
    wine_path = launcher.get_compatibility_tools_path(CompatToolType.WINE)

    assert proton_path == tmp_path / "runners"
    assert wine_path == tmp_path / "runners"
    assert proton_path.exists()


def test_get_compatibility_tools_path_unsupported_type_raises(tmp_path: Path) -> None:
    launcher = BottlesLauncher("Bottles", tmp_path, InstallMode.NATIVE)

    with pytest.raises(ValueError, match="BottlesLauncher only supports"):
        launcher.get_compatibility_tools_path(CompatToolType.DXVK)


def test_is_valid_bottles_home(tmp_path: Path) -> None:
    valid_home = tmp_path / "valid"
    (valid_home / "runners").mkdir(parents=True)

    invalid_home = tmp_path / "invalid"
    invalid_home.mkdir(parents=True)

    assert BottlesLauncher._is_valid_bottles_home(valid_home)
    assert not BottlesLauncher._is_valid_bottles_home(invalid_home)


def test_discover_finds_native_and_flatpak(monkeypatch: pytest.MonkeyPatch) -> None:
    native_root = Path("~/.local/share/bottles").expanduser()
    flatpak_root = Path("~/.var/app/com.usebottles.bottles/data/bottles").expanduser()

    def mock_exists(path: Path) -> bool:
        return path in {native_root, flatpak_root}

    monkeypatch.setattr(Path, "exists", mock_exists)
    monkeypatch.setattr(BottlesLauncher, "_is_valid_bottles_home", staticmethod(lambda _p: True))

    found = BottlesLauncher.discover()

    assert len(found) == 2
    assert {launcher.name for launcher in found} == {"Bottles", "Bottles Flatpak"}
    assert {launcher.install_mode for launcher in found} == {
        InstallMode.NATIVE,
        InstallMode.FLATPAK,
    }


def test_bottles_launcher_is_registered() -> None:
    assert BottlesLauncher in SUPPORTED_LAUNCHER_CLASSES
