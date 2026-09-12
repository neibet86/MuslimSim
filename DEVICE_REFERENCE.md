# MuslimSim device reference and live-test guide

## 2026-09-12 - Owner flight experience and focused development needs

Updated README and the device achievements guide with the owner's repeated
DFW–KLAS flights in Zibo and ToLiss: smooth overall, with slow PFP3N/MCDU32
LCD updates during climbs. Recorded the slow ToLiss exact-image USB-C
experiment without asserting a measured hardware refresh ceiling. Requested
help with transport/render profiling, coded screen design and substantial
MOZA force-feedback tuning in both aircraft families. The owner reports
decoded captures available; existing AB6 protocol validation limits remain.

Documentation only; no code, mappings, device ownership or output changes.
Validation: updated document links and diff checks passed. The existing
regression suite passed in the preceding documentation publication; not
repeated for this owner-report wording update. No new live test performed.

## 2026-09-12 - Public device-by-device achievements guide

Added [DEVICE_ACHIEVEMENTS.md](docs/DEVICE_ACHIEVEMENTS.md), covering all 25
catalogue entries, separate BB51/BB61 PDC variants, display-family identities
and MOZA accessories. Each device has its purpose, implemented/captured work
and remaining limitations; community profile groundwork is distinguished
from completed runtime support. README links the guide prominently.

Recorded the owner's successful 3M PDC backlight check in both Practice and
Live. Retained the existing confirmed A210 presence and throttle feedback
results, and the stated Zibo, LevelUp, ToLiss and MSFS24 development status.
Documentation only: no device code, profiles, assignments or outputs changed.

## 2026-09-11 - 3M PDC backlight and public compatibility status

Owner-requested exception: verified 3M PDC BB51/BB52 backlights stay at 255
while the device owner runs in Practice or Live, including simulator-off,
unpowered aircraft and idle Practice. An opt-in driver parameter preserves
all other callers; 3N panels retain their existing requested brightness.
The same HID owner sends captured packets, suppresses unchanged writes, and
still writes zero on normal stop/shutdown. Inputs and assignments are unchanged.

README now records the owner's Zibo/LevelUp/ToLiss status and identifies MSFS24
as unstarted working integration needing help, despite existing scaffolding.
Added developer notes for the existing MCDU/PFP keypad page gestures.


## 2026-09-11 - Hide small page instructions except AGP

At the owner's request, hid explanatory faceplate captions and control-setup
instructions across Studio except WINCTRL 32 AGP Metal. AGP instructions and
its quick-reference guide remain unchanged. Retained control labels, live
values, connection/error statuses, input tags and click targets. No device
reader, saved assignment, simulator route or output-power behavior changed.


## 2026-09-11 - Independent controller inputs and MOZA presence

MOZA A210 presence now recognizes verified USB 346E:1001 and both A210/AY210
product names. The lifecycle checker previously contradicted the connected HID
reader, making Studio alternately show and hide the device.

The shared SDL owner now skips only PU-specific reads and baselines when the
overhead is absent. WINCTRL throttle, pedals and TCA Boeing inputs continue;
no second reader, fabricated PU positions, output path or saved mapping changes.
The existing throttle pickup gate, TCA banks and stationary startup rules remain.
No new output behavior; existing power-off and shutdown protections are unchanged.

Validation: actual reader exercised with fake SDL controllers, independent and
combined devices, both TCA banks, moving and stationary inputs. Live confirmation
requires reopening Studio to load the changed modules.


## 2026-09-12 - WINCTRL PDC display names

The requested 3M title is now WINCTRL 3M PDC, without the firmware L suffix.
PDC display titles use WINCTRL; raw USB strings, device keys, serials, role
assignments and all controls are preserved. The configured cockpit role stays
separate from the model title. Source-only naming change; no output behavior.

## 2026-09-11 - Full 3M BB51 map verified and installed

The owner's completed PDC_3M_BB51_GUIDED_20260911_215753.json verifies all
38 labelled steps with no ambiguous contacts or absent controls. BB51 now has
its own explicit input map selected before the connection baseline is decoded.
BB61's map is restored on a BB61 connection. The connected PID stays pinned
through presence checks, preventing a newly visible model from changing an
open panel's identity or backlight packet model.

Verified 3M buttons: FPV 1, MTRS 2, VSD 3, WXR 4, STA 5, WPT 6, ARPT 7,
DATA 8, POS 9, TERR 10, RST 17, CTR 18, TFC 19, STD 20. RANGE uses separate
relative decrease/increase contacts 21/22. VOR1 is 11/12/13; VOR2 14/15/16;
MINS modes 25/26; BARO units 27/28; MODE 29/30/31/32. MINS slow dec/rest/inc
34/35/36 and fast dec/inc 33/37. BARO slow dec/rest/inc 38/39/40 and fast
23/24. These numbers come from this BB51 capture, independently of BB52.

Studio now reads the actual relative RANGE events, replacing the temporary
map_range-position unwrapping. VSD and both RANGE directions are implemented,
clickable sources with normal optional reassignment. No new VSD capture is
needed. 3N keeps its 5..640 faceplate and no VSD. The legacy map_range catalog
entry remains so saved profiles still load; it is hidden on the BB51 faceplate.

With Studio confirmed closed, four old Default-profile source corrections were
changed to their newly verified same-name sources: baro_std, ctr, mins_rst, tfc.
An exhaustive document comparison proves every simulator binding and every
other field unchanged. Other profile files are byte-for-byte unchanged. The
original profile and a change record are backed up with the code.

No new HID owner, simulator route, output command, hardware power behavior or
startup momentary replay was introduced. Existing captain/FO dispatch remains
in place; Practice still routes no input to the simulator. Verified BB51 OFF is
the unchanged 3M packet. Other protected device code was not edited.

Validation: all 38 recorded controls replay through the real decoder: 1,395
reports / 113 events, no unrelated control presses, fast repeat verified.
1,200 before/after reports each on BB61 and BB52 produce identical events and
mirrors (11,943 / 13,107 events), and all 256 brightness packets are identical.
Measured offline decode totals: BB61 13.36 -> 12.32 ms; BB52 12.13 -> 13.38 ms.
Model-map selection happens once per connection; no per-report scan was added.
Real Tk faceplates pass (BB51 121, BB62 140, BB52 119 items) with working click
regions and moving needles. Full live-cockpit acceptance needs Studio reopened.
Backup: Backup/bb51_verified_remap_20260911_223853.

## 2026-09-11 - Full 3M recapture prepared; mapping application pending

Owner authorised recapturing every physical BB51 3M control while preserving
saved simulator assignments. Added tools/capture_pdc_3m.py, a 38-step window
covering all buttons (including VSD), selector positions, endless RANGE and
slow/fast MINS/BARO directions. It saves labelled raw evidence under captures.
The authenticated device_diagnostics endpoint reads only the selected existing
owner's in-memory snapshot, avoiding cached global status polling and competing
HID readers. Recording requires Practice, BB51 identity and a consistent serial;
no hardware output, simulator write or profile change is issued by the tool.
The active Studio must restart once to expose the read-only endpoint.

The reviewer rejects missing steps, ambiguous contacts, duplicate identities
and mixed serials. It produces a proposal only; no mapping is applied until the
owner's complete capture is verified. Existing BB61/BB52/BB62 behavior remains
unchanged. This is preparation, not a completed 3M remap. Real UI render and
mandatory known regressions passed, including targeted read isolation,
authentication, Practice/identity guards and all existing protected features.
Capture-time sampling is limited to the selected PDC for 11 seconds per step;
there is no background idle polling. No new output path: existing power-off
rules and driver ownership are unchanged.

## 2026-09-11 - VSD belongs on the 3M faceplate

Owner correction supersedes the earlier VSD placement: show VSD on 3M BB51
and BB52, not 3N BB61/BB62. Keep 3M endless RANGE and 3N 5..640 unchanged.
BB51 VSD is clickable and supports the existing optional source assignment;
its current catalog has no verified VSD contact, so no bit is guessed. BB52's
existing VSD source is unchanged. Saved assignments, including any earlier
BB62 learned source, are not deleted. No driver, output or power-path change.

## 2026-09-11 - Correct 3M versus 3N RANGE behavior

Owner correction: the 3M PDC RANGE is endless; the 3N remains the 5..640
selector on the shared faceplate. BB51 now uses the endless drawing and
unwraps its existing map_range positions across 7/0 in both directions.
The initial snapshot does not invent rotation. BB62 and BB61 keep the bounded
5..640 drawing; BB52 keeps its existing encoder. No captured input mapping,
saved assignment, simulator dispatch, output packet or power behavior changes.
No new output path or reader. Added regression checks cover four clockwise
and five counterclockwise revolutions, idle/unknown input, model-specific
labels and the original map_range click target. Live knob acceptance after
Studio restart remains required.

## PDC shared Studio faceplate - 2026-09-11

Current USB enumeration: BB51 = WINWING 3M PDC L, owned by pdc_bb61_left;
BB62 = WINWING 3N PDC R, owned by pdc_bb62. The existing keys are compatibility
identities and have not been renamed. Titles use the detected product and the
saved cockpit side. BB62 now shares the 3M flat layout, with VSD added; the
existing BB52 page retains its continuous RANGE encoder and captured VSD.

BB62's existing per-position MINS/BARO/VOR/MODE/RANGE contacts are adapted only
for drawing and clickable selection. VSD, CTR and RANGE 640 have no confirmed
named source in the current BB62 input map: select their faceplate location and
use Assign hardware button in Live to capture an existing raw contact. Never
invent a bit index or erase other assignments. Captured controls keep their
current default sources unless the owner explicitly reassigns them.

Physical PDC input and canvas feedback work without simulator connectivity in
both Live and Practice. MINS/BARO direction contacts animate the inner dial;
fast taps remain visible after release. No firmware packets, output brightness,
HID ownership, role mapping, startup dispatch or shutdown behavior changed.
Verification: test_pdc_shared_faceplate.py (optional --render for real Tk),
existing PDC protocol/output suites and mandatory regressions. The running
bridge received the owner's BARO/WXR check; close/reopen Studio for the new
canvas and check the physical visual response once loaded.

## Physical input feedback without a simulator - 2026-09-11

Attached controls remain available for physical feedback in Live and for virtual
and physical testing in Practice with no simulator running. Generic service states
such as offline/waiting do not mean USB unplugged. Slow/failed discovery keeps the
last confirmed inventory; a successful scan or explicit USB absence updates it.
This supersedes automatic cache-age removal. Live lamps/screens still obey aircraft
power rules; input feedback does not require aircraft power or simulator connection.

## Connected-device list - 2026-09-11

The sidebar shows currently detected hardware. Unplugging removes its row after the
existing presence/status refresh; reconnecting restores its stable product key and
saved assignments. Registration alone does not prove connection. A USB-present unit
may remain listed while its reader reconnects. Physical power loss can remove a row
when it removes USB presence or is reported as disconnected; USB alone cannot prove
whether an external supply is switched off. No aircraft-power state is used here.
Unknown devices retain their reported product name rather than a WinCtrl label.
Logitech headset/audio interfaces are excluded from flight-control discovery.

## Optional reassignment of existing controls - 2026-09-11

In Live, select an input location on any device and click Re-assign hardware
button, then press or move its replacement physical control on the same device.
Existing assignments remain until that explicit action. Only the selected
visual-to-source relation is replaced; other mappings, simulator bindings,
calibration and TCA bank keys remain unchanged. Choose simulator function to
edit the replacement source's function separately. MOZA calibration widgets,
outputs and display-only elements are not physical input assignment targets.
Practice does not save assignments. Hardware must already publish a verified
input through the existing bridge; this feature adds no hardware driver.

### PFP3N teardown evidence and native-design archive, 2026-09-10

Owner photos preserved in design_archives/native_airbus_20260910_211335.
Processor appears marked STM32F429IGT6; panel T056VG0001NNA01. Photos alone
do not establish USB negotiated speed, ribbon pinout, display timing or a
compatible HDMI controller. ST processor LCD-TFT/DMA2D capabilities suggest
that the glass/graphics hardware should not be blamed solely from slow HID
rectangle uploads; actual firmware transfer capability remains unverified.
No firmware flashing, rewiring, runtime rollback or display changes performed.

### 2026-09-10 PFD newest-delta scheduling (restart Studio only)

PFD now replaces unsent outdated delta rectangles and services both side bands
alongside the centre. Initial load, native SD/ND, colours and geometry unchanged.
Test QNH/altitude response and speed changes independently, then together during
the owner's normal simulator operation. Verify no retained old digit fragments,
both tapes progress, power loss stays dark, and stationary display emits no
new drawing reports. Plugin still captures at 2Hz: do not claim smooth flight
refresh from this scheduler alone. Physical comparison remains pending.

