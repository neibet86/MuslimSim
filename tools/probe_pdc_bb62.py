"""Map every control on the WINWING 3N PDC (EFIS) panel, VID 4098 PID BB62.

The report descriptor says what the panel sends -- 64 buttons and two 16-bit
axes on report 0x01 -- but not which physical control each bit belongs to.
Nothing but the hardware can answer that, and guessing it would put the range
selector on the mode selector's datarefs, so this asks instead.

It names one control at a time, watches what changes while you operate it,
and prints a finished control map to paste into
`muslimsim/devices/pdc_bb62.py`.

Selector switches (MINS, BARO, VOR/ADF, MODE, RANGE) hold a position rather
than springing back, so each of their positions is a bit that is HIGH while
selected.  Those are captured position by position.  Pushbuttons are captured
as a single bit that goes high and low again.  The knobs are captured as
whichever axis or bits move when you turn them.

It only reads.  It writes nothing to the panel and does not touch the
simulator.  Run it with the bridge stopped, or the bridge takes the reports
first.

Usage:
    python tools/probe_pdc_bb62.py
    python tools/probe_pdc_bb62.py --quick     # buttons and knobs only
    python tools/probe_pdc_bb62.py --knob-trace
        # focused MINS/BARO raw direction/source capture
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

try:
    import hid
except Exception:  # pragma: no cover - probe tool
    hid = None

PDC_VID = 0x4098
PDC_PID = 0xBB62

BUTTON_BYTES = slice(1, 9)      # 64 buttons
AXIS_BYTES = slice(9, 13)       # X and Y, 16-bit little-endian each

SETTLE = 0.35
CAPTURE = 3.0
KNOB_TRACE_SECONDS = 4.0

#: (key, prompt, kind).  `kind` is "hold" for a switch position that stays
#: selected, "press" for a pushbutton, "turn" for a rotary.
CONTROLS = (
    ("mins_mode_radio",  "MINS selector to RADIO",            "hold"),
    ("mins_mode_baro",   "MINS selector to BARO",             "hold"),
    ("mins_knob",        "turn the MINS knob both ways",      "turn"),
    ("mins_reset",       "push the MINS knob (RST)",          "press"),

    ("baro_mode_in",     "BARO selector to IN",               "hold"),
    ("baro_mode_hpa",    "BARO selector to HPA",              "hold"),
    ("baro_knob",        "turn the BARO knob both ways",      "turn"),
    ("baro_std",         "push the BARO knob (STD)",          "press"),

    ("vor_adf_1_vor",    "left VOR/ADF switch to VOR",        "hold"),
    ("vor_adf_1_off",    "left VOR/ADF switch to OFF",        "hold"),
    ("vor_adf_1_adf",    "left VOR/ADF switch to ADF",        "hold"),
    ("vor_adf_2_vor",    "right VOR/ADF switch to VOR",       "hold"),
    ("vor_adf_2_off",    "right VOR/ADF switch to OFF",       "hold"),
    ("vor_adf_2_adf",    "right VOR/ADF switch to ADF",       "hold"),

    ("mode_app",         "MODE selector to APP",              "hold"),
    ("mode_vor",         "MODE selector to VOR",              "hold"),
    ("mode_map",         "MODE selector to MAP",              "hold"),
    ("mode_plan",        "MODE selector to PLAN",             "hold"),

    ("range_5",          "RANGE selector to 5",               "hold"),
    ("range_10",         "RANGE selector to 10",              "hold"),
    ("range_20",         "RANGE selector to 20",              "hold"),
    ("range_40",         "RANGE selector to 40",              "hold"),
    ("range_80",         "RANGE selector to 80",              "hold"),
    ("range_160",        "RANGE selector to 160",             "hold"),
    ("range_320",        "RANGE selector to 320",             "hold"),

    ("tfc",              "press TFC",                         "press"),
    ("wxr",              "press WXR",                         "press"),
    ("sta",              "press STA",                         "press"),
    ("wpt",              "press WPT",                         "press"),
    ("arpt",             "press ARPT",                        "press"),
    ("data",             "press DATA",                        "press"),
    ("pos",              "press POS",                         "press"),
    ("terr",             "press TERR",                        "press"),
    ("fpv",              "press FPV",                         "press"),
    ("mtrs",             "press MTRS",                        "press"),
)

QUICK_KINDS = {"press", "turn"}

KNOB_TRACE_STEPS = (
    ("MINS clockwise", "turn only the MINS knob 4-6 detents CLOCKWISE"),
    ("MINS counter-clockwise", "turn only the MINS knob 4-6 detents COUNTER-CLOCKWISE"),
    ("BARO clockwise", "turn only the BARO knob 4-6 detents CLOCKWISE"),
    ("BARO counter-clockwise", "turn only the BARO knob 4-6 detents COUNTER-CLOCKWISE"),
)


def _buttons(report) -> int:
    return int.from_bytes(bytes(report)[BUTTON_BYTES], "little", signed=False)


def _axes(report):
    raw = bytes(report)[AXIS_BYTES]
    return (
        int.from_bytes(raw[0:2], "little", signed=False),
        int.from_bytes(raw[2:4], "little", signed=False),
    )


def _read_state(device, seconds: float):
    """Latest button word and axis pair seen over a window."""
    buttons = None
    axes = None
    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:
        report = device.read(64)

        if not report:
            time.sleep(0.002)
            continue

        if report[0] != 0x01 or len(report) < 13:
            continue

        buttons = _buttons(report)
        axes = _axes(report)

    return buttons, axes


def _capture(device, seconds: float, base_buttons: int, base_axes):
    """Every button bit that went high and every axis that moved."""
    high = 0
    axis_moved = [0, 0]
    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:
        report = device.read(64)

        if not report:
            time.sleep(0.002)
            continue

        if report[0] != 0x01 or len(report) < 13:
            continue

        high |= _buttons(report) & ~base_buttons

        for index, value in enumerate(_axes(report)):
            delta = abs(value - base_axes[index])
            axis_moved[index] = max(axis_moved[index], delta)

    return high, axis_moved


def _trace_raw_states(device, seconds: float):
    """Return every distinct report-0x01 state during a short knob capture."""
    states = []
    previous = None
    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:
        report = device.read(64)
        if not report:
            time.sleep(0.002)
            continue
        if report[0] != 0x01 or len(report) < 13:
            continue

        state = (_buttons(report), _axes(report))
        if state != previous:
            states.append(state)
            previous = state

    return states


def _run_knob_trace(device, seconds: float) -> int:
    """Capture labelled raw transitions for the two ambiguous rotary controls."""
    resting_buttons, resting_axes = _read_state(device, 0.6)
    if resting_buttons is None:
        print("The panel sent no report 0x01. Is the bridge running?")
        return 2

    print("WINWING 3N PDC MINS/BARO raw knob trace\n")
    print(f"  resting buttons 0x{resting_buttons:016X}")
    print(f"  resting axes    X={resting_axes[0]}  Y={resting_axes[1]}")
    print()
    print("  Do not touch any selector or pushbutton during these four captures.")
    print("  After Enter, perform the named turn during the timed capture.\n")

    for label, prompt in KNOB_TRACE_STEPS:
        input(f"  -> {prompt}; press Enter to arm {seconds:.0f}s... ")
        print(f"     NOW: {prompt}.")
        states = _trace_raw_states(device, seconds)
        print(f"     {label} ({len(states)} distinct HID states):")
        if not states:
            print("       no report\n")
            continue
        for buttons, axes in states[:80]:
            print(
                f"       buttons=0x{buttons:016X} "
                f"X={axes[0]} Y={axes[1]}"
            )
        if len(states) > 80:
            print(f"       ... {len(states) - 80} more states omitted")
        print()

    print("Copy the four labelled sections exactly; they identify knob source and direction.")
    return 0


def _named_bits(mask: int):
    return [i for i in range(64) if mask & (1 << i)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument(
        "--knob-trace",
        action="store_true",
        help="Capture labelled raw MINS/BARO clockwise/counter-clockwise traces",
    )
    parser.add_argument("--seconds", type=float, default=CAPTURE)
    args = parser.parse_args()

    if hid is None:
        print("hidapi unavailable; install hidapi")
        return 2

    devices = list(hid.enumerate(PDC_VID, PDC_PID))

    if not devices:
        print(f"WINWING 3N PDC ({PDC_VID:04X}:{PDC_PID:04X}) not found")
        return 2

    device = hid.device()
    device.open_path(devices[0]["path"])

    wanted = [c for c in CONTROLS if not args.quick or c[2] in QUICK_KINDS]
    found = {}

    try:
        device.set_nonblocking(1)

        if args.knob_trace:
            return _run_knob_trace(device, max(KNOB_TRACE_SECONDS, args.seconds))

        buttons, axes = _read_state(device, 0.6)

        if buttons is None:
            print("The panel sent no report 0x01.  Is the bridge running?")
            return 2

        print("WINWING 3N PDC control mapping\n")
        print(f"  resting buttons  0x{buttons:016X}")
        print(f"  resting axes     X={axes[0]}  Y={axes[1]}")
        print()
        print("  Each selector position is captured against a different position")
        print("  of that SAME selector, so even the original resting position")
        print("  is captured correctly.")
        print()
        print(f"  {len(wanted)} controls, {args.seconds:.0f}s each."
              "  Ctrl+C stops and keeps what you have.\n")

        for key, prompt, kind in wanted:
            if kind == "hold":
                input(
                    "  -> Move that SAME selector to any DIFFERENT position, "
                    "then press Enter... "
                )
                inactive_buttons, _inactive_axes = _read_state(device, SETTLE)
                if inactive_buttons is None:
                    print("       no report -- skipped\n")
                    continue
                input(f"  -> {prompt}, then press Enter... ")
                target_buttons, _target_axes = _read_state(device, SETTLE)
                if target_buttons is None:
                    print("       no report -- skipped\n")
                    continue

                # Differencing the same selector eliminates all unrelated
                # maintained controls and still works when target was the
                # panel's original resting position.
                bits = _named_bits(target_buttons & ~inactive_buttons)

                if not bits:
                    print("       nothing changed -- skipped\n")
                    continue

                found[key] = ("bit", bits)
                print(f"       bit {bits}\n")
                continue

            input(f"  -> {prompt}, then press Enter... ")
            base_buttons, base_axes = _read_state(device, SETTLE)

            if base_buttons is None:
                base_buttons, base_axes = buttons, axes

            print(f"       now operate it for {args.seconds:.0f}s...")
            high, moved = _capture(device, args.seconds, base_buttons, base_axes)

            if kind == "turn" and max(moved) > 8:
                axis = 0 if moved[0] >= moved[1] else 1
                found[key] = ("axis", axis)
                print(f"       axis {'XY'[axis]}  (moved {moved[axis]})\n")
                continue

            bits = _named_bits(high)

            if not bits:
                print("       nothing changed -- skipped\n")
                continue

            found[key] = ("bit", bits)
            print(f"       bit {bits}\n")

    except KeyboardInterrupt:
        print("\n  stopped\n")
    finally:
        try:
            device.close()
        except Exception:
            pass

    if not found:
        print("Nothing was captured.")
        return 1

    print("\n" + "=" * 62)
    print("Paste this into muslimsim/devices/pdc_bb62.py as PDC_CONTROLS:")
    print("=" * 62 + "\n")
    print("PDC_CONTROLS = {")

    for key, (kind, value) in found.items():
        if kind == "axis":
            print(f'    "{key}": ("axis", {value}),')
        elif len(value) == 1:
            print(f'    "{key}": ("bit", {value[0]}),')
        else:
            print(f'    "{key}": ("bits", {value}),')

    print("}")

    duplicates = {}

    for key, (kind, value) in found.items():
        if kind != "axis":
            for bit in value:
                duplicates.setdefault(bit, []).append(key)

    clashes = {bit: keys for bit, keys in duplicates.items() if len(keys) > 1}

    if clashes:
        print("\nWARNING -- these bits were captured for more than one control:")

        for bit, keys in sorted(clashes.items()):
            print(f"    bit {bit}: {', '.join(keys)}")

        print("Re-run those controls; a stray touch usually explains it.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
