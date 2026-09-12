# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for MuslimSim.exe.

Build with:

    python build_exe.py

Three decisions worth knowing about, because each one is load-bearing:

**`uac_admin=True`.**  A real screen restart re-enumerates the panel on the
USB bus, and Windows refuses that to a normal process -- it does not fail
loudly either, it returns success and does nothing.  Shipping the exe with an
administrator manifest is what makes the Restart button honest.  The cost is
a UAC prompt at every launch.

**Data files, not just modules.**  `bridge/final.py` and
`tools/render_pfp_frame_png.py` are loaded by PATH rather than imported, so
PyInstaller's dependency analysis never sees them.  They have to be listed
here or the display mirror and the bridge both vanish from the build.  The
`.xpwwf` fonts are read from beside `final.py` at runtime for the same
reason.

**One file.**  A single exe to hand over, at the cost of a slower first
start while it unpacks.  Settings are deliberately written beside the exe
rather than into the unpacked bundle, which is a temporary directory that
Windows deletes on exit; see muslimsim/gui/paths.py.
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

PROJECT = Path(SPECPATH)

datas = [
    # Loaded by path, so the analyser cannot find them on its own.
    (str(PROJECT / "bridge" / "final.py"), "bridge"),
    (str(PROJECT / "bridge" / "pu_physical_authority.py"), "bridge"),
    (str(PROJECT / "launch.py"), "."),
    (str(PROJECT / "tools" / "render_pfp_frame_png.py"), "tools"),
]

# Runtime catalogues/plans loaded by file path rather than Python import.
for runtime_data, destination in (
    (PROJECT / "muslimsim" / "hardware" / "xplane_command_catalog.json", "muslimsim/hardware"),
    (PROJECT / "muslimsim" / "hardware" / "msfs24_command_catalog.json", "muslimsim/hardware"),
    (PROJECT / "muslimsim" / "devices" / "pfp_bank_line_plan.json", "muslimsim/devices"),
    (PROJECT / "muslimsim" / "hardware" / "driver_bundles.json", "muslimsim/hardware"),
):
    if runtime_data.is_file():
        datas.append((str(runtime_data), destination))


# Reviewed Windows driver assets, when present, are bundled as raw signed
# driver-package files. MuslimSim never bundles a manufacturer cockpit app.
driver_root = PROJECT / "drivers"
if driver_root.is_dir():
    allowed_driver_suffixes = {".inf", ".cat", ".sys", ".dll"}
    for driver_file in driver_root.rglob("*"):
        if not driver_file.is_file():
            continue
        if driver_file.suffix.casefold() not in allowed_driver_suffixes:
            continue
        relative_parent = driver_file.parent.relative_to(PROJECT).as_posix()
        datas.append((str(driver_file), relative_parent))

# The native display fonts, read from beside final.py at runtime.
for font in (PROJECT / "bridge").glob("*.xpwwf"):
    datas.append((str(font), "bridge"))

# The probe tools the Diagnostics menus offer.
for probe in (PROJECT / "tools").glob("probe_*.py"):
    datas.append((str(probe), "tools"))

hiddenimports = [
    "hid",
    "serial",
    "serial.tools",
    "serial.tools.list_ports",
    "websocket",
    "websocket._core",
    "pygame",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "PIL.ImageTk",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "muslimsim.hardware.product_registry",
    "muslimsim.hardware.device_manager",
    "muslimsim.hardware.runtime_bundle",
    "muslimsim.hardware.windows_bootstrap",
    "muslimsim.simulator.xplane_telemetry",
    # Device modules the bridge imports dynamically at startup.
    "muslimsim.devices.pap3_mcp",
    "muslimsim.devices.pdc_bb62",
    "muslimsim.devices.mcdu_bb36",
    "muslimsim.devices.mcdu_bb36_separate_paths",
    "muslimsim.devices.pfp_bb35_separate_paths",
    "muslimsim.devices.pfp_renderer",
    "muslimsim.devices.nd_renderer",
    "muslimsim.devices.pfp_shape_tiles",
    "muslimsim.devices.winctrl_output_bus",
]

# bridge/final.py is bundled as a data file and loaded by path, so PyInstaller
# cannot discover all of its runtime imports statically. Include the MuslimSim
# hardware/device/control packages explicitly. This is an end-user portability
# rule: MuslimSim.exe must not depend on a later `pip install`.
hiddenimports = sorted(set(
    hiddenimports
    + collect_submodules("muslimsim.devices")
    + collect_submodules("muslimsim.hardware")
    + collect_submodules("muslimsim.simulator")
    + collect_submodules("muslimsim.control")
))

a = Analysis(
    ["muslimsim_panel.py"],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy.testing", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MuslimSim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # No console: this is a windowed application.  A crash still leaves
    # muslimsim_panel_error.log beside the exe and raises a dialog.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # See the note at the top: without this the Restart button cannot work.
    uac_admin=True,
)