### 2026-09-10 Slow native raster transfer diagnostic revision

Restart Studio only to load BUG-57 corrections; leave X-Plane/plugin running.
Select PFD once and leave it until complete, then ND, first on each panel and
then together. Record physical load time separately from host progress.
New status fields: image_usb_reports (cumulative image-page reports),
image_usb_write_ms (cumulative time inside HID writes),
image_usb_max_write_ms (worst write), image_batch_ms (last committed burst).
Capture/recovery counters are not proof of device-rendered pixels.

Do not remove proven BB36 refresh pacing to chase USB 3 speeds. This path uses
56-byte command payloads, not a USB video/framebuffer transport. Microsoft
documents that endpoint polling depends on device speed, polling interval and
controller: https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbspec/ns-usbspec-_usb_endpoint_descriptor
Actual descriptor speed/poll interval of these units is not yet measured here.
Last captured native PFD/ND full jobs needed 5953/9361 reports in the emulator.
Brightness duplication is removed, and successful writes renew capture demand;
neither change eliminates the underlying large full-image command count.

### 2026-09-10 Native PFD/ND candidate - installed, live test pending

Installed after confirmed closure at 20:22 local. Installed SHA256:
D773E1E33988E40558FC7EA969C1E9196445840BF29966AEBFD94F43D55B6123.
Rollback DLL: Backup/native_flight_install_20260910_202214/win.xpl.
Offline regression suite passed; restart and physical checks below remain.

Candidate: tools/XTextureExtractor-trial/win-native-flight.xpl. Do not overwrite
the loaded DLL. With X-Plane and Studio closed, back up the installed isolated
trial win.xpl, then deploy this candidate into that same plugin's 64 folder.
Do not replace ToLiss or any other plugin. Retain its existing crop/config and
extraction window. The new channels depend on an active extraction draw callback.

Restart X-Plane and Studio, then select PFD/ND with the existing LCD gestures.
No aircraft display-page command is necessary for those two atlas crops.
Both panels show captain-side imagery. BB35 viewport is 640x480; BB36 keeps its
existing raw fit at x0,y10,w640,h440. The first image is hidden until committed;
subsequent transfers are exact deltas in bounded refreshed batches. Test each
panel independently and then different pages together. Native EWD capture is
prepared, but EWD has no new page-selector binding in this revision.

