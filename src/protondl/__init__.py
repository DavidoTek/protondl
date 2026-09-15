"""
protondl - a headless, async-first library for managing Linux gaming
compatibility tools (GE-Proton, Proton-Tkg, Wine, DXVK, vkd3d-proton, ...)
across game launchers (Steam, Lutris, Heroic, Bottles).

This module re-exports the supported public API surface. Everything listed in
``__all__`` is safe to import directly from ``protondl``; anything else is
considered an implementation detail and may change without notice.
"""

import logging
from importlib.metadata import PackageNotFoundError, version

from protondl.core.base_installer import CtInstaller as CtInstaller
from protondl.core.base_launcher import Game as Game
from protondl.core.base_launcher import Launcher as Launcher
from protondl.core.errors import AlreadyInstalledError as AlreadyInstalledError
from protondl.core.errors import APIRateLimitError as APIRateLimitError
from protondl.core.errors import ArchiveExtractionError as ArchiveExtractionError
from protondl.core.errors import ChecksumMismatchError as ChecksumMismatchError
from protondl.core.errors import DownloadError as DownloadError
from protondl.core.errors import FileSystemError as FileSystemError
from protondl.core.errors import InstallCancelledError as InstallCancelledError
from protondl.core.errors import LinkNotFoundError as LinkNotFoundError
from protondl.core.errors import NetworkError as NetworkError
from protondl.core.errors import NoDiskSpaceError as NoDiskSpaceError
from protondl.core.errors import NoInternetConnectionError as NoInternetConnectionError
from protondl.core.errors import NotSupportedError as NotSupportedError
from protondl.core.errors import NoWritePermissionError as NoWritePermissionError
from protondl.core.errors import ProtondlError as ProtondlError
from protondl.core.models import Arch as Arch
from protondl.core.models import CancelToken as CancelToken
from protondl.core.models import CompatTool as CompatTool
from protondl.core.models import CompatToolType as CompatToolType
from protondl.core.models import CompatToolVersionInfo as CompatToolVersionInfo
from protondl.core.models import InstallMode as InstallMode
from protondl.core.models import InstallProgress as InstallProgress
from protondl.core.models import InstallStep as InstallStep
from protondl.core.models import ProgressCallback as ProgressCallback
from protondl.core.models import ReleaseVersion as ReleaseVersion
from protondl.core.models import ToolUpdate as ToolUpdate
from protondl.core.models import TranslationDetails as TranslationDetails
from protondl.core.models import UpdateCheckResult as UpdateCheckResult
from protondl.installers import get_all_installers as get_all_installers
from protondl.installers import get_installer_by_name as get_installer_by_name
from protondl.installers import get_tool_type_by_name as get_tool_type_by_name
from protondl.installers import get_tools_for_launcher as get_tools_for_launcher
from protondl.launchers import create_launcher_from_path as create_launcher_from_path
from protondl.launchers import detect_all_launchers as detect_all_launchers
from protondl.launchers import is_valid_launcher_home as is_valid_launcher_home
from protondl.manage import batch_update_games_tools as batch_update_games_tools
from protondl.manage import check_for_updates as check_for_updates
from protondl.manage import update_compatibility_tools as update_compatibility_tools

try:
    __version__ = version("protondl")
except PackageNotFoundError:  # editable checkout without metadata
    __version__ = "0.0.0.dev0"

logging.getLogger("protondl").addHandler(logging.NullHandler())

__all__ = [
    "__version__",
    # launchers
    "detect_all_launchers",
    "create_launcher_from_path",
    "is_valid_launcher_home",
    "Launcher",
    "Game",
    # installers
    "get_all_installers",
    "get_installer_by_name",
    "get_tools_for_launcher",
    "get_tool_type_by_name",
    "CtInstaller",
    # orchestration
    "check_for_updates",
    "update_compatibility_tools",
    "batch_update_games_tools",
    # models
    "Arch",
    "CompatToolType",
    "InstallMode",
    "CompatTool",
    "CompatToolVersionInfo",
    "ReleaseVersion",
    "ToolUpdate",
    "UpdateCheckResult",
    "TranslationDetails",
    "InstallStep",
    "InstallProgress",
    "ProgressCallback",
    "CancelToken",
    # errors
    "ProtondlError",
    "NetworkError",
    "NoInternetConnectionError",
    "LinkNotFoundError",
    "APIRateLimitError",
    "DownloadError",
    "FileSystemError",
    "NoWritePermissionError",
    "NoDiskSpaceError",
    "ChecksumMismatchError",
    "ArchiveExtractionError",
    "InstallCancelledError",
    "AlreadyInstalledError",
    "NotSupportedError",
]
