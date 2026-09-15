from collections.abc import Callable
from pathlib import Path

import pytest

from protondl.core.base_launcher import Launcher
from protondl.core.models import CompatTool, CompatToolType, InstallMode
from protondl.launchers import SUPPORTED_LAUNCHER_CLASSES

# Capabilities that map 1:1 onto Launcher's abstract methods: when declared
# unsupported, the base class's subclass override must raise
# NotImplementedError; when declared supported, calling it must not.
CAPABILITY_CALLS: dict[str, Callable[[Launcher], object]] = {
    "supports_game_list": lambda launcher: launcher.get_game_list(),
    "supports_per_game_tools": lambda launcher: launcher.set_games_tools({}),
    "supports_global_tool": lambda launcher: launcher.get_global_tool(CompatToolType.PROTON),
}


def _make_launcher(launcher_cls: type[Launcher], tmp_path: Path) -> Launcher:
    return launcher_cls(launcher_cls.__name__, tmp_path, InstallMode.NATIVE)


@pytest.mark.parametrize("launcher_cls", SUPPORTED_LAUNCHER_CLASSES)
@pytest.mark.parametrize("capability", CAPABILITY_CALLS)
def test_capability_flag_matches_method_behavior(
    launcher_cls: type[Launcher], capability: str, tmp_path: Path
) -> None:
    """
    A declared-unsupported capability must raise NotImplementedError; a
    declared-supported one must not (other errors, e.g. from missing launcher
    files in tmp_path, are expected and ignored here).
    """
    launcher = _make_launcher(launcher_cls, tmp_path)
    supported = getattr(launcher, capability)
    call = CAPABILITY_CALLS[capability]

    if supported:
        try:
            call(launcher)
        except NotImplementedError:
            pytest.fail(
                f"{launcher_cls.__name__}.{capability} is True but the method "
                "raised NotImplementedError"
            )
        except Exception:
            pass
    else:
        with pytest.raises(NotImplementedError):
            call(launcher)


@pytest.mark.parametrize("launcher_cls", SUPPORTED_LAUNCHER_CLASSES)
def test_supports_global_tool_covers_set_global_tool(
    launcher_cls: type[Launcher], tmp_path: Path
) -> None:
    launcher = _make_launcher(launcher_cls, tmp_path)
    tool = CompatTool("Some-Tool", CompatToolType.PROTON, tmp_path / "Some-Tool")

    if launcher.supports_global_tool:
        try:
            launcher.set_global_tool(tool)
        except NotImplementedError:
            pytest.fail(
                f"{launcher_cls.__name__}.supports_global_tool is True but "
                "set_global_tool() raised NotImplementedError"
            )
        except Exception:
            pass
    else:
        with pytest.raises(NotImplementedError):
            launcher.set_global_tool(tool)


@pytest.mark.parametrize("launcher_cls", SUPPORTED_LAUNCHER_CLASSES)
def test_supports_shortcuts_matches_method_presence(
    launcher_cls: type[Launcher], tmp_path: Path
) -> None:
    """
    Shortcut management (get_shortcuts/add_shortcut/update_shortcuts/
    remove_shortcuts) is not part of the base Launcher interface, so there is
    no method to call unconditionally. Instead, check that the flag agrees
    with whether the launcher actually implements these methods.
    """
    launcher = _make_launcher(launcher_cls, tmp_path)
    shortcut_methods = ("get_shortcuts", "add_shortcut", "update_shortcuts", "remove_shortcuts")
    has_shortcut_methods = all(hasattr(launcher, name) for name in shortcut_methods)

    assert launcher.supports_shortcuts == has_shortcut_methods


def test_capability_flags_documented_in_mission_table(tmp_path: Path) -> None:
    """
    Locks in the capability matrix from missions/03: Steam supports
    everything, Lutris only the game list, Heroic everything but shortcuts,
    Bottles nothing.
    """
    from protondl.launchers.bottles import BottlesLauncher
    from protondl.launchers.heroic import HeroicLauncher
    from protondl.launchers.lutris import LutrisLauncher
    from protondl.launchers.steam import SteamLauncher

    expected: dict[type[Launcher], tuple[bool, bool, bool, bool]] = {
        SteamLauncher: (True, True, True, True),
        LutrisLauncher: (True, False, False, False),
        HeroicLauncher: (True, True, True, False),
        BottlesLauncher: (False, False, False, False),
    }

    for launcher_cls, flags in expected.items():
        launcher = _make_launcher(launcher_cls, tmp_path)
        actual = (
            launcher.supports_game_list,
            launcher.supports_per_game_tools,
            launcher.supports_global_tool,
            launcher.supports_shortcuts,
        )
        assert actual == flags, f"{launcher_cls.__name__} capability flags changed"