Accept only after comparing actual source and BOTH physical LCDs: edge fit,
moving tapes/horizon/route, page transitions, no old-page flashes, power-off,
self-test/recovery, source loss and X-Plane frame time. Source capture is capped
at 2 Hz TOTAL across flight channels (in addition to SD's 2 Hz); physical update
rate can be substantially lower. Status image_sequence/image_pending_rects and
image_commits are host-side progress, NOT device acknowledgement or FPS.

Rollback: with both programs closed, restore the saved previous trial DLL.
Absent new-flight producer leaves working vector PFD/ND available. For a
running process that still holds the old shared mapping, restart Studio too.
SD v1 and keypad/control mappings are unchanged by the new producer.

### 2026-09-10 Native twelve-page ECAM deck/full-width acceptance

Restart Studio only; retain the existing plugin/extractor window. Use ECAM32
buttons to select the same native page and both LCD routes. Verified native
IDs: ENG0 BLEED1 PRESS2 ELEC3 HYD4 FUEL5 APU6 COND7 DOOR8 WHEEL9 FCTL10
STATUS12. A local LCD gesture selecting a page does not force the aircraft SD;
when they disagree, the LCD waits dark until that native page is selected.
This deliberately avoids stale or mislabelled page content. CRUISE remains
on its old renderer; no automatic-CRUISE page ID is enabled by inference.

New first-load behavior: LCD dark while bounded refreshed chunks build the
image, then reveal the complete image. Subsequent deltas retain illumination.
Power off still overrides loading. Native unavailable readings stay unavailable.
Viewport: BB35 full640x480, BB36 full640 width and440 height at y10 for bezel.
This fills the requested rectangular area rather than preserving square aspect.
Verify title/footer clearance, first-load duration, live number/valve changes
and page-away/back on both units. No claims of faster total hardware throughput.
The requested native PFD/ND/EWD conversion is NOT yet installed or validated.


### 2026-09-10 Image transfer: physical failure, not accepted

PFP3N old page and MCDU32 white square patterns were reported after startup.
Do not interpret running/live or frame counters as proof of correct LCD output.
The next Studio-only restart loads bounded refreshed batches and exposes
image_active/pending_rects/commits/sequence fields in device status. These
measure host-side progress only. A photo and comparison with the native SD
are needed before accepting the transfer. No plugin restart required.


### 2026-09-10 BLEED old/new flicker and blank-BB36 follow-up

Restart Studio only to load the mid-copy reader fix and explicit BB36 startup
error status. Leave X-Plane and its extraction window open. Select BLEED and
verify the old numeric page no longer reappears. Copy collisions retain a
complete same-page frame only within its original two-second expiry; power
loss still blacks the LCD immediately through its original power gate.
If BB36 stays blank, inspect `devices.mcdu32_bb36.error` in the bridge status
instead of guessing a USB reset. No automatic reset was added.


### 2026-09-10 BLEED stream installation completed

The staged stream DLL is now installed (SHA256 `AD5C3412...D62C7F55`); the
earlier "installation pending" notes below describe its pre-install stage.
Open X-Plane and load the ToLiss A321, then open Studio. Select BLEED on the
aircraft and both displays, keeping an extractor window visible. Allow the
initial multi-batch image to finish. Physical correctness, stale-source and
power-off tests plus live capture/frame-time measurements remain pending.


### 2026-09-10 Staged BLEED image connection on BB35 and BB36

After installing the staged local plugin while X-Plane is CLOSED and restarting
Studio, use ECAM32 BLEED to select the native SD and both physical pages.
Keep a trial extraction window visible (its draw callback drives capture).
The native BLEED must remain selected: this does not force cockpit pages or
provide twelve independent textures. SDPage=1 is the only enabled image page.
Native XX remains XX when the aircraft itself declares a value unavailable.

Pixels are centred at (96,8), 448x448, on the 640x480 native LCD surface;
this preserves a square SD rather than stretching it. Validate bezel visibility.
Full recovery uses multiple chunks and may take seconds. Verify APU bleed
off/on, power-off black, self-test, page-away/back, Studio restart and stale
producer recovery on BOTH panels. Plugin absent/stale/wrong-page falls back
to the existing telemetry page, which can still have XX. No numeric substitution.
Measure live `capture_us` in the shared header plus before/after frame time
and hardware delivery latency. Current plugin installation is still the earlier
window-only trial until its DLL is replaced safely; no need to reset HID devices.


### 2026-09-10 ToLiss APU-on BLEED acceptance (BUG-53)

After a safe Studio restart, select BLEED with the mapped ECAM32 BLEED key so
the real ToLiss SD and both BB35/BB36 pages are selected together. With APU
AVAIL, APU BLEED open, X BLEED open, both packs open and engines stopped, verify:

- 5 °C over 210 °C on both pack stacks, 37/36 PSI and 190 °C from the aircraft;
- a full green horizontal manifold, horizontal green X valve, vertical green
  APU valve/branch, and the white GND marker;
- both engine numbers, IP valves and isolated HP branches amber, with no IP-HP
  connection;
- moving C-H and LO-HI needles follow live `PackTemp`/`PackFlow`, not the printed
  numbers.

The three engineering-temperature rows are native SD text and are published
only while ToLiss BLEED is selected. If that native page is not selected or the
row is unavailable, XX is correct; a cabin/TAT/photo fallback is forbidden.
The software on disk was verified offline only and has not been injected into
the running flight. Restart only when safely parked.

### 2026-09-10 ToLiss GPU lamp and PU starter acceptance (BUG-52)

Perform this only after landing and a safe Studio restart. Leave both PU engine
selectors at OFF during startup so the observation-only baseline is unambiguous.

- Attach the ToLiss GPU without selecting EXT PWR: PU `GRD PWR AVAIL` must light.
  Remove the GPU: it must extinguish. No neighbouring P7 lamp may change merely
  from this mapping. AVAIL is the only lamp permitted before a DC bus connects;
  every other PU output remains dark, and all output fails dark if ToLiss
  telemetry becomes unavailable.
- Move one PU engine selector to GRD. ToLiss ENG MODE must move to IGN/START, but
  that engine must not receive fuel until its matching WinCtrl master/fuel lever
  is moved ON. The physical selector must remain at GRD during crank.
- The selector may return only after the matching master is ON, FADEC is active,
  and N1/N2 have stabilized at idle for one second. At return, ToLiss ENG MODE
  must be NORM and the matching master must remain ON. A failed physical release
  gets only one separated retry; it must never become a continuously held coil.
- If both selectors are deliberately at GRD, the common P1 actuator must wait
  until both engines meet the full completion gate. CONT and FLT request shared
  continuous IGN/START and do not auto-return. Moving all active PU selectors to
  OFF returns NORM without shutting an engine down.
- While a PU GRD/CONT/FLT cycle owns ENG MODE, WinCtrl's separate ENG MODE edges
  are ignored; they work again as soon as the PU lease ends. The PU L/BOTH/R
  igniter-source selector remains Studio-observable only because Airbus FADEC,
  not the pilot, chooses the individual igniter.

Safe offline checks:

```powershell
cd D:\MuslimSim
py .\tools\test_toliss_pu_overhead.py
py .\bridge\final.py --test-starter-retract
py .\bridge\final.py --test-pu-lights
```

### 2026-09-10 ToLiss PU overhead acceptance (BUG-51)

After landing and making a safe Studio restart, check the PU against the native
ToLiss overhead. Startup is observation-only: no maintained physical switch may
move the aircraft until that physical control is changed after the baseline.

- PU IRS 1 must move ToLiss IR 1 only. PU IRS 2 must move IR 2 and IR 3
  together. PU ALIGN and NAV both select Airbus NAV; ATT selects ATT.
- The single PU wiper selector moves both Airbus wipers. The six fuel switches,
  FAC pair, window/probe bank, anti-ice, green/blue/yellow hydraulic pumps,
  batteries, generators, exterior lights, signs, packs/X BLEED/bleeds and
  overhead brightness must follow only their documented Airbus counterparts.
  Landing lights must reach the requested endpoint even if ToLiss was left in
  the middle detent; TAXI ON must select Airbus TAXI, never T.O.
  `--no-agp-display` must not disable these inputs.
- Move APU OFF -> ON -> START. The native MASTER must turn on, START must be
  requested once, and releasing the spring selector to ON must not issue a
  START-OFF command. The physical EGT needle must rise with the real ToLiss EGT
  and settle at mark 4 exactly when the native APU button shows AVAIL.
- Removing every ToLiss DC-bus supply must darken the PU even while the battery
  terminals retain charge. A final COM5 blackout/close occurs only after its
  sole writer exits. The Boeing FLT ALT and LAND ALT windows remain native
  dashes in the A321 because landing elevation is automatic/FMGS-controlled.
  BUG-52 now gives the two Boeing engine-start rotaries a guarded, leased Airbus
  ENG MODE path and stable-idle physical return. The separate L/BOTH/R igniter
  selector remains visible to Studio because Airbus FADEC owns igniter choice.

Safe offline check:

```powershell
cd D:\MuslimSim
py .\tools\test_toliss_pu_overhead.py
```

### 2026-09-10 full ND route acceptance (BUG-47)

After a safe Studio restart, select ROSE NAV, ARC and PLAN on BB35 and BB36.
The current ToLiss plan must continue past the active waypoint through every
visible expanded fix. For the live KLAS-KDFW proof, `TXO` was active at index 7
of 33 and the route continued through `TURKI`, `GANJA`, `KWANA` and the arrival.
The line must stop across the blank after `MANUAL` and resume at `ICKEL`; it
must not bridge that discontinuity. Change or insert a flight-plan leg and
confirm both displays adopt it when ToLiss next updates its automatic situation
save. Aircraft power-off still blacks both displays through the unchanged
router power gate.

### 2026-09-10 ND active-route acceptance (BUG-46)

After a safe Studio restart, select ROSE NAV, ARC and PLAN on BB35 and BB36.
The green current leg must point toward the live ToLiss WPT ID and update with
WPT course/distance; `FlightPlanDashed` must change it to dashed when ToLiss
requests that style. The installed A321 does not export full route-coordinate
arrays through public datarefs; BUG-47 now supplies the expanded plan from
ToLiss's own read-only autosave. The course/distance leg remains the safe
fallback while that file is missing, stale against the active WPT, or
structurally incompatible.

### 2026-09-10 working-system acceptance (BUG-45)

With both engines running, compare BB35/BB36 to native SD: approximately 51 PSI
manifolds should make the BLEED supply pipes/circles green; 3000 PSI should make
the HYD fire-valve circles green and vertical; all full wing-tank pump boxes
should be green/vertical with no stale LO. ENGINE and ELEC should no longer be
mostly XX. Values are live and will differ from this recorded state. Oil-quart,
vibration, generator load/frequency and IDG-temperature conversions remain
provisional and require comparisons through idle, takeoff and flight.

### 2026-09-09 provisional live ECAM telemetry acceptance (BUG-44)

After a safe Studio restart, verify both BB35 and BB36 against the native SD.
That old snapshot contains approximately 50 psia raw BLEED/APU supply (about
36 PSI gauge after BUG-53), 233 PSI
on six WHEEL positions, 38 °C wing fuel, SYS2, 1991 PSI cockpit oxygen, live
75,246 kg gross weight and NORMAL STATUS; these are recorded simulator values,
not hard-coded expectations, so they must change with the aircraft. Exercise
battery/GPU/APU/engine/flight states and verify every transition. Treat WHEEL
array order, PRESS SYS encoding, duplicated one-bottle oxygen indication and
bus-derived ELEC voltage as provisional until native-display comparisons pass.

### 2026-09-09 ELEC telemetry acceptance (BUG-43)

After a safe Studio restart, both BB35/BB36 ELEC pages should show live BAT 1/2
voltage and powered/failed colours for AC 1/2/ESS and DC 1/2/BAT/ESS. Engine
generator arrows, APU/external source and AC tie follow ToLiss connection
bitfields. Compare those states with the native SD under battery, external,
APU, each engine and abnormal configurations. Amps, loads, source V/HZ, TR and
IDG temperatures remain XX until a verified current ToLiss source is found.
Do not accept generic X-Plane electrical values or photographed numbers.

### 2026-09-09 WHEEL/BLEED detail acceptance (BUG-42)

Both displays share the corrected uppercase W, gear triangles, centre WHEEL
legends and four-arc BLEED/closed-branch artwork. Do not restart Studio while
flying to load it. The running read-only watchdog does not load display code
or drive any aircraft control. XBleedInd remains a provisional centre-valve
mapping; compare native horizontal/vertical indications during normal safe
operation before accepting a permanent rule. See `docs/TOLISS_BLEED_WATCHDOG.md`.
Braking labels use a limited hydraulic-supply model, not a complete verified
ToLiss failure map. Unknown pressure values must remain XX, not photo numbers.

### 2026-09-09 ECAM telemetry acceptance (BUG-41)

Read `docs/TOLISS_ECAM_TELEMETRY_AUDIT.md` before claiming exact live parity.
Both screens now consume measured cabin temperatures, audited A321 tank
positions and real DU self-test/brightness. Unknown/no AC/disconnected means
BLACK/OFF, not a retained frame. The current source changes have not been
loaded into the owner's running Studio session. Restart only when safely
parked, then supervise battery/GPU/APU/engine and per-DU supply comparisons.
Unmapped boxes and variant/abnormal states remain explicitly incomplete.

### 2026-09-09 ECAM reference-layout acceptance (BUG-40)

Both BB35 and BB36 now use `toliss_ecam_synoptics.py` for the twelve supplied
lower-ECAM reference pages. Existing page selection, CDU typing and power-off
behaviour are unchanged. Restart Studio only when safe, then select each ECAM
page independently on each display and compare against `PIC/`. Verify F/CTL
ailerons, elevators, rudder and individual spoilers move with aircraft outputs,
not merely joystick input; WHEEL uses the same spoiler telemetry. Check
unpowered/disconnected screens still go black. Do not accept the offline
sample numbers as evidence that oxygen/tire pressures, oil quarts, ISA, fuel
used or full STATUS content are available live: those mappings remain open.
See `docs/TOLISS_DISPLAY_COVERAGE.md` for limitations and `PNG/toliss-ecam-reference/`
for the native-font review images. No hardware was opened by these tests.

Last updated: 2026-09-09 - ToLiss now drives its full coded-display deck on
both BB35 and BB36: CDU, manual-shaped PFD/ND, and every authored lower-ECAM
page including live F/CTL. Native FMA, speed/ILS and VOR/ADF behavior and
strict power blackout remain isolated from Zibo/LevelUp.
Both ToLiss keypads now operate the mirrored captain CDU independently.

## Start and check

Normal source-tree launch from the canonical project requires no PU COM flag:

```powershell
cd D:\MuslimSim
py .\launch.py --with-pfd
```

The end-user target is the packaged `MuslimSim.exe`; its Python hardware
dependencies are bundled and it does not require pip/MobiFlight/SPAD.next or a
manufacturer cockpit application. `--port COMx` remains a diagnostic override,
not normal configuration.

Safe no-hardware check:

```powershell
cd D:\MuslimSim
py .\launch.py --check
```

## Portable identity rule

Supported hardware is matched as a product, not as the particular unit that
happened to be captured. MuslimSim does not require a saved serial number, COM
number, HID path or SDL index. If a D201, D203, BB35, BB36, PAP3, PDC, AGP or
other registered product is replaced by another unit of the same model, the
replacement receives the same device key/profile.

HOWALT D201/D203 are not distinguishable by their shared WCH VID/PID alone, so
their existing firmware identity probe remains mandatory. PU now resolves its
current COM locator from the supported `3561:8561` product identity/product
strings and resolves again on reconnect. A tie between two equally valid
serial copies is refused rather than guessed.

## Hardware map

| Hardware | Current role | Important safety rule | Offline check |
| --- | --- | --- | --- |
| PU Overhead (PU Korea) | Auto-discovered USB serial displays/output plus aircraft-specific switches, P7 lamps, brightness and APU EGT; ToLiss includes the safe Airbus counterpart map, native APU EGT/N/AVAIL gauge, GPU AVAIL lamp and guarded engine-start auto-return. **Has no hardware off detent** | Startup maintained positions are observation-only; one SDL reader and one COM5 writer; P1 is common/bounded and outputs go dark without aircraft power | `tools/test_toliss_pu_overhead.py`, `--test-pu-lights`, `--test-starter-retract` |
| WinCtrl throttle | Aircraft-specific thrust plus speedbrake, flaps, engine masters/mode, parking brake and trim; Zibo/LevelUp keep their established behavior, ToLiss cycles pitch/rudder only | Thrust is calibrated per unit/profile; every maintained startup contact is observation-only and continuous axes require pickup | `--test-winctrl-throttle`, `tools/test_toliss_winctrl_controls.py` |
| WinCtrl Orion pedals | Rudder and left/right toe brakes | Must pass through current simulator value before control takes over | `--test-pedals` |
| WinCtrl AGP | Gear/autobrake/clock panel; ToLiss TERR hold adds RADIO/CTRL | AGP stays separate from PFP and PU serial output; all output follows aircraft power | `--test-agp-display`, `tools/test_toliss_winctrl_controls.py` |
| WinCtrl PFP/MCDU | Aircraft-specific coded displays and CDU keypads; ToLiss CDU, PFD, ND and complete authored ECAM deck on BB35 and BB36 | One HID reader per panel; startup baseline sends no keys; display output requires live aircraft power | `--test-pfp-pfd`, `tools/test_toliss_displays.py`, `tools/test_toliss_bb35_keys.py` |
| WINCTRL 32 FCU + EFIS L/R (`4098:BA01`) | Zibo or ToLiss FCU/EFIS controls, value windows, backlight and integral lamps | Native report may be 41 bytes; only the confirmed first 12 payload bytes are controls; every output is dark without aircraft power | `tools/test_fcu_efis_toliss.py` |
| WinCtrl 3N PDC / EFIS (`4098:BB62`) | CAPT EFIS buttons, selectors, MINS, and BARO | First report is a no-write baseline | `tools/test_pdc_bb62.py` |
| WINCTRL 32 ECAM (`4098:BB70`) | A320 ECAM page/alert buttons after physical-name capture | Close Studio before capture; raw contacts have no Airbus name until measured | `tools/test_ecam32_button_capture.py` |
| Thrustmaster TCA Boeing (`044F:040A/040B`) | Three slides, handle contacts, five side buttons, select knob, continuous encoder | Bank is fixed at USB enumeration; Practice shows both banks and uses continuous raw drag values | `tools/test_tca_boeing_practice.py` |

### ToLiss BB35 / BB36 display controls

- BB35 starts on CDU. Double-SLASH advances through PFD, ND and every ECAM
  page in the hardware map above; after STATUS it returns to CDU.
- BB36 starts on CDU. Double-SLASH advances through PFD, ND and every ECAM
  page in the hardware map above; after STATUS it returns to PFD.
- Triple-PERIOD toggles directly between CDU and PFD on either panel.
- Both keypads operate ToLiss MCDU1, including when their local display shows
  PFD, ND or ECAM. BB35 works with BB36 absent. Since both mirror MCDU1, a CDU
  page change or entry made from either keypad appears on both CDU screens.
- A captured/bound ECAM32 page button requests its matching system page on
  both BB35 and BB36.
  CRUISE is an automatic/cycled page because the physical panel has no CRUISE
  selection key.
- F/CTL reads the actual ToLiss exterior-animation outputs for spoilers 1-10,
  both ailerons, both elevators and rudder. Moving the controls in the simulator
  must therefore move the matching physical-screen symbols. Unknown telemetry
  is amber rather than being replaced by an invented position.

BB35 has Boeing legends and different captured key indices from BB36. Its
ToLiss shortcuts are:

| BB35 physical key | ToLiss MCDU action |
| --- | --- |
| INIT REF | INIT |
| RTE / LEGS | F-PLN |
| CLB | PERF |
| CRZ | FUEL PRED |
| DES / PROG | PROG |
| MENU | MCDU MENU |
| DEP/ARR | AIRPORT |
| HOLD | SEC F-PLN |
| EXEC | DIR TO (Airbus changes are still inserted using their LSK) |
| N1 LIMIT | DATA |
| FIX | RAD NAV |
| PREV / NEXT PAGE | Left / right slew |
| DEL | OVERFLY |
| BRT - / + | MCDU dim / bright |

All twelve LSKs, letters, digits, SPACE, CLR, decimal and plus/minus retain
their corresponding functions. Single decimal and slash presses reach the
CDU after the short gesture timeout (or immediately before the next different
key). Triple-decimal and double-slash are consumed only as display shortcuts.
BB35's first HID report is a no-write baseline; repeated held reports do not
repeat a press. Studio observes each edge with mapping dispatch disabled, so
the ToLiss keypad worker is the only sender for that BB35 edge. Missing
commands or transport failure appear as `keypad_error` in its service status.

## MOZA AB6 FFB Base (`346E:1002`)

The AB6 entered the catalogue from an owner-supplied A320/MSFS2024 `.preset`
file. A preset carries calibration numbers, not a USB identity and not a report
layout, so it sat at `status: unimplemented` with no VID/PID and three axis
names taken from the preset rather than from the device.

**Captured 2026-09-02 from the connected base** with
`tools/capture_moza_ab6.py`, which is read-only by construction - it opens the
HID handle, reads the report descriptor and reads input reports, and never
calls `write`, `send_feature_report`, or any Moza SDK entry point. A test
asserts that at the AST level, because this is a force-feedback base.

- **Identity**: VID `346E` / PID `1002`, `Gudsen` / `MOZA AB6 FFB Base`,
  interface 2, Generic Desktop / Joystick. The serial number is diagnostic
  only, never identity.
- **Report descriptor**: 1259 bytes, SHA-256
  `d6749e4488da932e7584bd5ec30d2e862c0c14b3f5841b9488f636e84edbdd15` -
  **byte-identical to the A210's**. The AB6 was not assumed to match its
  sibling because they share a vendor id; both descriptors were read and
  compared. The input collection is therefore proven the same, and the
  capture-proven A210 decode applies unchanged.
- **Input**: report `01`, 34 bytes at about 975 Hz - eight unsigned 16-bit
  axes, a four-bit hat, and 128 generic HID contacts.
- **At rest**: stick near centre, hat 8 (the descriptor's null state), contact
  3 closed.

### Which axes the base actually carries

A 30-second full-travel exercise on the owner's base, 28669 frames:

| Axis | Observed | |
| --- | --- | --- |
| X, Y | `0 .. 65535` | full sweep |
| Slider, Dial | `0 .. 65535` | full sweep |
| Z | pinned `32767` | idle |
| Rx, Ry, Rz | pinned `0` | idle |

Hat positions `0, 2, 4, 6, 7` were seen plus the `8` null; 14 contacts were
observed closing. The four idle axes are **kept, not deleted** - the report
field genuinely exists and decodes, so each is marked observed-idle rather than
declared absent on one session's evidence.

**The AB6 prints no button names**, so the generic contact numbers are the
honest end of the capture: functions are assigned to them in Studio. The
`--capture` phase of the tool remains available if a labelled grip is fitted
later.

### Reader

`MuslimSimMozaA210` gained optional `vid`/`pid`/`label` parameters, all
defaulting to the A210, so the AB6 shares its capture-proven decode without
changing a single existing caller. The bridge starts the two bases in separate
`try` blocks: one Moza base being absent never silences the other.

### Studio page

Every Moza drawing helper takes a `device` argument defaulting to `moza_a210`,
so the A210 page is unchanged. The AB6 page passes `moza_ab6` and reads its own
live HID: the stick tracks X/Y, SLIDER and DIAL are drawn as live axes, and the
eight console contacts light on press.

**The MAX3 grip tab reads the AB6**, not the A210. The grip is mounted on the
AB6 base on this rig, and the capture observed contacts 1 and 10 - its TRIGGER
and TOP - closing there.

**No force-feedback output exists.** No Moza output protocol was supplied or
inferred, so `force_feedback_profile` stays `unimplemented` and untestable,
Practice drives nothing on this device, and Studio never sends a motor
command. `tools/probe_moza_flight_sdk.py` remains the open line of enquiry.

Covered by `tools/test_moza_ab6_capture.py`.

## Practice mode: which devices respond, and how

Practice exists to prove a device works with no simulator running. It is a
sandbox: **nothing practised is ever written to a saved profile.** Functions
are bound by assigning them in Live.

A device is *being practised* while one of its controls is exercised or its
Studio page is open. While practised, every capture-proven `led`/`lamp` on
that device is lit through the normal lab output path. Leave it alone and it
goes dark on its own after 20 s; leave Practice and every device goes dark at
once. Nothing else on the machine lights.

Practice drives only `led` and `lamp` controls the catalogue marks
`implemented` **and** `testable`. It deliberately does not drive:

- **displays** - each adapter takes its own shape (line lists, window dicts,
  digit strings). The five devices with an authored practice page keep it; a
  sixth would have to be authored rather than guessed.
- **gauges and solenoids** - these are real actuators, including the
  throttle's two vibration motors and the PU's timed starter retract.

| Device | Practice response |
| --- | --- |
| PU Overhead | 32 lamps + panel backlight |
| ECAM32 | all 19 LEDs; woken by opening its page, because it still has no catalogued input |
| MuslimRTP D201 | 11 LEDs and segment brightness |
| MuslimATC D203 | 6 LEDs and display brightness |
| WinCtrl throttle | 7 backlights and engine fault/fire lamps |
| AGP BB80 | CHR/UTC/ET windows, gear and autobrake lamps |
| PAP3 | LCD, backlight, annunciators |
| FCU/EFIS BA01 | windows and backlight |
| PFP3N / MCDU32 | authored practice FMC page |

Seven devices post nothing, and correctly so. `pdc_bb62`'s only output is
`unmapped_vendor_output`, whose protocol is `unknown`; both Moza units expose
only an `unimplemented` force-feedback profile; and `tca_boeing`,
`winctrl_pedals`, `pdc_bb61_left` and `pdc_bb52_right` have no output controls
at all. Those four are input-only: they post to Studio, not to themselves.

Measure this at any time with `tools/probe_practice_coverage.py`, which drives
the real lab and the real snapshot path and prints what each device actually
posts. Covered by `tools/test_practice_all_devices.py`.

## BB35/BB36 stalled-display supervision

Both colour displays can stop drawing while their Python thread is still
alive, because a native F0 write to a panel that has stopped acknowledging
blocks inside hidapi rather than returning. Thread liveness therefore proves
nothing about the glass, and the shared v46 output worker publishes a
frame-start heartbeat for exactly this reason.

- **BB36** has read that heartbeat since the live-owner work. **BB35 did not,
  and now does** - before this, a wedged PFP3N was reported live indefinitely
  and the router never reopened it.
- The stall threshold is **6.0 s on both**, below the 8.0 s startup grace.
  This is measured, not chosen: a wedged panel publishes no heartbeat at all
  after its path starts, so it surfaces at 8.0/8.1 s, while a live panel
  having one slow frame reads 3.0 to 3.6 s. The previous 3.0 s BB36 value sat
  inside the slow-frame population and tore down working hardware.
- **Neither panel's teardown may write while its own output worker might still
  own the handle.** Those darkening reports share one hidapi handle with the
  worker; interleaving them can leave the panel holding a torn native
  transaction, which outlives the handle close and is still there after a
  Studio restart. Both paths now send the blackout only once the worker has
  actually exited, and close the handle either way - the close is what
  unblocks a stalled native write.

**A wedged BB36 cannot be cleared by restarting Studio.** The only recovery
this panel responds to is a USB power cycle, and `pnputil /restart-device`
refuses one outside an elevated session, so automatic recovery fails with
`Restart screen/device requires Administrator rights`. Run Studio as
Administrator to let it recover the MCDU32 by itself, or unplug and replug the
panel. MuslimSim now says this once, plainly, and backs its retries off to a
30 s ceiling instead of reopening the panel - font upload included - every
twelve seconds for as long as Studio stays running.

Covered by `tools/test_display_stall_recovery.py`.

## BB35/BB36 CDU EXEC reminder

When Zibo has a pending CDU modification, MuslimSim reads the captain EXEC
indication and lights:

- BB35: the physical Boeing-labelled EXEC window (WinCtrl channel 16).
- BB36: the second top dash window from the right (WinCtrl channel 15).

The alert is available in the native FMC path and while either display is on
PFD, ND, ENG PRI, MFD, HYD or BB36 graphical FMC. It is a separate light-
channel write, not an LCD drawing command, so it does not reduce attitude,
airspeed or altitude refresh rate.

Live authority is mandatory. X-Plane must be connected, the aircraft display
must be powered, and the Zibo EXEC indication must be active. Starting a
display path first clears the window; simulator loss, cold/dark, mode handoff
and normal Studio shutdown clear it again before release. Once released,
MuslimSim sends nothing further to the panel.

Live acceptance check: enter a route/performance change that makes Zibo's CDU
EXEC light appear. Confirm BB35 EXEC and BB36's second window from the right
illuminate. Press EXEC and confirm both go dark without changing the currently
displayed PFD/ND/MFD/FMC page.

## BB35/BB36 coded cockpit pages

Both WinCtrl colour displays use the same native 640 x 480 drawing engine. For
Zibo/LevelUp, the normal graphical sequence remains
`PFD -> ND -> ENG PRI -> MFD -> HYD -> PFD`; double-SLASH advances it and
BB36's triple-PERIOD graphical FMC handoff remains separate.

### ToLiss Airbus PFD, ND and MCDU

ToLiss has its own display route. BB35 and BB36 both start on the live Airbus
CDU and expose PFD, ND and the complete authored Airbus ECAM/system deck.
Double-SLASH advances each panel independently. Triple-PERIOD switches directly
between CDU and PFD on either panel. Both keypads dispatch their own captured
edges to MCDU1 on every display page. This is the owner's explicit ToLiss CDU
keypad extension to the earlier BB35 display-only role. Both panels retain one
shared telemetry subscription and separate HID handles, canvases, page state
and differential caches; each keypad has its own command connection and never
reads the other panel's hardware.

The ToLiss PFD uses compact packed native cells and a geometry contract traced
from the installed ToLiss manual plus the owner's screen crops: three FMA rows,
narrow speed/altitude tapes, a stepped-rounded attitude aperture, slim tapered
V/S scale and a low central heading strip. `CaptIASValid`, `CaptALTValid`,
`CaptATTValid` and `CaptHDGValid` independently control the reference-specific
red `SPD`, split `ALT`, dark `ATT`, vertical `V/S` and three-sided `HDG`
silhouettes. Valid data restores only the affected region. The nonlinear V/S
scale labels 1, 2 and 6 and carries a thin green needle from its right-centre
pivot. ToLiss's native FMA1/FMA2/FMA3 colour layers are rendered directly, so
active and armed text/colour come from the aircraft rather than a Studio enum.

Takeoff speed presentation is not inferred from current IAS: ToLiss's
`show_to_speeds` output gates cyan V1 `1`, cyan VR ring and magenta V2 triangle.
Green F/S, green dot and amber VFE-next use ToLiss's computed display outputs.
The upper red/black strip follows ToLiss VMax, so it reacts to the applicable
flap/gear/VMO/MMO limit without a separate Studio limit table. Amber VLS and
alpha-protection remain low-speed cues, not a yellow overspeed zone. With LS
selected, LOC and G/S scales carry independent native magenta diamonds.

The ToLiss ND supports the live captain EFIS ARC, ROSE and north-up PLAN modes
and every published range index. ARC and PLAN carry two distance rings; the
active green plan and waypoint are projected and clipped at the selected range
in ROSE NAV, ARC and PLAN. `AirbusFBW/FlightPlanDashed` switches that same
green route to the off-managed-path dash pattern.
`CaptMAPAvail == 0` produces red invalid arcs, `HDG` and `MAP NOT AVAIL`, with
GS/TAS/wind replaced by dashes so stale finite values cannot look valid.
`GPSPrimMessCapt` independently selects green `GPS PRIMARY` or amber
`GPS PRIMARY LOST`. Captain VOR/ADF selector 1 draws the native single bearing
needle and lower-left ID/DME; selector 2 draws the double needle and lower-right
ID/DME. ADF/OFF/VOR uses absolute 0/1/2 positions and PLAN suppresses the
heading-relative needles. No unpublished waypoint-name array is invented; the
published active waypoint ID/distance and route coordinate arrays are used.

The BB35 and BB36 ToLiss CDU pages use a 24 x 14 grid at 23 x 29 native-cell
pitch. The extra font is isolated in slot 2 of
`winctrl-pfp-b737-cockpit-font2-3-4-5-6-8.xpwwf`; the complete established
Zibo/LevelUp resource is its byte-identical prefix. PFD/ND/MCDU runtime output
is code-native. Files under `PNG/toliss-display-preview/` are offline review
renders only and are never opened by the bridge.

`AirbusFBW/BatVolts` is the common output authority. Disconnected, unknown or
unpowered ToLiss state clears the retained framebuffer and sends brightness
off on both panels. Page transitions invalidate the cache, and normal shutdown
blacks both screens before releasing their handles. If the optional BB36 mirror
is disabled, production keeps that LCD black because no display worker remains
to establish power; MCDU keys still dispatch.

Offline acceptance:

```powershell
python -B tools/test_toliss_displays.py
python -B bridge/final.py --test-pfp-pfd
```

The measured guard limits are 290 PFD recovery reports, 450 ND recovery reports
and 375 ND turning reports. Current results are 274, 427 and 356 respectively;
the PFD moving-frame sample is 180 reports.
The remaining acceptance is live: cold/dark must be black; powered but invalid
IRS/GPS must show the red/amber source flags; alignment must restore the normal
PFD/ND; EFIS range/mode and both physical page gestures must update immediately.

Do not infer full Airbus coverage from the existence of a page. The exact
implemented and still-pending PFD/ND/system feature families are recorded in
`docs/TOLISS_DISPLAY_COVERAGE.md`. In particular, FMA capture boxing/pulsing,
minimums/rising-runway/pitch-limit/speed-trend variants, TCAS targets,
actual WXR/TERR imagery and advanced route/constraint symbology are not yet
claimed complete. ENG and the remaining lower-display pages use the coded
Airbus system groupings listed in that coverage contract.

The ToLiss PFD lower corners remain outside the central heading strip. They use
compact native runs such as `.783`, `QNH1013`, `109.50`, `12.4NM` and `ELEV610`;
STD is cyan inside its amber reference box. The layout guard prevents those
runs from overlapping the heading tape or bezel mask.

PFD text and numbers use native font slot 5 with 13 x 19 artwork inside the
same 17 x 29 cells. BB35's ND uses its dedicated experimental slot 4, with
10 x 15 printable ink, and its Boeing-specific layout: compact GS/TAS and wind
at left, live TRK boxed at centre, active fix/ETA/distance plus MAP/range at
right, vertical EFIS layers, right-side RNP/ANP, and `FMC L` when route data
exists. Its range guides are solid white. BB36 ND, ENG PRI, MFD and HYD retain
the larger slot 6 and their established geometry.

BB35 alone uploads `winctrl-pfp-b737-cockpit-bb35-font4-5-6.xpwwf`. BB36 keeps
the exact Point A `winctrl-pfp-b737-cockpit-dual-font5-6.xpwwf` and never sees
slot 4. All pages remain native commands; neither resource is a scaled PNG or
a framebuffer. Completely close and restart Studio after this change so BB35
receives the appended slot. If BB35 ND text is blank, corrupted or less useful,
close Studio and restore
`Backup/point_a_bb35_boeing_nd_20260901-011500/`.

On HYD, green AIL/ELEV/RUDDER markers follow the live pilot roll, pitch and
yaw positions during a control test. Each left/right wheel pair also contains
a green toe-brake position marker; the four white numbers remain brake
temperatures. Aircraft surface outputs are retained as fallback. `FLT` and
`SPLR` are stacked deliberately because the verified controller font has fixed
17 x 29 opaque cells. Headers and PFD top-right text stay inside the measured
physical safe band rather than touching the logical 640-pixel edge.

Selecting STA, WPT or ARPT starts a read-only background load of the installed
X-Plane database for that layer. Once indexed, nearby real entries appear at
the current map scale. WPT suppresses at 80 NM and above to avoid clutter.
The airport database is large, so its symbols can appear a few seconds after
the first ARPT selection; this loading never runs in the HID frame loop.

No live page opens a PNG. To review all pages without hardware or X-Plane:

```powershell
python -B tools/render_coded_display_pages.py --out display-qa
```

The command writes review PNGs only. For an offline integration check run
`python -B bridge/final.py --test-pfp-pfd`, then `python -B launch.py --check`.
The remaining acceptance check is live: compare each page against a running
Zibo aircraft and confirm page cycling, route/TCAS, FPV/approach, engines and
hydraulics on both physical displays.

## FCU / EFIS Studio faceplate

The Studio keeps the established three-part arrangement: captain EFIS on the
left, the four-window FCU in the centre, and first-officer EFIS on the right.
Its typography is intentionally larger than the first compact version. Knob
captions, PULL buttons, and both FCU action rows occupy separate bands; EFIS
STD/QNH, BARO, unit, MAP MODE, RANGE, NAV 1, and NAV 2 labels are separated
from their selector lines. All physical/mapping click tags are unchanged.

Offline visual check: `python tools/test_fcu_faceplate_layout.py`. It renders
the real Tk drawing and checks label/line separation and click coverage without
opening BA01 hardware or a simulator.

The physical BA01 input endpoint currently transmits 41 bytes even though the
HID transfer maximum is 64. MuslimSim accepts either form and decodes only its
first twelve payload bytes. For ToLiss, the SPD, HDG, ALT and V/S encoders move
the aircraft's own `FCU*KnobRotation` inputs through their native -10..29
range; the ALT 100/1000 switch writes `AirbusFBW/ALT100_1000`. Speed and
altitude are selected-target values. Speed uses the unit-aware
`sim/cockpit/autopilot/airspeed` (knots in SPD mode, `0.xx` in MACH mode),
altitude uses `sim/cockpit2/autopilot/altitude_dial_ft`, and heading and V/S
use `sim/cockpit/autopilot/heading_mag` and
`sim/cockpit/autopilot/vertical_velocity`, the selected targets.
SPD versus MACH is selected only by
`sim/cockpit/autopilot/airspeed_is_mach`. `AirbusFBW/ShowMachCapt` belongs to
the captain PFD's Mach-caption/crossover presentation and must never be used as
the physical FCU unit flag; doing so formats a cruise knot target as `.99`.
The PFD's `ap_alt_target_value` is deliberately not used for the FCU: a live
managed-descent snapshot showed that internal target holding `22000` while the
selected FCU dial was `8000`.

ToLiss also supplies both numeric BARO settings, managed/dashed state, captain
and first-officer FD/LS and ND-filter lamps, and the six captured FCU integral
lights. FCU selector order is LOC=3, AP1=5, AP2=7, A/THR=9, EXPED=11, APPR=13
on the `0x10/0xBB` light family. The capture-proven filter order is CSTR=5,
WPT=6, VOR.D=7, NDB=8 and ARPT=9 on both symmetric `0x0D/0xBF` and
`0x0E/0xBF` EFIS light families. The output manager sends only changed lamps;
loss of aircraft power sends every lamp and display dark.

The twelve captured VOR/ADF positions are no longer diagnostic-only. The
installed ToLiss A320 and A321 both bind the same writable controls:
`ckpt/fcu/adf1Left/anim`, `adf2Left/anim`, `adf1Right/anim` and
`adf2Right/anim`. Each physical selector performs an absolute write using
ADF=0, OFF=1 and VOR=2; a stationary baseline remains observation-only.

ToLiss opts into the Airbus FCU V/S presentation: two main hundreds digits
plus two smaller zero glyphs, a horizontal sign stroke with an additional
vertical stroke for positive V/S, and the `ALT <- LVL/CH -> V/S` annunciator.
`AirbusFBW/HDGTRKmode` switches the whole paired presentation: HDG mode lights
HDG/LAT, HDG/V/S and V/S; TRK mode lights TRK/LAT, TRK/FPA and FPA. FPA reads
`sim/cockpit2/autopilot/fpa` and is signed in tenths with its dedicated decimal
segment. MACH similarly sends a leading zero to the digit cell and uses its
dedicated decimal segment, producing `0.77` rather than a blank-leading `.77`.
Those options default off so the Zibo/legacy display packet is byte-for-byte
unchanged. ToLiss also zero-fills the whole physical field: IAS and HDG always
use three digits (`001`) and ALT always uses five (`00001`); MACH and managed
dashes retain their dedicated presentations. Specifically, managed SPD/MACH
and HDG/TRK show `---` plus the hardware's large managed dot, and a dashed
V/S/FPA field shows five horizontal strokes. `SPDdashed`/`VSdashed` never
electrically blank a powered window; true visibility and aircraft power remain
separate gates. Offline contract:
`python -B tools/test_fcu_efis_toliss.py`. Live
acceptance: restart Studio, load ToLiss, turn every FCU/BARO/range/mode knob in
both directions, exercise each listed lamp, and verify SPD/MACH, HDG/V/S,
TRK/FPA, plus positive and negative V/S/FPA formatting.

## WINCTRL 3N PDC / EFIS (BB62)

The connected panel currently reports as `WINWING 3N PDC R` even if it is
mounted on the left side. MuslimSim selects it by `4098:BB62`, not by the
product-string side label. It has a 64-bit button field and two 16-bit axes.

The captured switch/button map is bound to the current Zibo CAPT EFIS profile:
MINS RADIO/BARO and RST; BARO IN/HPA and STD; both VOR/ADF selectors; MODE;
RANGE; and TFC/WXR/STA/WPT/ARPT/DATA/POS/TERR/FPV/MTRS. It records a baseline
first, so a stationary selector never changes the aircraft at startup or after
reconnect. It does not write PDC displays/LEDs. Disable only this device with
`--no-pdc` (or launcher `--without-pdc`).

MINS and BARO are bound from the focused raw trace, rather than from the
misleading shared-axis reading in the original capture. MINS clockwise and
counter-clockwise use bits 41/39 and change the CAPT minimums setting up/down.
BARO clockwise and counter-clockwise use bits 44/42 and change the pilot
barometer up/down. The first HID report is still a no-write baseline.

`tools/probe_pdc_bb62.py --knob-trace` remains read-only diagnostic tooling;
use it only when an additional physical-control investigation is needed.

Both VOR/ADF selectors now use absolute, saturating Zibo command sequences:
VOR goes to its endpoint, ADF goes to its endpoint, and OFF goes to the VOR
endpoint then takes one step to centre. This avoids dependence on an inferred
simulator state value and remains reliable after selector movement.

To capture the semantic map, stop MuslimSim and every other application that
could own this panel, then run:

```powershell
& "C:\Users\noureddine aidoudi\AppData\Local\Programs\Python\Python311\python.exe" -B "D:\MuslimSim\tools\probe_pdc_bb62.py"
```

For each held selector position, the probe now asks for two states: move the
same selector to any other position, then set the named position. Complete the
sequence in the prompted order: MINS RADIO/BARO and knob/RST; BARO IN/HPA and
knob/STD; both VOR/ADF three-position selectors; MODE APP/VOR/MAP/PLAN; RANGE
5/10/20/40/80/160/320; then TFC, WXR, STA, WPT, ARPT, DATA, POS, TERR, FPV,
and MTRS. Turn each knob both ways during its three-second capture. Paste the
printed `PDC_CONTROLS` dictionary back unchanged, including any warning about
duplicated bits. The complete selector/button map and focused rotary trace
have now both been recorded.

## WINCTRL 32 ECAM (BB70) button names

The ECAM input report proves raw contacts such as `raw_r01_b02_bit5`; it does
not say ENG, BLEED, ELEC, or another printed Airbus legend. Do not reconstruct
the semantic map from packet order. The old order assumption is what caused a
physical button to select the wrong Studio name.

Close MuslimSim Studio completely, connect the ECAM, and double-click:

```text
D:\MuslimSim\CAPTURE_ECAM32_BUTTON_NAMES.cmd
```

Type `READY`, then follow the command window. For every prompt, release all
buttons, press Enter, tap only the named ECAM button once, and release it. The
wizard distinguishes left CLR from right CLR, rejects a second/duplicate
contact, and repeats a name if the press was not clean. After all 18, type
`SAVE`. Anything else cancels without changing a profile.

On save, the same measured physical map is installed into every named profile
inside each existing X-Plane/MSFS hardware profile file. This does not choose
simulator commands and does not erase existing command/dataref bindings.
Timestamped copies are kept in `%APPDATA%\MuslimSim\Backup`, with a separate
`ecam32_button_names_*.json` capture record.

The wizard never connects to a simulator or wakes the panel. It keeps captured
outputs at zero, sends the captured blackout before closing, and releases the
HID handle. Restart Studio only after the command window reports `SUCCESS`.
Then tap BLEED, ELEC, and every other physical key and confirm only the matching
faceplate button responds. This live 18-button verification is still required.

The measured-name progress box is drawn below the physical ECAM faceplate in
the dark-blue Studio margin. The sixth button row remains completely clear and
clickable; the compact colour/state legend sits in the panel's lower trim.

## Pedals

Detected device name:

```text
WINCTRL Orion Combat Rudder Pedals Metal
```

Default SDL map:

| Axis | Physical control | Output |
| --- | --- | --- |
| 0 | Left toe brake | `sim/cockpit2/controls/left_brake_ratio` (0.0 to 1.0) |
| 1 | Right toe brake | `sim/cockpit2/controls/right_brake_ratio` (0.0 to 1.0) |
| 2 | Rudder | `sim/cockpit2/controls/yoke_heading_ratio` (-1.0 to 1.0) |

Before the first live test, clear duplicate rudder and toe-brake assignments
for this device inside X-Plane. Otherwise X-Plane's own joystick assignment
and the bridge can fight each other.

On a normal bridge start, expect a message similar to:

```text
PEDALS axis pickup initialized: move each pedal through its current simulator position before it takes control.
```

Then test one control at a time on the ground:

1. Move rudder left and right slightly until pickup occurs; confirm the
   aircraft/yoke-rudder response is correct.
2. Press only the left toe brake; confirm only left braking responds.
3. Press only the right toe brake; confirm only right braking responds.

If one direction is backwards, stop MuslimSim and relaunch with the matching
option:

```text
--pedals-rudder-invert
--pedals-left-brake-invert
--pedals-right-brake-invert
```

To disable only pedals:

```powershell
& "C:\Users\noureddine aidoudi\AppData\Local\Programs\Python\Python311\python.exe" -B "D:\Howalt d203 requre signature\MuslimSim\launch.py" --with-pfd --without-pedals
```

## PU Overhead: the panel with no off (2026-09-01)

The PU Overhead is made by **PU Korea**, not WinCtrl, and it is the only panel
on this rig driven over a serial CDC port rather than USB HID.

**It cannot be turned off.**  Measured, not assumed: it dims but never
extinguishes, and PU CONNECT MSFS - the vendor's own software - cannot switch
it off either.  Rule 0.1 is satisfied for this device as far as the protocol
allows and no further.  Do not add another blackout for it.

The brightness protocol has three fields, captured from PU CONNECT in
`PU_Brightness.pcapng` (device 49, endpoint 0x02):

| Field | Range | What MuslimSim sends |
| --- | --- | --- |
| `P2` | 1 - 14 | fixed `4` in live frames, `1` at shutdown |
| `P3` | 1 - 14 | fixed `4` in live frames, `1` at shutdown |
| `P8` | 0 - 250 | 0 - `P8_MAX`, currently 125 |

The vendor's all-the-way-down frame is `OVHD,0,1,1,0,12345,12345,0,0`.  Closing
Studio now sends `OVHD,0,1,1,0,<blank>,<blank>,0,0`, which is that minimum.

Two things to know before touching this:

- **`P2` and `P3` were undocumented constants.**  The packet comment at the top
  of `bridge/final.py` explains P4 through P8 and skips them.  They are dimmer
  channels, not flags.  `build_packet` takes optional `p2`/`p3` that default to
  the constants, so live output is unchanged; only the shutdown frame passes
  the minimum.
- **`P8_MAX` is 125, but the vendor drives P8 to 250.**  MuslimSim's brightness
  range is half the hardware's.  `build_packet` already clamps P8 to 255, so
  the cap lives only in `brightness_to_p8`.  Raising it is a real change to how
  bright every panel gets, so it is deliberately left alone.

This was established by driving the panel directly, three ways: closing the
port, varying the frame contents, and sending PU CONNECT's own minimum.  In
every case the dim lasted exactly as long as the stream and no longer.  Five
attempts to hold it dark were made and all removed; the probes and the holder
that came with them are deleted.  The conclusion is what remains.

## PU engine-start protection

The PU engine-start rotary handles GRD, OFF, CONT, and FLT. A physical GRD
selection owns one short automatic retract window back toward the normal
detent. Do not add any WinCtrl engine-mode mapping to this feature.

Before changing engine-start code, run:

```powershell
& "C:\Users\noureddine aidoudi\AppData\Local\Programs\Python\Python311\python.exe" -B "D:\Howalt d203 requre signature\MuslimSim\launch.py" --test-starter-retract
```

## PFP/PFD notes

- `--with-pfd` enables the live custom captain PFD.
- `--without-pfp` starts cockpit controls without the PFD page.
- The PFD is native drawn 640 x 480 colour output, not a continuously uploaded
  PNG.
- The PFD is display-only; it does not write aircraft flight controls.
- Default live sampling is split: thirteen flight/motion values every 0.25
  seconds, and the complete 24-value sample every 1.0 second. Use
  `--pfp-pfd-refresh 0.50` only if the cockpit PC still needs lower display
  load; `0.20` is the protected minimum for a faster test.
- The renderer sends final-pixel dirty regions, not a complete PFD on every
  sample. A periodic full recovery and an offline/reconnect invalidation prevent
  stale regions.
- Use the compact native PFP font and protected zones documented in
  [PFD_PROJECT_HISTORY.md](PFD_PROJECT_HISTORY.md).
- The native font carries more than text: the static PFD shapes (heading rose
  and vertical-speed wedge) live in its spare lower-case glyph codes. Rebuild
  the font with `tools/build_pfp_compact17_font.py` and then always rerun
  `tools/build_pfp_shape_tiles.py`, or those shapes will appear as letters.
  Run `tools/build_pfp_dual_font.py` last to restore the PFD-small font 5 while
  copying the completed larger font 6 and its tiles unchanged.
- A renderer change can be seen without the cockpit: `tools/render_pfp_frame_png.py`
  draws the live renderer's own frame to PNG and reports its USB cost. The
  panel bills about one millisecond per HID report.
- Before a live PFD test, run the pixel-identity and traffic checker:

  ```powershell
  & "C:\Users\noureddine aidoudi\AppData\Local\Programs\Python\Python311\python.exe" -B "D:\Howalt d203 requre signature\MuslimSim\tools\check_pfd_differential.py" --frames 120
  ```

- Close or disable PU CONNECT MSFS output to the PFP while MuslimSim's PFD is
  enabled. PU CONNECT can still be used for hardware it does not compete for;
  the screen itself must have one owner.

## MUSLIMRTP D201 / MUSLIMATC D203: live routing (2026-09-02)

Both panels are native MuslimSim serial devices. No MobiFlight process and no
second simulator bridge is involved: they attach to the existing HardwareLab
and use the bridge's own X-Plane Web API helpers.

### Ownership rule

1. An explicit saved Studio mapping or remap wins.
2. With no saved mapping, the native default below is sent.
3. A control with no verified aircraft function stays remappable rather than
   being redirected into a guessed target.

### D201 native defaults

| Control | Key | Live action |
| --- | --- | --- |
| VHF1 / VHF2 | `vhf1` / `vhf2` | select COM1 / COM2 |
| Upper transfer | `tfr1` | flip selected COM active/standby |
| Upper outer / inner | `bmq2_1` / `bmq2_2` | selected COM standby coarse / fine |
| Lower transfer | `tfr2` | flip NAV1 active/standby |
| Lower outer / inner | `bmq3_1` / `bmq3_2` | NAV1 standby coarse / fine |
| VHF3, HF1, HF2, AM | - | selectable, not redirected to another radio |
| HF SENS, TEST | `hf_sens_push`, `test1/2` | remappable only |

### D203 native defaults

| Control | Key | Live action |
| --- | --- | --- |
| Five ATC/TCAS detents | `stby` … `ta_ra` | Zibo `transponder_mode_up`/`_dn` |
| IDENT | `ident` | X-Plane transponder IDENT |
| TEST | `atc_test` | X-Plane transponder TEST |
| Four encoder sections | `bmq1_1` … `bmq2_2` | edit the four octal squawk digits |
| ATC source 1/2 | `xpn_1_2` | Zibo `xpndr_atc` toggle, reconciled |
| ALT source 1/2 | `alt_1_2` | Zibo `xpndr_alt` toggle, reconciled |

STBY is target position 1 and TA/RA position 5; the physical intermediate
detents occupy 2/3/4.

### The two source switches are absolute against a toggle command

Zibo publishes `laminar/B738/switch/xpndr_atc_pos` and `..._alt_pos` read-only,
and moves each switch with the command
`laminar/B738/toggle_switch/xpndr_atc` / `..._alt`.

The D203 switch is absolute; the aircraft only offers "flip it". Firing the
toggle on every event would make the aircraft follow the *number of events*
rather than the physical position, and the two drift apart the first time
either side moves alone. So `_set_atc_source` reads the position, compares, and
toggles only on disagreement. Both switch edges are dispatched - moving to
position 2 arrives as a release, so that branch sits ahead of the release guard
that the rest of `_dispatch_atc_live` uses.

Which physical position means aircraft position 0 is held in one constant,
`ATC_SOURCE_PRESSED_POSITION`. If the switches ever read reversed on the
hardware, that constant is the whole fix.

### The D201 VHF3 window

Zibo publishes the third COM in parts, all read-only, so VHF3 is display-only:
`laminar/B738/comm/com3/act_freq_MHz` and `_kHz`, plus an `act_freq_data` flag
that puts **DATA** in the window instead of a number, and the matching
`stdby_freq_*` trio. A selector position with no verified source blanks its two
windows rather than showing another radio's frequency.

### If Live control does nothing

The failure mode to know about, fixed on 2026-09-02: the panel reads correctly
and writes nothing. Displays track, lamps follow, the selector moves, and no
control reaches the aircraft.

That is the signature of the bundle having no write path. `install_howalt_v4`
takes `resolve_dataref_id` and `read_dataref` for reading and `set_dataref`,
`resolve_command_id` and `activate_command` for writing. If the last three are
not passed at the call site in `bridge/final.py`, `_command_once` and
`_write_ref` return False on their opening `callable(...)` guard, silently, and
every control looks like an unmapped one.

Do not rely on the `getattr(__main__, ...)` fallback in
`HowaltV4Bundle.__init__` to cover this. `muslimsim/core/engine.py` loads
`bridge/final.py` as `_muslimsim_bridge_engine`, so `__main__` is `launch.py`
and the fallback always yields `None`. Pass the helpers explicitly.

### Output authority (rule 0.1, since 2026-09-02)

Both panels go dark with the aeroplane and sleep when Studio closes.

**How they go dark:** `_all_panels_dark` calls each router's own `all_off` -
`set_output(name, 0)` for every declared output, and a blank through the same
masked display writer that normal output uses. No vendor packet was invented.

Aircraft power comes from the same candidates `bridge/final.py` resolves for
the PU and the throttle: `laminar/B738/electric/dc_stdbus_status`, then
`sim/cockpit2/electrical/battery_on`, then `sim/cockpit/electrical/avionics_on`.
Rule 0.1 is one rule about the aeroplane, not a per-device opinion.

The two kinds of "no reading" mean opposite things and are handled separately,
the same way `_agp_aircraft_output_powered` does it:

| situation | judgement |
| --- | --- |
| no power ref resolved at all | aircraft publishes none - preserve, do not black out |
| ref resolved, unreadable now | live data lost - go dark |
| ref reads below 0.5 | unpowered - go dark |

Test mode stays user-owned. Both shutdown paths darken before the ports close:
`stop()`, and the monitor's own exit when the bridge's shutdown event fires.

## Aircraft and simulator notes

- The intended aircraft profiles are Zibo, LevelUp, and compatible Boeing 737
  dataref/command layouts.
- LevelUp starts the established BB35 and BB36 coded-page routes, including the
  BB36 graphical FMC. It does not use a separate renderer or alter Zibo's page
  design. Its published FMC surface covers every command/dataref those routes
  consume.
- The bridge has a generic/read-only profile rather than forcing Boeing
  controls into an unrelated aircraft.
- PU CONNECT MSFS may remain part of the user's normal setup, but its PFP
  output must be closed or disabled while the MuslimSim PFD is enabled.

## WinCtrl throttle: the below-idle split (2026-08-28)

The URSA MINOR is an Airbus quadrant - one continuous lever travel - driving a
737, which has a thrust lever above IDLE and a separate reverse lever below
it. The travel is cut at the IDLE detent:

```text
full reverse ... REV IDLE ... IDLE ......... TOGA
|<------ below idle ------->|<--- forward thrust --->|
```

Above IDLE drives the 737 thrust lever, 0.0 to 1.0. Below IDLE is inert until
the matching reverse handle (button 40 left, 41 right) is raised, and then
drives only the reverse lever, through the REV IDLE gate at which Zibo's
reverse first responds.

**Every throttle must be calibrated.** The three raw endpoints per lever were
hard-coded from a capture of one unit. On the machine that capture came from,
the left lever now reads 20165 against an assumed 19308 - 1.85% commanded
thrust with the lever in its own idle detent.

Calibrate in the control panel's Throttle tab: put both levers in the IDLE
detent and press *1. Capture IDLE*; raise both reverse handles, pull back to
the REV IDLE detent, and press *2. Capture REV IDLE*. The panel then passes
the measured points to the bridge on every start:

```text
--throttle-left-idle N   --throttle-left-rev-idle N
--throttle-right-idle N  --throttle-right-rev-idle N
```

An impossible calibration is refused by the bridge with exit 2, not clamped.

The quadrant is read over **raw HID**, matching the bridge's Windows Raw Input
decode - report 0x01, left axis bytes 13:15, right axis 15:17. Calibrating
through SDL would produce values the bridge never sees.

Offline check: `--test-winctrl-throttle`, plus the `throttle split is safe`
and `bad throttle calibration is not emitted` checks in
`muslimsim_panel.py --check`.

Full detail: [docs/THROTTLE_BELOW_IDLE.md](docs/THROTTLE_BELOW_IDLE.md).

## WinCtrl throttle: ToLiss A320/A321 aircraft calibration (updated 2026-09-09)

The Airbus path does **not** call the 737 converter above. It owns profile
`toliss-a320-a321-winctrl-v2` and writes the two indexed elements of
`AirbusFBW/throttle_input` only while the detected aircraft profile is ToLiss.
Zibo and LevelUp retain their existing `WINCTRL_*` calibration unchanged.

| Airbus gate | Engine 1 fallback raw / button | Engine 2 fallback raw / button | Direct ToLiss target |
| --- | --- | --- | --- |
| FULL REV | 0 / 17 | 0 / 23 | -1.000 |
| REV IDLE | 14115 / 16 | 14115 / 22 | -0.100 |
| IDLE | 20165 / 15 | 20165 / 21 | 0.000 |
| CL | 45371 / 14 | 45371 / 20 | 0.700 |
| FLEX/MCT | 55453 / 13 | 55453 / 19 | 0.875 |
| TOGA | 65535 / 12 | 65535 / 18 | 1.000 |

The two raw columns are separate profile entries even when one unit happens to
report equal counts. They are fallbacks, not an assumption that every WinCtrl
quadrant is identical. In Studio, press **CALIBRATE DETENTS** with both levers
at FULL REV and sweep upward through all six gates. A contact begins a sample;
the same contact and raw axis must remain settled for 0.30 seconds before the
resting count is saved. This avoids recording the leading edge while the lever
is still entering its notch. The two engines advance independently.

The saved payload is marked `toliss-a320-a321`, schema version 2, and contains
six strictly increasing raw gates under separate `left` and `right` objects in
`hardware_profiles_toliss.json`. Version-1 leading-edge captures, invalid or
collapsed values, and other aircraft-family payloads are rejected rather than
silently reused. Physical gates are always translated to the fixed direct
targets in the last column; ToLiss ISCS joystick ratios are diagnostics and do
not replace those final `AirbusFBW/throttle_input` values.

A detent contact snaps to its exact target while travel between gates remains
continuous. Below IDLE is clamped to zero unless `revOnSameAxis` is enabled and
the matching physical lift handle (40 for engine 1, 41 for engine 2) is raised.
If REV IDLE and IDLE briefly overlap while returning from reverse, IDLE wins.
Buttons 12..23 force a current axes snapshot on press and release.

Startup first captures a no-write baseline, reads each simulator lever and
waits for the matching physical lever to reach or cross it. Stable values are
delta-suppressed at `0.004`. The guided sweep suspends ToLiss thrust writes and
re-arms pickup on start, save and error/cancel paths, so a calibration exercise
cannot jump a parked aircraft.

Offline guards: `tools/test_toliss_throttle_calibration.py` and
`tools/test_toliss_throttle_probe.py`.

Live calibration acceptance: restart Studio with a ToLiss A320/A321 loaded and
parked; perform the six-gate sweep and hold each notch until saved. Confirm 6/6
on both engines and ruler lines at the resting markers. Move each engine alone
through IDLE, CL, FLEX/MCT and TOGA, then test each reverse handle and return
directly to IDLE.

## WinCtrl quadrant: complete ToLiss controls and trim modes (2026-09-09)

The same single raw-input owner now routes all non-thrust B930 controls while
ToLiss is active. A saved Hardware Lab binding is offered each ordinary input
first; the dedicated trim-role push remains profile-hard-coded.

| Physical control | B930 input | ToLiss action |
| --- | --- | --- |
| ENG 1 master IDLE / CUTOFF | buttons 1 / 2 | native Master1On / Master1Off |
| ENG 2 master IDLE / CUTOFF | buttons 3 / 4 | native Master2On / Master2Off |
| engine mode CRANK / NORM / IGN-START | buttons 7 / 8 / 9 | native three-position engine-mode commands |
| red lever buttons L / R | buttons 10 / 11 | A/THR disconnect (the real Airbus action) |
| IGN/START knob push | button 24 | next trim role: STAB/PITCH -> RUDDER -> STAB/PITCH |
| trim RESET / LEFT / RIGHT | buttons 25 / 26 / 28 | reset or repeat the selected trim axis |
| parking brake RELEASE / SET | buttons 29 / 30 | absolute writable `AirbusFBW/ParkBrake` 0 / 1 after baseline; native commands are fallback only |
| flap 0 / 1 / 2 / 3 / FULL | buttons 35 / 34 / 33 / 32 / 31 | exact 0.00 / 0.25 / 0.50 / 0.75 / 1.00 |
| speedbrake axis and ARM contact | axis plus buttons 36..39 | continuous lever; ARM is ToLiss -0.5 |

`MODE.pcapng` contains only two distinct 37-byte B930 reports for the knob
push. Their sole XOR is report byte 3 mask `0x80`, zero-based bit 23, hence
one-based button 24. This keeps the real engine-mode detents independent from
trim selection. The physical four-cell window briefly shows `PtCH` or `rUdr`,
then pitch units or signed rudder tenths. RESET centres rudder; pitch has no
invented centre command. ToLiss does not expose an aileron role.

The first maintained-button set and first speedbrake/flap samples are strictly
read-only. Continuous speedbrake and flap travel then require reach-or-cross
pickup against their current simulator values; later physical detent edges are
authoritative. Stable movement is delta-filtered. `AirbusFBW/DCBusVoltages` controls
all B930 backlights and the trim window, clears stale prior-aircraft digits on a
cold ToLiss load, and blacks the hardware out on power loss or shutdown.

Offline guard: `python -B tools/test_toliss_winctrl_controls.py`.

## WinCtrl AGP: ToLiss clock plus RADIO/CTRL (2026-09-09)

CLOCK remains the normal page and all ordinary clock controls retain their
meaning. A short TERR ON ND press toggles terrain. Holding it for at least 0.65
seconds changes only the display page and cycles:

```text
CLOCK -> RADIO -> CTRL -> CLOCK
```

- RADIO uses the RST rotary for fine RMP1 tuning, CHR for coarse tuning, either
  push for transfer, and the UTC three-position selector for VHF1/VHF2/VHF3.
- CTRL uses RST for selected speed, CHR for selected altitude and DATE for
  selected heading through ToLiss's native FCU knob-rotation inputs.

The three rotary counters are lossless and existing Studio bindings retain
precedence. RADIO RST counts are queued in order and one native fine command is
sent every 0.06 seconds, so a fast roll continues rapidly without bursting
several changes between physical LCD readbacks. Leaving RADIO deliberately
cancels any still-unsent queued steps. Without an energized
`AirbusFBW/DCBusVoltages` bus, every AGP
digit, backlight and lamp is dark. The Zibo AGP page order remains RADIO ->
CTRL -> NAV and is not reused by this ToLiss-only gesture.

The ToLiss A321 XP12 brake annunciators use
`AirbusFBW/OHPLightsATA32_Raw`: element 11 drives the amber BRK FAN HOT output
on AGP LED 6; elements 12/14/16 drive LOW/MED/MAX ON on LEDs 14/15/16; and
elements 13/15/17 drive LOW/MED/MAX DECEL on LEDs 11/12/13. These are aircraft
lamp states, not pushbutton animations, so ON stays latched until ToLiss
disarms it and HOT follows ToLiss's own brake-temperature/light-test logic.
All seven outputs join the AGP cold-start, power-loss and shutdown blackout.

Live acceptance after restarting Studio: load ToLiss cold-and-dark and confirm
AGP/B930/BA01 are dark, then apply aircraft power. Exercise each engine master
and all three engine-mode positions; move speedbrake through DOWN/ARM/HALF/FULL,
flaps through 0/1/2/3/FULL, and parking brake through RELEASE/SET. Engage A/THR
and press either red lever button; A/THR—not AP/FD—must disconnect. Press the
IGN/START knob repeatedly and verify `PtCH`, `rUdr`, `PtCH`; operate the rocker
in each role and compare its LCD value to ToLiss. Short-press TERR to toggle
terrain, then hold it three times while checking CLOCK/RADIO/CTRL operation.
In RADIO, turn RST one notch at a time and then rapidly: every captured step
must arrive in order, with no five-value burst between LCD readbacks.
Finally select FCU SPD 1, HDG 1 and ALT 1 and confirm `001`, `001`, `00001`.
At cruise, select MACH and compare the displayed target to ToLiss, then select
SPD: the FCU must change immediately to the selected knot value and must not
show `.99`. Heat the brakes under supervised ground testing and confirm HOT
LED 6 follows ToLiss, then select each autobrake mode and confirm its ON light
stays lit until manual or aircraft automatic disarm.

## RUD TRIM rocker: the Zibo/LevelUp stabilizer trim wheel (2026-09-05)

The physical rocker labelled **RUD TRIM** is hard-wired to the loaded supported
737's stabilizer trim wheel. The paint still says RUD TRIM; the control does
pitch.

| Contact | B930 button | Zibo | LevelUp | Does |
| --- | --- | --- | --- | --- |
| LEFT | 26 | `laminar/B738/flight_controls/pitch_trim_down` | `sim/flight_controls/pitch_trim_down` | nose down, repeated while held |
| centre | 27 | none | none | releasing 26/28 already stops the repeat |
| RIGHT | 28 | `laminar/B738/flight_controls/pitch_trim_up` | `sim/flight_controls/pitch_trim_up` | nose up, repeated while held |

These are each aircraft's **captain-side** electric trim commands, the pair its
yoke trim switches use. Zibo's `fo_pitch_trim_*` pair is deliberately not used.

- **It ignores the MODE selector.**  The rocker trims pitch in all three MODE
  detents, including IGN/START, where it used to be inert.
- **Direction lives in one place.**  `WINCTRL_PITCH_TRIM_COMMANDS` in
  `bridge/final.py` decides which way is which.  If it feels backwards on your
  unit, swap its two values - nothing else reads the direction.
- **A Studio binding still wins.**  `_muslimsim_observe_lab_event` consumes a
  remapped contact before the native path sees it, so no double command is
  possible and "hard-wired" means "the default until you say otherwise".

### The window reads out the trim

While the rocker is held - and once more after it is released - the RUD TRIM
numeric window shows live stabilizer units from
`laminar/B738/flight_model/stab_trim_units`, the same units the real 737 trim
indicator shows.

The window is four cells: direction glyph, tens, ones, tenths.  The captured
glyph table holds only digits, `L`, `R` and blank, and a trim setting is
neither a left nor a right, so the **leading cell stays blank**: `4.9` renders
as `"  49"`, `15.8` as `" 158"`.

- The signed rudder/aileron path is unchanged.  `-2.5` still renders `"L 25"`.
  The display functions take `signed=True` by default; only the stabilizer
  readout passes False.
- Bounds are separate, not widened.  Rudder and aileron keep
  `WINCTRL_TRIM_DISPLAY_MIN/MAX` at +/-10.0; the units readout uses
  `WINCTRL_STAB_TRIM_DISPLAY_MIN/MAX`, 0.0 to 19.9, which is what three digit
  cells can render.  Zibo's own limit is 15.8.  Above the maximum it saturates
  rather than wrapping to a smaller, believable, wrong number.
- The read is tied to the trim repeat, never polled.  Nothing is read from the
  simulator unless the rocker is being held.
- **In Practice** the rocker moves a simulated stabilizer value, 0.1 per press,
  and writes it to the window in the same units.  It is deliberately not gated
  on the MODE trim role: that gate returned silently whenever MODE sat in
  IGN/START, which is indistinguishable from a dead display.  Only the reset
  contact is still role-owned.
- **Both window modes are catalogue controls** - `rudder_trim_display` and
  `stab_trim_display`.  Every write is validated against the catalogue, so a
  window mode that is not declared there is refused, and the refusal is
  swallowed by the Practice sink and the live loop.  It fails invisibly.  The
  bridge self-test asserts both exist and stay implemented and testable.

If the window ever goes blank, drive it directly before reading any code:

```powershell
py tools\probe_winctrl_trim_display.py --hold 1.0
```

It opens the PAC interface with the bridge's own opener and writes through the
bridge's own writer, so whatever it shows is what the software would have
shown.  Studio and the bridge must be closed; they own that HID handle.

**Still on rudder/aileron:** the MODE selector and the reset contact (25).  So
MODE and reset act on rudder or aileron trim, while the rocker and the window
are both about the stabilizer.

Offline check: `python launch.py --check` runs
`_run_winctrl_trim_display_self_test`, which asserts both command names, that
the rocker maps exactly left and right, and that the two directions are not the
same command. `python tools/test_levelup_737_integration.py` separately pins
LevelUp's pair and proves the Zibo base pair was not replaced.

Live check: hold the rocker each way and watch the stab trim wheel and
`sim/cockpit2/controls/elevator_trim`.

## The control panel (2026-08-28)

`dist/MuslimSim.exe` - windowed, no console, manifested for Administrator.
Build it with `python build_exe.py`. Offline check: `MuslimSim.exe --check`
(16 checks, no hardware or simulator touched).

| Tab | What it is for |
| --- | --- |
| Devices | USB presence, manager state, per-device Reset and Power cycle, Configure, Diagnostics |
| Calibration | Live bar per axis for pedals, throttle and yoke; range and centre capture; invert |
| Throttle | The below-idle split, above |
| Displays | Live mirror of the PFP and MCDU, and the real screen restart |
| Output | The bridge's output, filterable and saveable |

Two kinds of reset, and they are not the same thing:

- **Reset / Redraw** restarts that device's manager inside the running bridge.
  Needs the bridge running.
- **Power cycle / Restart screen** re-enumerates the panel on the USB bus, so
  its firmware restarts and the WinCtrl logo appears. **Needs Administrator**:
  `pnputil /restart-device` exits 0 without elevation and does nothing, so the
  panel refuses rather than reporting a success it cannot have.

## Thrustmaster TCA Boeing quadrant (2026-08-31)

One physical unit with two enumeration-time USB identities.  The 1&2/3&4
selector emits no live joystick event, so the bank is fixed when USB
enumerates:

```text
selector 1&2 -> "TCA Quadrant Boeing 1&2" -> VID 044F / PID 040A
selector 3&4 -> "TCA Quadrant Boeing 3&4" -> VID 044F / PID 040B
```

Captured on bank 1&2 with `tools/capture_tca_boeing_one_unit_both_banks.py`,
the axis pass run twice and the button pass once.  The device declares six
axes but carries three levers: axes 0, 1 and 2 never leave their rest value.

| SDL | Control |
| --- | --- |
| axis 3 | Left slide, Captain side. -1.000..+1.000, rest +1.000 |
| axis 4 | Middle slide. Same range |
| axis 5 | Right slide, First Officer side. Same range |
| button 1, 2 | Buttons on the middle and right slides |
| button 4, 5 | Reverse levers on the middle and right slides |
| button 6-10 | Five side buttons (owner order: 9, 6, 7, 8, 10) |
| button 11, 12, 13 | Select knob, three detented positions |
| button 14 / 15 | Top knob, continuous encoder: CCW / CW |
| button 16 | Pushbutton on the knobs |

**No slide has a detent switch.**  Nothing closed during a full sweep of any
of the three levers, so reverse is the separate lever contact rather than a
below-idle band in the travel the way the WinCtrl URSA MINOR needs.

Buttons 0 and 3 complete the 0/1/2 slide-button and 3/4/5 reverse-lever runs
and closed during discovery, but were not isolated by their own prompt.  They
stay `unknown` rather than being promoted on a pattern.

The same physical six-axis / 17-button SDL interface remains selectable after
the quadrant re-enumerates as bank 3&4. Its captured controls are therefore
bindable under `bank34_*` keys. No bank 3&4 aircraft defaults are supplied:
bank 1&2 keeps the proven all-engine Zibo rules, while 3&4 is explicitly mapped
by the owner.

Two spelling rules, because breaking either one fails **silently**:

- Catalogue keys must use the bridge alias spelling - `bank12_axis_3`,
  `bank12_button_4`.  `_tca_boeing_control_aliases()` in `bridge/final.py`
  never tries a zero-padded index, so `bank12_button_04` routes nothing and
  reports no error at all.
- A control is bindable only when its catalogue `status` is `implemented`:
  `_input()` sets `remappable = (status == "implemented")`.

Offline check: `python tools/test_tca_boeing_catalog.py` - 158 checks, no
hardware or simulator touched.

### The Studio faceplate

Live keeps the V3 single-quadrant behavior. Practice composes two matching 2D
units into the optional full arrangement:

```text
AIRBRAKE | THRUST 1 | THRUST 2 || THRUST 3 | THRUST 4 | FLAPS
```

- **Handles follow the hardware.**  Travel is drawn as `(1.0 - raw) / 2.0`,
  deliberately the same expression the binding uses, so rest sits at the bottom
  stop and means idle thrust, speedbrake in, flaps up.  The panel and the
  aircraft cannot disagree about which way a lever points.
- **Every control is clickable.**  Each is tagged with its catalogue key, which
  is what `_faceplate_click` looks for.  A control the catalogue has not
  verified is drawn muted instead of being offered as mappable.
- **State is visible.**  A pressed contact lights, and the selected control
  takes the standard highlight ring.
- **Practice drag is continuous.** Clicking a handle or its slot starts a drag.
  Pointer motion moves only that handle group; it does not redraw the complete
  panel. Raw values use the same top `-1.0` / bottom `+1.0` convention as Live.
- **Posting is coalesced.** Only the newest value is sent at the live reader's
  15 ms cadence. A Practice-only server gate prevents any delayed value from
  being applied after Studio returns to Live.

If the panel ever stops responding to clicks, check for `_tag` calls first:
without them the faceplate still draws perfectly and nothing can be selected,
which is how V2 shipped.

Offline checks: `python tools/test_tca_boeing_faceplate.py` - 89 checks on a
real off-screen canvas; `python tools/test_tca_boeing_practice.py` - 20 checks
for per-pixel motion, coalescing, bank 3&4 routing, and the Test-mode boundary.

The current central SDL reader owns one physical TCA quadrant at a time. This
is intentionally unchanged because the same reader also owns PU, WinCtrl
throttle, and pedals. The two-unit Practice layout is complete; simultaneous
ownership of two physical quadrants requires a separate controlled live test.

Rendered preview: `PNG/tca_faceplate_2d.png`.

### The select knob and the top encoder

The select knob names what the top encoder adjusts.  This is behaviour, not a
binding: a binding is static per control, and encoder-clockwise means something
different at each detent.  It lives in `MUSLIMSIM TCA BOEING KNOB DISPATCH V1`
in `bridge/final.py`.

| Select detent | Encoder CW / CCW | Knob button |
| --- | --- | --- |
| Left - IAS/MACH | Steps the Zibo MCP speed dial | `spd_interv` |
| Middle - HDG/TRK | `sim/autopilot/heading_up` / `_down` | `hdg_sel_press` |
| Right - ALTITUDE | `laminar/B738/autopilot/altitude_up` / `_dn` | `alt_interv` |

Heading uses the **generic** X-Plane commands on purpose, the same choice PAP3
made: Zibo's own heading knob accelerates and coasts, while the generic pair
gives exactly one degree per physical detent.

Speed is **not** a command.  Zibo owns its MCP IAS/Mach dial and immediately
overwrites X-Plane's generic airspeed dial, so the dispatcher reads
`sim/cockpit/autopilot/airspeed_is_mach`, then read-modify-writes either
`mcp_speed_dial_kts` or `mcp_speed_dial_kts_mach`.  The step arithmetic is
`pap3_next_speed_value`, imported from the PAP3 module rather than copied, so
the two MCP speed paths cannot drift apart.

Behaviour worth knowing:

- **A saved binding wins.**  Rebind the encoder in Studio and the dispatcher
  stays out of the way entirely.
- **Before any detent has been seen, the encoder does nothing.**  There is no
  honest answer to "increase what?".  The detent is sampled at connect, so a
  reconnect does not leave it blank.
- **A release never repeats a press**, and a baseline sample never writes.

Offline check: `python tools/test_tca_boeing_knob.py` - 39 checks, no hardware
or simulator touched.

### Default lever rules, and changing them

Out of the box, one quadrant follows these rules.  Nothing needs to be bound
by hand first.

| Lever | Does | Target |
| --- | --- | --- |
| Left slide (Captain side) | Airbrake | `laminar/B738/flt_ctrls/speedbrake_lever` |
| Middle slide | Thrust, every engine | `sim/cockpit2/engine/actuators/throttle_ratio_all` |
| Right slide (F/O side) | Flaps | `laminar/B738/flt_ctrls/flap_lever` |
| Middle reverse lever | Reverse 1 | `laminar/B738/flt_ctrls/reverse_lever1` |
| Right reverse lever | Reverse 2 | `laminar/B738/flt_ctrls/reverse_lever2` |

The all-engine throttle target is engine-count agnostic, so the middle slide is
correct on a twin and on a four without any branching.

The knobs and the five side buttons are deliberately left unbound.

**Changing any of them** is normal Studio remapping: select the lever, choose a
simulator function, and the saved binding wins from then on.  Precedence is:

```text
saved user binding  >  declared device default  >  bridge dispatcher / nothing
```

An explicit **disable** is honoured and does *not* fall back to the default -
turning a lever off keeps it off.  **Restore this profile** clears saved
entries and the rules above come back.

The defaults live in `DEFAULT_BINDINGS` in `muslimsim/hardware/catalog.py`.
That table names `tca_boeing` and nothing else on purpose: every other device
falls through to its own bridge dispatcher, and adding a second device here
would change what an absent binding means for it.  A self-test enforces that.

Axis scaling: the sink computes `(1 - raw) * scale`, and the levers report
-1.000..+1.000 resting at +1.000, so `invert` with a 0.5 scale maps rest to 0.0
and full travel to 1.0.  Rest meaning 0.0 is deliberate - idle thrust,
speedbrake retracted, flaps up.  **If a lever works backwards on your unit, flip
`invert` on that one binding; it is not a code change.**

Bank 3&4 is the same physical unit but was not captured, so its controls stay
`unknown`.  To enable them: set the selector to 3&4, replug the USB, and run
the capture again.

Adding a device is one entry in `muslimsim/hardware/catalog.py`; set
`implemented=False` for hardware that is recognised but undriven.

## Portable replacement-unit behavior — Phase 2

For supported HID products, a Windows HID path change does not create a new
MuslimSim device. For supported SDL products, an SDL index, instance ID or GUID
change does not create a new MuslimSim device. The stable product key is retained
and existing Hardware Lab profiles/remaps continue to address that key.

If two physically identical SDL products are attached simultaneously and there
is no previously-valid runtime instance to disambiguate them, MuslimSim refuses
to guess by enumeration order.

## Portable driver families

Product registry entries now carry deployment-only `driver_family` metadata.
Examples: HOWALT=`wch-ch34x`, PU=`pu-composite`, WinCtrl HID panels=`windows-hid`,
TCA/pedals=`windows-game`. This field never participates in replacement-unit
identity and does not alter the existing device driver/protocol owner.

`driver_bundles.json` currently contains zero installable kernel packages.
That is intentional until a signed driver package is reviewed and pinned by
hash/signer.
Portable identity note: the live Phase-2 probe also exposes the pedals as HID `4098:BEF0`. This is now accepted as the same `winctrl_pedals` product; HID path/serial and SDL index/GUID remain runtime-only locators.

## WINCTRL 32 MCDU CAPTAIN — BB36 recovery behavior

The BB36 F0 graphical owner publishes progress after each successfully accepted
native F0 HID report. The lifecycle supervisor uses the freshest frame or F0
progress timestamp to decide whether output is alive.

On a verified output stall:
- the stale output handle is retired first;
- the current graphical page is remembered;
- no replacement output owner opens until the old output worker is gone;
- the first event gets one soft same-page reopen;
- repeated instability can escalate to BB36-only USB/PnP recovery;
- if Windows elevation prevents that recovery, MuslimSim stops the fast retry
  loop and uses a 60-second circuit/probe interval.

A physical unplug/replug clears the circuit. Keypad-only failures continue to
use the existing dedicated-input recovery and do not restart the display.

## Studio live feedback for every panel

A physical input that reaches `HardwareLab` is now visible from the common
Studio faceplate path even when the device does not publish a custom mirror.
Buttons/toggles/selectors use the latest physical state; relative rotaries use a
short recent-change indication because they have direction pulses rather than
an absolute shaft position. Device-specific displays (PAP3, FCU, AGP, HOWALT,
BB35/BB36, TCA, Moza, PU, etc.) keep their existing richer mirror and are not
overwritten by the generic state.

PDC BB62 is the important previously-missing example: its live manager exposed
buttons/axes only under `diagnostics`, so `_device_mirror()` returned an empty
dictionary. The composition layer now makes those read-only values available
without altering the PDC driver or Zibo dispatcher.


V2 also publishes the already-open private control-channel port with flushed stdout after in-memory lab wiring and before simulator-down physical output initialization. This is startup discovery only; the server, token, hardware owners, mappings, simulator dispatch and display paths are unchanged.
# ECAM follow-up — 2026-09-10

Live trial update: real BLEED imagery captured, with measured 620x620 EWD and
SD texture regions accepted by the extractor. Current installed trial config
uses EWD GL bounds [1521,2426,2141,3046] and SD [2151,2426,2771,3046].
These are for this measured 4096 atlas, not older 2048 definitions. BB35/BB36
still use their existing drawing path; no image-to-HID integration is claimed.

Deployment follow-up: local-only extractor is now installed in X-Plane's
`Resources/plugins/MuslimSimECAMTextureTrial/`. The earlier prepared/not-installed
notes describe the prior stage. No physical display transport changed. On the
next ground test inspect the native atlas/snapshot, not a guessed ECAM crop;
verify power-off black and frame time before further integration.

Live ToLiss profile additions (user-captured contacts, no guessed HID mapping):
T.O CONFIG `ecam32.raw_r01_b01_bit1` uses `AirbusFBW/TOConfigPress`;
EMER CANC `ecam32.raw_r01_b01_bit3` uses `AirbusFBW/EmerCancel`.
Saved through Studio's existing binding channel; all prior mappings preserved.
These are momentary commands routed by the existing input owner, not latched
states or new readers. No automatic T.O test, warning dismissal, or startup
command was sent. Physical press/release response needs live verification.
The local texture trial is not a BB35/BB36 raster driver and is not installed.
