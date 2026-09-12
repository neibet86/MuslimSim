"""Find this machine's MSFS installation without hardcoding anyone's drive.

MuslimSim needs the Community folder to know whether a WASM module is present,
and the owner's copy lives on ``D:\\MSFS24``. That is *this* machine, not
everyone's: MSFS lets the user put its packages anywhere, and the Store and
Steam builds keep their configuration in different places again.

The simulator records the answer itself. ``UserCfg.opt`` carries a line:

    InstalledPackagesPath "D:\\MSFS24"

so the packages root is read from there rather than assumed, and the Community
folder is that path plus ``Community``. Nothing here guesses a drive letter, and
a machine with no MSFS simply reports none.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional


# Where each MSFS build keeps UserCfg.opt. Ordered newest first, so a machine
# with both installed answers for MSFS 2024.
_USERCFG_CANDIDATES = (
    ("MSFS 2024", "APPDATA", "Microsoft Flight Simulator 2024/UserCfg.opt"),
    ("MSFS 2024 (Store)", "LOCALAPPDATA",
     "Packages/Microsoft.Limitless_8wekyb3d8bbwe/LocalCache/UserCfg.opt"),
    ("MSFS 2020", "APPDATA", "Microsoft Flight Simulator/UserCfg.opt"),
    ("MSFS 2020 (Store)", "LOCALAPPDATA",
     "Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalCache/UserCfg.opt"),
)

_PACKAGES_LINE = re.compile(r'InstalledPackagesPath\s+"([^"]+)"', re.I)


def user_config_files() -> List[tuple]:
    """Every ``UserCfg.opt`` present, as ``(build name, path)``."""

    found = []
    for label, variable, relative in _USERCFG_CANDIDATES:
        base = os.environ.get(variable)
        if not base:
            continue
        candidate = Path(base) / relative
        if candidate.is_file():
            found.append((label, candidate))
    return found


def packages_roots() -> List[tuple]:
    """Every installed-packages root MSFS reports, as ``(build name, path)``."""

    roots = []
    for label, config in user_config_files():
        try:
            text = config.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = _PACKAGES_LINE.search(text)
        if not match:
            continue
        root = Path(match.group(1).strip())
        if root.is_dir():
            roots.append((label, root))
    return roots


def community_folders() -> List[tuple]:
    """Every Community folder on this machine, as ``(build name, path)``."""

    folders = []
    for label, root in packages_roots():
        community = root / "Community"
        if community.is_dir():
            folders.append((label, community))
    return folders


def find_wasm_module(*names: str) -> Optional[Path]:
    """The first installed WASM module matching any of ``names``.

    ``names`` are package folder names, e.g. ``mobiflight-event-module``.
    Returns the ``.wasm`` file, or ``None`` when the module is not installed.
    """

    for _label, community in community_folders():
        for name in names:
            package = community / name
            if not package.is_dir():
                continue
            for module in sorted(package.glob("modules/*.wasm")):
                return module
    return None


def find_any_wasm_module(filename: str) -> Optional[Path]:
    """The first installed module with this exact file name, whatever its package."""

    for _label, community in community_folders():
        for module in sorted(community.glob("*/modules/" + filename)):
            return module
    return None


__all__ = (
    "community_folders", "find_any_wasm_module", "find_wasm_module",
    "packages_roots", "user_config_files",
)
