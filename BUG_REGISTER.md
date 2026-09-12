# MuslimSim bug register

## BUG-65 - BB51 reused the BB61 input map (FIXED from full labelled capture)

BB51 had been accepted by the Captain reader without a separate model map.
The owner's complete 38-step capture now proves every 3M contact, including
VSD and true relative RANGE. An explicit BB51 map is selected before baseline;
BB61 and BB52 retain their previous decoding. Presence checks retain the
opened model identity. Four stale 3M learned source corrections were updated
with Studio closed; simulator bindings and unrelated profile data are intact.
Guards: test_pdc_bb51_verified.py replays 1,395 actual reports / all 38 steps,
rejects cross-talk, verifies fast stages and model isolation. Shared-faceplate
and capture-integrity guards remain in mandatory regressions. Updated runtime
physical acceptance is pending reopening Studio.

## BUG-64 - VSD appeared on 3N instead of 3M

VSD visibility followed the right-side key rather than the model. The owner's
correction is now enforced: 3M BB51/BB52 show VSD; 3N BB61/BB62 do not.
Guard: test_pdc_shared_faceplate.py checks all four identities, click regions,
optional BB51 source learning and preservation of stored assignments.

## BUG-63 - 3M RANGE was drawn with the 3N hard stops

The shared PDC renderer chose range behavior by cockpit-side key, which groups
BB51 (3M L) with BB61 (3N L). It now distinguishes the actual model: 3M draws
continuous rotation, 3N keeps 5..640. Existing BB51 map_range records are
unwrapped visually without changing assignments or hardware decoding.
Guard: test_pdc_shared_faceplate.py tests repeated turns in both directions,
model-specific range labels and preserved sources. Live acceptance is pending.

## BUG-62 - PDC faceplates differed and rotary/tap feedback could disappear

BB62 used a separate grouped diagram while fixed PDCs used the requested flat
panel. The fixed canvas had no MINS/BARO rotational indicator or turning hit
areas, relied on existing mirror keys for maintained poses, missed taps whose
latest record was already released, and rescheduled missing-data paints forever.

The shared renderer preserves all captured source keys, adds BB62 VSD without
guessing its contact, draws knob motion, reads physical selector records and
briefly acknowledges recently released taps. Unknown positions await status
changes rather than building timer chains. Guard: test_pdc_shared_faceplate.py
in mandatory regressions, plus real Tk --render checks. The existing bridge
received the owner's 3M BARO/WXR test with the simulator disconnected; updated
Studio visual acceptance after restart remains open. No driver or profile edit.

## BUG-61 - Presence filtering hid hardware during simulator/service downtime

BUG-60's filter confused generic service state with physical USB absence and expired
positive inventories after eight seconds. This could remove the selected throttle,
pedals or other panel while its physical controls remained connected. Explicit USB
presence now wins; generic offline/waiting/connected=False cannot veto a scan.
A failed scan retains known hardware; a successful empty inventory still removes it.
Tests combine simulator-disconnected Live/Practice with sidebar visibility and
physical feedback across 22 device catalogs, including throttle and pedal axes.
Guards: test_connected_device_list.py and test_simulator_independent_hardware.py.

## BUG-60 - Disconnected rows remained visible and unknown pages said WINCTRL

Studio treated waiting/running registrations as attached hardware and merged stale
positive rows without rejecting explicit disconnects. The generic faceplate also
hardcoded WINCTRL device. Positive physical presence, cache expiry, and actual USB
names now determine the sidebar and unknown-page title. Audio devices are not flight
controllers just because Logitech appears in their identity. Guard:
tools/test_connected_device_list.py in mandatory regressions, with unplug/replug,
empty inventory, stale sources, unknown identity and headset fixtures.

## BUG-59 - Re-assign was limited to ECAM instead of all device inputs

Studio disabled capture for other devices, accepted only ECAM raw-contact events,
and ignored stored source overrides on MOZA/FCU. Optional reassignment now uses
the existing catalog-validated physical event stream for every input faceplate.
Only the selected relation changes after explicit user action; existing mappings
are never reset. Practice does not save. Guard: tools/test_reassign_all_devices.py
in mandatory regressions checks enablement, capture, persistence, and preservation
of unrelated assignments and bindings across all available input catalogs.

## BUG-58 — PFD finishes outdated deltas before serving current tape pixels

Old scheduler committed every remaining rectangle of a superseded PFD delta.
PFD-only newest-update mode now keeps a shadow of committed pixels, discards
unsent obsolete work, and fairly groups left/right/centre rectangles. Both
speed and altitude use this path. Initial page completion remains non-preemptive
so it cannot be starved while hidden. Other image pages keep existing defaults.
Guard test_toliss_pfd_latest.py in mandatory regressions covers replacement,
both side bands, partial-frame shadow, erasure and idle. Queue correctness is
fixed offline; physical smoothness remains OPEN (including 2Hz capture limit).

## BUG-57 — Native image loading sends repeated brightness and can outlive its lease

Owner reports approximately 17 seconds for PFP3N and longer/non-completing
MCDU loads. Exact captured PFD/ND encodings require 5953/9361 fake-USB reports;
the initial-image design is inherently expensive on this command transport.
Do not label this a USB 3 host failure or a completed throughput fix.

Two software defects corrected: each incomplete batch sent OFF both before
and after drawing, and successful slow writes did not renew the producer's
1500ms demand lease until the next batch. Brightness now changes only on state
transitions; image transfers temporarily chain the existing successful-write
callback to renew demand at most every 250ms. No background timer can keep a
stalled/stopped owner alive. Power/stale-image rejection remains unchanged.
The lease mechanism is reproduced offline, not yet confirmed as the cause of
this owner's intermittent blank MCDU. Physical speed/blanking remains OPEN.

Guard: tools/test_toliss_image_transfer.py in mandatory regressions simulates
a 3-second burst, preserves the original recovery callback, checks exception
cleanup and transition-only brightness. Added actual native-write count/time
metrics for the next live test. Studio restart required; plugin unchanged.

## BUG-56 — Image transfer reports live but LCD pixels are wrong (OPEN)

Follow-up: owner photos now confirm complete BLEED imagery on both physical
LCDs after committed-batch changes and physical restarts. Slow colour-grouped
first loading remains. Next revision hides the initial job until complete,
removes old-artwork fallback when the producer exists, fits full width and
enables all twelve command-verified SD pages. New fit/latency acceptance is
pending; this does not establish native PFD/ND motion performance.

Owner reports old PFP3N page and MCDU32 white squares. The shared-memory source
is visibly correct; running/live status only measured worker activity. Existing
offline test emulated fills and counted reports but did not prove firmware
acceptance of 31 drawing bursts without a refresh. Staged correction commits
every bounded batch and reasserts colour; tests require each commit and real
BB35/BB36 framing with fake devices. Image-specific progress is exposed, without
claiming physical acknowledgement. Root cause/physical success still unverified;
request reference photos and test after Studio restart. No control/input changes.


## BUG-55 — BLEED flickered between image and numeric rendering

Reader interpreted an odd shared-memory sequence (producer copying its next
frame) as source loss. The renderer discarded its image job and restored the
numeric page. Live observation: 22/600 headers busy during normal capture.
Retain the last complete same-page image only until its original freshness
deadline; stable off/invalid/other-page data still withdraws imagery. Updated
reader returned 600/600 complete frames live. Physical acceptance after Studio
restart remains pending. `test_toliss_sd_image.py` in known regressions guards
copy collisions, expiry, page changes and stable power-off. Separate BB36
startup failure is still unresolved; its exception now appears in device status
and the real handler is exercised with a synthetic error by the same test.


## BUG-54 follow-up — window extraction did not feed physical LCDs

The successful native-image trial only displayed PC windows. Both physical
workers continued to draw numeric telemetry, so unpublished SD temperature
fields correctly remained XX. A window screenshot was not an LCD fix.

Staged September 10: BLEED-only local image producer and exact sampled-RGB
adapter in both existing display owners, behind their power/self-test gates.
`test_toliss_sd_image.py` is in the mandatory regression runner: checks sampled
pixels, changes/erasure, real native report framing, zero idle output, bounded
chunks, stale/off headers and page isolation. Plugin builds but is NOT yet
installed. This issue remains OPEN pending native crop readback, physical panel,
power transitions and performance acceptance. Other pages are not yet enabled.


## BUG-54 — ECAM degree glyph replacement and SD text truncation

The LCD transport encodes ASCII with replacement, turning Unicode degree
signs into question marks. ECAM now draws a small hollow ring with native
rectangles; font uploads and other instrument renderers are unchanged.
The SD fixed-column decoder also preserves embedded NUL cells as spaces;
the CDU's original NUL-terminated decoding is unchanged. Guards are in
`test_toliss_wheel_bleed_details.check_details` (glyph pixels and ASCII text)
and `test_toliss_ecam_telemetry.check_telemetry_contract` (bytes, integer arrays,
base64, exact columns and unchanged CDU behavior); both run in the mandatory
regression suite. Follow-up remains open: live SD temperature rows were wholly
NUL, which decoding cannot recover. Do not describe BLEED telemetry as complete.

---

## BUG-53 — APU-on BLEED values and topology disagreed with the native A321

**Symptom (owner):** With the APU supplying bleed air, the physical ECAM still
showed incorrect/XX temperatures and roughly 51 PSI instead of the native
37/36 PSI. It also failed to show the green APU/cross-manifold path correctly
and could paint stopped-engine branches as though the engines supplied air.

**Cause:** `LeftBleedPress` and `RightBleedPress` are absolute psia, but the
adapter printed them directly. It used cabin temperature, TAT and an invented
`20 + 80 * PackTemp` formula for unrelated BLEED boxes; `PackTemp` is actually
an arc ratio. The renderer discarded `APUBleedInd`, drew no APU branch/main
manifold, rotated X BLEED backwards, and inferred engine/HP operation from
pressure shared by the APU. Fault codes 2/3 were also numerically truthy.

**Fix (2026-09-10):** Subtract live ambient Pa converted to psi, decode the
fixed native green/amber columns in `SDline2/5/13`, clamp `PackTemp`, normalize
`PackFlow` from 0.8..1.2, and keep absent text unknown. Build manifold supply
from actual APU/X/ground/engine indications. X=1 is horizontal/open; the APU
branch is vertical. A stale-zero engine indication is recovered only with its
own switch, running flag, N2 > 50, APU bleed off and gauge PSI > 4; native 2/3
remain abnormal and cannot connect or colour a branch green.

**Guard:** `tools/test_toliss_ecam_telemetry.py` pins the exact 5/210/37-36/190
APU fixture, absolute-to-gauge math, flow scale, missing/amber rows, external-
power, engines-only and failure states. `tools/test_toliss_wheel_bleed_details.py`
pins valve orientation, APU/GND/manifold geometry, independent engine branches,
failure colours, exact incremental pixels and rendering budgets. Both are in
the mandatory regression suite. Backup:
`Backup/toliss_bleed_apu_telemetry_20260910_143913/`.

---

## BUG-52 — ToLiss GPU lamp stayed dark and PU starters had no Airbus action

**Symptom (owner):** attaching/removing ground power did not illuminate/clear
the PU overhead ground-power lamp. The left and right PU engine-start selectors
also needed Boeing-style operation and automatic physical return after the
matching Airbus engine was fully running.

**Cause:** the ToLiss telemetry worker deliberately published `light_mask=0`
because BUG-51 had no confirmed Airbus lamp source. Engine-start tuples were
made Studio-observable but then intentionally fell through as no-ops to avoid
fighting the WinCtrl quadrant's shared Airbus ENG MODE selector.

**Fix (2026-09-10):** the installed A321 ground-equipment set proves its GPU car
uses `AirbusFBW/EnableExternalPower`; that value now owns only confirmed P7 bit
12 (`GRD PWR AVAIL`) and clears safely on invalid/unavailable telemetry. The
existing DC-bus gate still blacks every other output; offered-source AVAIL is
the sole pre-bus exception, and the existing COM5 worker remains the only writer.

A post-baseline PU GRD edge now selects ToLiss IGN/START and arms only that
engine. The existing WinCtrl master/fuel lever remains a distinct step, exactly
as a Boeing start switch and fuel-control lever are distinct. Completion requires
the matching master ON, `FADECStateArray=1`, N1 >= 18% and native `ENGN2Speed`
>= 55% continuously for one second. The already-confirmed P1 route then receives
one bounded request (one separated retry while GRD persists), followed by ENG
MODE NORM. P1 is common, so two active GRD engines must both complete before it
can pulse. OFF cancels the cycle but never commands `MasterNOff`; CONT/FLT hold
IGN/START without automatic release. A PU lease suppresses WinCtrl ENG MODE
commands only while the PU is actively using the shared selector.

**Guard:** `tools/test_toliss_pu_overhead.py` pins 116 source/value/startup/
dwell/grouping/ownership checks. ToLiss WinCtrl/AGP (88), throttle calibration
(58), starter-retract, P7-light, aircraft-profile and mandatory known-regression
guards pass. Development was read-only against the running simulator and opened
no HID/serial output. Physical acceptance awaits the owner's next safe restart.

---

## BUG-51 — PU overhead was inert in ToLiss and APU EGT had no Airbus source

**Symptom (owner):** PU overhead switches did not operate their logical Airbus
controls. The requested first IRS selector could not control IR 1 independently,
the second could not control IR 2+3 together, and the physical APU EGT gauge did
not show a ToLiss start rise followed by a settled mark-4 AVAIL indication.

**Cause:** `_run_toliss_agp_profile` correctly stopped the preflight SDL reader
and opened one profile-owned reader, but its consumer accepted only WinCtrl
button/flap/axis tuples. All PU overhead tuples were silently filtered out.
The process-wide COM5 writer was already running, but the ToLiss branch never
updated its PU cache; generic X-Plane APU fields are stale for this aircraft.
That branch also returned without the Boeing path's explicit COM5 cleanup.

**Fix (2026-09-10):** added an Airbus-only event dispatcher using writable
ToLiss arrays and native commands. IR 1 writes `ADIRUSwitchArray[0]`; the second
physical selector atomically writes the installed cockpit's IR 2/3 slots `[2]`
and `[1]`. Fuel/FAC/hydraulic array slots, electrical commands, lights, signs,
packs, anti-ice, bleeds, wipers, battery, brightness and APU are mapped to their
logical A321 controls. Many-to-one controls use cached physical baseline only
for arbitration; the baseline itself performs zero simulator writes. Saved
Hardware Lab mappings and Test mode retain precedence.

A read-only ToLiss PU worker now feeds the existing serial cache from native
`DCBusVoltages`, `OHPBrightnessLevel`, `APUN`, `APUEGT`, `APUEGTLimit` and
`APUAvail`. Start EGT/redline drives the needle rise; AVAIL forces the existing
calibrated midpoint (`apu_temp=50`, P4=100), which is physical mark 4. OFF,
invalid telemetry and loss of every DC bus produce zero/dark; charged battery
terminals alone cannot wake the hardware. No second serial writer or SDL reader
was added. COM writes are bounded, and shutdown writes/closes only after the
sole writer exits. Unknown power clears the shared output frame on the first
failed sample. Bounded convergence makes three-position landing lights exact,
and the two-state physical TAXI switch selects Airbus TAXI rather than T.O.

**Guard:** `tools/test_toliss_pu_overhead.py` pins 68 selector/index/gauge/
startup/power/ownership checks. The loaded A321 resolved every new dataref and
command through GET-only Web API calls. Existing ToLiss WinCtrl/AGP (88), throttle (58)
and mandatory known-regression suites pass. Physical acceptance awaits a safe
restart; no running flight or aircraft control was mutated during development.

---

## BUG-50 — Parking brake, AGP brake lamps and cruise FCU speed mode were wrong

**Symptom (owner):** the B930 parking-brake switch no longer controlled the
aircraft; an AGP autobrake light illuminated only during the tap instead of
remaining selected; the amber HOT brake-fan light never illuminated; and
switching the physical FCU from MACH to SPD at cruise showed `.99` until the
aircraft descended below the Mach crossover.

**Cause:** the parking contacts invoked native commands that were not changing
this installed A321 even though `AirbusFBW/ParkBrake` is writable. Autobrake
outputs followed `ABrk*ButtonAnim`, which describes the momentary push rather
than the maintained aircraft annunciator. HOT had no output mapping. Both FCU
display consumers used `AirbusFBW/ShowMachCapt`, the PFD Mach-caption/crossover
state, as the FCU's unit selector; at altitude it stayed true and caused a knot
target to be formatted and clamped as Mach `.99`.

**Fix (2026-09-10):** buttons 29/30 now make edge-only absolute ParkBrake 0/1
writes after the existing no-write startup baseline, with the old commands
retained only as fallback. The XP12 ToLiss ATA 32 annunciator array now drives
confirmed AGP HOT 6, autobrake ON 14/15/16 and DECEL 11/12/13 selectors. This
delegates latching, automatic disarm, brake-HOT thresholds and annunciator test
to ToLiss. Every added lamp is included in global AGP blackout. Both BA01 and
AGP FCU display paths now pair the unchanged unit-aware selected-speed value
with `sim/cockpit/autopilot/airspeed_is_mach`.

**Guard:** `tools/test_toliss_winctrl_controls.py` pins absolute parking state,
startup ordering, the exact array/source/index map, distinct ON/DECEL selectors
and blackout. `tools/test_fcu_efis_toliss.py` rejects `ShowMachCapt` in both
FCU roles and pins cruise SPD 257 versus MACH .77 packets. Live evidence was
read-only: the current A321 publishes the raw 64-element ATA 32 array, the
unit flag, and writable ParkBrake. Physical acceptance still requires a safe
Studio restart and supervised brake heating/automatic-disarm check.

---

## BUG-49 — Altitude drum sections and lower PFD information were misplaced

**Symptom (owner):** the altitude digits still occupied one surrounding yellow
shape. The large first three and smaller last two digits were not separated as
in the supplied ToLiss crop. STD/altitude information sat too far right, and
Mach sat left of rather than right-aligned beneath the speed tape.

**Correction (2026-09-10):** the main three-digit altitude field is now a
larger slot-6 value inside two open-ended amber horizontal rails wholly bounded
by the grey altitude tape. A separate 30 x 44 amber vertical drum begins at the
right scale wall, contains the smaller slot-4 rolling pair and alone projects
into the black outboard area. Mach/preselect right-align to the speed-tape edge;
STD/QNH, landing elevation and ILS DME right-align to the drum edge below the
altitude area. No telemetry mapping or simulator control changed.

**Guard:** `tools/test_toliss_displays.py` asserts main-cradle/tape coincidence,
outboard-only drum projection, distinct font IDs/sizes, absence of a left main
vertical border, and the exact lower-information right edges. Dedicated ToLiss
tests pass at 319 recovery / 244 moving reports and known regressions pass.
Backup: `Backup/toliss_pfd_alt_drum_layout_20260910/`.

---

## BUG-47 — ND route stopped at the active waypoint

**Symptom:** The ND showed a green line from the aircraft to the current TO
waypoint, but no subsequent FMGS legs.

**Cause:** BUG-46 correctly restored a live active-leg fallback, but the
installed A321 does not publish its full `toliss_airbus/flightplan/*` arrays in
X-Plane's public dataref catalogue. The renderer also filtered blank route
slots and could therefore join the fixes on either side of a discontinuity.

