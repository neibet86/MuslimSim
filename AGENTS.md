# MuslimSim change and documentation rules

These rules apply to every future code, configuration, renderer, font, or
hardware-mapping change in this folder.

## Rule 0 - read this before anything else

These two outrank every other rule in this file. Check them before starting a
task, and check them again before calling one finished.

### 0.1 No output lights while the aircraft is unpowered

**If aircraft power is off, every MuslimSim-controlled output is off.** Screens
black, lamps dark, backlights off, numeric windows blank. That includes the
WinCtrl throttle backlight, every panel currently connected through Studio, and
**every device added in the future** - a new device inherits this rule the day
it is added, without being named here.

- Applies in Live mode, and to a normal Studio shutdown, which sends each
  device its proven OFF/BLACK state while MuslimSim still owns the hardware.
- Practice/Test mode lights the **device being practised** - all of its
  capture-proven lamps and LEDs - and nothing else, and returns them to
  OFF/BLACK when the practice session ends. A device is being practised while
  one of its controls is exercised or its Studio page is open; leaving it alone
  is what ends the session, and it goes dark on its own after
  `PRACTICE_IDLE_SLEEP_SECONDS`. Leaving Practice darkens every device at once.
  - The earlier "only the one output being tested" wording was narrower than
    the owner wants and made Practice useless for its actual purpose: twelve
    of seventeen devices posted nothing at all, so a working panel and a dead
    one looked identical with the simulator off. Amended deliberately on
    2026-09-02 at the owner's explicit instruction; do not narrow it back.
  - Practice still drives only `led`/`lamp` controls the catalogue marks
    `implemented` **and** `testable`. Displays are authored per device or left
    alone, and gauges/solenoids are never driven - Practice lights panels, it
    does not shake motors or fire the PU starter retract.
- **Practice never writes to a saved profile.** It is an experiment sandbox.
  A function is bound only by assigning it in Live; nothing exercised in
  Practice may become a saved binding.
- A device with no capture-proven safe OFF is left alone and flagged for
  capture. Never guess a vendor output packet to force something dark.
- One device is exempt from the **shutdown** half of this rule, and it is not a
  bug to be fixed again: the **PU Overhead has no off state**. It returns to
  its physical brightness knob about a second after anything stops sending it
  frames, so no shutdown code can leave it dark. It still goes dark while the
  aircraft is unpowered, which is the part that works and the part that
  matters. Five separate attempts were made and removed; see
  `DEVICE_REFERENCE.md` before spending an evening on a sixth.
- Unknown is not powered. If the power state cannot be read, treat it as off
  rather than leaving hardware lit on an assumption - but see the distinction
  in `SYSTEM_ARCHITECTURE.md` between "this aircraft publishes no such dataref"
  and "the dataref exists and cannot be read right now".

Any new output path must state, in its changelog entry, how it goes dark.

### Owner exception — WINCTRL 3M PDC backlight (2026-09-11)

The owner explicitly requested the 3M PDC backlight to stay on in both
Practice and Live. For verified BB51/BB52 hardware, the active bridge owner
keeps the captured panel backlight at 255 even when the simulator is offline,
aircraft power is off/unknown, or Practice is idle. This narrow exception
does not apply to 3N PDC hardware or any other device. Disabling/stopping the
device and normal Studio shutdown still send capture-proven zero before
closing its HID handle. Do not remove this exception as an aircraft-power bug.

### 0.2 Never disturb something that already works

Fix the smallest part that is actually broken. A change must not alter the
behaviour of the working parts around it, of the device it lives in, or of any
other device.

- Do not rewrite, restructure or "tidy" working code while fixing a defect in
  it. Change the one expression that is wrong.
- Prefer a new parameter with a default that preserves current behaviour over
  editing an existing code path. Every existing caller must keep behaving
  exactly as it did.
- Prove it where the proof is cheap: compare the before and after output of the
  captured path, and say so in the changelog.
- If a fix appears to need a working part changed, stop and ask first.

### 0.3 Build for a project twice this size

