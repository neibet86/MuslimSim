"""Where things live, whether running from source or from the built exe.

PyInstaller unpacks the bundled files into a temporary directory and points
`sys._MEIPASS` at it, while `sys.executable` becomes the exe rather than a
Python interpreter.  Both facts break assumptions that are perfectly safe in
a source checkout:

  * `bridge/final.py` is loaded by path, not imported, so it has to be found
    inside the bundle;
  * settings and logs must NOT go in the bundle -- it is deleted when the
    program exits -- so they go beside the exe instead;
  * the bridge cannot be started with `sys.executable launch.py`, because
    `sys.executable` is the exe.  The exe re-runs itself with `--run-bridge`
    instead, which is why that flag exists.

Keeping these three decisions in one file means the rest of the application
never has to ask whether it is frozen.
"""

from __future__ import annotations

from pathlib import Path
import sys

#: The argument that makes the executable run the bridge instead of the panel.
RUN_BRIDGE_FLAG = "--run-bridge"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resources() -> Path:
    """Where the bundled read-only files are: bridge, fonts, tools.

    From source this is the project root; from the exe it is the unpacked
    bundle, which is temporary and must never be written to.
    """
    if is_frozen():
        base = getattr(sys, "_MEIPASS", None)

        if base:
            return Path(base)

        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def install_dir() -> Path:
    """Where the program itself sits: the exe's folder, or the project root.

    Settings, profiles and error logs belong here, because it survives
    between runs and the user can find it.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def bridge_path() -> Path:
    return resources() / "bridge" / "final.py"


def launcher_path() -> Path:
    return resources() / "launch.py"


def bridge_command(arguments) -> list[str]:
    """The command line that starts the bridge, however we are running.

    Frozen, the executable runs itself: there is no interpreter to call, and
    shipping one alongside would double the download for no gain.
    """
    if is_frozen():
        return [sys.executable, RUN_BRIDGE_FLAG, *arguments]

    return [sys.executable, "-u", str(launcher_path()), *arguments]


def ensure_importable() -> None:
    """Make the bundled project importable when frozen."""
    root = str(resources())

    if root not in sys.path:
        sys.path.insert(0, root)
