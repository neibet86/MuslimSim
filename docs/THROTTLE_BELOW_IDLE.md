# The throttle's below-idle split

How the WinCtrl URSA MINOR quadrant is made to behave like a 737 throttle,
why every unit has to be measured, and how the separate ToLiss A320/A321
calibration prevents one aircraft family from retuning another.

---

## The problem

The WinCtrl URSA MINOR 32 is an **Airbus-shaped quadrant**: one continuous
lever travel with detents along it. A **737** has two quite different things
in that space — a thrust lever from IDLE forward, and a *separate* reverse
lever that only exists once the reverser handle is lifted.

Shown as a single slider, the boundary between them is invisible. You cannot
see whether the lever is a count above idle or a count below it, and "idle"
and "reverse" blur into each other.

So the travel is cut in two at the IDLE detent:

```
   full reverse  ......  REV IDLE  ......  IDLE  .............  TOGA
   |<-------------- below idle ---------->|<--- forward thrust --->|
        reverse lever, handle-gated              thrust lever 0..1
```

- **Above IDLE** the lever is the 737 thrust lever, 0.0 → 1.0.
- **Below IDLE** is the red REV travel. It is completely inert until the
  matching reverse handle is raised; then it drives *only* the reverse lever.
- **REV IDLE** is the gate at which Zibo's reverse first responds
  (`WINCTRL_REV_IDLE_VALUE = 0.0600001`). Travel from IDLE to REV IDLE scales
  0 → 0.06; from REV IDLE to full reverse scales 0.06 → 1.0.

This mapping already existed in `bridge/final.py` as
`_winctrl_throttle_values`. What did not exist was any way to measure the
detents, or to see the two bands separately.

---

## Why every throttle must be calibrated

The three raw endpoints per lever were **hard-coded from a PCAP capture of one
throttle**:

```python
WINCTRL_LEFT_IDLE_RAW      = 19308
WINCTRL_RIGHT_IDLE_RAW     = 20165
WINCTRL_LEFT_REV_IDLE_RAW  = 13976
WINCTRL_RIGHT_REV_IDLE_RAW = 14115
```

Reading the live device on the same machine that capture came from:

```
right lever   reads 20165   hard-coded 20165   ok
left  lever   reads 20165   hard-coded 19308   wrong by 857 counts
```

With the left lever sitting in its own idle detent, the bridge computes

```
forward = (20165 - 19308) / (65535 - 19308) = 857 / 46227 = 0.0185
```

— **1.85% thrust on engine 1 at idle**. Confirmed by running the bridge's own
mapping function, not by re-deriving the arithmetic. Calibrated to where the
lever actually sits, the same reading gives 0.00%.

That is the whole argument for forcing calibration: baked-in detents are one
unit's, and a lever that is 857 counts out commands thrust nobody asked for.

---

## Reading the hardware

**The throttle is not an SDL device to the bridge.** It is decoded from raw
HID report bytes through Windows Raw Input:

```python
button_bits = int.from_bytes(report[1:13],  "little")
left_raw    = int.from_bytes(report[13:15], "little")
right_raw   = int.from_bytes(report[15:17], "little")
speed_raw   = int.from_bytes(report[19:21], "little")
flap_raw    = int.from_bytes(report[21:23], "little")
```

Calibrating through SDL would produce scaled values the bridge never sees.
`muslimsim/hardware/throttle.py` therefore reads the **same report bytes** over
hidapi — the report belongs to the device, not to the transport, so both see
identical bytes.

Only one process can hold the device, so the bridge must be stopped to
calibrate. The tab says so rather than showing frozen bars.

The reverse handles and idle contacts are buttons on the same report:

```python
REVERSE_BUTTON      = {"left": 40, "right": 41}
IDLE_CONTACT_BUTTON = {"left": 15, "right": 21}
```

---

## The mapping is borrowed, not copied

`throttle.py` imports `_winctrl_throttle_values` from `bridge/final.py` rather
than reimplementing it:

```python
def outputs(raw, lever, *, reverse_active, idle_contact=False):
    """(forward thrust, reverse lever), as the bridge computes it."""
```

Copying the arithmetic would let the preview and the aeroplane disagree the
first time either was changed — which is precisely the failure this
calibration exists to remove. What the bars show is what the aircraft will do.

---

## ToLiss A320/A321 is a separate aircraft calibration

The 737 split above must never be reused for ToLiss. Its
`WINCTRL_REV_IDLE_VALUE = 0.0600001` is the response threshold of Zibo's
separate reverse lever; it is not an Airbus thrust-lever position.

The ToLiss branch therefore owns
`TOLISS_A320_A321_THROTTLE_RAW_ANCHORS`, with a separate six-point table for
each engine:

```text
                    engine 1              engine 2
FULL REV            raw     0 / B17       raw     0 / B23
REV IDLE            raw 14115 / B16       raw 14115 / B22
IDLE                raw 20165 / B15       raw 20165 / B21
CL                  raw 45371 / B14       raw 45371 / B20
FLEX/MCT            raw 55453 / B13       raw 55453 / B19
TOGA                raw 65535 / B12       raw 65535 / B18
reverse lift handle             B40                   B41
```