**Correction:** Parse ToLiss's own already-written A321 situation autosave as a
strictly bounded record stream. Structurally identify matching latitude,
longitude and waypoint-ID arrays using the live active WPT ID, cache by file
mtime, and supply every expanded SID/enroute/STAR/approach fix to both displays.
A blank source slot survives as `break_before`, so ARC/ROSE/PLAN never connect
across an FMGS discontinuity. No ToLiss, aircraft, MCDU or situation write is
performed.

**Guard:** `tools/test_toliss_displays.py` builds a synthetic QPS record stream,
proves route discovery without fixed record IDs, retains fixes after a blank,
asserts the break boundary, checks bridge delivery and exercises the existing
ND report budgets. A read-only live proof matched active WPT `TXO` at index 7
in a 33-slot expanded route and found the actual break before index 20.

## BUG-46 — ND route source did not exist in the installed ToLiss

**Symptom:** The ND drew compass/navigation data but no green FMGS route.

**Cause:** Route geometry depended exclusively on four
`toliss_airbus/flightplan/*` arrays absent from the A321 1.8 live catalogue.

**Correction:** Subscribe to native `AirbusFBW/WPT_Crs`; with existing WPT
distance/ID and aircraft position, calculate the live active waypoint endpoint
and draw the active leg. Prefer full arrays whenever they actually exist.

**Guard:** `tools/test_toliss_displays.py` checks translator fallback selection,
spherical endpoint construction, route feature emission and active WPT label.
The live fixture proves the installed-aircraft path.

## BUG-45 — Working BLEED/HYD/FUEL states were painted failed

**Symptom:** With both engines and systems operating, BLEED and HYD valves were
amber, the right wing pump showed LO, and ENGINE/ELEC retained many XX fields.

**Cause:** Current ToLiss `ENG*BleedInd` stays zero despite about 65 psia raw
(approximately 51 PSI gauge) and switches
on; pressure was ignored. HYD fire valves had no source. Fuel code 3 was decoded
using an obsolete enum assumption. Several usable generic live fields were not
subscribed.

**Correction:** Combine live bleed switch/pressure for effective flow, colour
normal HP and pressurised hydraulic valves green, decode wing-pump code 3 as
running, and add explicitly provisional live/derived ENGINE and ELEC fields.

**Guard:** The engines-running GET-only fixture and telemetry tests assert the
working states, values and page-local inputs; reference, BLEED/WHEEL, display
and mandatory known-regression suites protect the shared rendering paths.

## BUG-44 — Live ECAM telemetry was erased or never subscribed

**Symptom:** Most lower ECAM pages showed XX even though the running ToLiss
aircraft exposed changing values.

**Cause:** The BUG-41 safety adapter intentionally overwrote TAT/SAT/GW,
BLEED pressures, cargo temperatures and several plausible fields with NaN.
Tire pressure and ToLiss's 90 native STATUS text layers were not subscribed.

**Correction:** Preserve live common values; connect BLEED pressure, APU bleed,
COND selector/cargo temperature, FUEL temperature, oxygen pressure, six tire
pressures, PRESS SYS and electrical bus-derived voltage. Subscribe and render
all native STATUS colour layers. Undocumented interpretations are explicit
provisional mappings, never constants copied from reference images.

**Guard:** `tools/test_toliss_ecam_telemetry.py` checks every new source,
page-scoped delivery, empty/populated STATUS semantics and provisional index
order. Reference, WHEEL/BLEED, display-performance and mandatory regression
tests cover rendering and isolation.

## BUG-43 — ELEC telemetry was deliberately masked after removing false page-flag mappings

**Symptom:** The ELEC synoptic appeared but its batteries, buses and source
arrows stayed unknown even while ToLiss published electrical telemetry.

**Cause:** BUG-41 correctly removed `SDELEC`/`SDELECDC` (page-selection
scalars) and `ElecOHPArray` (switch positions) as fake measurements, but its
ELEC override then forced every bus/generator source to unknown. The valid
replacement arrays and connection bitfields were never connected.

**Correction:** Battery voltage now comes from `BatVolts`; AC/DC bus health
comes from `ACBusVoltages`/`DCBusVoltages`; engine-generator source connection
uses bit 0 of `SDELConnectLeft/Right`; APU/external source and bus tie use the
documented `SDACCrossConnect` codes. Unsupported amps, load, frequency, TR and
IDG values remain unknown—no screenshot constants or generic X-Plane values.

**Guard:** `tools/test_toliss_ecam_telemetry.py` asserts exact battery values,
powered/unpowered buses, independent generator bits, APU/external/tie source
codes, missing-data fail-closed behaviour and absence of invented engineering
values. Its page-scoped snapshot comparison proves both display workers receive
the added fields without scanning unrelated telemetry.

## BUG-42 — Missing WHEEL details and incorrect BLEED closed-state topology

**Symptom:** Native W looked lowercase; WHEEL omitted all three down-lock
triangles and the centre steering/braking block. BLEED lacked the four pack
arcs and connected IP/HP branches even with bleed off. A centre-valve switch
guess risked becoming an unverified permanent telemetry rule.

**Correction:** Page-local W shape; telemetry-dependent down-lock triangles
and steering/limited supply-derived braking indications; two arcs per pack,
left-foot FCV connections and independently gated IP/HP connectors. XBleedInd
is provisional. The requested GET-only watchdog separates actual indication
edges from switch commands and refuses to mark any source verified without
native-symbol evidence. Full ToLiss BSCU fault logic remains unverified.

**Guard:** `tools/test_toliss_wheel_bleed_details.py`, called by
`tools/test_known_regressions.py`, checks missing features, colours, independent
branches, centre-valve changes, exact incremental pixels, idle suppression and
ambiguous/switch-only watchdog events. No shared font, FCU or keypad route changed.
See `docs/TOLISS_BLEED_WATCHDOG.md` and the telemetry audit for acceptance limits.

## BUG-41 — ECAM page flags/settings misread as measurements; DU startup absent

- Symptom: plausible but wrong ECAM numbers/colours under ground power;
  photographed examples appeared more complete than actual live telemetry.
- Cause: scalar SDFUEL/SDELEC page selectors treated as arrays, cabin target
  settings used as measurements, switch commands substituted for indications,
  source-validity masks missing, and battery voltage used as display supply.
- Correction: audited typed adapter, measured cabin sources/A321 tank layout,
  validity/availability masks and actual DU countdown/brightness on both
  owners. Unsupported values remain unknown. This fixes those faults, NOT
  all remaining ECAM telemetry/artwork gaps; the audit lists them explicitly.
- Guards: `test_toliss_ecam_telemetry.py`, called in part by known regressions;
  power/self-test transition checks for BB35 and BB36, exact sample-free
  translations and page-scoped snapshots unaffected by 10,000 unrelated keys.
- No live process restart or flight-control/simulator writes were performed.

Every defect this project has actually shipped and fixed, with the guard that
stops it coming back. A bug that has already cost a debugging session must never
cost a second one.

**Read this before hunting a new fault** — several entries here looked like
different problems than they were.

Each entry records the *symptom the owner saw*, the *real cause*, and the
*guard*. Where the guard is a test, that test names the bug number, so a failure
points straight back here.

Run every guard:

```bash
py tools/test_known_regressions.py
py tools/test_live_feedback_contract.py
py tools/test_studio_status_latch.py
py tools/test_msfs24_detection.py
py tools/test_pdc_detent_knobs.py
py tools/test_gaze_focus.py
py tools/test_platform_v7_discovery_dedup.py
py tools/test_moza_yoke_faceplate.py
py tools/test_levelup_737_integration.py
py tools/test_toliss_throttle_calibration.py
py tools/test_toliss_throttle_probe.py
py tools/test_toliss_displays.py
```

**A note on parallel work:** BUG-18 and BUG-19 landed from two different
sessions working the same register at once - unrelated fixes (LevelUp
display gating; the yoke's button map), touching different files, that
happened to be recorded around the same time. If you are reading this while
adding a twentieth entry, check the current end of the file rather than
assuming the last number you remember is still the last one there.

---

## The pattern behind most of them

Six of these eleven are the same shape: **a failure with no signal.** Nothing
crashed, nothing logged, and the only symptom was something quietly not
happening. That is why so many of the guards assert *that a failure is
reported*, not just that the happy path works.

The second pattern, worth naming: **a diagnosis that was never proved.** BUG-07
was attributed to the telemetry counters and "fixed" twice before anyone traced
the actual writers. Rule 0.3 in `AGENTS.md` exists partly because of it — a claim
without a measurement is an opinion.

---

## BUG-01 — Serial write blocked forever with no timeout

**Symptom:** a write to the PU overhead on COM5 hung, then the device dropped
off the USB bus entirely.

**Cause:** `serial.Serial(...)` was opened with a read `timeout` only.
`write_timeout` defaults to `None`, so a device that stops draining its endpoint
blocks the writer indefinitely.

**Fix:** `write_timeout=2.0`, explicit DTR/RTS, and flushed output so a
backgrounded run reports instead of buffering silently. `tools/pu_ovhd.py`.

**Lesson:** a read timeout is not a write timeout. Any blocking I/O needs both.

---

## BUG-02 — Slow status reply killed all live feedback

**Symptom:** devices listed in Studio, but nothing moved. Panels frozen; closing
and reopening Studio did not help.

**Cause:** `ControlServer` collected every device's `status()` and
`diagnostics()` *inside* the status request. One slow driver pushed the reply to
**3.05 s** against a **3.00 s** client timeout, so every 0.10 s poll timed out,
`self._lab` was never refreshed, and the device list stayed on screen from the
last reply that landed. Nothing raised.

**Fix:** device status moved to a background sweep behind
`DEVICE_STATUS_TTL_SECONDS`, the same pattern already used for hardware
discovery; client timeout 3.0 s → 8.0 s. Measured 3.05 s → **0.016 s**.

**Guard:** `tools/test_live_feedback_contract.py` — a deliberately slow driver
must leave a warm reply inside the poll budget, and the client must keep its
timeout margin.

---

## BUG-03 — Changing aircraft froze live feedback until restart

**Symptom:** switch aircraft and live feedback stops. Only closing and reopening
Studio brought it back.

**Cause:** a race. `_tick_once` read `supervisor.client`, found it alive, set the
`_status_pending` single-flight latch, then called `_request`, which read
`supervisor.client` **again**. A workspace change tears the bridge down on its
own thread, so the client could become `None` between the two reads. `_request`
returned early without submitting, no result ever arrived, and the latch stayed
set for the rest of the session.

**Fix:** `_request` returns whether it submitted; the poll releases its latch
when nothing was sent.

**Guard:** `tools/test_studio_status_latch.py` — a dropped client and a closing
worker pool are both reported, the retry floor is applied *before* the request,
and a new poll still requires the latch to be free.

---

## BUG-04 — A failed telemetry hook was invisible

**Symptom:** none. That is the bug.

**Cause:** the Platform V7 Studio hook is installed inside a bare
`except Exception`, which stored the error in
`_MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR` and set the installed count to `0`.
**Nothing anywhere read either.** That hook merges the bridge telemetry driving
live physical feedback, so a failed install silently reduced the panel.

**Fix:** Studio reports it once in the footer on the first tick.

**Guard:** `tools/test_live_feedback_contract.py` — the error must be *read*
somewhere, not merely assigned.

---

## BUG-05 — A failed lifecycle import was invisible

**Symptom:** USB plug/unplug tracking silently inert.

**Cause:** a failed `device_manager` / `product_registry` import installed no-op
fallbacks and printed nothing.

**Fix:** prints a `WARNING:` line, which the supervisor surfaces in the Studio
footer — the same mechanism the Platform V7 bootstrap directly above it already
used correctly.

**Guard:** `tools/test_live_feedback_contract.py`.

---

## BUG-06 — Two producers, one key, different shapes

**Symptom:** the Studio header always read `Physical 0 • #0`, whatever the
hardware was doing.

**Cause:** `physical_telemetry.py` wrote the summary Studio reads — `devices`
counts and a `sequence`. The Platform V7 `bootstrap.py` then **overwrote the same
key** with the raw per-control mapping, which has neither field.
`studio_hooks.py` repeated the overwrite client-side after receipt. The counters
could never resolve, and the duplicate added ~93 KB to a reply fetched ten times
a second.

**Fix:** both producers write the summary shape. Payload 537,417 → 444,488 bytes;
that key alone 93,285 → 362 bytes.

**Guard:** `tools/test_known_regressions.py::check_bug06_...` — the key must keep
`devices` and `sequence`, its counts must match the recorded inputs, and it must
stay at least 20× smaller than `inputs`.

**Lesson:** a new layer must replace or reference an existing structure, never
ship a second copy of it. Two producers of one key is how shapes diverge in
silence.

---

## BUG-07 — Header flickered between two different strings

**Symptom:** the text at the top of Studio flickered constantly.

**Cause — and note it was misdiagnosed twice.** It was first blamed on the
Platform V7 counters, which were removed; it still flickered. The real cause: the
status-poll `if/elif` chain skips its first branch whenever a poll is *already in
flight* **or** *not yet due* — most ticks on a perfectly healthy bridge — and
execution fell through to `elif self.supervisor.running:` which wrote
"Starting private hardware service…". The next reply wrote the real status line.
The two took turns about fourteen times a second.

"A poll is in flight" never meant "the service is starting".

**Fix:** the banner appears only before the first successful reply, tracked by
`_status_seen`, which a workspace change resets. Added `_set_connection_text`,
which writes only when the string differs — Tk re-renders a label on every
`StringVar.set` even with identical text.

**Guard:** `tools/test_known_regressions.py::check_bug07_...`.

**Lesson:** prove the cause before fixing it. Two plausible fixes shipped before
anyone traced the actual writers.

---

## BUG-08 — The whole faceplate repainted up to three times per tick

**Symptom:** none visible, but everything got heavier as panels grew.

**Cause:** `_draw_faceplate` begins with `canvas.delete("all")` and rebuilds
every item. The practice preview step, the status reply and the flash expiry each
called it independently inside one 70 ms tick — up to 42 full rebuilds a second
where 14 produce the same picture.

**Fix:** the three tick-path draws mark the canvas dirty and the tick paints
once. The status trigger additionally compares a signature of what the faceplate
draws from, so a still cockpit paints zero times instead of ten a second.

**Guard:** `tools/test_known_regressions.py::check_bug08_...`.

**Still open:** studio.py has 520 `create_*` calls and **zero** uses of
`itemconfigure` / `coords`. The real fix is retained canvas items — build the
static panel once and mutate only the lamps, needles and digits that change.

---

## BUG-09 — A detection rule with no workspace to switch to

**Symptom:** would have detected an installed PMDG 777-200ER and had nowhere to
put it.

**Cause:** the selector was built from a description ("777-300ER") rather than
from the installed packages. The PMDG 777 actually installed is
`pmdg-aircraft-77er`.

**Fix:** the 777-200ER is offered. Later the same survey found FSLabs *is*
installed (`fsl-a32x`, the A321neo) and the iFly MAX 8200 is a separate airframe.

**Guard:** `tools/test_msfs24_detection.py` — every rule must resolve to an
offered workspace, and 15 real installed aircraft must be identified correctly.

**Lesson:** build detection from what is on disk, not from what was described.

---

## BUG-10 — A shell heredoc turned `\b` into a backspace character

**Symptom:** the iFly MAX 8200 detection rule never matched and folded into the
MAX 8.

**Cause:** a heredoc collapsed `\\b` to `\b`, which Python read as the backspace
escape. Four regexes silently became patterns containing `0x08`. The file parsed,
imported and ran; 13 escapes were corrupted.

**Fix:** all 13 repaired. Prefer the file-writing tools over shell heredocs for
anything containing backslashes.

**Guard:** `tools/test_known_regressions.py::check_bug10_...` — no control
characters anywhere in the package source.

---

## BUG-11 — Function search was linear per keystroke

**Symptom:** fine at 2,355 entries, would become visibly laggy as the catalogue
grows.

**Cause:** `search_msfs24_functions` rebuilt a lowercase joined string for every
entry on every query — 3–4 ms per keystroke, linear in the catalogue.

**Fix:** the search text is built once when the cached catalogue loads.
Measured 3–4 ms → **0.30 ms**.

**Guard:** `tools/test_known_regressions.py::check_bug11_...`.

---

## BUG-12 — WinWing PDC BARO and MINS read backwards on both units

**Symptom:** on both the 3M PDC L and R, turning BARO to **HPA** showed **IN**,
and turning MINS to **RADIO** showed **BARO**.

**Cause:** four one-hot selector maps paired a rising bit with a falling index:

```python
BB61_MINS_MODE = {25: 0, 24: 1}    # bit 24 is RADIO, but mapped to index 1 = BARO
BB61_BARO_UNIT = {27: 0, 26: 1}
BB52_MINS_MODE = {26: 0, 25: 1}
BB52_BARO_UNIT = {28: 0, 27: 1}
```

These were the **only** descending maps on either device — VOR1, VOR2, MAP MODE
and MAP RANGE all ascend — and the bit ranges are contiguous only when they
ascend too (BB61: mins 24‑25, baro 26‑27, then MAP MODE from 28). The capture
files confirmed those bit numbers toggle and that each pair is genuinely
one‑hot, never both set.

**This was not display-only.** The same decoded index feeds X‑Plane through
`_set_maintained`, so the simulator was driven to the opposite position too.

**Fix:** all four maps corrected to ascending, matching every other selector.

**Guard:** `tools/test_known_regressions.py::check_bug12_...` — no PDC selector
map may pair a rising bit with a falling index, and each selector's lowest bit
must map to its first catalogued choice (`RADIO`, `IN`).

**Lesson:** when one member of a family is written differently from all the
others, that is the bug, not the style. A structural inconsistency is worth
checking before a behavioural test even runs.

---

## BUG-13 — Two PDCs on one product id left one panel invisible

**Symptom:** after flipping the left/right roles in SimAppPro, "the software
will never identify them".

**Cause:** the PDC role is carried by the USB **product id**, which SimAppPro
reassigns — and `_FixedPDCBase._open` took `entries[0]` from
`hid.enumerate(VID, PID)` with no further check. If both units ever answered on
one PID, two owners raced for the same physical panel and the second unit was
never identified at all. Nothing reported it; the panel simply was not there.

**The stable identity is the serial, not the product id.** Every WinWing unit
carries one burned in:

| product id | role | serial |
| --- | --- | --- |
| `BB52` | PDC R | `F5EDF0690E57486133167062` |
| `BB61` | PDC L | `CC35F0690E57487533167062` |

The **product id says which role SimAppPro currently assigns**; the **serial says
which physical box that is**. Only the serial survives a role reassignment.

Those two serials are **this machine's**, shown only as evidence that the field
exists and is unique. Nothing in the shipped code contains them: the driver reads
whatever ``serial_number`` the device reports, so another owner's units work with
no change. `check_no_machine_specific_paths_in_shipped_code` in
`tools/test_known_regressions.py` keeps it that way.

**Fix:** `_open` refuses when more than one distinct serial answers for a single
PID, naming both, instead of silently picking one. Both the service and
diagnostic snapshots now carry the serial, so a role swap is visible rather than
looking like unknown hardware.

**Guard:** `tools/test_known_regressions.py::check_bug13_...` — an ambiguous
enumeration must raise, and both snapshots must report the serial.

**Design note:** mappings stay keyed to the **role**, not the box. The captain's
EFIS is the captain's EFIS whichever unit is plugged in on that side, and the
profiles are already keyed `pdc_bb61_left` / `pdc_bb52_right`. The serial exists
so MuslimSim can *recognise* a swap, not to move mappings with the hardware.

**Still open:** persisting serial → role across sessions, so MuslimSim can say
"these are your two known units with their roles swapped" rather than only
refusing an ambiguous PID.

---

## BUG-14 - the MINS and BARO knobs were read as spring switches, not two-stage detents

**Symptom (owner):** "the baro knob and the mins knob does not work the way
expected like in the sim - when you turn it it reaches a small dent, when you
reach that dent the baro or mins change one by one; however if I tug it a bit
more it passes that notch and now it goes faster."

**What the driver believed.** Four independent spring contacts per panel:

```python
BB61_SPRING = {40: "mins_dec", 42: "mins_inc", 43: "baro_dec", 45: "baro_inc"}
```

Each of those going high emitted one click. That is all the panel could say.

**What the hardware actually reports.** `3M PDC L FULL.pcapng` and
`3M PDC R FULL.pcapng` show **five** contacts per knob, one-hot: a rest contact,
one detent contact per direction, and one *held past the notch* contact per
direction. Each direction of each knob was worked five times slowly and five
times past the notch, so every row below is backed by ten recorded gestures:

| unit | knob | dec past-notch | dec detent | rest | inc detent | inc past-notch |
| --- | --- | --- | --- | --- | --- | --- |
| BB61 L | MINS | 20 | 40 | 41 | 42 | 21 |
| BB61 L | BARO | 22 | 43 | 44 | 45 | 23 |
| BB52 R | MINS | 33 | 34 | 35 | 36 | 37 |
| BB52 R | BARO | 23 | 38 | 39 | 40 | 24 |

The two units do **not** lay these out the same way, so BB52 is read from its own
capture rather than mirrored from BB61.

**Why it looked like nothing was wrong.** The four detent bits were correct, so
slow turning worked perfectly. Only the fast gesture misbehaved, and it did not
fail loudly - it produced *two* clicks:

```
rest -> detent   (click)  -> past the notch  -> detent (click again) -> rest
```

The second click was the spring carrying the knob back through the detent. A
deliberate fast run came out as two ticks, which reads as "the knob is just
slow" rather than as a decoding fault.

**The bits were not hidden.** Bits 20-23 on BB61 and 23/24/33/37 on BB52 were
sitting unmapped between the mapped ones. A gap in a bit map is a question, not
a spare.

**Fix:** a three-phase state machine per knob - `rest -> detent -> fast`.
Entering a detent from rest is one click; entering the fast contact starts a run
at `PDC_KNOB_FAST_PERIOD` (10 clicks a second) driven from the reader loop's
existing non-blocking spin, so a held knob costs no thread and no timer of its
own however many panels are added later. Coming back *from* the fast contact
through the detent emits nothing, because that is the spring, not a turn. A
stalled loop cannot bank a burst: the next step is due a period from *now*, not
from when it was owed. Unplugging the panel or holding a knob at connect emits
nothing.

**The repeat rate is a choice, not evidence.** The panel reports only that the
knob is *held*, never a speed. Ten a second is one named constant,
`PDC_KNOB_FAST_STEPS_PER_SECOND`, and it is the only line to change.

**The fix nearly broke live feedback, and that is worth recording.** The first
version emitted each click as a press *and* an immediate release, which is the
obvious shape for a momentary tap. `HardwareLab.input` keeps one record per
control and the last event wins, and Studio's faceplate only turns a knob whose
latest record is a press with a non-zero value - so every knob would have read
"released" between frames and the faceplate would have sat still while the real
panel turned. Every count-based test still passed. The release is now emitted
when the knob returns to rest, and repeats re-press the way a held key does.

**Guard:** `tools/test_pdc_detent_knobs.py` - thirteen checks, including the
recorded gestures replayed with their real timestamps and the live-feedback
shape Studio actually tests. Re-broken four ways (reading only the detent
contacts, counting the spring's return, banking owed steps, releasing straight
after each press) and all four were caught.

---

## BUG-15 - a blink read as looking away, and the pointer chased a stale timestamp

**Symptom (owner):** ran `probe_tobii_focus.py` staring at one spot for 12
seconds and got 3 separate focus episodes, median 0.48 s, instead of one
continuous lock. Recorded to `gaze.txt` and handed over rather than described.

**What the trace showed that synthetic tremor never could.** Two real problems,
both found only because real hardware data was available to replay:

1. **The eyelid, not the eye.** Around the tracker's own 3-sample blink flag,
   the *valid* samples on both sides of it are still corrupted - roughly four
   samples before the tracker admits the eyes are closing, and seven after it
   says they are open again, some of them a tenth of the screen away from
   where the owner was actually looking, every one flagged `valid: true`.
   Trusting them at face value threw focus away on every blink. Fixed with
   `recovery_seconds`: gaze is coasted, not believed, for a short window after
   any invalid reading, whether or not the tracker still calls it valid.

2. **Drift needs to persist, not just occur.** Even with recovery in place, the
   *near* side of a blink - the few samples before the tracker's own flag ever
   fires - has no warning sign to gate on. Fixed by requiring drift past the
   break radius to hold for `break_hold_seconds` before it releases, rather
   than releasing on the first sample. A genuine look-away still leaves
   instantly, because that path is the *speed* check, not this one - the two
   are independent, and only the slow, silent kind of excursion pays the wait.

**A second bug, found by feeding the trace across a bigger gap.** `dt` for the
smoothing filter was measured from `self._last_time`, which advanced on every
call to `update()` - including the coasted ones a blink produces. But the
filter's own internal state (its stored previous point, used to estimate
velocity) is untouched during a coast. So the first real sample after any gap
divided a real position change by a single sample's worth of time instead of
the true elapsed gap: an apparent speed roughly ten times too high, which
blows the filter's cutoff wide open and defeats the smoothing at exactly the
moment a spurious jump most needs to be damped. Fixed by giving the filter its
own clock (`_filter_last_time`), touched only on samples it actually sees.