Every change is made on the assumption that MuslimSim keeps growing - more
devices, more aircraft, more functions, more panels. A design that is merely
fast enough today is not acceptable if its cost grows with that. Before calling
a change finished, ask what it costs when the project is twice this size, and
if the answer is "twice as much", fix it now rather than leaving it.

The failure to watch for is **work that scales with the whole, repeated at a
fixed rate**. Three real examples from this codebase, all measured:

- The Studio faceplate was destroyed and rebuilt - several hundred canvas items
  - on every repaint, up to three times per 70 ms tick, to change one lamp.
  Cost grows with controls per panel multiplied by the tick rate.
- The MSFS function browser rebuilt a lowercase search string for every entry
  on every keystroke: 3-4 ms at 2,355 entries, and linear in the catalogue.
- The bridge status payload carried the same physical inputs three times and
  was fetched ten times a second: 537 KB per reply at 805 controls, growing
  with every control ever touched.

Practical rules that follow:

- **Do work once, not per frame or per keystroke.** Precompute anything derived
  from immutable data at load time.
- **Send and draw deltas, not whole states.** A payload or a repaint whose size
  is the whole world will eventually be too slow, whatever the constant factor.
- **Do not duplicate a structure across layers.** A new layer must replace or
  reference what exists, never ship a second copy of it. Two producers of one
  key is also how shapes silently diverge.
- **Nothing that grows may sit on a fixed-rate path.** Anything on a tick, a
  poll, or a keystroke must be O(what changed), not O(everything).
- **Measure before and after, and record the numbers in the changelog.** A
  performance claim without a measurement is an opinion.

### 0.4 Read the bug register before hunting a fault

`BUG_REGISTER.md` records every defect this project has shipped and fixed, with
the guard that stops each one returning. Several of them looked like a different
problem than they were, and one was misdiagnosed and "fixed" twice before anyone
traced the real writer.

- Check it before diagnosing anything that smells familiar - a frozen panel, a
  silent stop, a flickering label, a control that never fires.
- When a new defect is fixed, add an entry and a guard. A bug that has already
  cost a debugging session must never cost a second one.
- Most entries share one shape: **a failure with no signal**. Nothing crashed,
  nothing logged, and the only symptom was something quietly not happening. That
  is why several guards assert that a failure is *reported*, not merely that the
  happy path works.

## Required completion steps

1. Work only inside `D:\MuslimSim` unless the user explicitly asks to use
   another location. `D:\MuslimSim` is the canonical project. The folder
   `D:\Howalt d203 requre signature\MuslimSim` is a working copy the user
   keeps on the side - never edit it, and never treat it as the source of
   truth, because it can be stale.
2. Before changing an existing material file, create a timestamped backup in
   `D:\MuslimSim\Backup`.
3. Preserve existing ownership boundaries:
   - PU Overhead only owns engine-start selectors, auto-retract, and ignition.
   - PFP is display-only.
   - Pedals do not own autobrake, parking brake, rudder trim, or throttle.
   - No second pygame/SDL reader may compete with the existing controller
     reader.
4. Update documentation in the same task:
   - Always update `CHANGELOG.md`.
   - Update `PROJECT_HISTORY.md` for every new capability, milestone, safety
     change, or important behaviour change.
   - Update the relevant specialist document: `DEVICE_REFERENCE.md`,
     `SYSTEM_ARCHITECTURE.md`, `PFD_PROJECT_HISTORY.md`, or `PNG/README.md`.
5. Run the relevant offline tests and record the result in the changelog when
   it is a material change. `tools/test_known_regressions.py` is always
   relevant: it is one guard per entry in `BUG_REGISTER.md`.
6. State clearly which tests passed and what still needs a live-cockpit check.

## Backup naming

Use a descriptive, non-overwriting filename, for example:

```text
bridge_final_before_pedals_YYYYMMDD_HHMMSS.py
pfp_renderer_before_layout_change_YYYYMMDD_HHMMSS.py
```

## Safety priorities

No design, performance, or refactoring task is allowed to make a bridge
restart write a stationary physical control position into a live simulator.
Keep safe pickup and read-only startup reconciliation intact unless the user
specifically approves a reviewed replacement.