Equal numbers do not mean shared storage. Engine 1 and engine 2 remain
independent entries so either can be calibrated later without moving the
other.

### Matching ToLiss's direct cockpit-lever input

ToLiss has two different coordinate systems here. Its ISCS publishes the
configured **raw joystick-axis** detent locations as:

```text
toliss_airbus/joystick/throttle/idleDetentRatio
toliss_airbus/joystick/throttle/clDetentRatio
toliss_airbus/joystick/throttle/mctDetentRatio
toliss_airbus/joystick/throttle/revOnSameAxis
```

Those values are for a joystick assigned through X-Plane and ToLiss ISCS. The
ToLiss manual explicitly asks the user to read the hardware's raw 0..1 axis at
IDLE, CL and MCT and copy those readings into the ISCS sliders. MuslimSim does
not use that layer: it writes the final signed cockpit-lever array
`AirbusFBW/throttle_input` directly. Applying the raw-axis slider arithmetic a
second time was the reason the first guided calibration recorded the correct
WinCtrl gates but still missed CL and FLEX/MCT in the aircraft.

The installed A321 itself defines the direct coordinate system. Its cockpit
object has signed lever animation keys at REV IDLE `-0.10`, IDLE `0.00`, CL
`0.70`, and TOGA `1.00`; its FMOD gate conditions accept CL in `0.68..0.72`
and FLEX/MCT in `0.86..0.90`, while the live cockpit lever reads exactly
`0.875` in FLEX/MCT. MuslimSim therefore uses these canonical direct targets:

```text
FULL REV   -1.00
REV IDLE   -0.10
IDLE        0.00
CL          0.70
FLEX/MCT    0.875
TOGA        1.00
```

The ISCS IDLE/CL/MCT ratios are retained only as diagnostics;
`revOnSameAxis` remains a live reverse-safety setting. Adjacent measured raw
anchors interpolate linearly, so the lever remains smooth rather than jumping
between the six contacts. When a detent contact is present it wins over ADC
jitter and holds the exact canonical ToLiss value.

Reverse retains two gates: the ToLiss `revOnSameAxis` setting and the matching
physical reverse lift handle must both be active. Raw movement below IDLE with
the handle down always produces zero.

### Guided six-detent calibration in Studio

The six numbers above are safe fallbacks. They are no longer assumed to be the
exact positions of every WinCtrl unit. When ToLiss is the active X-Plane
workspace, Studio replaces the static ruler with two profile-backed rulers and
shows each lever's current raw count.

With the aircraft parked:

1. Put both thrust levers at **FULL REV** and press **CALIBRATE DETENTS**.
2. Sweep upward, pausing at **REV IDLE**, **IDLE**, **CL**, **FLEX/MCT**, and
   **TOGA**.
3. Watch the independent ENG 1 and ENG 2 progress. Either lever may arrive
   first; both must reach 6/6 before the profile is saved.

The probe does not decide that a stable-looking analog value must be a detent.
It starts a candidate only when the expected physical gate contact closes:
B17..B12 for engine 1 and B23..B18 for engine 2. The contact's leading edge is
not saved, because the lever can still travel several thousand raw counts
before it rests in the mechanical notch. While that same contact remains held,
the probe follows the raw axis and saves only after it has remained within the
40-count motion threshold for 0.30 seconds. Releasing the contact cancels the
candidate. A main-loop heartbeat completes the dwell even after the
delta-filtered axis stream becomes quiet; it uses the existing one-owner
snapshot and does not open another hardware reader.

The saved schema is deliberately narrow:

```json
{
  "aircraft_family": "toliss-a320-a321",
  "version": 2,
  "left":  { "full_reverse": 0, "reverse_idle": 14115, "idle": 20165,
             "climb": 45371, "flex_mct": 55453, "toga": 65535 },
  "right": { "full_reverse": 0, "reverse_idle": 14115, "idle": 20165,
             "climb": 45371, "flex_mct": 55453, "toga": 65535 }
}
```

All twelve gates are required, bounded to 0..65535, and must increase by at
least 100 raw counts. Version 2 means every value is a contact-held resting
sample. A version-1 leading-edge profile is rejected once and the safe fallback
is used until one new sweep is completed; after that the version-2 calibration
persists across Studio restarts. The payload lives in the active profile in
`hardware_profiles_toliss.json`; a Boeing family marker is rejected. During
the sweep, the probe leaves the simulator's existing thrust values alone.
Starting the sweep disarms both pickup gates, so save, cancel, or a save error
all require safe pickup before either lever resumes live control. A successful
save also swaps the precomputed physical-to-direct table atomically. A valid
version-2 set of raw gates does not need to be captured again merely because
the aircraft-side target mapping changes.

Returning from reverse has a separate contact guard: if the REV IDLE and IDLE
contacts overlap briefly, IDLE always wins and outputs exactly zero. This is
what prevents the lever from remaining in IDLE REV until it is pushed beyond
IDLE and returned.

### What stayed untouched

- `_winctrl_throttle_values`, all `WINCTRL_*_IDLE_RAW` values and the Zibo
  reverse threshold are unchanged.
