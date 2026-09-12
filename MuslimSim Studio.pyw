"""Double-click entry point for MuslimSim Studio (intentionally no console)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import ctypes
import os

# MUSLIMSIM_PINNED_PYTHON311_BOOTSTRAP_V1
# Normalize the interpreter before importing MuslimSim. This makes direct
# double-clicks and old Windows .pyw associations use the verified runtime.
_MUSLIMSIM_ROOT = Path(__file__).resolve().parent
_MUSLIMSIM_REQUIRED_PYTHONW = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Programs"
    / "Python"
    / "Python311"
    / "pythonw.exe"
)


def _muslimsim_same_executable(left: Path, right: Path) -> bool:
    try:
        return left.resolve().samefile(right.resolve())
    except Exception:
        return str(left.resolve()).casefold() == str(right.resolve()).casefold()


def _muslimsim_normalize_interpreter() -> None:
    if os.name != "nt":
        os.chdir(_MUSLIMSIM_ROOT)
        return

    expected = _MUSLIMSIM_REQUIRED_PYTHONW
    current = Path(sys.executable)

    if expected.is_file() and _muslimsim_same_executable(current, expected):
        os.chdir(_MUSLIMSIM_ROOT)
        return

    if not expected.is_file():
        ctypes.WinDLL("user32", use_last_error=True).MessageBoxW(
            None,
            f"Required MuslimSim Python was not found:\n{expected}",
            "MuslimSim Studio",
            0x00000010,
        )
        raise SystemExit(2)

    if os.environ.get("MUSLIMSIM_PYTHON311_BOOTSTRAP") == "1":
        ctypes.WinDLL("user32", use_last_error=True).MessageBoxW(
            None,
            "MuslimSim could not switch to its required Python 3.11 runtime.",
            "MuslimSim Studio",
            0x00000010,
        )
        raise SystemExit(3)

    environment = os.environ.copy()
    environment["MUSLIMSIM_PYTHON311_BOOTSTRAP"] = "1"
    subprocess.Popen(
        [str(expected), str(Path(__file__).resolve())],
        cwd=str(_MUSLIMSIM_ROOT),
        env=environment,
        close_fds=True,
    )
    raise SystemExit(0)


_muslimsim_normalize_interpreter()

from muslimsim.gui.studio import MuslimSimStudio


def _single_instance_mutex():
    """Return the Windows mutex handle, or ``None`` for a duplicate launch."""

    if os.name != "nt":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(
        None, False, "Local\\MuslimSimStudio.SingleInstance.v1"
    )
    if not handle:
        return None
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        user32.MessageBoxW(
            None,
            "MuslimSim Studio is already running. Use the open Studio window.",
            "MuslimSim Studio",
            0x00000040,
        )
        return None
    return handle


if __name__ == "__main__":
    mutex = _single_instance_mutex()
    if mutex is not None:
        try:
            MuslimSimStudio().mainloop()
        finally:
            if os.name == "nt" and mutex is not True:
                ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(
                    ctypes.c_void_p(mutex)
                )
