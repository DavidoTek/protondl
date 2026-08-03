import shutil
from pathlib import Path

import pytest

from protondl.core.models import (
    CompatTool,
    CompatToolType,
    CompatToolVersionInfo,
    InstallMode,
)
from protondl.launchers.lutris import LutrisLauncher
from protondl.util.version_file import write_version_file


def test_get_installed_tools_detects_types_via_version_file(tmp_path: Path) -> None:
    """
    Lutris stores Proton and Wine tools in the same folder (runners/wine).
    The tool type must be resolved from protondl_version.json.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    wine_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON)

    proton_tool = wine_dir / "GE-Proton11-3"
    wine_tool = wine_dir / "wine-tkg-master"
    manual_tool = wine_dir / "Some-Manual-Tool"
    for tool_dir in (proton_tool, wine_tool, manual_tool):
        tool_dir.mkdir()

    write_version_file(
        proton_tool,
        CompatToolVersionInfo(
            compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=1785769458
        ),
    )
    write_version_file(
        wine_tool,
        CompatToolVersionInfo(
            compat_tool="Wine-Tkg (Wine Master)", version="wine-tkg-master", installed_at=1785769458
        ),
    )

    tools = launcher.get_installed_tools()
    tools_by_name = {tool.full_name: tool for tool in tools}

    assert len(tools) == 3
    assert tools_by_name["GE-Proton11-3"].tool_type == CompatToolType.PROTON
    assert tools_by_name["wine-tkg-master"].tool_type == CompatToolType.WINE
    assert tools_by_name["Some-Manual-Tool"].tool_type == CompatToolType.PROTON


def test_get_installed_tools_filters_by_resolved_type(tmp_path: Path) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    wine_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON)

    proton_tool = wine_dir / "GE-Proton11-3"
    wine_tool = wine_dir / "wine-tkg-master"
    for tool_dir in (proton_tool, wine_tool):
        tool_dir.mkdir()

    write_version_file(
        proton_tool,
        CompatToolVersionInfo(
            compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=1785769458
        ),
    )
    write_version_file(
        wine_tool,
        CompatToolVersionInfo(
            compat_tool="Wine-Tkg (Wine Master)", version="wine-tkg-master", installed_at=1785769458
        ),
    )

    wine_tools = launcher.get_installed_tools([CompatToolType.WINE])
    assert [tool.full_name for tool in wine_tools] == ["wine-tkg-master"]
    assert all(tool.tool_type == CompatToolType.WINE for tool in wine_tools)


def test_get_installed_tools_without_version_file_defaults_to_folder_type(
    tmp_path: Path,
) -> None:
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    wine_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON)
    (wine_dir / "Some-Manual-Tool").mkdir()

    tools = launcher.get_installed_tools()

    assert len(tools) == 1
    assert tools[0].full_name == "Some-Manual-Tool"
    assert tools[0].tool_type == CompatToolType.PROTON


def test_remove_tool_delegates_to_matching_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that Launcher.remove_tool delegates to the installer referenced by the
    tool's protondl_version.json.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    tool_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / "GE-Proton11-3"
    tool_dir.mkdir(parents=True)
    write_version_file(
        tool_dir,
        CompatToolVersionInfo(
            compat_tool="GE-Proton", version="GE-Proton11-3", installed_at=1785769458
        ),
    )

    removed: list[tuple[CompatTool, object]] = []

    class FakeInstaller:
        def remove(self, tool: CompatTool, launcher: object) -> None:
            removed.append((tool, launcher))
            shutil.rmtree(tool.install_dir)

    monkeypatch.setattr("protondl.installers.get_installer_by_name", lambda _name: FakeInstaller())

    launcher.remove_tool(CompatTool("GE-Proton11-3", CompatToolType.PROTON, tool_dir))

    assert len(removed) == 1
    assert removed[0][0].full_name == "GE-Proton11-3"
    assert removed[0][1] is launcher
    assert not tool_dir.exists()


def test_remove_tool_deletes_folder_when_no_installer_matches(tmp_path: Path) -> None:
    """
    Test that Launcher.remove_tool deletes the folder directly when no matching
    installer can be found.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    tool_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / "Some-Manual-Tool"
    tool_dir.mkdir(parents=True)

    launcher.remove_tool(CompatTool("Some-Manual-Tool", CompatToolType.PROTON, tool_dir))

    assert not tool_dir.exists()


def test_remove_tool_outside_tools_dir_raises(tmp_path: Path) -> None:
    """
    Test that Launcher.remove_tool refuses directories outside the supported tools root.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    outside_dir = tmp_path / "somewhere-else"
    outside_dir.mkdir()

    with pytest.raises(ValueError, match="not inside the proton compatibility tools directory"):
        launcher.remove_tool(CompatTool("Some-Manual-Tool", CompatToolType.PROTON, outside_dir))


def test_remove_tool_missing_dir_raises(tmp_path: Path) -> None:
    """
    Test that Launcher.remove_tool raises FileNotFoundError for a missing directory.
    """
    launcher = LutrisLauncher("Lutris", tmp_path, InstallMode.NATIVE)
    missing_dir = launcher.get_compatibility_tools_path(CompatToolType.PROTON) / "Not-There"

    with pytest.raises(FileNotFoundError):
        launcher.remove_tool(CompatTool("Not-There", CompatToolType.PROTON, missing_dir))