**A gap in the tests, found while trying to prove the fix.** The first version
of the drift-persistence guard checked "one sample past the break radius does
not release" - but the one-euro filter smooths the very first sample of any
jump so heavily that smoothed drift does not even cross the break radius on
sample one, with or without persistence. The check passed regardless of
whether the mechanism existed, and a mutation test proved it: removing the
persistence code entirely left the guard green. Replaced with a check that
measures the actual gap between drift crossing the break radius and release
firing, and asserts it lands within one sample of `break_hold_seconds` -
0.152 s against a 0.150 s setting. The recorded blink trace itself does not
exercise persistence either, for the same reason; it needed its own direct,
synthetic test.

**The fix nearly broke live feedback, and that is worth recording.** The first
version emitted each click as a press *and* an immediate release, which is the
obvious shape for a momentary tap. `HardwareLab.input` keeps one record per
control and the last event wins, and Studio's faceplate only turns a knob whose
latest record is a press with a non-zero value - so every knob would have read
"released" between frames and the faceplate would have sat still while the real
panel turned. Every count-based test still passed. The release is now emitted
when the knob returns to rest, and repeats re-press the way a held key does.

*(That paragraph describes BUG-14's near-miss, not this bug - left in verbatim
because it is the reference example this project keeps pointing back to for
"the test still passed, and the code was still wrong.")*

**Guard:** `tools/test_gaze_focus.py::check_the_owners_recorded_blink_does_not_break_focus`
replays the owner's exact recorded blink, unedited; `check_drift_must_be_sustained_not_glimpsed`
measures the persistence timing directly; `check_the_filter_measures_its_own_gap_not_the_coast_gap`
exercises the dt bug with a genuine position jump across a real gap of actual
calls, not just elapsed wall-clock time with nothing in between. All three
were re-broken and caught.

---

## BUG-16 - every status poll re-saved every device to SQLite, forever

**Symptom (owner):** "check why the studio is so slow... thorough investigation."

**What a live profile of the actually-running app found.** Attached `py-spy`
to the owner's live Studio and bridge processes (pid 36904 / 31856, already
running) rather than guessing or restarting anything. Two socket
request-handling threads answering Studio's `status` poll were spending
95-99.7% of their own CPU time inside one line:

```python
outbox_count = int(self._conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
```

Measured directly against the live database: **151 ms per call**, against a
100 ms poll interval Studio itself was waiting on. Querying the file found why:
`outbox`, `device_sightings` and `audit_log` each held **3.68 million rows**,
in a **9.4 GB** database file, growing at a measured, sustained **22-72 rows a
second continuously for 46.3 hours** - since this project's work on the machine
began, never once pruned.

**Why: every status poll re-persisted every visible device, changed or not.**
`ingest_discovery()` called `save_device()` and `record_sighting()`
unconditionally for every device in the (server-cached) hardware-discovery
payload, on every single status reply - roughly ten times a second, forever,
whether or not a single byte about that device had changed since the last
poll. `save_device()` in turn wrote an unconditional `audit_log` row and queued
an unconditional `outbox` row on every call - and with no cloud account
configured, nothing ever drained the outbox, so it simply grew. Confirmed
directly against the live database: every one of the last 2,000 rows in both
`outbox` and `audit_log` was the identical event, `device-saved`, for the
same handful of already-known devices.

**A second, compounding bug in the same request path.** `server_handle` called
`runtime.snapshot()` - the exact call that runs the slow query above - a second
time to fill a field that was already filled, moments earlier, by
`HardwareLab.snapshot()` (patched as `lab_snapshot`) inside the very
`original_handle()` call it had just returned from. Three independent copies
of the same expensive payload were being computed per single status reply
before this was noticed; two of the three were pure duplication.

**Fix, in the order the evidence pointed to it:**

- `ingest_discovery()` now compares each sighting against an in-memory
  signature of the last one actually persisted for that device (everything
  except `observed_at`, which is fresh on every call by construction and would
  defeat any comparison that included it). A repeat sighting costs one dict
  comparison and nothing else. A genuine change - new device, role
  reassignment - still persists exactly as before. The device-online state
  Studio actually displays comes from `IdentityRegistry.observe()`, in memory,
  on every call regardless of this gate, so nothing about live device status
  changed.
- `server_handle` no longer calls `runtime.snapshot()` at all; it reuses the
  one `lab_snapshot()` already computed, matching how Studio's own status
  handler already falls back to `lab["platform"]` when the top-level key is
  absent.
- `ProfileDatabase.snapshot()`'s two `COUNT(*)` queries are now bounded to
  5,000 rows regardless of true table size - `outbox_count`/`conflict_count`
  are diagnostic fields nothing in the codebase actually reads, so an exact
  count was never buying anything an unbounded table couldn't eventually cost
  dearly for.
- Added `ProfileDatabase.prune_history()`, capping `outbox`, `device_sightings`
  and `audit_log` at 20,000 rows each, run automatically on every fresh
  connection - a second, independent line of defence, because the write-side
  fix being careful today does not guarantee every future code path will be.

**Still requires a restart to take effect.** The running bridge is a separate,
already-started Python process; editing its source does not change what it is
currently executing. Restarting Studio restarts the bridge, which opens a
fresh `ProfileDatabase` connection - and `prune_history()` runs automatically
on that connection, so the existing 3.68-million-row backlog is cut back to
20,000 rows per table the moment it reopens, with no manual database surgery.

**Guard:** `tools/test_platform_v7_discovery_dedup.py` - six checks: a repeated
sighting writes nothing, a genuine change still persists, two distinct devices
are each persisted exactly once, the in-memory device-online state keeps
updating regardless of the dedup, history is pruned back to the cap on a fresh
startup, and the bounded count never scans past its bound. Re-broken three
ways (no dedup, no startup prune, unbounded count restored) and all three were
caught.

---

## BUG-17 - the yoke was drawn as a bar that slides, not a yoke that turns

**Symptom (owner):** "the yoke faceplate its not clear the design i so bad...
rebuild it in a way it look like the original Moza yoke and also it move
freely like a yoke."

**What was actually wrong, not just plain.** The old drawing was a flat
horizontal bar with two rectangles on the ends. Roll moved the whole bar
sideways by up to 19 px; pitch moved it up or down by up to 15 px. Both
numbers are so small that on a monitor the "movement" was barely visible at
all - which is a large part of why it read as broken rather than merely
unpolished. Worse, the *kind* of motion was wrong, not just its size: a real
yoke's roll axis turns the wheel around its own hub, the way a car's steering
wheel turns. Sliding the whole shape sideways is not a smaller version of that
motion, it is a different motion entirely.

**Confirmed against the real hardware before redrawing anything.** Fetched the
manufacturer's own product photography for the MOZA MFY yoke (the detachable
yoke the A210 base takes) rather than guess a shape from memory: a swept
"gull-wing" silhouette, two horns curving down and outward from a central hub
to a pair of vertical hand grips, with a dial cluster and buttons mounted on
each grip.

**Fix.** Every point of the new shape - both horns, the hub, the two grip
capsules, and every button mounted on them - is defined once in a *local*
frame centred on the yoke's own hub, then carried through one shared
rigid-body transform: rotate by roll, translate and scale by pitch. Because
every piece shares the same transform, the whole assembly turns together the
way the real bolted-together yoke does, buttons included - a button drawn at a
fixed screen position while the grip it is mounted on rotates out from under
it would have looked more broken than the flat bar it replaced.

Full roll deflection is now 42° each way (previously an up-to-19-px slide);
full pitch travel is 76 px measured end to end on the actual rendered canvas
(previously at most 30 px). Tk 8.6's native text rotation turns the hub
badge with the rest of the assembly, the way a nameplate bolted to a turning
wheel would.

