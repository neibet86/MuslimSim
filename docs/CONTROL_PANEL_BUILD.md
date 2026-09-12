# Building the MuslimSim control panel

2026-08-27 to 2026-08-28

This is the record of one stretch of work: what was asked for, what was built,
how it works, and — the part worth keeping — what turned out to be false along
the way. The measurements matter more than the code, because three of them
overturned a design that looked finished.

Contents:

1. [What was asked, in order](#1-what-was-asked-in-order)
2. [The EFIS panel (BB62)](#2-the-efis-panel-bb62)
3. [The control panel](#3-the-control-panel)
4. [Turning it into an application](#4-turning-it-into-an-application)
5. [The throttle's below-idle split](#5-the-throttles-below-idle-split)
6. [How the code is arranged](#6-how-the-code-is-arranged)
7. [Findings that changed the design](#7-findings-that-changed-the-design)
8. [What is verified, and what is not](#8-what-is-verified-and-what-is-not)

---

## 1. What was asked, in order

| # | Asked for | Outcome |
| --- | --- | --- |
| 1 | "why this same fix does not apply on the mcdu 32… black glitches or small points on the pfd" | Investigated; **no fix applied** — the defect is not in the software. See [§7.1](#71-the-mcdu-speckles-are-not-in-the-rendering) |
| 2 | "now i added efis3npdc left try to add it to the rest" | PDC / EFIS (BB62) added as a full device. [§2](#2-the-efis-panel-bb62) |
| 3 | "build a gui with interactive interface… reset for each device by its own… unplug it and replug it… without having to stop all the cmd window" | Control panel with per-device reset and USB power cycle. [§3](#3-the-control-panel) |
| 4 | "MuslimSim Control Panel this does not work" | Launcher hardened; could not reproduce, made failure visible instead |
| 5 | "why this ?" (the console message) | Console removed; app now launches windowed through `pythonw` |
| 6 | "useless… a real software… msi or exe not bat… visually calibrate… show what the pfp3n and the mcdu 32 is doing… a real force screen shutdown and restart" | Rebuilt as a tabbed application, packaged as an exe. [§4](#4-turning-it-into-an-application) |
| 7 | "for the throttle create something that i call below Idle… hard coded and every new winctrl throttle hove to be forcefly calibrated" | Two-band throttle calibration, forced onto the bridge. [§5](#5-the-throttles-below-idle-split) |

Point 6 was fair criticism. What existed at that stage was a launcher that
shelled out to console tools — a wrapper, not an application. Everything from
§4 onward is the response to it.

---

## 2. The EFIS panel (BB62)

**`WINWING 3N PDC R`, VID `0x4098` PID `0xBB62`.** The only panel on the bus
with no driver.

### How its protocol was established

Not by guessing. The HID report descriptor was read off the device and
decoded:

```
report 0x01  IN   64 buttons (8 bytes) + X,Y as 16-bit LE (4 bytes)
report 0x02  IN   2 + 11 vendor bytes
             OUT  13 bytes          <- WinCtrl LED / dimming channel
report 0xF0  IN   63 bytes
             OUT  63 bytes          <- WinCtrl native channel
```

Comparing this against the PAP3's descriptor showed the **OUT halves are
byte-identical**. The PAP3's `pap3_led_packet` embeds `0F BF` at bytes 1–2 —
its own PID, little-endian — so the output protocol is parameterised by
device id, and the PDC gets it by substituting `62 BB`. That is reuse on
evidence, not on resemblance.

The input halves are *not* shared (PAP3: 128 buttons, one axis; PDC: 64
buttons, two axes), so nothing was copied there.

### The control map

Which bit belongs to which physical control is not in the descriptor and was
not guessed. `tools/probe_pdc_bb62.py` names one control at a time and records
what changes. 37 controls captured, no bit collisions:

```
fpv 0   mtrs 1   wxr 2   sta 3   wpt 4   arpt 5   data 6   pos 7   terr 8
vor_adf_1 9-11   vor_adf_2 12-14   mins_reset 15   tfc 17   baro_std 18
mins_mode 23-24  baro_mode 25-26   mode 27-30      range 31-37
mins_knob ccw/cw 39/41            baro_knob ccw/cw 42/44
```

The two rotaries were the hard part: they looked like a shared analogue axis
until a focused trace separated the direction pulses from background HID
movement.

### Verifying the Zibo names

A control map from hardware still cannot tell you the dataref names, and a
wrong name fails **silently** — the control simply does nothing. All 25 were
resolved against the running aircraft; all present.

That check earned its place immediately. Two names looked like typos:

- `laminar/B738/EFIS_control/cpt/minimums` — no `a`, where every sibling uses
  `capt`
- `laminar/B738/EFIS/capt/map_range` — unlike the bridge's own
  `sim/cockpit2/EFIS/map_range_nm`

**Both are real.** The `cpt` spelling is genuinely how Zibo spells the
minimums entries; "correcting" it to `capt` silently kills the MINS knob and
its reset. There is a comment at the table saying so, and
`tools/probe_pdc_datarefs.py` re-runs the whole check.

### Wiring

Same places as every other device: `pdc.py` descriptor → `ALL_DEVICES`,
`DeviceSelection.pdc`, `--without-pdc` in the launcher, and in `final.py` the
import, `--no-pdc` / `--diagnose-pdc`, startup and shutdown alongside the PAP3.

---

## 3. The control panel

### The problem

Before this, the only granularity was Ctrl+C. Recovering one wedged MCDU
display restarted the throttle, the pedals, the MCP and the overhead with it,
and bringing them back meant retyping a command line of flags.

### Two kinds of reset

| | What it does | Needs |
| --- | --- | --- |
| **Reset** | Stops and restarts that device's manager *inside the running bridge* — its HID handle closes and reopens, nothing else is touched | Bridge running |
| **Power cycle / Restart screen** | Re-enumerates the panel on the USB bus: it leaves the bus, its firmware restarts, and the WinCtrl logo appears | Administrator |

The first needed a way to reach into a running bridge, which is the control
channel ([§6](#6-how-the-code-is-arranged)). The second needed Windows' PnP
machinery, and turned out to need more care than expected ([§7.2](#72-pnputil-reports-success-without-doing-anything)).

### Extensibility

Adding a device is one entry in `muslimsim/hardware/catalog.py`. The card, its
lamps, its settings form, its enable flag and its reset buttons are all
generated from it. `implemented=False` marks hardware that is recognised but
undriven — the ECAM (BB70) is listed that way, so a new panel shows up as
detected with no driver rather than not at all.

---

## 4. Turning it into an application

### No console, no batch file

`dist/MuslimSim.exe` — 27 MB, one file, built by `build_exe.py` from
`MuslimSim.spec`. It launches through `pythonw`, so no console window exists
at any point.

The manifest requests Administrator. That is not incidental: without it the
screen restart cannot re-enumerate the device, and Windows does not fail
loudly about it ([§7.2](#72-pnputil-reports-success-without-doing-anything)).

Three things in the spec are load-bearing:

- **`uac_admin=True`** — makes the Restart button honest.
- **Data files, not just modules.** `bridge/final.py` and
  `tools/render_pfp_frame_png.py` are loaded *by path*, so PyInstaller's
  analysis never sees them. Missing from the build, the bridge would not start
  and the mirror would stay blank, with no obvious cause. A self-test check
  now asserts they are present.
- **One file**, with settings written *beside* the exe rather than into the
  unpacked bundle — that bundle is a temporary directory Windows deletes on
  exit. `muslimsim/gui/paths.py` holds all three decisions so nothing else has
  to ask whether it is frozen.

A frozen exe also has no interpreter to start the bridge with, so it re-runs
**itself** with `--run-bridge`.

### The tabs

| Tab | What it does |
| --- | --- |
| **Devices** | Every panel: USB presence, manager state, enable, Reset, Power cycle, Configure, Diagnostics |
| **Calibration** | Live bar per axis for pedals / throttle / yoke, range capture, centre capture, invert |
| **Throttle** | The below-idle split — two bands per lever ([§5](#5-the-throttles-below-idle-split)) |
| **Displays** | Live mirror of the PFP and MCDU, and the real screen restart |
| **Output** | The bridge's output, filterable, saveable |

### Live calibration

`muslimsim/hardware/axes.py` runs SDL on its own thread with the dummy video
driver, so it never opens a window and never competes with Tk for the main
loop. SDL rather than raw HID **because SDL is what the bridge reads these
devices through** — calibrating against a different source would look right
and behave wrong.

Calibration is keyed by controller *name*, not SDL index: SDL renumbers
devices when one is unplugged, and a calibration that jumped to another device
would be worse than none.

### The display mirror

`muslimsim/hardware/displays.py` renders at ~12 ms/frame — the same renderer
the bridge uses, fed the same values the bridge drew its last frame from.

The bridge now records those values at the one point both its value paths
converge (`muslimsim_display_telemetry`) and serves them over the control
channel. The alternative — having the panel read the same datarefs itself —
was rejected deliberately: the display worker smooths, interpolates, falls
back to REST and substitutes a standby card when the aircraft loses power. A
second reader would show live numbers while the panel showed standby, which is
exactly the plausible-but-false picture this project has lost the most time to.

---

## 5. The throttle's below-idle split

The full detail is in [THROTTLE_BELOW_IDLE.md](THROTTLE_BELOW_IDLE.md). In
short:

The WinCtrl URSA MINOR is an Airbus quadrant — one continuous lever travel —
driving a 737, which has a thrust lever above IDLE and a separate reverse
lever below it. The travel is cut at the IDLE detent:

```
full reverse ... REV IDLE ... IDLE ......... TOGA
|<------ below idle ------->|<--- forward thrust --->|
```

The Throttle tab shows those as **two separate bands per lever**, each drawn
only over its own travel, so both read 0.0% at the idle detent and there is no
ambiguity about which side of it the lever is on.

The three raw endpoints are per-unit and had been hard-coded from a capture of
one throttle. On the machine that capture came from, the left lever now reads
20165 against an assumed 19308 — **1.85% thrust with the lever in its own idle
detent** ([§7.3](#73-the-hard-coded-throttle-detents-were-wrong-on-this-hardware)).

Calibration is therefore forced, not optional: two capture buttons, values
passed to the bridge on every start, an impossible calibration refused by the
bridge with exit 2 rather than clamped.

---

## 6. How the code is arranged

```
muslimsim/
  hardware/           talks to devices; knows nothing about the UI
    catalog.py        every device, declaratively (369 lines)
    usb.py            presence and per-device power cycling (364)
    axes.py           live SDL axis reading for calibration (380)
    displays.py       the display mirror and the real reboot (315)
    throttle.py       the two bands and the raw HID reader (396)
  control/            the channel into a running bridge
    protocol.py       JSON-line wire format (143)
    server.py         runs inside the bridge (334)
    client.py         the panel's side (146)
  gui/                the window; knows nothing about HID
    app.py            the tabbed window (1270)
    widgets.py        indicators, cards, dialogs, theme (474)
    settings.py       what is remembered, and the command line (378)
    supervisor.py     owns the bridge process (357)
    paths.py          source vs frozen (87)
    calibration.py    the axis bars (422)
    throttleview.py   the two-band throttle view (397)
    displayview.py    the mirror (218)
    selftest.py       16 checks, no hardware needed (600)
muslimsim_panel.py    entry point, --check / --run-bridge
build_exe.py          builds dist/MuslimSim.exe
MuslimSim.spec        the PyInstaller recipe
```

About 6,900 lines. `bridge/final.py` gained three additive blocks: the control
channel, the display telemetry, and the throttle calibration flags. Each is
marked with `>>> MUSLIMSIM ... >>>` fences matching the file's existing
convention, and each is wrapped so a failure is reported and stepped over
rather than raised.

### Why the bridge is a child process

The panel never runs bridge code in its own interpreter. The bridge opens
serial ports, HID handles and SDL, and blocks forever; a GUI hosting it would
freeze on the first hardware stall and die with it on every crash.

### Threading

Nothing blocking happens on the UI thread. USB power cycles shell out to
Windows and take seconds; control calls cross a socket; both run on worker
threads and deliver results through a queue the timer drains. Only the visible
tab is updated — rendering two 640×480 mirrors while you are looking at the
calibration bars would cost frames for nothing.

### Security

The control channel binds to loopback only and carries a per-run token, so
another process on the machine cannot reach in and move the aircraft's
controls. `--control-port` is off unless the panel passes it, so nothing
changes for anyone starting the bridge from a terminal.

---

## 7. Findings that changed the design

These are the parts worth keeping. Each one overturned something that looked
settled.

### 7.1 The MCDU speckles are not in the rendering

The request was to fix "black glitches or small points on the pfd in the
mcdu". The obvious suspect was the MCDU's vertical squeeze: compressed rows
collide, and a background fill drawn second punches a hole through a mark.
Plausible, and **wrong**.

Rendering the same three attitudes on both panels and counting gaps pixel by
pixel:

```
PFP  (no squeeze, no speckle complaint) : 108 gaps
MCDU (squeezed)                         :  69 gaps
```

The MCDU's picture is *cleaner* than the PFP's. The earlier hole counts I had
been steering by (30 vs 20 vs 34) were counting designed gaps between tape
ticks and digits, which is why zero squeeze scored worst of all. Drawing 300
successive frames onto one canvas to catch accumulation gave **zero**
wrongly-black pixels and two stale white pixels, fixed and non-growing.

Two changes were made on the false hypothesis and **both were reverted**: the
squeeze back to the known-good 0.10, and an erase-rounding change whose stated
rationale had been disproved. A note at the constant says not to re-tune it
chasing these specks. `tools/probe_mcdu_speckle.py` paints flat fields to
settle whether the panel speckles with no PFD on screen at all.

### 7.2 `pnputil` reports success without doing anything

`pnputil /restart-device` **exits 0 when not elevated and does nothing at
all**. Measured: polled the bus at 50 ms for 3.5 s after a reset that reported
`Power-cycled 1 instance` — the device never left the bus, 0 absent samples
out of 80.

Trusting that exit code would have told you a display had been power-cycled
when it had not, and sent you hunting for the fault elsewhere. The reset now:

- checks for Administrator up front and refuses with `needs_admin` if absent;
- after a restart, watches the bus to confirm the device really dropped off
  **and came back**, and reports failure if it did not;
- targets the `USB\` parent node, not the `HID\` child — restarting the child
  only rebinds the driver and leaves the device's own state untouched, which
  is no use when that state is the fault.

A self-test check asserts an unelevated power cycle never claims success.

### 7.3 The hard-coded throttle detents were wrong on this hardware

```
right IDLE hard-coded 20165   lever reads 20165   ok
left  IDLE hard-coded 19308   lever reads 20165   wrong
```

`(20165 − 19308) / (65535 − 19308)` = **1.85% thrust on engine 1 with the
lever in its idle detent**, confirmed through the bridge's own mapping
function. Calibrated, it is 0.00%.

Also established while building it: the throttle is **not** an SDL device to
the bridge — it decodes raw HID report bytes through Windows Raw Input.
Calibrating through SDL would have produced numbers the bridge never sees.

### 7.4 The control channel opened too late

First version registered the channel where all the device managers exist. It
never came up, because the bridge blocks in "Waiting for X-Plane Web API" long
before that point — so with the sim down there was no per-device control at
all, which is exactly when the panels are powered and may already need
resetting.

The channel now opens *before* that wait, and the wait loop can be broken by a
stop request. Stop went from a Ctrl+Break kill (`0xC000013A`) to a clean
unwind in 1.9 s, **exit code 0**, restoring the panels to their WinCtrl state.

### 7.5 Smaller ones

- **`hid.enumerate(0, 0)` treats zero as a wildcard**, so a presence check for
  a nonexistent device returned True. `present()` now verifies the returned
  entries rather than trusting the filter.
- **The launcher strips `--pfp-pfd`** unless its own `--with-pfd` was given
  (`muslimsim/devices/pfp.py`), so a catalogue emitting the engine flag would
  have it silently deleted. A self-test check pins this.
- **`%ERRORLEVEL%` inside a parenthesised cmd block** expands at parse time,
  not run time. This made the batch launcher pause on success and then report
  exit 1 while printing "passed". Fixed with labels and `goto`, with a note in
  the file saying why.
- **The PU overhead has no off switch** — neither the launcher nor the engine
  has a flag that disables it while leaving everything else running. Its
  checkbox is greyed rather than silently doing nothing.

---

## 8. What is verified, and what is not

### Verified by measurement

- 16 self-test checks pass from source **and inside the frozen exe**
  (`MuslimSim.exe --check`).
- All pre-existing bridge self-tests still pass: `--test-pfp-pfd`,
  `--test-winctrl-throttle`, `--test-aircraft-profiles`,
  `--test-startup-safety`, `launch.py --check`.
- All 25 PDC datarefs and commands exist on the running aircraft.
- Control channel: attaches with the sim down, restart does stop-then-start,
  bad tokens rejected, dead bridge handled, graceful stop in 1.9 s exit 0.
- Display mirror renders both panels correctly at ~12 ms/frame, with the
  MCDU's fitted geometry visibly different from the PFP's.
- Axis reader: 10 controllers, 0–16 ms latency, correct deadzone and invert.
- Throttle: 0.00% at a calibrated IDLE, zero thrust anywhere below it whatever
  the handle does, reverse inert with the handle down, full reverse reaching
  1.0, TOGA reaching 1.0.
- The exe starts, opens its window, and runs the bridge as itself.

### Not verified

- **The soft-reset path against real managers.** The control channel's
  round-trip, token rejection and stop-then-start ordering are tested against
  stubs, but registering the *real* device managers needs the bridge to get
  past the X-Plane wait, and the simulator was down for that part of the
  session. Worth one run with the sim up.
- **The shipped exe's own UAC path.** Its manifest raises a prompt that cannot
  be approved unattended, so a byte-identical bundle *without* the manifest
  was built and tested instead. That testing caught two real bugs the source
  build hid.
- **A real USB re-enumeration.** It has never been performed with
  Administrator rights, so the claim that the WinCtrl logo appears is reasoned
  from how the hardware behaves on a physical unplug, not observed.
- **The MCDU speckles themselves.** Not reproduced in software; the flat-field
  probe exists to locate them on the hardware and has not been run.
