# MuslimSim Control Panel

**Double-click `dist\MuslimSim.exe`.** Windows will ask for administrator
rights; say yes — that is what makes the screen restart real.

One window for the whole cockpit, so recovering one panel no longer means
stopping every panel.

```text
MuslimSim.exe                    open the window
MuslimSim.exe --check            self-test, no hardware or simulator needed
python build_exe.py              rebuild the exe from source
```

From a source checkout, `python muslimsim_panel.py` does the same thing.

---

## The tabs

| Tab | What it is for |
| --- | --- |
| **Devices** | Every panel: is it plugged in, what is its manager doing, and per-device Reset, Power cycle, Configure and Diagnostics |
| **Calibration** | A live bar per axis for the pedals, throttle and yoke. Capture range, capture centre, invert |
| **Throttle** | The below-idle split — two bands per lever, and the calibration every quadrant needs |
| **Displays** | A live picture of what the PFP and MCDU are actually showing, and a real screen restart |
| **Output** | The bridge's output, filterable and saveable |

---

## Two kinds of reset

They are not the same thing, and the difference matters.

| Button | What it does | Needs |
| --- | --- | --- |
| **Reset** / **Redraw** | Stops and restarts that device's manager *inside the running bridge*. Its HID handle closes and reopens; nothing else is touched | Bridge running |
| **Power cycle** / **Restart screen** | Re-enumerates the panel on the USB bus — it leaves the bus, its firmware restarts, and the WinCtrl logo appears, exactly as if you unplugged it | Administrator |

**Power cycle needs Administrator, and says so.** Windows'
`pnputil /restart-device` exits with *success* when it is not elevated and
does nothing at all — measured: the bus was polled at 50 ms for 3.5 s after a
reset that reported success, and the device never left it. Trusting that would
have told you a display had been restarted when it had not. So the panel
checks for elevation first, and after a restart it watches the bus to confirm
the device really dropped off and came back. If it did not, that is a failure,
not a success.

---

## The throttle

The WinCtrl quadrant is an Airbus shape driving a 737, so its travel is cut in
two at the IDLE detent:

```text
full reverse ... REV IDLE ... IDLE ......... TOGA
|<------ below idle ------->|<--- forward thrust --->|
```

The Throttle tab draws those as **two separate bands per lever**, each over
its own travel only, so both read 0.0% at the idle detent and there is no
doubt which side of it you are on. Below IDLE does nothing until the reverse
handle is raised.

**Every throttle must be calibrated.** The detents were hard-coded from one
unit; on this hardware the left lever reads 20165 against an assumed 19308,
which commands 1.85% thrust with the lever sitting in its own idle detent.

1. Put both levers in the **IDLE detent** → press *1. Capture IDLE*
2. Raise both reverse handles, pull back to the **REV IDLE detent** →
   press *2. Capture REV IDLE*

The measured points are then passed to the bridge on every start. An
impossible calibration is refused by the bridge rather than corrected.

Stop the bridge before calibrating — it holds the throttle, and the tab says
so rather than showing frozen bars.

Full detail: [docs/THROTTLE_BELOW_IDLE.md](docs/THROTTLE_BELOW_IDLE.md).

---

## The displays

The pictures in the Displays tab are not illustrations. They are drawn by the
same renderer the bridge draws with, from the values the bridge drew its last
frame with. **What is wrong there is wrong on the glass.** Standby is shown as
standby, with the reason, rather than as a frozen last frame.

Full detail:
[docs/DISPLAY_MIRROR_AND_RESTART.md](docs/DISPLAY_MIRROR_AND_RESTART.md).

---

## Profiles

Three are supplied: **Full cockpit**, **Displays only**, and **Dry run (no
hardware)**. *Save as...* keeps your own.

Settings live in `muslimsim_panel.json` beside the exe, in plain JSON —
readable, and safe to delete if you want to start over. Calibration is stored
per machine and is deliberately **not** part of a profile: it describes the
hardware on your desk, not a choice of which devices to run, so switching
profiles never discards it.

---

## Adding a device

One entry in `muslimsim/hardware/catalog.py`. The card, its lamps, its
settings form, its enable flag and its reset buttons are all generated from it:

```python
DeviceSpec(
    key="ecam",
    title="ECAM 32 (BB70)",
    purpose="What it does, in one line",
    pid=0xBB70,
    disable_flag="--no-ecam",
    diagnose_flag="--diagnose-ecam",
    requires=("winctrl",),
    manager="ecam_bb70",          # attribute name inside the bridge's main()
    options=(
        Option("--ecam-refresh", "Display refresh (s)",
               "float", 0.12, 0.02, 2.0),
    ),
    probes=(("Map the controls", "tools/probe_ecam.py"),),
)
```

Set `implemented=False` for hardware that is recognised but has no driver yet:
it appears as a detected panel with no controls, which is what you want to see
when a new box arrives. The ECAM is currently listed that way.

For **Reset** to work on a new device, register its manager in the bridge's
control-channel registration block (search `MUSLIMSIM CONTROL CHANNEL
REGISTRATION` in `bridge/final.py`).

Then run `MuslimSim.exe --check`. It will tell you if the entry names a flag
nothing accepts, a dependency that does not exist, a default outside its own
range, or a USB id another device already claims.

---

## If something goes wrong

- A crash on startup writes `muslimsim_panel_error.log` beside the exe and
  raises a dialog.
- `MuslimSim.exe --console` runs it with output visible.
- `MuslimSim.exe --check` runs 16 checks that touch no hardware and no
  simulator.

---

## Further reading

| Document | Covers |
| --- | --- |
| [docs/CONTROL_PANEL_BUILD.md](docs/CONTROL_PANEL_BUILD.md) | The full build record: what was asked for, how it was built, and what turned out to be false |
| [docs/THROTTLE_BELOW_IDLE.md](docs/THROTTLE_BELOW_IDLE.md) | The below-idle split and its calibration |
| [docs/DISPLAY_MIRROR_AND_RESTART.md](docs/DISPLAY_MIRROR_AND_RESTART.md) | The mirror, and what a real restart is |
| [docs/CONTROL_CHANNEL.md](docs/CONTROL_CHANNEL.md) | The channel into a running bridge |
| [DEVICE_REFERENCE.md](DEVICE_REFERENCE.md) | Every device, its ownership rules and its offline check |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | How the layers fit together |