**What did not change.** Every one of the 29 numbered HID contacts the old
layout placed is still there, under the same tag, wired to the same button
number - the redesign relocated them onto the new silhouette, it did not
renumber or drop any of them. The axis-to-motion sign convention (which raw
HID direction the owner's own capture proved is "roll right" versus "roll
left") was carried forward unchanged from the working code; only how that
motion is *drawn* changed.

**V2 - what watching V1 actually move caught.** Static review missed three
things that only showed up once the owner watched the first rebuild turn:

1. **Upside down.** V1 put the hub at the top and swept the horns down to
   grips below it. The real MFY yoke's own product photography - already
   fetched for V1, apparently not read carefully enough - has the grips
   *above* the hub, which sits low, over the column. Corrected by mirroring
   every local y-coordinate: grips at negative y, hub at positive y.
2. **A visible rod where there should be a fixed point.** V1 drew pitch as
   the hub sliding along a rendered connecting rod down to a fixed base
   point. The owner's fix is more correct than V1's was: "move the yoke on
   its axel fixed in the middle" - no rod, one fixed pivot, roll rotates
   around it up to 90 degrees either way (not V1's 42), pitch scales the
   whole assembly larger or smaller around that same fixed point rather than
   sliding it.
3. **Buttons that stopped turning with their own grip.** Each five-way
   cluster's own five dots were positioned as fixed screen offsets from an
   already-rotated cluster centre - the centre turned correctly, the dots
   riding on it did not, which is the same "not every piece shares the
   transform" mistake V1's own writeup warned against, reintroduced one
   level deeper. Fixed by rotating the dot offsets through the identical
   transform as everything else. Caught by the angle-swept assertion below,
   which measured 83.9 degrees instead of the commanded 90 until this was
   fixed - a genuinely useful test failure, not a rounding error.

Also addressed in the same pass: "get rid of this button design they all
wrong and they all go by numbers wich does not make any sense" - every
numbered contact used to be drawn with an arrow glyph and a printed
diagnostic badge ("B029") beside it. Replaced with a plain dot or button that
carries only live colour; the number still identifies the contact for
Practice-mode calibration, on the same tag, it is simply not printed on the
hardware's own face. And "still so slow... it has to go smouth": physical
status only arrives ten times a second, which is fine for a switch and reads
as stutter for something watched turning continuously. Roll and scale now
ease toward each new target across additional frames drawn at roughly 60 fps
between real telemetry replies (`_moza_yoke_ease`, reusing the PDC panel's
own proven eased-animation store rather than inventing a second one), so the
yoke keeps moving smoothly in the gaps between what the bridge actually
sends.

**A test-writing lesson worth keeping.** The first version of the roll check
asserted that both grips move by a large amount in both x *and* y, and that
the two grips swing opposite vertical directions. Both assertions are false
in general - a 90-degree rotation of a point can legitimately produce a
small change in one coordinate depending on the point's starting angle, and
two points that are mirror images left-right (not diametrically opposite
through the hub) are not required to move opposite ways under a shared
rotation. Both read as very plausible checks and both were wrong; they
happened to hold at V1's 42-degree deflection by coincidence of geometry, not
because they were correct in general, and broke as soon as the angle changed
to 90. The fix that actually holds at any angle: measure the angle swept
about the *known, fixed* hub position via `atan2`, and require it to equal
the commanded roll exactly.

**Guard:** `tools/test_moza_yoke_faceplate.py` - ten checks, rendering the
real drawing function on a real (hidden) Tk canvas and reading back actual
on-screen bounding boxes rather than trusting the transform math by
inspection: all 29 original contacts still exist and print no raw number,
grips sit above the hub, no shaft is drawn, both grips sweep through exactly
the commanded roll angle about the fixed hub, full deflection is 90 degrees,
the whole silhouette stays inside its panel at every tested extreme, the
pivot implied by the two grips' mirror symmetry never moves under pitch,
push zooms in while pull zooms out, the rotation transform preserves every
point's distance from the hub at every angle including the full 90-degree
extremes, and roll eases toward a new target across frames instead of
snapping. Re-broken six ways (shaft reintroduced, hat dots left unrotated,
push/pull sign reverted, roll range shrunk back to 42, dot radius left
unscaled under zoom, animation forced to snap) and all six were caught.

---

## BUG-18 - LevelUp was detected, then excluded from the displays and pitch trim

**Symptom (owner):** with a LevelUp 737 loaded, BB35 held the last Zibo image,
BB36 stayed black/frozen, and the physical RUD TRIM rocker neither moved the
stabilizer trim wheel nor armed its units readout. The same devices still
worked under Zibo.

**Cause:** automatic LevelUp detection, its isolated command library, shared
display telemetry and the hard-coded trim loop were already present. Three
later startup gates still admitted only Zibo and the probed B738-compatible
profile, however, so the existing BB35/BB36 routers were never started for a
known LevelUp load. The trim loop did start, but inherited Zibo's
`laminar/B738/flight_controls/pitch_trim_*` pair. LevelUp's captain yoke instead
publishes `sim/flight_controls/pitch_trim_*`. Because the LCD readout is armed
only after a trim command resolves and is sent, one wrong command pair made
both the wheel and its readout appear dead.

**Evidence before changing code:** the installed
`LevelUp/737NG_Series_V2/b738_cockpit.obj` assigns the captain electric trim
switches to the two generic X-Plane commands. Its `B738.tablet.lua` publishes
`laminar/B738/flight_model/stab_trim_units`. All 69 FMC1 commands and all five
FMC1 datarefs consumed by MuslimSim's BB35/BB36 modules are present in the
installed LevelUp command/dataref lists, so using the existing routers requires
no renderer, font or page-layout fork.

**Fix:** admit LevelUp at only the captain-PFD resolution, BB35-router and
BB36-router gates. Add the two captain trim commands to
`LEVELUP_WINCTRL_COMMAND_OVERRIDES`, leaving the Zibo base dictionary unchanged.
No display drawing code, startup refresh, shared telemetry, recovery threshold,
device ownership or non-LevelUp gate changed.

**Guard:** `tools/test_levelup_737_integration.py` reads source without importing
the bridge or opening hardware. It pins the three display gates, the exact two
LevelUp captain trim overrides, the original two Zibo trim commands, and the
absence of the obsolete explicit LevelUp BB36 skip.

---

## BUG-19 - the yoke's button map was guessed, and half the guesses were wrong

**Symptom (owner), after watching V2 and pressing the real controls while a
fresh capture ran (`yoke.pcapng`):** "the right upper and the left upper its
just one button not five buttons... you can tap it from multiple angle. the
right and left grip text should be on the side. the select buttons missing
too many... there is four buttons on each corner... they don't work at all."

**What the capture proved, checked contact by contact against the exact byte
math `muslimsim/devices/moza_a210.py` already uses to decode report 01.**

- **Eleven contacts read as permanently pressed for the entire 91.5 s
  capture** - 31, 32, 53, 59, 62, 64, 66, 68, 70, 72, 74. A firmware idle
  pattern, not buttons. Two of them (31, 32) were the whole of the old "LEFT
  UPPER" guess's supporting evidence.
- **Contacts 29, 28, 30, 27, 23, 26 never moved once** in the entire
  capture, despite the owner working every control on the yoke. These made
  up the rest of the old "LEFT UPPER" and "RIGHT UPPER" guesses.
- **24 and 25 asserted together for the whole ~0.9 s of one press**, across
  several hundred consecutive USB reports, and released together. One
  physical switch, reported on two bits - which is exactly "one button you
  can tap from multiple angles," proven rather than described. That is
  RIGHT UPPER now.
- **The left-hand equivalent was never pressed in this capture.** Rather
  than mirror 24/25 into an unproven number, it is drawn with nothing bound
  to it - see the fix below.
- **19, 20, 21, 22 and 14, 15, 16, 17** each produced one clean edge on its
  own, individually, with nothing else moving at the same instant - the
  grips, replacing an old five-a-side guess that included two numbers (13,
  18) that never moved at all.
- **5 through 12 - eight contacts, not five** - each produced one clean
  edge on its own, in one continuous test run. The owner's own diagnosis,
  "select buttons missing too many," was exactly right: the old guess had
  five of these eight.
- **1, 2, 3, 4** matched the old guess exactly - real, clean, individually
  proven. "They don't work at all" is not explained by wrong numbers: the
  catalogue declares all 128 contacts as implemented, the bridge forwards
  every one unfiltered (`bridge/final.py`'s `_muslimsim_moza_a210_lab_event`
  has no button-number filter at all), and the capture shows all four
  firing cleanly. The likely cause is layout, not identity - these four sat
  with two of them touching the hub's own edge, in a 90-degree-deflection
  layout that did not exist when they were first placed. Moved further from
  the hub and given more separation; the number binding is unchanged because
  nothing about it was disproven.

**Fix.** `_draw_moza_yoke_rocker` draws a single switch that lights if *any*
of its bound contacts are active, for the proven case (right) and the
honestly-unmapped case (left, drawn dashed with no control tag at all, on
purpose - a wrong guess would light up on a press that has nothing to do
with it, which is worse than admitting it is not wired yet).
`_draw_moza_yoke_ring` replaced the old five-fixed-slot hat with one that
lays out however many contacts it is given evenly around a circle, serving
the four-contact grips and the eight-contact select cluster with the same
function, and takes an explicit caption offset so "the text should be on
the side" is the caller's choice per cluster rather than a fixed "always
above."

**Guard:** `tools/test_moza_yoke_faceplate.py` - fourteen checks. Verifies
every capture-proven contact exists and none of the disproven ones are
drawn; the right rocker lights on *either* of its two bits, not only both
together; the left rocker is drawn dashed and carries no control tag;
select has all eight contacts; no contact prints its raw number; grips sit
above the hub with their captions offset to the side; plus the full V1/V2
geometry suite (no shaft, exact 90-degree sweep about the fixed hub, stays
on-panel at every extreme, push zooms in and pull zooms out, the transform
preserves distance from the hub, motion eases rather than snaps). Re-broken
five ways (select shrunk back to five, the left rocker given an invented
number, the rocker requiring both bits instead of either, the grip caption
moved back above, a disproven noise bit drawn as a real corner button) and
all five were caught.

**Still open:** the left-hand rocker's real contact number(s). Not guessed,
and not fixable without a capture that actually presses it - if a short
follow-up capture exercises just that one control, decoding it is the same
few minutes of work this entry already did for its right-hand twin.

**Follow-up - select moved to the sides, and a live axis was found dead:**
"the select button they should be located on the side in the place of those
two slides in the corner witch they don't give any feed back am not sure
why." The two "corner slides" were `axis_z` and `axis_dial`, drawn pinned to
the panel rather than as part of the rotating yoke. Checked against the same
capture before touching either: `axis_z` held the exact value 32767 for all
76,345 reports in the file - the identical idle pattern already on record
for the AB6's own Z axis, now confirmed on the A210 too, which is the actual
reason it never looked live. `axis_dial` is not idle: it swept its full
0..65535 range in the same capture, a genuine working control removed to
make room for select rather than a second dead one - worth knowing if that
axis is wanted back somewhere else on this panel, since it was never proven
broken. `_draw_moza_axis`, now with no callers anywhere in the file, was
removed rather than left in place. Select's eight contacts now split 5-8 to
the left and 9-12 to the right, positioned further from the hub than the
grips, and - unlike the sliders they replaced - computed through the same
rotating transform as everything else, so they turn with the wheel the way
a crossbar-mounted contact actually would. Guard: two more checks in
`tools/test_moza_yoke_faceplate.py` (select sits outboard of both grips;
the removed sliders leave no drawn trace), sixteen in total. Re-broken by
moving select back to the centre crossbar, and caught.

**Second follow-up - grip pads reshaped and moved, the whole yoke shifted
down, and a real panel-size limit found in the process:** "move left pad
button and right pad button and change their shape to rounded rectangular
and move each above the yoke than move the entire yoke down about 3 cm."
The two grip clusters (19-22, 14-17) moved from a round ring to a rounded
rectangle - reusing the exact corner-rotation technique
`_moza_yoke_capsule` already used for the hub and grip housings, since a
rounded rectangle is the same shape wherever it is drawn - and up to local
y=-128, clearly above the rocker at -108.

The 3 cm shift does not fit as asked. Computed directly rather than eyeballed:
at full zoom-in (push, scale 1.16), the grip capsule - unchanged, existing
geometry from V1, nothing to do with this request - already needs 227 px of
clearance below the pivot at rest, and a full 113 px shift (3 cm at 96 DPI)
would leave only 207 px there. The cap is about 77 px (roughly 2 cm) before
that capsule alone draws off the bottom of its own panel at full zoom, found
by computing every drawn element's true worst-case reach from the pivot -
including a rounded rectangle's corner, which reaches further than its own
half-width in every direction, not just half-width itself, an undercount
that broke the first estimate of how far the new pads could safely go.
Applied 70 px (about 1.9 cm), the largest shift that keeps every element on
the panel at every roll and pitch extreme actually tested, and said so
plainly in the constant's own comment rather than silently deliver less than
what was asked - the full 3 cm is only reachable by also shrinking geometry
nobody asked to touch.

**A test-writing mistake, caught immediately by re-breaking the guard on
purpose.** The first two checks for this compared a single dot's own drawn
position (`button_019`, `button_005`) to a cluster's true centre, as if the
two were the same point. They are not: each dot sits offset from its ring or
pad's centre by that shape's own radial spread, so a single-dot position is
already off by that spread - about 15 px here, enough to make both checks
fail even against the *correct* geometry. The tell was informative on its
own: mutating the code (reverting the pad's shape, zeroing the shift) did
not change which assertion failed, because the check was measuring the wrong
point regardless of what the code did. Fixed by using the combined bounding
box of a whole cluster's contacts, which is only ever correct at that
cluster's own true centre.

**Guard:** two more checks in `tools/test_moza_yoke_faceplate.py` (the grip
pads are polygons - not ovals - positioned above the rocker; the yoke's
drawn position matches what `MOZA_YOKE_VERTICAL_SHIFT` predicts, not merely
that the constant is positive), eighteen in total. Re-broken four ways
(pad housing reverted to a circle, pad moved back down level with the
rocker, the shift constant zeroed, the shift constant left unwired to the
actual pivot) and all four were caught.

---

## BUG-20 - three faceplates hopped between polls, and the throttle's MODE selector had the wrong roles

**Symptom (owner):** "now you have check thrustmaster TCA and the winctrl
Minor throttle and Moza ab6 they all choppy i feel like they jump one inch
each time they move they have to move smoothly no shopping nothing at all."
Same message, second half: "on the winctrl thrust change the pitch angle
trigger to Crank an make sure its lcd remain working and make Mode Norm the
rudder Trim also make sure the lcd give life feed back from the rudder trim
and change the IGN/ Strat to be aileron trim."

### Part 1 - three faceplates read a lever straight off the last status poll

**Cause:** the WinCtrl throttle's three continuous axes (`left_thrust`,
`right_thrust`, `speedbrake`, `flap_axis`), the AB6's stick/slider/dial, and
the TCA quadrant's three levers all called their fraction/value straight into
the drawing call with no interpolation. Status only arrives about ten times a
second; a real, continuous physical motion between two polls was drawn as one
instantaneous hop on the next redraw - the reported "jump one inch."

The MOZA yoke had already solved this exact problem for roll and scale with
`_pdc_flat_animate`, run at ~60fps via `self.after(16, ...)` through
`_moza_yoke_request_frame`, fully decoupled from the poll rate.

**Fix:** generalised that same primitive rather than writing three new ones.
`_axis_ease(device, key, target, speed=0.30)` scales a 0..1 (or -1..1)
fraction up before calling `_pdc_flat_animate` (whose own snap-to-target
threshold, 0.20, is tuned for degree/percentage-scale values and would
otherwise just snap a raw fraction on almost every poll) and back down after.
`_axis_ease_request_frame(device)` mirrors `_moza_yoke_request_frame`,
redrawing only while that specific device is still selected. Wired into all
three faceplates' continuous axes. The TCA quadrant's levers skip easing
while the owner is actively dragging that exact lever in Practice
(`self._tca_drag_axis == axis_key`), so dragging still tracks the pointer
1:1 - only the polled/live path is smoothed.

**Guard:** `tools/test_winctrl_smooth_axes_and_trim_remap.py` drives
`_axis_ease` directly with no Tk canvas (a fresh key lands exactly on target;
a jump afterward eases across frames, not in one; debounced - a still-pending
frame is not re-requested; converges within a bounded number of frames; the
scheduled frame redraws only while its device is still selected) and confirms
by source that all three faceplates actually call it. Re-broken once
(`WINCTRL_TRIM_ROLE_BUTTONS` mutated to prove the harness's own source checks
have teeth) and caught.

### Part 2 - the MODE selector's trim roles, and the pitch trim already wired in a separate fix

**What was already true before this request, from a different, already-shipped
fix (`WINCTRL PITCH TRIM WHEEL V1`):** the RUD TRIM rocker is hard-wired to the
real 737 electric pitch/stabilizer trim regardless of the MODE selector - "It
is deliberately NOT gated on the MODE trim role: that gate returns silently
whenever MODE sits in IGN/START, which looked exactly like a dead display."
That value lives under the key `"STAB"` and its own display channel,
`stab_trim_display`, which uses a different (unsigned, units) segment
encoding than the signed rudder/aileron scale. The MODE selector itself,
separately, only ever gated which of two *local, non-hardware-verified*
practice numbers (`RUDDER`, `AILERON`) the rocker's RESET/left/right buttons
showed at rest - CRANK meant rudder, NORM meant aileron, IGN/START meant
neither.

**What the request asked for:** "the pitch angle trigger" is standard trim
nomenclature for pitch trim, so read together the three clauses ask for a
full pitch/roll/yaw remap: CRANK selects pitch, NORM selects rudder (moved
off CRANK), IGN/START selects aileron (moved off NORM). Naively adding a
fourth, disconnected local float called `"PITCH"` for CRANK - matching how
`RUDDER`/`AILERON` already worked - would have been a regression: it would
have hidden the *already-working, hardware-verified* live pitch readout
behind a fake local number that Live mode never touches, on the one part of
this request the owner explicitly asked to keep working ("make sure its lcd
remain working").

**Fix:** CRANK now selects the existing `"STAB"` role instead of a new one,
so its LCD shows the same live pitch/stabilizer number the rocker's
already-proven wiring already produces - not a second, disconnected number.
`_muslimsim_select_winctrl_trim_role` now picks the display channel by role
(`stab_trim_display` for STAB, `rudder_trim_display` otherwise) so switching
into CRANK pushes the correct segment encoding immediately, and Studio's
`_throttle_trim_display_value` reads the confirmed value back the way the
bridge actually reports it - under the one `"rudder_trim_display"` mirror key
regardless of which channel wrote it, since the physical window is one piece
of glass with only one last-confirmed value. RESET has no real centre command
for electric trim, so it stays a deliberate no-op for the pitch/STAB role, in
both Practice and Live - matching the already-proven mechanism rather than
inventing a "reset pitch to zero" behaviour nothing on the real hardware
supports. The UI labels this role "PITCH" (what the owner asked for and what
737 nomenclature calls it) while reusing "STAB" internally, so it never has
to touch the separately-proven pitch trim mechanism at all.

Also added, on every mode change: the LCD shows the newly selected role's
name for about one second (`_throttle_trim_label_until`, a one-shot
`self.after(1050, ...)` redraw) before it starts showing that role's live
number - "each time you move to a mode make sure the lcd right the mode its
one for a second before it start showing the numbers." This is Studio-only:
the real physical B930 window's captured glyph table holds only digits, L, R
and blank, so the real hardware LCD cannot spell out a mode name at all - only
Studio's own mirror of the panel can.

**Guard:** the same test file parses `bridge/final.py`'s three separate
copies of the trim-role map (the `WINCTRL_TRIM_ROLE_BUTTONS` literal, its own
self-test's expected literal, and `_muslimsim_select_winctrl_trim_role`'s
`selected` dict) and confirms all three read CRANK=STAB / NORM=RUDDER /
IGN-START=AILERON; confirms the live RESET dispatch table has no STAB entry
and prints "no reset command for..." instead of the now-obsolete "IGN/START
neutral" message; confirms exactly one practice-mode `if role == "STAB":`
no-op guard exists; and drives Studio's `_set_throttle_trim_selector`,
`_apply_throttle_trim_visual` and `_throttle_trim_display_value` directly to
prove the mode switch, the label-then-numbers timer, the STAB-only RESET
no-op, STAB's real 0.0-19.9 clamp range, and the single shared display-mirror
read-back all behave as described.

---

## BUG-21 - the MOZA A210 yoke was Studio-visualization-only and never moved the aircraft

**Symptom (owner):** "also the moza a210 its not moving the aircraft yoke."
When asked whether a simulator function had been assigned to the yoke's axes
in Studio: "it use to work b4 why i have to assign anything also the
functions because its a yoke should be automaticly assigned."

**Diagnosis:** three full `--control-port=0 --diagnose-controls` runs (the
first of three attempts had used `--diagnose-controls` alone, which silently
disables the whole hardware-lab subsystem including MOZA, since
`hardware_lab` is only constructed when `--control-port >= 0`) all showed the
MOZA A210's HID reader starting and reporting live axis/button/hat activity
to Studio, but never once printed a dataref-resolution line for it - unlike
every other analog input (WinCtrl throttle, pedals), which always print
`"<DEVICE> <key> -> id <ref_id> -> <name>"` at startup. Reading
`_muslimsim_moza_a210_lab_event` confirmed why: it only ever called
`hardware_lab.input(...)` for the 2D panel. "Its reader has no output path
and is deliberately independent from the WINCTRL switch" was already stated
in its own comment. The yoke was never bound to anything in X-Plane through
MuslimSim; whatever worked "b4" was X-Plane's own native joystick binding,
which the owner then chose to replace rather than restore, picking "build
real bridge routing" so the bridge drives the aircraft the same way it
already does for the WinCtrl pedals - no per-user function assignment needed.

**Fix:** added a `MOZA_A210_DATAREFS` dict (`roll` ->
`sim/joystick/yoke_roll_ratio`, `pitch` -> `sim/joystick/yoke_pitch_ratio`,
the same generic ratios X-Plane's own joystick binding would use) and gave it
the identical no-jump startup-safety pickup and tolerance-cached write the
pedals already use, so a parked yoke can never snap a live aircraft's
attitude on bridge restart, and identical crash isolation (one axis's write
failure disables only that axis for the run). Because the MOZA A210 is read
on its own hidapi thread rather than the pedals' shared SDL poll, its
baseline is taken directly from the reader's own `live_snapshot()` at the
same startup-safety checkpoint the pedals use, instead of the SDL-only
`startup_hardware_snapshot` event; continuous updates route through a new
`_queue_latest_moza_a210_axes` coalescing helper (matching
`_queue_latest_pedal_axes`) called from the existing lab callback whenever
`event.control` is `axis_x` or `axis_y` - the hat and 128 generic buttons
stay exactly as Studio-only as before.

`axis_x -> roll` reuses the sign already hardware-confirmed earlier in this
project (turning the yoke right raises `yoke_roll_ratio` and banks right).
**`axis_y -> pitch` direction is not independently re-verified in this
change** - it mirrors the same open, previously-disclosed assumption already
written into `studio.py`'s MOZA visualization code. If the aircraft pitches
the wrong way when the yoke is pushed, the fix is exactly one sign flip,
called out at both the `MOZA_A210_DATAREFS` definition and the roll/pitch
conversion in the main loop.

One real hazard surfaced building this: the MOZA A210's HID reader thread is
started long before `event_q` used to be constructed (`event_q` was created
just before the main loop, while the reader is started as part of much
earlier setup). Its callback closes over `event_q` by name, and the reader
emits its first report - and therefore its first queued event - immediately
on connect, which could race the queue's construction. Rather than tolerate
that race, `event_q`'s construction was moved to sit immediately beside
`moza_a210_lab_reader = None` at the top of the reader-state block, strictly
before any reader (MOZA included) is started, closing the window entirely
instead of relying on the callback's existing try/except to paper over it.

**Guard:** `tools/test_moza_a210_yoke_routing.py` parses `bridge/final.py`'s
source (no bridge import, no HID handle, no simulator - same convention as
`test_levelup_737_integration.py`) and confirms: the datarefs/tolerance/CLI
flag are correct; `event_q`'s construction precedes both the reader-callback
definition and its `.start()` call; the lab callback checks
`event.control in ("axis_x", "axis_y")` and reads both axes together from
`live_snapshot()` before queuing; the coalescing helper tags its event
`moza_a210_axes`; the startup baseline reads X-Plane read-only via
`read_dataref` and seeds `moza_a210_last_sent` before ever arming; and the
main-loop branch reuses `_winctrl_axis_pickup_reached` and
`_winctrl_set_cached` rather than inventing new ones. Re-broken once (the
`pitch` dataref name mutated to prove the literal-equality check has teeth)
and caught.

### Follow-up - the write reached X-Plane but the flight model kept fighting it

**Symptom (owner), after the fix above shipped:** "it still show me that
mouse square however when i move the yoke in and out i feel it want to move
it chaky in the sim." The on-screen mouse-yoke square is X-Plane's own
fallback control, shown specifically when it has no real joystick calibrated
to roll/pitch - direct evidence X-Plane still believes nothing is bound to
those axes.

**Cause:** `sim/joystick/yoke_roll_ratio` and `yoke_pitch_ratio` are not
plain state - X-Plane recomputes both itself on every flight-model frame,
either from whatever hardware axis it has calibrated to roll/pitch, or, with
none calibrated, from its own mouse-yoke fallback. Either source overwrites
a plain external PATCH write on the very next frame. The pedals' rudder axis
never hit this because X-Plane's mouse-yoke fallback only covers pitch/roll,
not yaw - rudder had nothing fighting it. Roll and pitch, freshly unbound
after whatever previously connected the MOZA A210 natively stopped doing so,
had X-Plane's own fallback actively resetting them every frame: the bridge
writes a value, X-Plane's own recompute overwrites it, the bridge writes
again - exactly the alternation "chaky" describes.

**Fix:** added `MOZA_A210_OVERRIDE_DATAREF =
"sim/operation/override/override_joystick"`, X-Plane's documented mechanism
for telling the flight model to trust an external source for the joystick
ratios instead of recomputing them itself. Resolved once, right after the
roll/pitch datarefs themselves resolve successfully, and set to `1` a single
time at startup (not on every write - it is a static mode switch, not a
per-frame value). Resolution failure warns and leaves the override unset,
the same fail-open pattern every other optional dataref in this file uses;
nothing else about the routing depends on it succeeding.

This is a reasoned hypothesis, not yet confirmed against the owner's live
X-Plane: the fix targets the exact mechanism the symptom describes (the
still-visible mouse-yoke square proves no axis is calibrated, which is
precisely the condition that makes X-Plane's fallback fight an external
write), but confirming it requires watching the real aircraft respond
smoothly with the square gone.

**Guard:** extended `tools/test_moza_a210_yoke_routing.py` to confirm the
override dataref name, that it is resolved and armed only after
`moza_a210_ids` is non-empty (never attempted with nothing to route), and
that a failed resolution warns rather than raising. Re-broken once (the
`set_dataref` arm call removed) and caught.

### Second follow-up - routing confirmed live, but every raw HID sample was relayed as an instant jump

**Symptom (owner), once both fixes above were confirmed working (diagnostic
log showed real dataref ids, the override armed, and both `MOZA A210 roll
pickup reached at 0.012` and `MOZA A210 pitch pickup reached at 0.026`):**
"it respond it chacke very tiny ammount once i touch the yoke its obvious
the yoke causing that but the problem the chacking is not normal." Cause and
effect was now proven - the yoke really was driving the aircraft - but the
motion itself was not smooth.

**Cause:** the MOZA A210's HID reader emits a report whenever the yoke's
raw value happens to change, an irregular cadence entirely driven by hand
movement. The main-loop write branch relayed each one to X-Plane the
instant it arrived via `_winctrl_set_cached` - a "jump straight to this
exact position" instruction with nothing filling the real time between two
reports. A native joystick axis never has this problem because X-Plane
polls it directly, continuously, every render frame; pedals and the WinCtrl
throttle do not show it either because those axes are driven from the SDL
poll's own steady cadence, not an irregular HID-report cadence. For a fast,
large yoke movement the steps are too small and fast to notice; for a slow,
tiny touch - exactly what was tested - each step became visible.

**Fix:** moved the actual `_winctrl_set_cached` write out of the
"moza_a210_axes" event branch entirely. That branch now only records the
yoke's latest real position (`moza_a210_pickup_previous`) and runs the
existing no-jump pickup gate - it never touches X-Plane directly anymore. A
new fixed-cadence tick (`MOZA_A210_EASE_INTERVAL` = 0.02s, outside the
event-queue drain loop so it runs every main-loop pass regardless of
whether a new HID report arrived) eases each already-armed axis's last-sent
value a `MOZA_A210_EASE_SPEED` (0.35) fraction of the way toward that
target and writes the result through the same tolerance-cached helper. This
is the identical smoothing idea `_axis_ease` already applies to Studio's
own redraw (BUG-20 Part 1), just aimed at the simulator write instead of a
redraw, and it never bypasses the pickup gate: only an axis already in
`moza_a210_pickup_armed` is touched.

**Guard:** extended `tools/test_moza_a210_yoke_routing.py` with a check
that the pickup branch no longer contains a `_winctrl_set_cached` call at
all, and a second check that the new ease-tick block exists, only touches
`moza_a210_pickup_armed` axes, targets `moza_a210_pickup_previous`, and is
the one remaining place that calls `_winctrl_set_cached` (34 checks total
for this file). Re-broken once (the ease step replaced with an unsmoothed
direct jump to target) and caught.

### Third follow-up - the ease tick's own tolerance check silently undid the smoothing

**Symptom (owner), after confirming with the "where do you see it" question
that this was purely visual and only happened while actively moving the
yoke:** "am watching the yoke it self in the sim once i move it it chake
very very tiny movement i concider chacking not movement." Watching
X-Plane's own 3D cockpit yoke model, a slow deliberate movement still did
not read as smooth motion at all - "same problem" after the write-side ease
timer above.

**Cause:** the ease tick still passed `MOZA_A210_VALUE_TOLERANCE` (0.0015 -
the same floor pedals/throttle use to avoid flooding X-Plane with no-op
writes from a settled axis) into `_winctrl_set_cached` for its own 35%
easing step. For a fast, large yoke movement the target-current gap is
large, so 35% of it comfortably clears 0.0015 every tick - smooth. For the
slow, tiny movement being tested, 35% of a small gap can land *under*
0.0015: the write is skipped, and because a skipped write also means the
cached "current" value never advances, the real gap between the yoke's
actual position and what X-Plane had been told kept growing every tick
until it finally cleared 0.0015 and dumped out as one visible jump - then
went quiet again while the gap re-accumulated. That hold/hold/hold/jump
cadence, not the intended continuous glide, is exactly "chacking, not
movement": the general-purpose settle-tolerance was fighting the very
smoothing mechanism built to use it.

**Fix:** added `MOZA_A210_EASE_WRITE_TOLERANCE = 0.00005`, a floor two
orders of magnitude smaller, used only by the ease tick's own write call.
`MOZA_A210_VALUE_TOLERANCE` keeps its original job everywhere else
(pickup-adjacent bookkeeping); the ease tick alone gets a floor small
enough that a genuinely tiny real step still goes out every ~20ms instead
of being silently absorbed and left to accumulate.

**Guard:** extended `tools/test_moza_a210_yoke_routing.py` to assert
`MOZA_A210_EASE_WRITE_TOLERANCE` is strictly smaller than
`MOZA_A210_VALUE_TOLERANCE`, that the ease-tick block references the new
constant, and that it does *not* reference the general one at all (37
checks total for this file). Re-broken once (the ease tick's write call
reverted to `MOZA_A210_VALUE_TOLERANCE`) and caught - the test correctly
named the exact regression this fix targets.

### Fourth follow-up - a direct DataRef probe proved X-Plane itself was resetting the value between writes

**Symptom (owner), after rebooting both X-Plane and Studio and confirming
the tolerance fix above:** "same result." Three targeted write-side fixes
(the joystick override, the fixed-rate ease timer, and the tolerance-floor
fix for that timer) had all failed to change the reported choppiness, which
is a strong signal that reasoning about the write path further without new
evidence would just be another guess.

**Diagnosis tool:** built `tools/probe_moza_yoke_dataref.py` - a standalone
script with no dependency on the bridge, HID, or any MuslimSim code. It
reads `sim/joystick/yoke_roll_ratio`/`yoke_pitch_ratio` straight from
X-Plane's own Web API on a plain timer, printing every value change with a
timestamp. Run alongside the normal bridge while the owner did the same slow
movement that showed the problem, it produced the actual ground truth: the
value did not drift or wobble near where it should be - it repeatedly
snapped to *exactly* `0.00000` for one sample, then jumped back near the
real position on the very next sample, over and over, for the entire
capture. A grep across the whole file confirmed nothing else writes to
either of these two DataRefs.

**Cause:** `sim/operation/override/override_joystick` does not appear to
make X-Plane *hold* the last externally-written value indefinitely the way
a plugin-owned dataref normally would. X-Plane's own flight-model frame
runs faster than the write cadence used until now (a tolerance-gated,
skip-if-unchanged write at roughly 50Hz) and resets the value to 0 in the
gaps between writes. Any smoothing applied only to *what* gets written
(the previous two fixes) cannot help if the simulator discards the value
entirely before the next write arrives - the ease tick was computing a
correctly smoothed value the whole time, it just wasn't reaching X-Plane
often enough to survive between resets.

**Fix:** the ease tick now writes unconditionally, every tick, through a
plain `set_dataref` call instead of the cache-skipping `_winctrl_set_cached`
helper every other device uses - "skip because it didn't change enough" is
exactly what let X-Plane's own reset show through. `MOZA_A210_EASE_INTERVAL`
dropped from 0.02s to 0.008s (roughly 125Hz per axis) to stay ahead of
X-Plane's own frame rate rather than just a display-smoothing cadence. The
now-unused `MOZA_A210_EASE_WRITE_TOLERANCE` from the previous fix was
removed rather than left as dead code.

This is a testable, evidence-driven hypothesis, not yet confirmed: the same
probe tool run again is the test - a smooth staircase with no more exact
zeros would confirm it, while the flashes persisting would point to
something else (possibly the override dataref itself not being correctly
supported by this X-Plane/aircraft combination).

**Guard:** rewrote the write-side-ease-tick checks in
`tools/test_moza_a210_yoke_routing.py` to assert the tick uses `set_dataref`
directly (not `_winctrl_set_cached`), records what it actually sent, and
runs at a rate meant to outpace a flight-model frame rather than merely a
display-smoothing one (36 checks total for this file). Re-broken once (the
direct `set_dataref` call reverted to the cache-skipping helper) and
caught.

### Fifth follow-up - the ground truth: this is a documented Zibo limitation, not a bridge bug

**Symptom (owner), re-running the same probe against the 125Hz unconditional
write:** identical result. Roll/pitch still snapped to exactly `0.00000` on
almost every other sample, proving write frequency was never the variable
that mattered - four targeted write-side fixes in a row (override, ease
timer, tolerance-floor fix, unconditional 125Hz writes) had changed nothing
about the actual symptom.

**Root cause, found by searching rather than guessing a fifth time:** an
X-Plane.org forum thread ("Zibo B738X is ignoring dataref yoke_pitch_ratio
and override_joystick_pitch") documents the identical failure from a native
X-Plane SDK plugin - `xp.setDataf`/`xp.setDatai` called on *every single
flight-loop frame* (`registerFlightLoopCallback(..., -1.0, ...)`, i.e. as
fast as X-Plane's own engine runs, strictly faster than anything an
HTTP-based bridge could ever achieve) still got silently overridden back
toward 0 by Zibo. The thread's own conclusion: "I guess in Zibo you can't
override the joystick value." A second thread ("Joystick Calibration With
Zibo 737") confirms Zibo's actual supported mechanism: the yoke must be
natively assigned in X-Plane's own Joystick/Equipment settings, with feel
tuned through Zibo's own in-cockpit response/stability sliders - not driven
by an external DataRef write at all. Zibo's own deeply-modeled control-
loading system processes elevator/aileron input itself and ignores external
writes to the standard joystick-ratio DataRefs, at any speed. This is a
documented, unresolved limitation other X-Plane plugin developers have
independently hit and abandoned - not a bug anywhere in this bridge.

What "used to work b4" almost certainly *was* native X-Plane joystick
binding; whatever broke it (a driver update, a replug that changed the
device's Windows path, a settings reset) needs fixing in X-Plane's own
Joystick settings, not in anything the bridge writes.

**Fix:** flipped `--no-moza-yoke` (opt-out, on by default) to `--moza-yoke`
(opt-in, off by default). The routing code, the pickup gate, the joystick
override, and the write-side ease tick all remain in place exactly as
built - none of it was wrong on its own terms, it simply cannot win against
Zibo's own control processing. Left available and documented for a
simpler aircraft that might actually respect the standard override, but no
longer silently active against an aircraft it cannot control.

**Guard:** extended `tools/test_moza_a210_yoke_routing.py` to assert the
exact `parser.add_argument("--moza-yoke", ...)` call exists, that the old
`--no-moza-yoke` string is gone everywhere (an opt-out flag left lying
around would silently mean something different, or nothing, under the new
name), and that every gating site reads `args.moza_yoke` (38 checks total
for this file). Re-broken once (reverted to the old flag name, which would
have silently broken the `args.moza_yoke` reads elsewhere at runtime with an
`AttributeError`) and caught.

**Interim workaround confirmed by owner:** manually reassigned the MOZA
A210's roll/pitch axes directly in X-Plane's own Joystick/Equipment
settings ("yes done") - proving the root-cause diagnosis correct, but only
as a manual step, not the automatic behaviour the owner actually asked for
from the start ("it should be automaticly assigned"). Told to do this
manually every time a driver update or replug loses the binding again: "i
don't want it to work thru xplane do u think am stupid i know it can work
thru xplane." The owner explicitly wanted something built into MuslimSim
itself, not a manual X-Plane settings step, and explicitly rejected
installing a third-party virtual-joystick driver as a shortcut to it: "no i
want to build something unique for muslimsim studio ... creating something
from scratch."

### Sixth follow-up - the bridge performs the native assignment itself, automatically

**What "from scratch" turned out to mean, once researched properly:**
X-Plane exposes the native assignment mechanism itself as an ordinary
DataRef - `sim/joystick/joystick_axis_assignments` (`int[500]`, one slot
per physical axis X-Plane has enumerated across every connected device;
values are the documented function enum, confirmed writable per-index in
DataRefs.txt), alongside `sim/joystick/joystick_axis_values` (the parallel
array of each slot's live raw reading). Writing a slot's assignment is
exactly what X-Plane's own Settings > Joystick screen does when a user
clicks an axis there - the one thing proven, across five rounds of
evidence, to actually work against Zibo. No virtual driver, no kernel
driver, no manual X-Plane step: the bridge finds which slot is the MOZA
A210's own roll/pitch by elimination, then writes it once, all through the
same Web API mechanism already used everywhere else in this file.

**Detection algorithm:** for each of "roll" (axis_x) and "pitch" (axis_y),
track the set of X-Plane axis slots still consistent with everything
observed. On a ~150ms poll, whenever the HID reader reports that axis
moving by a meaningful amount (`MOZA_A210_DETECT_MIN_OUR_DELTA`), any
candidate slot that did *not* also move drops out; whenever our axis did
*not* move but some candidate slot did anyway, that slot drops out too
(ruling out unrelated devices/axes). A slot is only ever accepted once it
has actually been seen moving (`moza_a210_axis_seen_moving`) - surviving
purely through inaction proves nothing, and would otherwise let a
permanently-static, unrelated slot masquerade as the real one. X-Plane's
raw units for `joystick_axis_values` were never independently confirmed
(integer DirectInput-style vs. normalized -1..1), so the elimination only
ever asks "did this change at all" (`MOZA_A210_DETECT_XPLANE_EPSILON`,
scale-agnostic), never "by how much."

**Safety:** the moment an assignment lands, X-Plane starts reading that
hardware axis directly, every frame - exactly like a parked lever could
otherwise snap a live aircraft on bridge restart. So the one-time
assignment write is gated behind the same no-jump pickup check
(`_winctrl_axis_pickup_reached`) every other physical control already
uses: X-Plane's *current* roll/pitch ratio is read once the moment a slot
is confirmed, and the write only fires once the physical yoke has crossed
that value.

**Studio correction UI**, per direct request ("create a way in the studio
to correcte the axis if the encounter such problem"): an "AXIS ASSIGNMENT"
button on the yoke faceplate opens a dialog showing each axis's live
status (idle / detecting, with a candidate count / detected / assigned /
ambiguous / failed), refreshing every 500ms - real live feedback, not a
one-shot snapshot. Three actions per axis: set a specific slot manually,
clear a bad assignment (which also undoes it in X-Plane, writing function
code 0 back to the old slot), or ask the bridge to redetect from scratch.

**Plumbing note:** neither of the two existing device-control RPCs fit a
free-form correction payload. `lab_output` requires a control key that is
pre-cataloged as a numeric/boolean output (`muslimsim/hardware/lab.py`'s
`output()` calls `self._control(device_key, control_key)`, which would
reject `"axis_manual"` outright). `calibration_set` looked closer, but
MOZA's calibration path is hardcoded in `muslimsim/hardware/profiles.py`
to a bounded FFB/spring-settings schema (`normalise_moza_calibration`) that
would raise on an `{"action": ..., "axis": ..., "slot": ...}` payload
before ever reaching a callback. So `muslimsim/control/server.py` gained a
new `DeviceRegistration.command` field and a `device_command` RPC verb,
dispatched exactly as unvalidated as the existing `power_cycle` verb
already is - a deliberate, minimal, reusable addition for exactly this
class of device-specific correction, not routed through HardwareLab at
all.

**Simplification:** since detection now polls
`moza_a210_lab_reader.live_snapshot()` directly on its own timer, the
entire event-queue plumbing built for the earlier (disproven) ratio-write
approach - `_queue_latest_moza_a210_axes`, the `"moza_a210_axes"`
queue-drain branch, the lab-event callback's queue push - is gone. The lab
event callback is back to exactly what it was before any of this routing
work started: Studio-visualization-only.

**Guard:** `tools/test_moza_a210_yoke_routing.py` was rewritten for the new
architecture (56 checks): the new DataRefs/enum/CLI flag; every artifact of
all five disproven ratio-write approaches confirmed gone by name, not just
disabled; the lab-event callback confirmed reverted to visualization-only;
the resolution block; the detection tick's elimination logic, its
seen-moving requirement, its pickup-gated one-time write, and its
already-assigned guard (checked both for the guard's presence *and* that a
successful write actually sets the status the guard checks for - re-broken
once with the status update removed, confirmed the test failed, restored);
the correction command's three actions and its X-Plane-undoing clear; the
new `device_command` server verb; and Studio's dialog, including that its
button is genuinely wired on the faceplate (re-broken once with the
canvas binding removed, confirmed the test failed, restored). Real imports
of `muslimsim/control/server.py` and `muslimsim/gui/studio.py` (not just
`ast.parse`) confirmed both load cleanly with the new methods present.

### Seventh follow-up - Studio's own launch never knew the new flag existed

**Symptom (owner), after restarting through Studio as normal:** "i see the
mouse square." Detection running perfectly would still show the mouse
square if the whole feature never started in the first place.

**Cause:** `--moza-yoke` defaults off in the bridge's own argparse, which
is correct - the whole detection tick is a harmless no-op on any run
without a MOZA A210. But `muslimsim/gui/supervisor.py`'s `BridgeSupervisor`
builds the bridge's command line itself when Studio launches it, and that
command list was written before `--moza-yoke` existed. Studio's normal
launch was silently never requesting the feature at all - every fix in
this bug had been tested by running the bridge directly from a terminal
with the flag typed by hand, which masked this gap completely.

**Fix:** added `"--moza-yoke"` to the X-Plane branch of
`BridgeSupervisor`'s command list, alongside the other X-Plane-specific
flags (`--mapping-aircraft`, `--with-pfd`, `--no-display-startup-refresh`).
Studio's own launch now requests it unconditionally - the entire point was
automatic, not a flag the owner has to remember to type every session.

**Guard:** extended `tools/test_moza_a210_yoke_routing.py` to assert
`"--moza-yoke"` appears in `BridgeSupervisor`'s X-Plane command block (57
checks total for this file). Re-broken once (the flag removed from that
block) and caught.

### Eighth follow-up - roll worked, pitch didn't; a false-elimination bug in the detection algorithm itself

**Symptom (owner):** "wow u got it it turn left right but it does not do it
backaward and forward." Roll genuinely auto-detected and assigned - later
independently confirmed by seeing it show up as assigned in X-Plane's own
Joystick settings screen (a brief detour clarified that seeing it there is
the *expected* result of the bridge's own DataRef write, not evidence the
owner or X-Plane did it manually - Settings only ever displays whatever is
currently in `joystick_axis_assignments`, regardless of who wrote it).
Pitch never got there.

**Diagnosis:** the same filtered diagnostic as always
(`--moza-yoke --diagnose-controls`), this time capturing a long, deliberate,
full-range pitch sweep, showed: `MOZA A210 pitch axis detection lost track
(no slot matched every observed movement)`. Re-reading the elimination
logic against this evidence found a real asymmetry: `MOZA_A210_DETECT_MIN_OUR_DELTA`
(0.02, requiring a *meaningful* ~2% movement on our own normalized axis
before treating it as "moving") was being compared against
`MOZA_A210_DETECT_XPLANE_EPSILON` (1e-6, counting *any* flicker on
X-Plane's side as "moving") using strict two-way agreement
(`our_moved == slot_moved`). During a long, slow, natural sweep - exactly
what pitch got tested with - there are always moments where a hand is
still moving but slowly enough that the coarse 2% threshold reads "not
moving," while the genuine X-Plane slot keeps creeping by an amount that
still clears the near-zero epsilon. That mismatch reads as "this slot
moved when we didn't," and gets the *correct* slot eliminated. Roll likely
survived only because it happened to get tested with faster, more decisive
movements that never opened this gap.

**Fix:** made elimination one-directional. A slot is now only eliminated
for staying completely flat while our own axis moved substantially
(`if our_moved and not slot_moved: continue`) - a reliable signal, since a
truly unrelated slot really will show zero variation across a real sweep.
The reverse case (a slot flickers while our own coarser threshold reads
"still") no longer eliminates anything; it was never a reliable signal to
begin with; it was the bug. A slot still only counts as detected once it
has genuinely been seen moving (`moza_a210_axis_seen_moving`), so this
does not weaken the "must actually observe motion" guarantee - it only
removes the false-positive elimination path.

**Guard:** updated the detection-tick check in
`tools/test_moza_a210_yoke_routing.py` to assert the one-directional
`if our_moved and not slot_moved:` guard exists and that the old
two-directional `our_moved == slot_moved` match is gone (58 checks total
for this file). Re-broken once (reverted to the two-directional match) and
caught.

### Ninth follow-up - a confirmed assignment did not survive a bridge restart

**Gap (not owner-reported, found by re-reading the owner's own original
ask):** "it should be automaticly assigned" was the request from the very
start of this bug. Detection state - candidates, confirmed slots, manual
corrections - lived entirely in the bridge's own memory. Every bridge
restart threw all of it away, meaning the yoke had to be moved through its
full range again before either axis took over, every single session. A
much smaller inconvenience than the original manual X-Plane assignment
problem, but not the "automatic" that was actually asked for either.

**Fix:** a confirmed slot (auto-detected or manually corrected) is now
persisted to a small sidecar journal, `moza_a210_axis_slots.json`, saved
next to the hardware profile the same way `starter_return_state.json`
already sits next to it for the PU engine-start return logic (same
schema-versioned JSON, same atomic write-via-temp-file-then-`os.replace`
pattern, same fail-open-to-empty-on-any-error read). On startup, a
restored slot is treated exactly like a manual Studio correction - it
skips detection entirely and goes straight to the existing no-jump
pickup-gated write, so the assignment reappears the moment the yoke
crosses X-Plane's current position again, with no re-detection needed.
Clearing or redetecting an axis from Studio also removes it from the
journal, so a rejected slot can never come back on the next restart.

**Guard:** added `_check_axis_slot_persistence` to
`tools/test_moza_a210_yoke_routing.py`, which actually executes the
extracted `_load_moza_a210_axis_slots`/`_save_moza_a210_axis_slots`
functions (not just source-pattern matching) against a real temporary
file: round-trips a saved assignment exactly, confirms omitting an axis on
save actually drops it rather than leaving a stale slot, confirms a
missing or corrupt journal fails open to empty rather than raising, and
confirms an out-of-range slot is rejected on load. Also confirmed by
source that the startup path actually calls the loader and seeds
`moza_a210_axis_manual`, and that clearing an axis calls the persist
helper (67 checks total for this file). Re-broken once (the persist call
removed from the successful-assignment branch) and caught.

### Decided, not built (later reversed - see tenth follow-up) - real force feedback stays outside MuslimSim

Once the yoke was genuinely, natively driving the aircraft, the owner asked
for the reverse direction too: live force feedback from the aircraft back
into the yoke. Investigated rather than assumed: X-Plane's own native FFB
support (a Settings tab that only appears for a DirectInput FFB device) did
not appear for the MOZA AY210, because MOZA's force feedback is implemented
over the newer `Windows.Gaming.Input` API rather than legacy DirectInput -
X-Plane's generic FFB tab never sees it. MOZA does publish an official
Flight SDK covering the AY210, but building real feedback into MuslimSim
around it would mean either that proprietary SDK (licensing terms not
publicly available - the owner was in the middle of deciding whether
MuslimSim itself will ever be sold commercially, which makes an
unclarified third-party SDK license a real risk, not a formality) or
reverse-engineering MOZA's protocol specifically to avoid needing that
license, which is a worse position than just asking MOZA for terms.

**Decision:** point to FFB-Bridge instead - a free, MOZA-partnered,
already-built application (officially listing the AY210 as supported) that
reads X-Plane's own telemetry over UDP and drives the base's real FFB
motors directly, independent of MuslimSim entirely. Confirmed from its own
documentation: no MOZA Cockpit/Pit House installation needed (their docs
say to keep it closed while FFB-Bridge runs), no X-Plane-side
configuration, no admin rights, no account for the free tier, which covers
the complete force model. Notably, FFB-Bridge's own documentation
independently confirms the same Zibo 737 joystick-override limitation
discovered earlier in this bug ("The Zibo 737-800X is detected through its
own autopilot and its datarefs are never written") - independent
confirmation from a different vendor of the same root cause.

Not built into MuslimSim at the time. This was a project-scope decision,
not a bug - but the owner revisited it (see tenth follow-up below).

### Tenth follow-up - real force feedback, built from scratch after all

**Owner's directive, overriding the earlier decision:** "we have to build
our own interceptor without using any of their sdk we gonna probe moza and
every move she does." Explicitly not the MOZA SDK (unclear commercial
licensing) and not a request to keep depending on FFB-Bridge - the owner
wanted the AY210's own real force output driven directly by MuslimSim.

**Method:** captured the AY210's actual USB traffic with USBPcap while
FFB-Bridge drove it - legitimate under FFB-Bridge's own EULA, which
explicitly permits "ordinary debugging, profiling, monitoring, or
inspection of your own computer system while FFB-Bridge is running" while
prohibiting decompiling FFB-Bridge itself (never done). Captured across
five real flights (Cessna 172, Boeing 737, A320, Boeing 747-8, and the AB6
joystick on an A320neo), then Flight Check's individual bench tests
one at a time (all 17 Effect Gains, both Forces tests, both Trim tests),
then a genuinely fresh device replug with nothing having touched it yet.

**What the AY210 actually is:** a HID collection (interface 2, endpoints
0x03 OUT / 0x83 IN, confirmed from the capture's own configuration
descriptor) using report layouts that are byte-for-byte the public USB HID
PID (Physical Interface Device) force-feedback spec - not a MOZA invention.
Reports 0x11/0x13/0x14/0x15 map to Set Effect / Set Condition / Set
Periodic / a global constant-force channel; channel 2's Condition report is
the yoke's centering spring, its `CP Offset` field is literally the trim
position (proven by two sequential trim tests toggling the two
`ParameterBlockOffset` values in order). Fourteen of the seventeen Effect
Gains tests (runway rumble, buffets, shimmy, etc.) each map to a distinct
(channel, frequency-code) pair on the periodic-effect channels. None of
this alone produced physical force when replayed.

**The real gate, found only by capturing a truly fresh power-on:** every
capture used as a reference up to this point had been taken from a device
FFB-Bridge had *already* switched into active force-feedback mode earlier
in the same power cycle - so every replay reproduced fully-correct,
fully-acknowledged parameter writes (confirmed via the AY210's own live
firmware debug log, which streams in the clear over a second USB interface
- a Windows COM port, `MI_00` on the same VID/PID - and states outright
what it did with each write, e.g. `Table 7, Param 101 Written: ... 1.0`)
and produced zero motor torque, because the motor itself stays gated. Real
force needs three things together, none of them sufficient alone:
1. Sustained periodic polling on that same serial port (a genuine
   connect/disconnect lifecycle - stop polling and the firmware logs a
   real `Host Disconnect`).
2. A single serial write (param `0x85` = 1) sent once after the firmware
   logs `Host Connected`. Its own log ties this directly to
   `steer set mode: 1` -> `Table 7, Param 49 Written: 1` -> `steer set
   mode: 2` - mode 2 is force-feedback-active. This is a persistent
   per-power-cycle latch: once reached, it survives later
   disconnects/reconnects, which is exactly why it was invisible in every
   earlier capture - none of them happened to start before this had
   already fired once for that power-on.
3. The HID-side reset-then-arm sequence (four parameters explicitly
   zeroed, then a gain-arm write) immediately preceding the actual
   Condition-report coefficient ramp.

**Fix:** `tools/probe_moza_ay210_ffb_bench.py` - opens the AY210's HID
handle (the same one `muslimsim/devices/moza_a210.py` already opens
read-only) and its CDC serial port together, keeps the serial poll alive
on a background thread for the program's whole lifetime, watches the
device's own debug log for `Host Connected` before sending the one-time
enable write, then replays a real, complete, verbatim capture across all
three channels (HID interrupt, HID Feature reports over the control
endpoint, and CDC serial) with a clean teardown on every exit path
(normal, Ctrl+C, exception, or a hard timeout watchdog).

**Confirmed live by the owner:** "yes the yoke feel exactly as i felt it
earlier on ffb-bridge" - the AY210's real spring motor, driven by MuslimSim
alone, with FFB-Bridge and Pit House both closed.

**Guard:** every stage was verified against the device's own live debug
log via a self-captured USBPcap trace of this script's own USB traffic,
not just visual/physical inspection - each new piece (the serial connect
handshake, the enable latch, the HID reset+arm sequence) was confirmed
producing the identical log lines a genuine FFB-Bridge session produces
before being accepted. Two real bugs were caught this way during
development: a background "keep polling" loop that accidentally re-sent
the one-time reset+arm writes on every poll cycle instead of only once,
and a stale-serial-buffer race (USB-layer data already in flight at the
moment of a buffer flush) that made an early connect-detection check
return a false positive; both reproduced and fixed via the same live-log
verification loop rather than guessing.

---

## BUG-22 - ToLiss BA01 accepted sim-side values but discarded its physical FCU controls

**Symptom (owner):** "the fcu efis work but we have problem with buttons light
knobs and lcd not posting the numbers unless if i use the sim knobs ... only
the altitude and the speed moves the heading and the V/S don work at all
heading only display '0' and V/S only display '1'."

**Diagnosis:** four independent faults overlapped. First, the current BA01
firmware sends a 41-byte report on input endpoint `0x81`, while
`MuslimSimFCUEFIS._report()` rejected everything shorter than 64 bytes. The
first twelve payload bytes in that real report still contain the already-known
96-control bitmap, so HID-stack padding determined whether any physical input
was seen. Second, the ToLiss dispatcher explicitly returned without action for
all eight SPD/HDG/ALT/V/S encoder directions. That no-op was based on failed
writes to read-only *display output* datarefs, not the aircraft's actual control
inputs. The installed ToLiss A321's own VR manipulator configuration names four
writable `AirbusFBW/FCU*KnobRotation` AXIS_KNOB datarefs with range -10..29.
A reversible live X-Plane Web API test moved each by one detent, observed the
native selected value change (SPD/HDG +1, ALT +100, V/S +100), then restored
every original value. Third, the LCD read `AirbusFBW/HDGCapt` and
`AirbusFBW/VS`, the aircraft's present heading and vertical speed, rather than
the selected targets. That directly produced the observed near-zero `0` and
absolute-value `1`. Speed and altitude were already correct. Fourth, BA01's
output table exposed only A/THR on the central FCU even though the capture's
lamp test and individual writes established all six odd selectors.

**Fix:** BA01 now accepts both the native 41-byte report and a padded 64-byte
form, but compares only the confirmed first twelve control bytes so trailing
device state can never become phantom buttons. The ToLiss dispatcher advances
the four native knob-position datarefs by one, wrapping -10..29, and writes the
100/1000 selector to `AirbusFBW/ALT100_1000`. The display preserves its proven
speed and altitude sources and changes only HDG/V/S to X-Plane's selected
`sim/cockpit/autopilot/heading_mag` and
`sim/cockpit/autopilot/vertical_velocity`. Numeric captain/FO BARO settings,
managed/dashed states, all captured EFIS lamps, and FCU LOC/AP1/AP2/A/THR/
EXPED/APPR selectors 3/5/7/9/11/13 are mirrored on the existing 0.2-second
poll. The output manager remains delta-driven. If `AirbusFBW/BatVolts` does
not establish power, all integral lamps are explicitly forced off together
with the windows and backlight.

**Guard:** `tools/test_fcu_efis_toliss.py` uses the exact 41-byte captured
sample and verifies it is accepted while short/wrong-ID reports are refused;
proves bytes after the twelve-byte bitmap cannot emit controls; checks all six
FCU lamp selectors; executes both directions of all four ToLiss rotaries,
including both wrap boundaries and the 100/1000 selector; pins the selected
HDG/V/S sources while also pinning the unchanged working SPD/ALT sources; and
requires the unpowered lamp blackout. This base repair originally passed 48
checks; BUG-23 expands the same guard to 72 without importing the bridge,
opening X-Plane, or touching HID hardware. The existing BA01/Zibo semantic
test and FCU faceplate layout test also pass. Physical ToLiss acceptance
remains required after Studio is restarted.

---

## BUG-23 - ToLiss EFIS filter lamps were permuted and the BA01 V/S window used the legacy presentation

**Symptom (owner):** "the V/S should look identical to the real FCU" and
"when I tap the CSTR WPT VOR.D NDB ARPT the green light jump all over the
place". ARPT alone illuminated its own button correctly.

**Diagnosis:** the earlier BA01 repair proved the central FCU lamp selectors
but left the five EFIS filter selectors inferred. That inferred ordering was
rotated: CSTR/WPT/VOR.D/NDB were assigned 8/5/6/7 while ARPT happened to have
the correct selector 9. In `EFIS L.R .pcapng`, the ordered right-side physical
presses on raw bits 66/67/68/69/70 at 61.624/61.934/62.204/62.494/63.074
seconds are followed by light-on selectors 5/6/7/8/9 at
61.987/62.210/62.515/62.792/63.410 seconds. The left and right EFIS units use
the same symmetric order. Separately, the display encoder rendered V/S as
four full-size legacy digits and did not enable the BA01's V/S sign and
`ALT <- LVL/CH -> V/S` annunciator segments, so it could not match the real
Airbus FCU reference.

**Fix:** both EFIS sides now use the capture-proven selector order CSTR=5,
WPT=6, VOR.D=7, NDB=8, ARPT=9. ToLiss display updates explicitly request the
Airbus presentation: the hundreds are followed by the BA01 small-zero glyphs,
the horizontal sign stroke is always present, positive V/S adds its vertical
stroke, and the LVL/CH legend plus both arrows are enabled. The presentation
flag defaults off, so the existing Zibo and all other legacy callers retain
their exact prior packets. The power-off path remains fully dark and output
writes remain delta-driven.

**Guard:** `tools/test_fcu_efis_toliss.py` now pins exact on/off reports for all
five filters on both EFIS sides, exact ToLiss `-4800` and `+4800` display-byte
slices, and the exact unchanged legacy `-4800` byte slice. This stage brought
the guard to 72 checks; BUG-24 later extends it to 80 without opening X-Plane
or BA01 hardware. Live acceptance remains: restart Studio with ToLiss loaded,
verify both V/S signs, then press CSTR, WPT, VOR.D, NDB and ARPT one at a time
on both sides.

---

## BUG-24 - ToLiss BA01 FCU did not reproduce MACH, HDG/V/S, or TRK/FPA display states

**Symptom (owner):** four cockpit-reference screenshots showed the required
differences between `SPD 113` and `MACH 0.77`, and between the complete
`HDG/LAT + HDG/V/S + V/S` and `TRK/LAT + TRK/FPA + FPA` states. The owner
asked to make the physical FCU match those differences.

**Diagnosis:** the ToLiss renderer switched only the SPD/MACH heading flag.
In MACH mode it sent the text `.77`; because the decimal point is a dedicated
BA01 flag rather than a character cell, the unmapped `.` blanked the leading
digit instead of producing `0.77`. The renderer always enabled HDG and V/S,
never enabled LAT, never read `AirbusFBW/HDGTRKmode`, and did not read the
selected `sim/cockpit2/autopilot/fpa`. Consequently the paired lower labels,
right-side V/S/FPA title, decimal location, and FPA value could not follow the
aircraft's mode.

**Fix:** the ToLiss worker now reads both confirmed mode/value datarefs and
passes them through two new presentation fields. MACH sends `077` to the three
digit cells and lights the separate decimal segment. HDG/V/S mode enables
HDG+LAT, HDG+V/S, and the V/S title; TRK/FPA mode enables TRK+LAT, TRK+FPA,
the FPA title, and the FPA decimal, formatting the selected angle in signed
tenths (`+0.0`, `-3.2`) with unused cells blank. Both new fields default to
the old state and only the existing ToLiss path opts in, so Zibo and legacy
callers are byte-for-byte unchanged. Stable values add no output writes,
because the BA01 manager remains delta-driven. The existing power gate still
zeros every digit, annunciator and backlight when aircraft power is off.

**Guard:** `tools/test_fcu_efis_toliss.py` now passes 80 checks. It pins exact
dynamic bytes for the reference `SPD 113 / HDG 000 / V/S +0000` and
`MACH 0.77 / TRK 357 / FPA +0.0` states, a signed `FPA -3.2` state, both V/S
signs, both new ToLiss datarefs and transformations, exact unchanged legacy
IAS/MACH packets, and an all-zero unpowered dynamic region. Live acceptance
remains: restart Studio, toggle SPD/MACH and HDG/TRK in ToLiss, then compare
all titles, decimals, values and signs with the virtual FCU.

---

## BUG-25 - ToLiss thrust levers inherited the Zibo/LevelUp 737 calibration

**Symptom (owner):** the WinCtrl engine 1/2 throttles need their own hard-coded
calibration for the ToLiss A320/A321 family, without changing the calibration
already established for Zibo and LevelUp. Each aircraft must retain an
independent control profile.

**Diagnosis:** the ToLiss branch had its own writable target,
`AirbusFBW/throttle_input`, but `_toliss_winctrl_throttle_output()` still
called the Boeing `_winctrl_throttle_values()` converter with the Boeing
`WINCTRL_*_IDLE_RAW` constants. That also imported
`WINCTRL_REV_IDLE_VALUE = 0.0600001`, which is specifically the point where
Zibo's separate reverse lever begins responding, not an Airbus thrust-lever
detent. ToLiss's own IDLE/CL/FLEX-MCT ratio datarefs were resolved but never
used. The result was aircraft isolation in name only: changing either
calibration necessarily changed both families.

**Fix:** ToLiss now owns a separate `toliss-a320-a321-winctrl-v1` table with
six independently stored anchors per engine: FULL REV, REV IDLE, IDLE, CL,
FLEX/MCT and TOGA. The owner's calibrated A320/A321 raw IDLE and REV IDLE are
20165 and 14115 on both levers; CL, FLEX/MCT and TOGA retain their captured
45371, 55453 and 65535 gates. Physical detent contacts snap to the exact
anchor, adjacent ranges interpolate continuously, and negative travel remains
blocked unless the matching reverse handle is raised. At ToLiss startup the
loaded aircraft's own IDLE/CL/MCT ratios are read once and converted into the
signed `throttle_input` scale; the live A321 values were 0.3000, 0.6915 and
0.8412. Invalid/unavailable readings fall back to those captured values. No
Boeing constant or converter was edited. The existing one-SDL-owner queue,
delta write tolerance and read-current/cross-target safe pickup remain in the
same order.

**Guard:** `tools/test_toliss_throttle_calibration.py` is hardware- and
simulator-free. Its 46 checks pin every pre-existing Boeing raw/reverse
constant and representative Boeing outputs; reject any ToLiss reference to the
Boeing converter or calibration symbols; exercise all six detents on both
engines with deliberate ADC jitter; prove reverse-handle and
`revOnSameAxis` gating; prove engine 1 and engine 2 may carry different raw
calibrations; prove monotonic interpolation; and require simulator readback,
safe pickup, then write in that order. It also requires both raw engine axes to
reach Hardware Lab with `route=False` before the ToLiss dataref-availability
gate. Live acceptance remains: restart Studio with the ToLiss A321/A320 loaded,
move each lever separately through IDLE, CL, FLEX/MCT and TOGA, then test
reverse only after raising its handle.

**Follow-up symptom (owner):** after activating the new ToLiss calibration,
the two throttle sliders in Studio no longer moved even though the physical
levers still reached the aircraft.

**Follow-up diagnosis and fix:** the ToLiss-specific SDL reader correctly
replaces the simulator-independent preflight reader so only one owner opens
the WinCtrl. However, its queue consumer only dispatched the axis values to
`AirbusFBW/throttle_input`; it did not reproduce the preflight consumer's
read-only Hardware Lab observations. Consequently the hardware worked but the
Studio model stopped receiving `left_thrust` and `right_thrust`. The ToLiss
consumer now publishes both raw axes to Hardware Lab before its simulator
dataref guard. Routing is explicitly disabled, preventing duplicated aircraft
writes, and telemetry failure is isolated from the real throttle dispatch.

---

## BUG-26 - ToLiss CL/FLEX gates were wrong and reverse could remain latched at IDLE

**Symptom (owner):** Studio still showed the old Zibo-style throttle scale
after ToLiss loaded. TOGA and IDLE were correct in the aircraft, but physical
CL and FLEX/MCT did not land on their ToLiss detents. After using reverse and
returning to IDLE, ToLiss sometimes remained in IDLE REV until the lever was
pushed above IDLE and returned.

**Diagnosis:** ToLiss had been isolated from the Boeing converter, but the
WinCtrl side of its new table still used one fixed set of six raw counts.
Studio also drew six fixed percentages instead of the active ToLiss profile,
so it could neither reveal nor correct unit-specific gate positions. The live
reader emitted axis events only for analog deadband movement and reverser/
speedbrake contacts, not thrust-detent contacts 12..23. On the return from
reverse, a short REV-IDLE/IDLE contact overlap was resolved by whichever
anchor happened to be nearer the lagging analog count, allowing the negative
anchor to win despite the physical IDLE contact being present.

**Fix:** a bridge-owned, ToLiss-only probe now captures FULL REV, REV IDLE,
IDLE, CL, FLEX/MCT and TOGA in order from their real contacts, separately for
both engines. The validated twelve-gate payload is saved in the active ToLiss
hardware profile and Studio draws its rulers from that payload. Calibration
opens no second SDL/HID reader, suspends ToLiss thrust writes during the sweep,
and disarms readback/cross-target safe pickup at the start, so save, cancel, or
failure cannot apply the sweep's final lever position. Buttons 12..23 now
force a matching axis snapshot. If IDLE and REV IDLE
overlap, IDLE explicitly wins and outputs zero. Zibo/LevelUp constants,
conversion and saved profile files are unchanged.

**Guard:** `tools/test_toliss_throttle_calibration.py` now has 49 checks,
including the overlapping-contact IDLE case and the unchanged Boeing values.
`tools/test_toliss_throttle_probe.py` adds 35 checks for contact order,
independent engine progress, invalid-spacing recovery, one-shot completion,
family-marked profile persistence, dynamic Studio rulers, Live-mode action
reachability, forced gate snapshots, and suspended writes during capture.
Live acceptance remains: restart Studio with ToLiss parked, perform one full
six-gate sweep, verify CL/FLEX-MCT on both engines, then move from FULL REV
straight to IDLE and confirm IDLE REV clears immediately.

---

## BUG-27 - Guided ToLiss calibration saved physical gates but did not drive ToLiss's detents

**Symptom (owner):** the Studio probe successfully recorded the six positions
from each WinCtrl thrust lever, but that recording did not force the ToLiss
levers to follow the calibration. TOGA and IDLE worked while CL and FLEX/MCT
still missed their aircraft detents.

**Diagnosis:** the probe completed only the hardware side correctly. Its
runtime table converted ToLiss's `idleDetentRatio`, `clDetentRatio`, and
`mctDetentRatio` as though those numbers were positions in
`AirbusFBW/throttle_input`. The ToLiss simulation manual defines those ISCS
sliders as locations on an assigned joystick's raw 0..1 axis. MuslimSim
bypasses the native joystick/ISCS conversion and writes the final signed
cockpit-lever dataref directly, so the code was applying the conversion twice.
With the owner's live ISCS settings it sent approximately `0.56` at physical
CL and `0.77` at physical FLEX/MCT—both below ToLiss's direct detents. It also
derived REV IDLE from the WinCtrl travel, rather than using ToLiss's direct
`-0.10` position.

**Fix:** runtime profile `toliss-a320-a321-winctrl-v2` now maps the measured
physical gates directly to FULL REV `-1.00`, REV IDLE `-0.10`, IDLE `0.00`, CL
`0.70`, FLEX/MCT `0.875`, and TOGA `1.00`. These values are pinned from the
installed aircraft: `objects/knobs.obj` defines the signed lever geometry and
`fmod/a321_XP11.snd` defines CL inside `0.68..0.72`, FLEX inside `0.86..0.90`,
TOGA above `0.98`, IDLE below `0.02`, and reverse engagement below `-0.06`.
ISCS ratios remain diagnostic only; `revOnSameAxis` still gates reverse. The
saved version-1 raw-gate payload is intentionally reused, because the physical
measurements were valid. Studio now displays `raw -> direct input` at all six
anchors. Zibo and LevelUp were not edited.

**Guard:** `tools/test_toliss_throttle_calibration.py` now has 58 checks. It
pins the six canonical direct inputs and the aircraft's detent windows, proves
that changing valid ISCS raw-axis ratios cannot move CL/FLEX again, and retains
all Boeing-isolation, independent-engine, reverse, monotonic interpolation,
safe-pickup and Studio-telemetry guards. `tools/test_toliss_throttle_probe.py`
now has 37 checks and additionally pins the two-sided Studio ruler. Live
acceptance remains necessary after a Studio restart: both physical levers must
produce ToLiss IDLE, CL, FLX/MCT and TOGA at their matching gates.

---

## BUG-28 - Guided ToLiss ruler saved the contact edge instead of the resting detent

**Symptom (owner):** after calibration, ToLiss itself reached the correct IDLE,
CL, FLEX/MCT and TOGA states, but Studio's saved vertical lines stayed far from
the live lever markers. The screenshots showed resting values near REV IDLE
`14115`, IDLE `20165`, CL `45370`, FLEX/MCT `55452` and TOGA `65534`, while the
saved labels included CL near `43710` and FLEX/MCT near `53305`.

**Cause:** the physical contact closes before the lever finishes moving into
its mechanical notch. The probe committed the raw value on that leading-edge
report. Contact identity was correct, but its paired axis sample described the
entry point, not the final resting position. Because raw-axis reports are
delta-filtered, merely delaying the contact callback would also fail once the
lever stopped and no later queue event arrived.

**Fix:** a contact edge now begins a per-engine candidate. The same contact must
stay closed while the raw value remains below the 40-count motion threshold for
0.30 seconds; the final value is then committed. Contact release clears the
candidate. The main loop services an active probe from the latest snapshot so
the stable timer can expire without a second hardware reader. Studio reports
`HOLD <DETENT> STEADY`. The persisted schema is version 2; version-1
leading-edge samples fall back safely until the owner performs one replacement
sweep. The physical raw positions remain unit-specific, while the six direct
ToLiss targets remain fixed. Zibo and LevelUp paths are untouched.

**Guard:** `tools/test_toliss_throttle_probe.py` now has 53 checks. It proves
that a moving contact cannot save its first sample, the final settled count is
saved, the exact unit-specific values survive a profile save/reload, releasing
a contact cancels the dwell, old schemas are rejected, both engines remain
independent, and the periodic one-owner service plus Studio hold prompt remain
wired. The separate 58-check aircraft-side calibration guard continues to pin
direct ToLiss targets and Boeing isolation.

---

## BUG-29 - WinCtrl throttle instructions and controls were rendered as microtext

**Symptom (owner):** the ToLiss throttle faceplate contained too many labels
that were too small to read. The calibration instruction directly below the
WinCtrl title was hidden behind the throttle ruler, and several lower-panel
notes competed with the actual controls.

**Cause:** the status text and ruler shared the same top coordinate, the output
card overlapped the bottom of the ruler, every tick repeated both a raw value
and a fixed ToLiss target in six-point text, and explanatory paragraphs were
fitted into the remaining gaps. The trim selector also used escaped `\n`
characters instead of real line breaks.

**Fix:** the header, status and ruler now occupy separate bands. Each detent is
a readable two-line name/raw label, close REV IDLE and IDLE labels extend away
from each other, and visible faceplate text has an eight-point minimum. Output
tests have their own card; redundant microcopy was removed; the lower controls
were re-spaced; trim roles use real two-line labels; and the speedbrake no
longer stacks DOWN and ARM text. No control, calibration value or live route was
removed or changed.

**Guard:** `tools/test_winctrl_throttle_faceplate_layout.py` renders the ToLiss
faceplate on the authored 980x680 surface and performs 187 checks: all text is
at least eight points and inside the panel, the status ends before the ruler,
both engines have six separated gate labels, no literal newline escape is
visible, and removed microcopy stays absent. The 57-check probe guard retains
the calibration behavior and Studio ruler contract.

---

## BUG-30 - ToLiss received thrust but not the rest of the WinCtrl controls

**Symptom (owner):** the calibrated B930 thrust levers moved the ToLiss A320/
A321 correctly, but its engine masters, CRANK/NORM/IGN-START selector,
speedbrake, flaps, parking brake, trim rocker and red lever buttons did nothing.
The trim LCD did not follow pitch/rudder/aileron. The AGP clock worked but had
no ToLiss RADIO/NAV/CTRL workflow, and FCU values such as speed/heading `1` or
altitude `1` did not fill the physical windows as `001` and `00001`.

**Cause:** the isolated ToLiss loop consumed only the B930 axes event used by
the new thrust calibration. It did not dispatch the existing B930 button and
flap-axis events. The knob's push was not catalogued separately from its three
engine-mode detent contacts; the supplied USB capture proves it is its own bit.
The ToLiss AGP branch remained clock-only, and the shared FCU renderer used its
legacy space-padding policy for every aircraft.

**Fix:** the ToLiss profile now maps every listed contact to verified native
ToLiss datarefs/commands. `MODE.pcapng` pins the knob push to B930 button 24;
it cycles STAB/RUDDER/AILERON while contacts 7/8/9 retain real engine-mode
operation. The rocker repeats with the proven fine/held cadence and its one
physical LCD briefly shows the role then the live selected value. The red
Airbus lever buttons command A/THR disconnect, their actual aircraft function.
TERR ON ND short press still toggles terrain; a 0.65-second hold cycles CLOCK,
RADIO, NAV and CTRL. ToLiss alone requests zero-filled FCU windows.

All maintained controls are observation-only until the first complete raw-axis
baseline. Thrust, speedbrake and flaps require simulator-value pickup before
continuous writes; detent edges remain exact. Saved Studio bindings retain
precedence. `AirbusFBW/BatVolts` gates AGP, B930 and BA01 output; a cold start,
power loss and shutdown blank all new lights/backlights/windows, including
stale digits left by another aircraft. Zibo/LevelUp mappings and packet defaults
are unchanged.

**Guard:** `tools/test_toliss_winctrl_controls.py` pins the two literal captured
reports and their single-bit XOR, all native command names, pure speedbrake/flap
translations, the independent trim/page cycles, strict startup ordering,
surface pickup, power blackout, Hardware Lab visibility and absence of any
Laminar B738 command. `tools/test_fcu_efis_toliss.py` pins exact `001/001/00001`
bytes and the unchanged legacy packet. The existing throttle calibration/probe,
faceplate/layout, launch and known-regression checks remain part of acceptance.

**Current scope:** BUG-31 subsequently narrows the experimental ToLiss set to
PITCH/RUDDER and CLOCK/RADIO/CTRL, without reverting BUG-30's wiring, safety or
fixed-width FCU work.

---

## BUG-31 - ToLiss exposed non-Airbus modes and burst RST changes past the LCD

**Symptom (owner):** the ToLiss knob-push cycle still offered AILERON after
PITCH/RUDDER, the AGP long-press cycle still offered NAV, and a small RST turn
could appear to jump roughly five radio values instead of visibly advancing
one value at a time.

**Cause:** the first full control pass reused every experimentally available
trim/page role instead of stopping at the Airbus-specific set the owner wants.
RST input itself was not losing or multiplying detents: a fresh read of
`captures/knobs.pcapng` shows its signed counter changing one count at a time.
The bridge immediately issued every delta accumulated between host reads while
the physical LCD refreshed more slowly, so several valid native changes could
become one visible jump.

**Fix:** the ToLiss-only role tuple is now STAB/PITCH and RUDDER, and its page
tuple is CLOCK, RADIO and CTRL. ToLiss aileron and NAV1 datarefs, commands,
state and dispatch/render branches were removed. Zibo/LevelUp retain their
independent trim behavior and Zibo retains RADIO/CTRL/NAV. RADIO RST now expands
every captured delta into an ordered FIFO and drains exactly one native ToLiss
fine command every 0.06 seconds. A fast roll therefore stays fast and lossless
without a multi-command burst between display opportunities. A deliberate
page change clears only steps not yet issued, preventing stale tuning on the
next visit to RADIO.

**Guard:** the 69-check `tools/test_toliss_winctrl_controls.py` asserts the
two-role and three-page cycles, absence of ToLiss aileron/NAV paths, unchanged
Zibo page order, signed step expansion in both directions, FIFO pacing, startup
no-write ordering, output blackout and profile isolation. Studio's ToLiss AGP
view separately labels CLOCK/RADIO/CTRL and reports TERRAIN ON/OFF rather than
mislabeling the terrain switch as a NAV mode.

---

## BUG-32 - shared ToLiss datarefs could silently freeze one display consumer

**Symptom (owner):** the ToLiss flight displays were incomplete on BB36 and did
not have a persistent BB35 path. During aircraft changes or page selection one
panel/page could retain old content or appear black/frozen even though another
ToLiss page was still receiving data. Invalid IRS/GPS state also needed to look
like the real red/amber Airbus presentation rather than a partly valid display.

**Cause:** one ToLiss feed flattens the local PFD and ND dataref sets before
subscribing. Several local keys intentionally refer to the same physical
ToLiss ID, including captain heading and heading-validity. Its reverse lookup
was a one-to-one dictionary, so adding the later ND key overwrote the earlier
PFD key (or vice versa); each incoming value was delivered to only one consumer.
BB35 also had no persistent ToLiss HID/display owner, and the first-pass renderers
did not consume the aircraft's explicit captain validity/map/GPS state.

**Fix:** subscription IDs are deduplicated, but the reverse lookup now maps each
ID to every local key and fans one WebSocket update out to all of them. BB35 and
BB36 share that one feed while retaining independent HID handles, canvases,
page state and dirty caches. BB35 alternates PFD/ND; BB36 retains MCDU and all
Airbus graphical pages. Exact ToLiss validity datarefs drive PFD red zones and
ND `MAP NOT AVAIL` / `GPS PRIMARY LOST`; validity transitions invalidate and
repaint the affected content. Power loss, feed loss, shutdown and production
mirror-off all fail closed to black. The ToLiss MCDU uses a new isolated large
font slot whose prefix is the unchanged Zibo/LevelUp resource.

**Guard:** `tools/test_toliss_displays.py` asserts exact dataref names,
duplicate-ID fan-out, BB35 PFD/ND cycling, BB36 mirror-off/shutdown blackout,
all PFD/ND invalid flags, ARC/PLAN geometry behavior, font-prefix isolation and
native-report ceilings. It currently measures PFD 274 recovery / 180 moving and
ND 427 recovery / 356 turning reports. `bridge/final.py --test-pfp-pfd`, shared
telemetry, aircraft isolation, BB36 recovery and known-regression guards remain
part of acceptance. No hardware or simulator is opened by those tests.

---

## BUG-33 - subscribed ToLiss speed and ILS values were invisible or placeholders

**Symptom (owner):** the ToLiss PFD needed takeoff/flap speed cues, a speed-limit
zone that follows aircraft configuration, and real ILS diamonds/bars. The feed
already contained several related values, which made the feature set look more
complete in code than it was on BB35/BB36.

**Cause:** VR was subscribed but never drawn; V1 and V2 were not subscribed;
the takeoff-phase visibility output and S-speed were absent; LOC and G/S used
12 x 12 square placeholders. The upper speed limit was a solid red block rather
than the Airbus red/black VMax strip. There was no rendered-symbol assertion,
so a value could remain permanently invisible without failing a test.

**Fix:** V1, VR and V2 are independently mapped and gated by ToLiss
`show_to_speeds`. The tape draws cyan `1`, cyan ring and magenta triangle plus
ToLiss-driven F/S, green dot and amber VFE-next cues. ToLiss VMax drives a
red/black upper strip, while VLS/alpha values retain the amber/red low-speed
presentation. LOC and G/S now use a reserved native magenta diamond glyph.
The slot-3 ring/triangle glyphs keep the complete recovery frame below the
BB36 ceiling without runtime bitmap assets.

**Guard:** `tools/test_toliss_displays.py` asserts the exact V1/V2/S/visibility
datarefs and bridge translation, requires V1/VR/V2 to render and then disappear
when ToLiss clears the phase flag, requires F and S cues and two ILS diamonds,
proves the red/black VMax band moves with its input, validates the three native
glyphs and enforces the 290-report PFD ceiling. Current measurements are 274
full and 180 moving reports. `docs/TOLISS_DISPLAY_COVERAGE.md` prevents the
remaining Airbus display backlog from being described as implemented.

---

## BUG-34 - ToLiss PFD/ND geometry and EFIS bearing controls were incomplete

**Symptom (owner):** the ToLiss PFD still looked like a generic display instead
of the real Airbus/ToLiss shape. The loaded flight plan was incomplete on the
ND, physical EFIS VOR/ADF selectors did nothing, and neither the single nor the
double bearing pointer appeared when selected.

**Cause:** the first ToLiss display pass used generic rectangular regions and a
synthetic one-row FMA even though ToLiss publishes complete colour-layer FMA
strings. The ND drew an unclipped magenta route without consuming ToLiss's
solid/dashed state or radio-bearing outputs. The four physical three-position
selectors were deliberately discarded because the static command catalogue did
not identify their writable cockpit datarefs; installed ToLiss object animation
keys and live API values had not yet been traced.

**Fix:** the PFD now uses the manual/reference proportions: a three-row FMA,
stepped rounded attitude aperture, narrow inboard-edged speed/altitude tapes,
split invalid altitude blocks, tapered V/S scale and the low heading strip. Its
nine native ToLiss FMA text/colour layers are composed at their published
positions. ROSE NAV, ARC and PLAN render a range-clipped green plan and honor
`FlightPlanDashed`. The captain selectors now write absolute ADF/OFF/VOR values
to the four object-verified `ckpt/fcu/adf*` refs. Published VOR/NDB arrays, IDs,
validity and VOR DME drive the lower source fields plus a white NAV1 single
pointer and NAV2 double pointer; PLAN correctly suppresses relative bearing
needles.

**Guard:** `tools/test_fcu_efis_toliss.py` pins all twelve physical selector
positions and their exact absolute values. `tools/test_toliss_displays.py` pins
the source datarefs, manual-shaped PFD regions and failure silhouettes, native
FMA layers, green solid/dashed route in all three navigational modes, clipped
geometry, single/double pointers and PLAN suppression while retaining the HID
report ceilings (currently PFD 274 full / 180 moving and ND 427 full / 356
turning). Offline preview generation remains code-native and never adds runtime
PNG dependencies.

---

## BUG-35 - BB36 system pages were unguarded and F/CTL did not show the aircraft's controls

**Symptom (owner):** BB36 needed every screen available on BB35, the CDU and
the remaining Airbus ECAM pages. F/CTL had to receive live simulator telemetry
so moving the controls could be seen and tested, in a presentation resembling
the Airbus system display.

**Cause:** the initial BB36 route contained most lower-system names but no
end-to-end assertion proved that every page could be reached and drawn. CRUISE
was absent. F/CTL consumed only a representative spoiler pair and trim values,
explicitly omitted ailerons, and had no actual elevator or rudder output. The
static dataref catalogue did not expose that the installed ToLiss A320/A321
objects share normalized `anim/*` sources for all of those exterior surfaces.
Only F/CTL/CRUISE carried the permanent SD data line, and tightly adjoining
status cells made several labels and values read as one word.

**Fix:** BB36 now starts on CDU and cycles PFD, ND, all authored Airbus system
pages, CRUISE and STATUS. F/CTL draws a code-native Airbus wing/tail synoptic
driven by ten individual spoiler animations, both ailerons, both elevators and
the rudder, together with ToLiss trim/hydraulic values. The centered title and
TAT/SAT/GW/UTC strip are common to every system page and row values have a
visible cell gap. BB35 remains PFD/ND only. Existing power-loss, disconnect and
shutdown blackout paths were not changed.

**Guard:** `tools/test_toliss_displays.py` pins the exact A320/A321 animation
sources and translator shape; walks CDU through the complete BB36 page order;
retains the BB35 two-page order; requires F/CTL spoiler/aileron/elevator/rudder
features and the common Airbus header/footer on every system page; and caps
all ECAM recovery pages at 400 reports, F/CTL recovery at 250 and F/CTL motion
at 100. Current measurements are 299 maximum, with F/CTL 229 full / 79 moving.

---

## BUG-36 - ToLiss managed FCU windows went blank and its Mach value saturated at .99

**Symptom (owner):** after the EFIS VOR/ADF work, the physical BA01 no longer
showed SPEED or V/S in automatic/managed mode. Heading displayed a stale
selected number with its managed dot instead of `---` plus the dot, and MACH
showed `.99` while the ToLiss FCU was around `.77`. The owner's cockpit
reference required `MACH ---` plus its large dot, `HDG ---` plus its large dot,
`ALT 36000`, and five V/S dashes.

**Cause:** the selector change was adjacent but not causal. The display worker
converted `AirbusFBW/SPDdashed` and `AirbusFBW/VSdashed` into
`speed_visible=False` and `vertical_speed_visible=False`; the renderer correctly
interpreted those fields as electrical blanking and removed digits *and*
annunciators. No equivalent heading-dash presentation existed, so managed HDG
left the selected number visible. Separately,
`toliss_airbus/pfdoutputs/general/ap_speed_value` always returned an IAS
equivalent. A read-only live Web API snapshot while the owner was cruising
proved `ShowMachCapt=1`, `SPDmanaged=1`, `SPDdashed=1`, `HDGmanaged=1`,
`VSdashed=1`, PFD speed `257.7408`, and the unit-aware AP dial `0.7781`.
Feeding `257.7408` through the Mach formatter clipped it to the maximum `.99`.

**Fix:** three new Airbus-only presentation fields distinguish dashes from
true visibility. ToLiss sets SPD and V/S dashed state directly and derives HDG
dashes from its managed state. The renderer sends three dash glyphs while
retaining the SPD/MACH or HDG/TRK title and large managed dot; V/S/FPA combines
its separate sign stroke with four dash cells for the required five strokes.
Its positive-sign vertical segment is suppressed while dashed. The ToLiss FCU
and AGP CTRL speed source is now `sim/cockpit/autopilot/airspeed`, which follows
the dial's current knots/Mach unit. All new fields default false, preserving
selected values and byte-identical Zibo/legacy output. Power-off still zeros
the complete packet. The twelve VOR/ADF absolute mappings were not edited.

**Guard:** `tools/test_fcu_efis_toliss.py` now passes 108 checks and pins exact
BA01 byte slices for managed IAS and managed MACH, including both large dots,
HDG dashes and the five-dash V/S field. It requires the unit-aware speed source,
rejects the old PFD source in the FCU worker, retains selected MACH/TRK/FPA and
fixed-width numeric cases, verifies the exact legacy packet, all-zero power-off
packet, and all twelve VOR/ADF selector writes. The BA01 semantic, ToLiss
WinCtrl/AGP, aircraft-isolation, known-regression and launcher checks also pass.
Live acceptance remains: restart Studio, then compare managed and selected
SPD/MACH, HDG/TRK and V/S/FPA states against the running ToLiss cockpit.

---

## BUG-37 - ToLiss physical FCU altitude froze on an internal managed target

**Symptom (owner):** the BA01 altitude window remained at `22000` while the
altitude selected on the virtual ToLiss FCU changed.

**Cause:** the physical window and WinCtrl CTRL page read
`toliss_airbus/pfdoutputs/general/ap_alt_target_value`. That value can represent
an internal managed/PFD target rather than the FCU selector. A read-only live
Web API snapshot captured the divergence directly: the old source was
`22000.0`, while both `sim/cockpit/autopilot/altitude` and
`sim/cockpit2/autopilot/altitude_dial_ft` were `8000.0`. The physical encoder
write path was already working; only the display observer watched the wrong
state.

**Fix:** both ToLiss display consumers now read
`sim/cockpit2/autopilot/altitude_dial_ft`, the selected FCU dial. This replaces
one existing source without adding fixed-rate work. The altitude encoder,
100/1000 selector, five-digit formatting, managed dot, all VOR/ADF mappings,
Zibo/LevelUp paths, delta suppression and unpowered blackout are unchanged.

**Guard:** `tools/test_fcu_efis_toliss.py` now passes 110 checks. It requires
the selected-dial source in both the BA01 worker and WinCtrl CTRL map and
explicitly rejects the internal PFD target from the FCU setup. Existing exact
packet guards continue to cover selected/managed altitude formatting, legacy
bytes and all-zero power-off output. The BA01 semantic, ToLiss WinCtrl/AGP,
aircraft-isolation, known-regression and launcher checks pass. Live acceptance
remains: restart Studio and sweep the virtual or physical ALT selector through
several values while confirming the BA01 follows immediately.

---

## BUG-38 - BB35 could not show the ToLiss CDU or ECAM pages

**Symptom (owner):** BB35 still exposed only PFD and ND after CDU and the full
authored Airbus system-display deck became available on BB36.

**Cause:** this was an explicit routing restriction rather than missing
telemetry or a renderer failure. `TOLISS_BB35_DISPLAY_PAGE_ORDER` contained only
`pfd` and `nd`, its worker always sent the selected name to the graphical
secondary renderer, and only the BB36 router received direct ECAM32 page
requests. BB35 also loaded the PFD/ND-only font, which contains no isolated CDU
slot-2 glyphs.

**Fix:** BB35 now starts on CDU and cycles the same PFD, ND and complete ECAM
inventory as BB36. Its worker selects either live CDU text or the existing
graphical renderer, and ToLiss alone opens BB35 with the combined coded-display
font. ECAM32 page requests fan out to both independent routers. BB35 remains
display-only: it adds no key command worker, simulator write, subscription or
competing HID owner. Default font arguments preserve every existing
Zibo/LevelUp and non-ToLiss BB35 caller. The existing ToLiss electrical gate,
lost-feed blackout and shutdown blackout remain unchanged and use BB35's own
brightness authority.

**Guard:** `tools/test_toliss_displays.py` now walks BB35 from CDU through all
fifteen graphical pages and back, checks known/unknown direct selection,
executes the BB35 CDU worker and requires `display_id="BB35"`, proves ToLiss
BB35 requests the combined font, pins ECAM32 fan-out to both routers, and
verifies the combined font has more packets while retaining the entire original
font as its byte-identical prefix. Existing PFD, ND and ECAM output ceilings
remain 274/180, 427/356 and 299 reports, with F/CTL at 229/79.

---

## BUG-39 - BB35 displayed ToLiss CDU text but ignored its keypad

**Symptom (owner):** BB35 showed the CDU but none of its buttons operated it;
only pressing BB36 changed the mirrored CDU pages.

**Cause:** the previous display-deck fix retained an explicit display-only
input handler: it looked only for slash bit 69 and discarded all other BB35
keys. No BB35 command worker was started. Reusing the BB36 key numbers would
also have been wrong: BB35's digits start at 29, letters at 41, decimal is 38,
and its final row is SPACE/DEL/SLASH/CLR at 67/68/69/70.

**Fix:** the existing single BB35 HID reader now queues the captured keypad
edges to a ToLiss command worker, using an explicit 71-key Airbus map. The
worker reuses the BB36 command/gesture implementation through parameters whose
defaults preserve BB36 behavior. Each panel owns its own input and command
connection, and either may operate MCDU1 without the other present. Studio
records BB35 edges with route=False. Initial held keys cause no writes,
duplicate held reports cause no repeated presses, stale restart queues are
cleared, and held commands are released on shutdown. Missing command IDs and
transport failures appear in BB35 service status. The output/rendering/power
paths are unchanged. Current key-legend translations are in DEVICE_REFERENCE.md.

**Guard:** `tools/test_toliss_bb35_keys.py` sends synthetic raw HID reports
through the production BB35 reader and actual ToLiss command loop. It verifies
all 71 keys against the captured layout and command catalogue, exactly 142
press/release phases, single decimal/slash timeout and interrupted replay,
double-slash/triple-period local gestures, input while ECAM is shown, baseline
and held-key deduplication, held-command shutdown release, missing-command
status, unchanged BB36 default commands, and real BB35 start/stop with no
BB36 hardware. Command resolution is 69 unique lookups per connection with
no per-frame catalogue scan. Existing display/power and regression guards
remain required; live acceptance needs a Studio restart and physical typing.

---

## BUG-40 - Generic ECAM pages did not resemble the supplied Airbus SD references

**Symptom:** both coded displays had the page names but used generic gauges,
tables and a cramped single-row footer instead of the owner's twelve reference
synoptics. Lower ENGINE also resembled primary engine instrumentation rather
than the oil/fuel-used/vibration SD page.

**Fix (2026-09-09):** isolated native `toliss_ecam_synoptics.py` artwork for all
twelve references, dispatched through the existing shared renderer and power
gate. Three-column permanent data footer, surface tracks and hydraulic boxes,
pipes, valves, electrical buses, tank/fuselage/wheel diagrams. Unmapped physical
quantities remain XX; cleared master alerts no longer fabricate NORMAL STATUS.
Existing fonts, keypad/FCU owners, PFD/ND/CDU paths remain unchanged.

**Guard:** `tools/test_toliss_ecam_reference.py` checks all twelve reference
markers, footer, bounds, unknown/STATUS behaviour, all fifteen moving F/CTL
indications, WHEEL spoiler reuse, fuel-flow conversion and immutable line cache.
It is also called by `test_known_regressions.py`. Display budget/ownership/power,
keypad, FCU, recovery and aircraft-isolation suites pass. Native preview sheets
were visually inspected. Max SD full redraw 299 -> 266 reports; detailed F/CTL
229/79 -> 255/113 full/moving, bounded by 270/125. Actual panel and simulator
acceptance, missing dataref semantics and exact live parity remain open.

---

## Known, recorded, not yet fixed

- **TCA Boeing quadrant not confirmed connected across three diagnostic
  runs**, including one the owner annotated "this 1&2" (its normal-working
  switch position). `py bridge/final.py --control-port=0 --diagnose-controls`
  printed `TCA BOEING SDL: not found in the protected initial scan...` at
  startup in all three runs, with no subsequent `Joystick N: 'TCA Quadrant
  Boeing...'` line - unlike PU/WinCtrl/pedals, which always print that line
  immediately when connected. This has not yet demonstrated the reported bank
  3&4 symptom ("its not shwing any feedback if i move it 3&4"); it has only
  shown the more basic fact that Windows/SDL did not see the device at all
  during any of these three sessions. Next step: confirm the TCA quadrant's
  USB connection and power, re-run the diagnostic, and check for that
  `Joystick N:` line before re-attempting the bank-3&4-specific test.
- **`test_bridge_control_channel.py` fails whenever MuslimSim Studio is open**,
  and the failure says only "Bridge did not expose a loopback control port".
  The test starts its own `BridgeSupervisor`, whose bridge cannot come up while
  the running Studio already owns the devices and the control port. Nothing is
  broken; the suite simply cannot be trusted while the application is running.
  Close Studio before reading a suite result, or treat this one failure as
  noise. It cost a detour once already - it looked like a regression from an
  unrelated change.
- **Three offline tests fail on the untouched tree**, and did so before BUG-14
  was touched - confirmed by re-running them against the pre-change driver.
  `test_studio_practice_feedback_v3.py` never adds the project root to
  `sys.path`, so it dies on `ModuleNotFoundError: No module named 'muslimsim'`
  and has been testing nothing; `test_final_cockpit_state_v6.py` still requires
  the Studio header telemetry indicator that was deliberately removed when the
  owner asked for the flickering text to go; `test_display_stall_recovery.py`
  fails on "the supervisor must still record why the path failed". The first is
  a dead test, the second contradicts a decision already made, and the third is
  a real assertion nobody has read yet.
- **FSLabs' original 18 catalogue entries are corrupt.** All share the truncated
  target `ipc.control(66587` — the source workbook was split on the comma inside
  `ipc.control(66587, 10)` and the argument landed in the `protocol` column. The
  64 imported FSLabs entries are clean, so the family works regardless.
- **The `platform` block is ~74% of the status payload** and carries
  `telemetry.latest`, a third copy of the same physical inputs. The data model
  already has a per-record `sequence` and a `cursor`, so the fix is a delta
  protocol: Studio sends its last-seen cursor, the bridge replies with newer
  records only.
- **No MSFS power gate.** `AGENTS.md` rule 0.1 says every output goes dark when
  the aircraft is unpowered and that new devices inherit it. The X-Plane side
  reads `aircraft_powered`; the MSFS connector has no equivalent yet, and must
  have one before any transport is installed.
- **Bridge convergence loops have no attempt cap.** `irs_pending`,
  `wiper_pending`, `stage3_selector_pending`, `stage5_ign_pending` and
  `winctrl_stab_trim_readout_pending` retry at the step interval indefinitely if
  a target is unreachable, and their `except Exception: print(...)` paths do not
  clear the flag. Bounded in practice by `*_commands_ready` gates; left alone
  deliberately under rule 0.2.
## BUG-48 — ToLiss PFD used fat generic tapes and a false altitude readout

**Symptom (owner):** the PFD did not resemble the supplied A321 screen. Speed
and altitude tapes were too wide; altitude used one same-size five-digit value,
the scale wall and ticks were on the wrong side, and the selected-altitude mark
was not the cyan notched rectangle around the centred hammer.

**Cause:** BUG-34 established independent Airbus page ownership and source
validity but retained 78-pixel first-pass tape proportions. The altitude value
was rounded to 20 ft and painted as a single slot-3 string, so it could neither
show the smaller 00/20/40/60/80 drum nor move continuously between steps.

**Fix (2026-09-10):** traced the owner's `ALT.png`, `SALT.png`, `SPEED.png`,
`VS.png`, `compass.png`, `INFO.png` and full `PIC/BARO.png` references. Both
tapes are now 56 pixels wide. Altitude has one right-hand white wall, leftward
100-ft ticks, edge-clamped `>335`/`>325`-style 500-ft labels, a black centred
amber hammer, fixed live hundreds and a smaller slot-4 rolling 20-ft pair. The
cyan target box is live-selected-altitude geometry, not a fixed decoration.
Speed uses the narrow grey datum instead of the oversized white rectangle.
The heading strip is reference-height; the attitude presentation has the full
5-degree bilateral ladder, brighter reference palette and stepped Airbus
aircraft symbol. All values remain sourced from the existing ToLiss feed.

**Guard:** `tools/test_toliss_displays.py` fixes both tape widths, right scale
wall, hammer/target features, 335/325 labels, slot-4 80/00/20 drum, continuous
10-ft motion, 331 transition at 33,100 ft, ladder/reference features and bounded
native traffic. `tools/test_known_regressions.py` retains power, ownership,
FCU, ECAM, ND and aircraft-isolation coverage. Runtime PNGs were not introduced;
`PNG/toliss-display-preview/pfd-altitude-reference.png` is offline QA only.

---
