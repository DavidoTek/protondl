from pathlib import Path

from protondl.core.models import CompatToolType, CompatToolVersionInfo, InstallMode
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
