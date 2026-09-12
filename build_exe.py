#!/usr/bin/env python3
"""Build MuslimSim.exe.

    python build_exe.py

Produces `dist/MuslimSim.exe`: one windowed executable, no console, no batch
file, manifested to run as administrator so the per-device screen restart can
actually re-enumerate the USB device.

The self-test runs first.  Shipping a build whose catalogue names a flag the
bridge does not accept would only be discovered by a user, and the check
costs a second.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parent


def main() -> int:
    print("MuslimSim build\n")

    print("  1/3  self-test + portable-device checks")
    checks = (
        [sys.executable, str(PROJECT / "muslimsim_panel.py"), "--check"],
        [sys.executable, str(PROJECT / "tools" / "test_portable_device_platform.py")],
        [sys.executable, str(PROJECT / "tools" / "test_portable_runtime_bundle.py")],
        [sys.executable, str(PROJECT / "tools" / "test_windows_bootstrap.py")],
        [sys.executable, str(PROJECT / "tools" / "test_shared_xplane_telemetry.py")],
        [sys.executable, str(PROJECT / "tools" / "test_shared_pfd_telemetry.py")],
    )
    for command in checks:
        check = subprocess.run(
            command, cwd=str(PROJECT), capture_output=True, text=True,
        )
        if check.returncode != 0:
            print(check.stdout)
            print(check.stderr)
            print("  a pre-build self-test failed; not building.")
            return 1
    print("       passed")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("\n  PyInstaller is not installed.  Install it with:")
        print("      python -m pip install pyinstaller")
        return 2

    print("  2/3  cleaning previous build")

    # Reported, not ignored.  A previous exe that is still running, or still
    # being scanned by Windows Defender, cannot be replaced -- and with
    # `ignore_errors` the build then failed much later with an opaque
    # PermissionError from inside PyInstaller.
    for folder in ("build", "dist"):
        target = PROJECT / folder

        if not target.exists():
            continue

        try:
            shutil.rmtree(target)
        except OSError as exc:
            print(f"       could not remove {target}: {exc}")
            print("       Close MuslimSim.exe if it is running, then retry.")
            return 1

    print("  3/3  packaging (this takes a couple of minutes)")
    started = time.monotonic()

    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean",
            str(PROJECT / "MuslimSim.spec"),
        ],
        cwd=str(PROJECT),
    )

    if result.returncode != 0:
        print("\n  packaging failed; the PyInstaller output is above.")
        return result.returncode

    exe = PROJECT / "dist" / "MuslimSim.exe"

    if not exe.is_file():
        print("\n  packaging reported success but produced no exe.")
        return 1

    size = exe.stat().st_size / (1024 * 1024)
    print(f"\n  built in {time.monotonic() - started:.0f}s")
    print(f"  {exe}  ({size:.0f} MB)")
    print("\n  Double-click it.  Windows will ask for administrator rights,")
    print("  which is what lets the Restart screen button work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