- Zibo and LevelUp still use `_winctrl_axis_outputs`; they never receive the
  ToLiss table.
- ToLiss still uses the existing single SDL owner and latest-value queue.
- Before the first ToLiss write, the simulator's current indexed lever value
  is read and the physical lever must reach or cross it. The safe-pickup order
  is unchanged.
- The table is built once per aircraft generation. No whole-profile work was
  added to the fixed-rate axis loop.

The permanent offline guards are `tools/test_toliss_throttle_calibration.py`
and `tools/test_toliss_throttle_probe.py`. The live check is intentionally
manual: calibrate once while parked, move each engine separately through IDLE,
CL, FLEX/MCT and TOGA, then raise its reverse handle, check FULL REV, and
return directly to IDLE.

---

## What the tab shows

Per lever, two bands, each drawn **only over its own travel**:

```
Engine 1  (left lever)                    raw 20165    REV handle down  o

  FORWARD   IDLE |                                    |  TOGA     0.0 %
  REVERSE   IDLE |          |REV IDLE                 |  F.REV    0.0 %   handle down - inert

  IDLE 20165    REV IDLE 14115    TOGA 65535    FULL REV 0
```

Because each band covers only its own side of the detent, **both read 0.0% at
idle**. That is the clear distinction between idle and reverse that a single
slider cannot give you.

The reverse band is drawn in amber when the handle is up and grey when it is
down, with a `handle down - inert` note, and carries a marker at the REV IDLE
gate positioned at the real detent rather than an arbitrary fraction:

```python
span = max(1, calibration.idle_raw - calibration.full_rev_raw)
gate = (calibration.idle_raw - calibration.rev_idle_raw) / span
```

---

## Capturing the calibration

Two steps, matching what the hardware physically does:

1. **Put both levers in the IDLE detent** → *1. Capture IDLE*
   Records `left_raw` and `right_raw` as `idle_raw`.
2. **Raise both reverse handles, pull back to the REV IDLE detent** →
   *2. Capture REV IDLE*
   Records both as `rev_idle_raw`.

`max_raw` (TOGA) and `full_rev_raw` default to 65535 and 0, the ends of the
ADC range.

### Validation

A capture is rejected rather than clamped if the points cannot describe a real
lever:

```python
0 <= full_rev_raw < rev_idle_raw < idle_raw < max_raw <= 65535
max_raw - idle_raw      >= 1500     # forward band big enough to be real
idle_raw - rev_idle_raw >= 500      # REV IDLE gate big enough to be real
```

---

## Forcing it onto the bridge

The calibration is **not a preference**. Whenever the quadrant is enabled and
calibrated, `Settings.build_arguments()` appends:

```
--throttle-left-idle 20165   --throttle-left-rev-idle 14115
--throttle-right-idle 20165  --throttle-right-rev-idle 14115
```

`bridge/final.py` applies these immediately after `parse_args()`, before
anything reads the quadrant, and prints what it applied:

```
Throttle calibrated: LEFT idle=20165 rev=14115, RIGHT idle=20165 rev=14115
Below-idle split active: IDLE->TOGA drives thrust; below IDLE drives only the
reverse lever, and only with the reverse handle raised.
```

An impossible calibration is **refused, not corrected**:

```
ERROR: LEFT throttle calibration is impossible (REV IDLE 20000, IDLE 14000).
       REV IDLE must be below IDLE and both inside 0..65535.
```

and the bridge exits 2. A silently "corrected" throttle calibration would
command thrust the pilot did not ask for; the right answer to nonsense here is
to refuse to fly with it.

Pressing **Start bridge** with an uncalibrated quadrant warns and offers to
open the Throttle tab.

The calibration is stored per machine in `muslimsim_panel.json` and is
deliberately **excluded from profiles** — it describes the quadrant on the
desk, not a choice of which devices to run, so switching profiles never
discards it.

---

## Safety checks

Two self-test checks guard this, because it is the one calibration on the
machine that can move the aircraft by itself
(`muslimsim/gui/selftest.py`):

**`throttle split is safe`**

- at the measured IDLE detent, forward thrust is exactly zero;
- below IDLE, forward thrust stays zero whatever the reverse handle is doing;
- reverse is exactly zero at every point below idle while the handle is down;
- the reverse band increases through the gate to exactly 1.0 at full reverse;
- TOGA reaches exactly 1.0.

**`bad throttle calibration is not emitted`**

- an inside-out calibration is reported invalid;
- and is never passed to the bridge;
- while a valid one is.

Run them with `MuslimSim.exe --check` or `python muslimsim_panel.py --check`.

---

## Files

| File | Role |
| --- | --- |
| `muslimsim/hardware/throttle.py` | Raw HID reader, `LeverCalibration`, `ThrottleCalibration`, `outputs()` |
| `muslimsim/gui/throttleview.py` | The two-band view and the capture steps |
| `muslimsim/gui/settings.py` | Storage, validation, `to_arguments()`, `throttle_needs_calibration()` |
| `bridge/final.py` | `--throttle-*-idle` flags, validation, and the existing `_winctrl_throttle_values` |
