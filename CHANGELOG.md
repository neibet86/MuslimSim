# MuslimSim changelog

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

Validation: all 25 catalogue entries covered; README/guide local links PASS;
mandatory known-regression suite PASS (including independent controller inputs,
PDC remap replay and active-backlight/shutdown guards). No new live test run.

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

Validation: mandatory regression suite, existing fixed-PDC packet checks and
new 3M active-backlight/shutdown checks PASS. Documentation links verified.
Owner confirmed after Studio reload: the 3M PDC backlight stays on in both
Practice and Live.

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

Validation: mandatory known-regression suite and real Tk faceplate drawing
checks PASS. Every AGP method is identical to the pre-change source.

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

Validation complete: mandatory known-regression suite PASS. All 20 controller
fixture cases PASS. With the PU connected, before/after event streams are
identical in both TCA banks (50 stationary / 2135 moving events each).
After Studio reopened, the existing bridge reported physical MOZA presence
and WINCTRL/TCA input values with the simulator disconnected. Owner confirmed: A210 stays visible and both throttle sliders move.

Validation: actual reader exercised with fake SDL controllers, independent and
combined devices, both TCA banks, moving and stationary inputs. Owner subsequently confirmed A210 visibility and both throttle sliders
after Studio reload; see the confirmation above.


## 2026-09-11 - Public collaboration preparation

Documented the present need for development help and the intended one-time
purchase model if a paid release is made later. Added contribution guidance,
component licensing notices, and issue/PR templates. No blanket open-source
license or copyright transfer was added; existing third-party terms remain.
Verified documentation links and scanned existing Git history for credential
patterns with no matches. Documentation only; device code and profiles unchanged.

## 2026-09-11 - Project-wide README

Replaced the upload-focused introduction with a project overview covering
MuslimSim capabilities, simulator and hardware scope, startup, documentation,
and development. Removed recent-device-fix details from the landing page.
Documentation only; verified all README links against the live project.

## 2026-09-11 - Initial private GitHub source upload

Prepared the canonical source, assets, documentation and offline tests for GitHub.
Local backups, credentials/scratch files, large raw captures, historical ZIP
archives and generated native build products stay local. The verified BB51
guided capture is included as a regression fixture. Modified XTextureExtractor
source is included as ordinary files; its local nested Git history is preserved.
No saved device profiles or assignments are changed.

## 2026-09-12 - WINCTRL PDC display names

The requested 3M title is now WINCTRL 3M PDC, without the firmware L suffix.
PDC display titles use WINCTRL; raw USB strings, device keys, serials, role
assignments and all controls are preserved. The configured cockpit role stays
separate from the model title. Source-only naming change; no output behavior.
Validation: shared-faceplate drawing checks and mandatory known-regression
suite PASS (hardware open-path check skipped in the offline Python runtime).

## 2026-09-11 - Full 3M BB51 map verified and installed

Final validation: mandatory known-regression suite PASS, including complete
BB51 evidence replay and 22-catalog assignment/presence checks. All ten
additional PDC, live-feedback, Practice and TCA Boeing checks PASS.


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

Validation: shared PDC tests, real Tk click/rotation checks and mandatory
known regressions PASS. BB51 draw items 117 -> 120; BB62 143 -> 140;
BB52 remains 119. No new polling work. Restart Studio to load the change;
physical BB51 VSD source capture/acceptance remains a live check.


Owner correction supersedes the earlier VSD placement: show VSD on 3M BB51
and BB52, not 3N BB61/BB62. Keep 3M endless RANGE and 3N 5..640 unchanged.
BB51 VSD is clickable and supports the existing optional source assignment;
its current catalog has no verified VSD contact, so no bit is guessed. BB52's
existing VSD source is unchanged. Saved assignments, including any earlier
BB62 learned source, are not deleted. No driver, output or power-path change.

## 2026-09-11 - Correct 3M versus 3N RANGE behavior

Validation: mandatory known regressions, shared PDC guard, real Tk canvas
checks and existing endless-RANGE suite PASS. BB51 draw items: 124 before,
117 after; BB62 remains 143 and BB52 remains 119. The new position-to-angle
step is constant work with two retained scalars and no additional timer.


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

## 2026-09-11 - Shared 3M/3N PDC faceplate and physical feedback

BB62 (the connected WINWING 3N PDC R) now uses the same flat faceplate and
control positions as the connected BB51 3M PDC L, with VSD added. The USB product
and configured cockpit side supply the title. The older BB52 faceplate/encoder
and all saved bindings retain their existing identities.

The drawing adapts BB62's existing individual selector keys without rewriting
its captured input map. VSD, CTR and RANGE 640 are selectable faceplate locations;
the current BB62 map has no confirmed named contacts for those three, so they
start without a guessed source and use the existing Assign hardware button action.
Existing raw-contact assignments remain available and are never cleared.

MINS/BARO now draw rotation and expose both directions as clickable targets.
Quick press/release pairs remain visible between status polls, selector poses
can use physical records even without a driver mirror, and generic service
"offline" does not override explicit USB presence. Missing positions no longer
schedule an endless chain of redraws. Drawing only: no hardware output path,
new reader, mapping migration, device role or power-gate change. Existing
capture-proven OFF behavior and Practice/profile separation remain unchanged.

Validation: mandatory known-regression suite PASS, including 22-catalog
reassignment/presence/simulator-off checks. PDC BB62, detent, backlight, V5.3
output contract, transport, RANGE, live feedback (39), all-device Practice
(285), Practice data plane, TCA Boeing Practice (20) PASS. V5.3's stale literal
class-field assertion was replaced by actual packet verification, including
BB51's existing 3M bytes; driver unchanged. Real Tk rendered BB51/BB62/BB52
(124/143/119 items), checked click interiors and moving MINS/BARO needles.

200-draw fake-canvas comparison: existing BB51 114 items / 0.361 ms versus new
124 / 0.695 ms per draw. Missing-position timer requests fell from 200 to 0;
new feedback work is bounded to the displayed PDC, with no new polling worker.
Running bridge confirmed the owner's BARO and WXR test and 17 distinct 3M
input records while simulator_connected=False in Practice. That verifies the
hardware-to-bridge path, not the updated running UI. Close/reopen Studio to load
the change; visual acceptance on the owner's panel remains a live check.
Backup: Backup/pdc_shared_faceplate_20260911_212956.

## 2026-09-11 - Restore simulator-independent hardware availability (BUG-61)

The connected-only filter incorrectly interpreted generic service connected=False,
offline, waiting and power labels as physical absence, and aged confirmed hardware
out after eight seconds. Those states do not establish a USB unplug. Only explicit
USB/presence evidence or USB-specific unplug states now veto inventory. Slow or
failed scans retain the last confirmed inventory; successful scans still replace
it, including empty scans. A newer scan can supersede an older unplug status.
Physical inputs remain visible in Live and Practice without a simulator. Existing
assignments, faceplates, banks, input owners and output/power gates are unchanged.
Rule 0.1 continues to darken Live outputs without aircraft power; physical input
feedback is independent. This supersedes the earlier generic-state/expiry policy.
Validation: mandatory suite PASS, including simulator-off Live/Practice physical
feedback across 22 input catalogs, throttle/pedal analog travel and Practice input,
and all-catalog sidebar availability during service offline/waiting states. Existing
Practice all-device tests: 285 checks PASS; live feedback: 39 PASS; Practice data
composition PASS; physical telemetry proxy PASS; TCA Practice: 20 PASS.
The PDC real-open branch was skipped without hidapi. No running bridge was available
for a live hardware check. Source changes require a Studio restart; EXE unchanged.
Added test_simulator_independent_hardware.py and expanded sidebar guards.

## 2026-09-11 - Connected-only device list and honest unknown-device names

Studio lists positive physical connection evidence rather than registered workers.
Explicit disconnect/USB absence overrides positive cached rows; failed/stale bridge
inventories are withdrawn and expired sources are cleared on the existing discovery
pulse. Reconnection restores the same device key. Removing a selected row cancels
its pending capture; all saved assignments, profiles, banks and faceplates remain.
Unknown pages use the reported product name instead of WINCTRL device. Logitech
headsets/audio accessories no longer qualify merely because of their brand, and
text matching cannot assign a known vendor's identity to a different USB vendor.
No hardware readers, output packets, simulator writes or power gates changed.
Rule 0.1 remains intact. Physical presence is independent of aircraft power: an
externally unpowered unit that still enumerates over USB needs a hardware power
signal to distinguish it from a connected idle unit. Detection uses existing scans.
Validation: mandatory known-regression suite PASS, including connected-only sidebar,
unplug/replug, startup-empty, stale-source expiry, accurate unknown title and headset
fixtures. Existing reassignment preservation guard PASS across 22 device catalogs.
Portable device platform: 11 checks PASS. The PDC real-open branch remains skipped
without hidapi. No GUI/hardware unplug test was performed; restart Studio from source
for live verification. Packaged EXE unchanged.
Guard: test_connected_device_list.py.

## 2026-09-11 - Optional hardware reassignment on every input faceplate

Re-assign hardware button now works for existing input locations on every device,
including MOZA, FCU/EFIS, WinCtrl throttle and both TCA banks. It listens to the
existing physical input stream and saves only the selected visual-to-source
relation after an explicit click and a new press/movement. Merely viewing a
control or arming capture does not modify a profile. Other assignments, bindings,
calibrations, faceplates, banks and hardware owners remain in place. Saved source
overrides are respected by MOZA/FCU as well. Practice cannot save reassignment.
No output path added; Rule 0.1 power behavior is unchanged.
Validation: mandatory known-regression suite PASS; reassignment guard PASS across
22 device catalogs; ECAM capture PASS; TCA catalog 158 checks PASS and TCA Practice
20 checks PASS. TCA/WinCtrl graphical layout checks skipped because the audit
runtime lacks Tcl/Tk. Source comparison confirms every drawing and TCA function
is unchanged. Live physical interaction still needs verification after Studio
restart. No running process or saved user profile was modified.
Guard: test_reassign_all_devices.py.

## 2026-09-11 - Community device profile system (Phase 1)

Adds a generic hardware layer so third-party flight hardware is recognised
in Studio and mappable without any per-device Python code.

### What was added (no existing files were changed in behaviour)

**`community/devices/` folder** — 6 JSON profiles, each describing one
third-party hardware product in the `muslimsim-device-v1` schema:
- `honeycomb_alpha_family.json` — Honeycomb Alpha / Alpha XL yoke (294B:0070)
- `honeycomb_bravo.json` — Honeycomb Bravo Throttle Quadrant (294B:006D)
- `logitech_x52_pro.json` — Logitech/Saitek X52 Pro HOTAS (06A3:0255, 06A3:0052)
- `thrustmaster_tca_airbus.json` — TCA Airbus Officer Pack (044F:0408/0409)
- `logitech_saitek_multi_panel.json` — Saitek Multi Panel (06A3:0D06)
- `virpil_vpc_alpha.json` — VPC Alpha / WarBRD-D stick (3344 family)

**`muslimsim/hardware/device_profiles.py`** — profile loader (new).
Reads all `*.json` from `community/devices/`, converts them to `ProductSpec` /
`DeviceSpec` / `ControlSpec` objects. `@lru_cache` — reads disk exactly once per
process. Fails silently when the folder is absent (packaged `.exe` builds).

**`muslimsim/hardware/generic_hid.py`** — generic driver stub (new).
Defines `GenericSDLDevice` (routes SDL axes/buttons/hats through the community
profile's control map to `HardwareLab.input`) and `GenericHIDDevice` (Phase 1
placeholder for raw-HID community panels). No hardware is opened in Phase 1;
wiring into the bridge dispatch is Phase 2.

### Minimal hooks in existing files (purely additive)

**`muslimsim/hardware/product_registry.py`** — added `_extend_with_community()`
(called once at module load). Appends community `ProductSpec` objects to
`PRODUCTS` and rebuilds `PRODUCT_BY_KEY`. Built-in keys always win; a community
profile whose key collides with a built-in is silently skipped. Backups:
`Backup/product_registry_before_community_profiles_20260911_160603.py`.

**`muslimsim/hardware/catalog.py`** — `device_by_key()` now falls back to
`community_device_by_key()` when the built-in `ALL_HARDWARE` tuple has no
match. `catalogue_snapshot()` appends community devices to its device list and
merges community default roles. Both calls are lazy-imported with a try/except
so any load error is non-fatal. Backup:
`Backup/catalog_before_community_profiles_20260911_160603.py`.

### What this changes for users

A user who plugs in a Honeycomb Alpha, Bravo, X52 Pro, TCA Airbus, Saitek
Multi-Panel, or VPC stick now sees it in Studio as a **recognised** device with
its full labelled control map — rather than "needs a control definition". They
can see all axes/buttons, create mappings, and assign default roles without any
manual configuration. Active simulator dispatch (Phase 2) is the next step.

### Safety

All 6 community profiles declare `"outputs": []` or only `"status": "unknown"`
outputs. No output packet is ever guessed. Rule 0.1 is satisfied: a new device
cannot light hardware because no output path exists for it.

### Tests

- `tools/test_community_profiles.py` (new) — 7 smoke checks: loader, USB
  lookup, alias resolution, built-in integrity, snapshot inclusion, default
  roles, no key collisions. PASS.
- `tools/test_known_regressions.py` — all pre-existing passing checks still
  pass. The PIL failure and the two moza_*_ffb authority failures pre-date this
  change.

## 2026-09-10 - Native design preserved for faster display hardware

Owner requested preservation and provided PFP3N teardown photos. Saved source,
plugin candidate, tests, crop documentation and photos under
design_archives/native_airbus_20260910_211335 with copied-file SHA256 manifest.
Prior changelog/history/device reference preserved there before this entry.
No runtime code, power behavior, firmware or device configuration changed.
Small appearance and slow/jumping refresh remain unaccepted. Archive is a
design snapshot, not a standalone installer. No hardware compatibility claimed.

## 2026-09-10 - PFD newest-update scheduler for both tapes (staged)

- PFD-only opt-in drops unsent superseded delta work and replans against a
  shadow of successfully committed rectangles, not the previous complete frame.
  Interleaves 32-rectangle left/right/centre groups so neither tape waits behind
  the other region's entire colour-sorted queue. No palette/artwork changes.
- Initial loading still completes once before illumination to prevent a moving
  source from keeping the page dark indefinitely. ECAM/ND defaults unchanged.
  Existing off/stale/self-test gates and successful-write leases remain intact;
  no extra USB owners, simulator writes or capture-rate increase.
- PASS mandatory regressions and legacy display tests. New guard verifies both
  edge bands receive new pixels in the next batch, obsolete pending target is
  replaced, shadow equals emulated pixels, erasures converge and idle emits zero
  reports. This is a correctness result, NOT measured physical speed improvement.
- Studio restart required. Installed plugin unchanged: its 2Hz capture cap and
  expensive full-page report count remain unresolved smoothness limits.
  Backup: Backup/pfd_latest_20260910_205920.

## 2026-09-10 - Slow native image transfer corrections staged (BUG-57)

- Owner measures ~17s PFP3N load and longer/intermittent MCDU completion. Last
  captured PFD/ND pixel encoding measured 5953/9361 reports, 48/95 batches and
  84/107ms offline planning/test-raster time; not live USB timings. No picture
  quality reduction or unsupported vendor bitmap opcode introduced.
- Removed repeated brightness commands from image batches/idle ticks. A
  fixture with 48 incomplete ticks plus reveal reduces 194 brightness reports
  to 4. Page/power transitions re-establish the state; failed writes aren't
  cached. This is NOT a claimed 17s-to-instant load-time improvement.
- Renew the producer demand lease during successful native USB report writes,
  throttled to 250ms, preserving BB36's existing progress/recovery callback.
  This prevents multi-second successful bursts from expiring their own demand.
  No new timer/thread/USB handle or simulator writes. Existing power/self-test
  gates and original stale-data limits remain authoritative; no valid source
  means dark. Callback and metrics hooks are removed even after write failure.
- Added image_usb_reports, image_usb_write_ms, image_usb_max_write_ms and
  image_batch_ms to host status for actual throughput evidence after restart.
  These measure host write completion, not LCD pixel acknowledgement.
- PASS: test_known_regressions.py (including 3s slow-burst regression) and
  test_toliss_displays.py. Legacy renderer report counts unchanged. Backup:
  Backup/image_transfer_pacing_20260910_204516. Studio restart required;
  installed plugin unchanged. Main raster-transport performance remains OPEN.

## 2026-09-10 - Native PFD/ND candidate installed after confirmed closure

- Verified no X-Plane, Studio or Python process remained, then replaced only
  the isolated MuslimSimECAMTextureTrial/64/win.xpl. Installed SHA256 matches
  the tested candidate: D773E1E33988E40558FC7EA969C1E9196445840BF29966AEBFD94F43D55B6123.
- Previous DLL and documentation backed up under
  Backup/native_flight_install_20260910_202214. ToLiss files, extraction
  configuration and controls were not changed. Existing DU/off/stale gates
  keep the new image path dark without valid power and current source data.
- Mandatory test_known_regressions.py passed again after installation.
  Restart/load and physical BB35/BB36 fit/motion/power acceptance remain pending;
  installation and offline tests do not establish physical display performance.

## 2026-09-10 - Native PFD/ND channels built for controlled LCD trial

- Added independent captain PFD/ND crop streams using measured 4096-atlas
  coordinates (6,2834,750) and (764,2834,750). EWD producer/reader is staged
  at (1521,2426,620); EWD is NOT added to the page-selection order. CDU and
  automatic CRUISE retain their current paths. SD v1 producer is unchanged.
- Both existing LCD workers select native PFD/ND only when the new producer
  header exists. Old plugin/absent producer retains the vector path without
  darkening it. No second HID owner, control remapping, or startup input writes.
- Uses the existing full-width viewports and committed <=200-rectangle batches;
  first image stays dark until complete. Existing connection/DU power/self-test
  gates precede imagery. Invalid/off/stale native images darken the display;
  a copy collision retains only a still-fresh complete image. Plugin stop or
  invalid aircraft/texture removes power validity. No invented telemetry.
- New streams share an aggregate cap of two readbacks/sec, round-robin only
  among demanded channels; no demand means no readback. This budget is separate
  from SD's existing 2 Hz. Synchronous GL readback remains a live-performance
  risk; this is NOT a smooth-motion or simulator-FPS improvement claim.
- Exact nearest-pixel resize measured 4.07 ms accelerated vs 26.39 ms pure
  Python on the same 750-square fixture, identical output. No colour reduction.
  Unchanged source pixels skip decoding; both owners share each channel cache.
  LCD report counts/throughput are not reduced by this decoder improvement.
- PASS: test_known_regressions.py, test_toliss_displays.py, and
  test_toliss_bb35_keys.py. New flight-image guard includes malformed headers,
  stale/off/copy states, channel isolation, absent producer, exact orientation,
  both viewport bounds, identical optional decoder fallback and zero idle writes.
  Legacy PFD/ND report counts remain 319/244 and 434/364 respectively.
- Built tools/XTextureExtractor-trial/win-native-flight.xpl, SHA256
  D773E1E33988E40558FC7EA969C1E9196445840BF29966AEBFD94F43D55B6123.
  NOT installed over the live DLL. Close X-Plane and Studio before deployment;
  physical fit, page changes, blackout/recovery, image lag and FPS are pending.
  Backup: Backup/native_flight_channels_20260910_201248.

## 2026-09-10 - Twelve native ECAM pages and full-width fit staged

- Owner photos now prove complete native BLEED on BOTH physical LCDs after
  committed batches; remaining complaints are first-load buildup and side bars.
- Verified actual ECP page commands against live SDPage and restored BLEED:
  ENG0, BLEED1, PRESS2, ELEC3, HYD4, FUEL5, APU6, COND7, DOOR8, WHEEL9,
  F/CTL10, STATUS12. Both existing owners now accept those native image pages.
  No system/control switch was operated. Automatic CRUISE remains unverified.
- Native decode now uses 640x480 rather than 448-square. BB35 uses (0,0)
  640x480; BB36 uses (0,10) 640x440 inside the existing safe bezel limits.
  Square source is fitted to the requested rectangular display area; no crop,
  palette reduction or fabricated measurements. Physical proportions need QA.
- Build the first image using existing brightness OFF and reveal only after
  the complete job; retain normal delta drawing thereafter. Once the producer
  is present, stale/wrong-page/settling frames wait dark rather than flashing
  old numerical artwork. No producer retains the old numerical fallback.
  Aircraft/DU blackout and self-test gates are unchanged; these precede images.
- Pending batches resume after 5ms instead of waiting the normal telemetry
  refresh interval. Per-batch rectangle limit and BB36 USB pacing unchanged.
  This eliminates scheduler delay, not USB transmission cost. No live latency
  claim yet: the owner must restart Studio to load these Python changes.
- Full-width current APU fixture: shared decode40.7ms; BB35 5295 reports over
  48 batches (max136), BB36 coordinate-fit emulation4916 (max127), excluding
  its separated-refresh framing overhead. Previous narrower fixture3604/31;
  figures use different live snapshots and are not a controlled speed comparison.
  Full-width first-load cost is higher; stable frames still send zero reports.
- Mandatory image/regression tests and legacy ToLiss display tests pass.
  Legacy fallback fixture now explicitly disables image routing and has a
  two-second timeout, avoiding a live simulator bypassing its mock callback.
- PFD/ND/EWD/CDU image conversion NOT implemented in this change. Current atlas
  has native PFD ATT/HDG-invalid state; moving-display throughput remains to be
  tested. Existing working PFD/ND/CDU rendering and input routes are retained.
- Backup: `Backup/ecam_fullscreen_pages_20260910_195125/`, including measured
  native atlas. No plugin DLL or simulator restart needed for these SD changes.


## 2026-09-10 - LCD image acceptance failed; bounded refresh correction staged

- Owner reports PFP3N still shows the old page and MCDU32 shows white square
  outlines despite both reporting running/live. These statuses proved worker
  activity, NOT correct physical rendering. Latest shared-memory image remains
  visually correct (6/200 C, 37/36 PSI, 180 C). Hardware transfer is unresolved.
- Identified an unverified transport assumption: 31 native drawing batches
  were flushed without LCD refresh until the final batch, creating one large
  uncommitted drawing job. Now every <=200-rectangle batch uses the established
  0x103 refresh and reasserts its first colour. BB36 retains its existing
  separated-refresh/pacing semantics. No new USB opcode, handle or control route.
  This is a staged correction, NOT a proven cause of the reported white squares.
- Both workers now expose image_active, image_pending_rects, image_commits
  and completed image_sequence. Commits count successful host writes, not
  hardware visual acknowledgements. Missing/old source still falls back to
  numeric BLEED; all existing power-off/self-test gates remain authoritative.
- Offline exact-pixel fixture: 3604 reports/31 refreshed chunks versus 3575
  reports/31 unrefreshed chunks before, peak149 vs148 reports/chunk. Idle0;
  ten-pixel change2. Tests now assert every batch commits and exercise actual
  BB35 and BB36 framing with fake USB devices. Mandatory regressions pass.
- Backup: `Backup/ecam_committed_batches_20260910_191619/`. Studio-only restart
  needed to load this correction. Photo/physical acceptance still required;
  no X-Plane restart or plugin update was performed in this task.


## 2026-09-10 - Fix BLEED mid-copy fallback flicker; expose BB36 startup error

- Live sampling found 22/600 headers in the producer's odd-sequence copy
  interval. The old reader returned unavailable for those legitimate updates,
  causing the LCD owner to abandon image drawing and restore numeric BLEED.
  Reader now retains only a previously complete, same-page frame within its
  original two-second freshness limit across a copy collision. Stable off,
  malformed/other-page headers and expired data still withdraw imagery;
  aircraft/DU blackout and self-test gates are unchanged.
- New reader returned 600/600 complete frames against the live producer.
  This fixes the identified race, not yet confirmed physical flicker: restart
  Studio to load it, without restarting X-Plane or replacing the plugin.
- BB36 currently reports only registered despite the blank display. Its
  startup exception path now publishes the exact error through the existing
  status API instead of leaving a misleading pre-open placeholder. No guessed
  recovery, USB reset, new reader or input/control change. Root cause pending.
- Mandatory regression suite passes, including busy-copy/stale/off/page guards
  and execution of the real BB36 failure handler with a fake device error.
  Backup: `Backup/ecam_copy_race_20260910_190314/`.


## 2026-09-10 - BLEED shared-image plugin installed

- Confirmed X-Plane, Studio and its bridge were closed. Replaced only the
  isolated `MuslimSimECAMTextureTrial/64/win.xpl` with the staged stream build;
  installed SHA256 matches
  `AD5C3412D25DD90FE9B5C75C36C5B69578912C4133B7121C5FBB191ED62C7F55`.
  Measured region file, licenses and all other plugins remain unchanged.
- Recoverable original DLL/config and documentation saved in
  `Backup/ecam_stream_install_20260910_184651/`.
- Existing disconnected/unpowered-DU blackout remains authoritative on both
  LCDs. This installation adds no control write or startup control sync.
- Mandatory known-regression suite passed after installation, including the
  image pixel/report guard. Live Vulkan readback, both LCDs, power transitions
  and performance still require reopening X-Plane/Studio and selecting BLEED.


## 2026-09-10 - BLEED image-to-LCD link staged; live installation pending

- Added `toliss_sd_image.py` to the two existing ToLiss display workers after
  their connectivity, actual-DU power and self-test gates. Verified SDPage=1
  can replace only BLEED with the native aircraft pixels; CDU/PFD/ND, other
  ECAM pages, FCU and input routes are untouched. This is not numerical data
  recovery. Current simulator/Studio still run the previous version.
- Plugin source adds local shared memory and demand-leased 620x620 readback,
  at most 2 Hz, instead of continuous full-4096 atlas reads or PNG writes.
  Read framebuffer/PBO/pixel-pack state is restored. Unknown/off/other aircraft,
  incompatible atlas, page transitions or readback errors invalidate output.
  One per-frame timing measurement is exported; GPU cost is not yet measured.
- Exact RGB nearest-neighbour 448-square viewport, no palette reduction or
  guessed digits. Shared image decode, per-panel changed-pixel runs and bounded
  200-rectangle batches use only proven native colour/fill/refresh commands.
  Feed stale >2 seconds or wrong SD page withdraws imagery and rebuilds the
  existing telemetry renderer. Power loss uses the existing complete blackout;
  page swaps/reconnect discard pending image jobs. No second HID owner.
- Offline captured APU-on fixture: 17.6ms shared decode; full generation/test
  raster 56.2ms; 3,575 reports over 31 chunks, maximum 148 reports/chunk;
  unchanged image 0 reports, ten changed pixels 2 reports. Lower-bound naive
  full-raster estimate was 3,451 reports before colour commands. Existing BLEED
  renderer remains 366 reports full. Full image recovery is therefore heavier
  and may take seconds: hardware throughput/latency and simulator A/B testing
  are mandatory before claiming acceptable performance or deploying all pages.
- `test_toliss_sd_image.py`, `test_toliss_displays.py` and mandatory
  `test_known_regressions.py` pass. New test verifies every sampled pixel,
  replacement/erasure, header freshness/power, page isolation, zero idle output,
  bounded batches and both workers' power/self-test ordering. Plugin builds.
- Backup: `Backup/ecam_image_link_20260910_181837/`. Close Studio and X-Plane
  before installing `win-sd-stream.xpl`; do not overwrite the loaded DLL.


## 2026-09-10 - Live BLEED texture extracted and ECAM regions measured

- Trial found texture 94 at 4096x4096. Startup snapshot contained INVALID DATA;
  a later single `XTE/png` request captured real BLEED at SDPage=1, including
  temperature digits, valve graphics and footer. No aircraft commands sent.
- Preserved startup/current atlases under
  `diagnostics/toliss-ecam/texture_trial_20260910/`. Measured PNG bounds:
  EWD [1521,1050,2141,1670), SD [2151,1050,2771,1670), both 620 square.
  Updated only the installed trial's region file and reloaded via XTE/load;
  log confirms both new regions accepted. No DLL reload or simulator restart.
- Twenty frame-period samples over approximately five seconds: mean 24.954ms,
  min 16.979ms, max 38.020ms (about 40.07 FPS reciprocal of mean). This is not
  a controlled trial-on/off comparison. Log repeatedly reports texture scale
  changes with GPU headroom near zero; cause and trial contribution unresolved.
- Actual imagery is proven for this selected page/state, not yet independent
  numeric telemetry or BB35/BB36 hardware delivery. Unpowered black, APU-on
  transitions and other pages still need live acceptance. No production
  renderer/control mapping/output authority changed.
- Backup: `Backup/ecam_texture_regions_20260910_174827/`.
- Mandatory known-regression suite passed. Live image/power/performance and
  physical-panel acceptance remain separate from these offline checks.

## 2026-09-10 - Approved local ECAM texture trial installed

- Verified X-Plane was closed and no extractor plugin/destination existed.
  Installed only `Resources/plugins/MuslimSimECAMTextureTrial/` with the tested
  local-only binary, full-atlas A321 definition and license/readme files.
  Installed SHA256 matches `0F593866E3FF6E0A899CEE431FFB774B5D3C7EC5F5DF3FE0E67E1493344B853F`.
- No existing plugin, aircraft file, Studio code or binding was overwritten.
  No network listener/continuous GPU capture; the trial window blacks out
  without valid AC-bus supply. No hardware outputs or aircraft commands added.
- Live texture discovery, crop measurement, power behaviour and performance
  remain pending the next on-ground launch. Installation is not a telemetry fix.
- Backup: `Backup/ecam_texture_install_20260910_172337/`.
- Mandatory known-regression suite passed after installation. No live FPS or
  extraction result is claimed before the next simulator run.

## 2026-09-10 - ECAM controls reviewed; local texture trial prepared

- Live ToLiss profile had 16 ECAM bindings but no T.O CONFIG or EMER CANC.
  Verified all 18 targets against the running simulator command catalogue.
  Saved only `raw_r01_b01_bit1 -> AirbusFBW/TOConfigPress` and
  `raw_r01_b01_bit3 -> AirbusFBW/EmerCancel` via the existing validated bridge
  control channel. Exact before/after profile comparison passed. No command
  was executed; physical press/release acceptance remains pending.
- Captured 573 sources GET-only, with zero read errors and 90 empty SD text
  layers. Page review and remaining provisional values are in the ECAM audit.
- Downloaded upstream XTextureExtractor commit
  `9cba63f4c2243d86d877fee85cffd5cec3e0c0a8` to an isolated tools trial folder.
  Compiled a GPL local-only variant: no networking source/startup and no
  continuous GPU readback; one-time texture snapshot retained. Its window
  blacks out when AC supply is unavailable/unknown. No hardware output path.
  Full-atlas 4096 definition is measurement-only, not guessed ECAM crops.
- Trial binary SHA256 `0F593866E3FF6E0A899CEE431FFB774B5D3C7EC5F5DF3FE0E67E1493344B853F`.
  Dependency inspection: OpenGL32, XPLM_64, KERNEL32 only. Not installed while
  X-Plane remains running. No FPS improvement or live acceptance claimed.
- Known regressions, ECAM32 button capture, typed ECAM telemetry and all twelve
  reference-page checks passed. Existing mappings and production rendering
  code unchanged; added bindings add no fixed-rate work. Backup:
  `Backup/ecam_trial_20260910_170802/`.

## 2026-09-10 - Native BLEED page-1 source test completed

- Reset only the read-only probe through Plugin Admin, with native BLEED visible.
  All three new samples reported SDPage=1. All 63 SD byte reads returned a
  single NUL; declared size 37, request lengths 36/40/256, guards intact.
  Native display meanwhile showed 32/32, 30/30 and 32/32 degrees Celsius.
- This rules out web transport alone for these missing SD text values in this
  aircraft state; it does not prove every possible export is unavailable.
  Pack1Temp/Pack2Temp stayed 0.5 (pointer values, not Celsius).
- No production code, controls or hardware outputs changed. The probe stopped
  reads automatically after sample 3; Plugin Admin was closed. Missing BLEED
  temperatures remain unresolved. No performance improvement is claimed.
- Preserved original log and prior docs in
  `Backup/sd_probe_live_20260910_165858/`.
- Mandatory `tools/test_known_regressions.py` passed after the documentation
  update. Live temperature acceptance remains failed, not replaced by this test.

## 2026-09-10 - Approved native SD probe installation

- Verified X-Plane was closed, then installed only the tested `win.xpl` in
  the new `Resources/plugins/MuslimSimSDProbe/64/` directory. No existing
  plugin, aircraft file, Studio code or control mapping was overwritten.
- Source and installed SHA256 matched. The probe has no aircraft setters,
  hardware access or illuminated outputs; logging only, three bounded samples.
- Offline probe test and mandatory regression suite passed again. Live native
  readings remain pending the next on-ground launch with BLEED selected.
- Backup: `Backup/sd_probe_install_20260910_162248/`.

## 2026-09-10 - ToLiss BLEED source research and native diagnostic preparation

- Added `docs/TOLISS_BLEED_SOURCE_RESEARCH.md`: traced old temperature columns
  to XHSI native SD text reads, reviewed GitHub/forum alternatives, and documented
  that ToLiss folder V1p8 has a V1.9.1/1696 changelog. Live API catalog contains
  16,711 refs; no verified independent six-temperature mapping was found.
- Prepared `tools/toliss_sd_native_probe/win.xpl`, source and offline harness.
  It only reads named refs and logs three samples, comparing buffer lengths;
  no aircraft commands, dataref writes, hardware or illuminated outputs.
  No recurring whole-catalog work, and no production polling/rendering change.
- Native x64 build, five exports, synthetic bounded-read/lifecycle tests and
  mandatory known regressions passed. Native-vs-REST behavior is NOT live-tested.
  Plugin remains outside X-Plane; simulator/Studio were not restarted.
- Live-image fallback has a specific obstacle: upstream A321 texture definition
  is 2048-square but the installed panel PNG is 4096-square. No blind deployment.
- Documentation backup: `Backup/toliss_bleed_research_20260910_172500/`.

## 2026-09-10 - ECAM degree rings and fixed-column SD decoding (BUG-54)

- ECAM degree signs were sent to an ASCII-only LCD encoder, producing `?`.
  Draw a small hollow degree ring using four native rectangles beside C;
  no font upload or PFD/ND/CDU changes. All SD temperature labels share this fix.
- SD colour-layer decoding now preserves embedded NUL cells as spaces instead
  of terminating the row. The existing CDU decoder remains the default.
- Live read-only diagnosis: SDline2g/5g/13g each returned 36 NUL bytes while
  LeftBleedPress and local ambient pressure returned real numbers. SDPage was
  1. This does NOT establish that all BLEED temperature boxes are fixed:
  native source availability still needs a live check. No sample numbers,
  stale-value cache, simulator commands or Studio restart introduced.
- Offline telemetry and display tests passed. BLEED full-frame traffic is
  366 reports versus 344 before; nine degree rings increase primitives from
  731 to 785. F/CTL is 270 full/116 moving reports versus 260/114. Constant
  per-glyph work, existing delta renderer and power-off blackout unchanged.
- Backup: `Backup/bleed_degree_decode_20260910_164500/`.
- Mandatory `tools/test_known_regressions.py` passed, including both new
  fixed-column and degree-ring guards. Physical LCD verification remains due;
  changes are saved on disk, not injected into the running Studio process.
- Operator confirmed native BLEED selection; repeat GETs still returned blank
  temperature rows. Page selection is ruled out as a sufficient remedy.
  WHEEL/BLEED and twelve-page reference tests also passed. The former claim
  that SD columns are a working live temperature source is withdrawn pending
  actual nonempty measurements.

## 2026-09-10 - BUG-53 exact ToLiss APU-on BLEED state

- Corrected ToLiss `LeftBleedPress`/`RightBleedPress`: they are absolute psia,
  not the gauge PSI printed on the SD. The shared BB35/BB36 adapter now
  subtracts live `barometer_current_pas`; the captured APU state consequently
  renders 37/36 PSI instead of approximately 51.
- Removed the photographed-looking substitutes for all six BLEED temperatures.
  Pack outlet 5/5, compressor outlet 210/210 and duct 190/190 now come from
  the exact green/amber columns of native `SDline2`, `SDline5` and `SDline13`.
  `PackTemp` is only the C-H pointer, and `PackFlow` is normalized from its
  native 0.8..1.2 scale. Cabin temperature, TAT and formulas are no longer used.
- Rebuilt the live APU topology: the open X BLEED valve is horizontal, the APU
  valve/branch is vertical, the full supplied manifold is green, and the static
  GND marker is present. APU pressure can no longer turn stopped-engine IP/HP
  branches green; those remain amber and disconnected. Engines-running recovery
  now also requires its own running/N2/switch facts, APU bleed off and positive
  gauge pressure. Native failure codes 2/3 never render as operative.
- The ECAM32 BLEED command already selects the real ToLiss BLEED page and both
  local displays together, which is when ToLiss publishes those native SD text
  rows. Missing rows remain amber XX rather than a retained or invented value.
- Offline verification passed telemetry, WHEEL/BLEED detail, all-reference,
  full/delta pixel and complete ToLiss display suites. BLEED is 343 HID reports
  under the 400 ceiling; the inspected APU fixture is 756 primitives under its
  780 guard. No simulator command, hardware handle or running process was used.
  Backup: `Backup/toliss_bleed_apu_telemetry_20260910_143913/`.

## 2026-09-10 - BUG-52 ToLiss GPU lamp and PU engine-start auto-return

- Wired the PU `GRD PWR AVAIL` annunciator to P7 bit 12 from the installed
  ToLiss GPU-car authority, `AirbusFBW/EnableExternalPower`. Hooking the GPU now
  sets only that confirmed lamp bit; removing it clears the bit. The established
  DC-bus gate still blacks every other output; this offered-source AVAIL lamp is
  the sole pre-bus exception. Test precedence, fail-dark behavior and the sole
  COM5 writer remain unchanged.
- Made both post-baseline PU engine-start selectors behave like their Boeing
  hardware. GRD selects ToLiss `IGN/START`; the existing separate WinCtrl engine
  master/fuel levers still introduce fuel. CONT and FLT request continuous
  ignition, while OFF returns ENG MODE to NORM and never sends an engine-master
  OFF command.
- The physical P1 solenoid releases GRD only after that engine's master is ON,
  FADEC is active, N1 is at least 18%, and native ToLiss N2 is at least 55% for
  one uninterrupted second. Because P1 is common to both selectors, simultaneous
  GRD starts wait for both engines. Requests use the existing two-attempt bounded
  path; WinCtrl ENG MODE edges are temporarily suppressed while the PU owns the
  shared Airbus selector.
- No simulator control, live process, HID output or serial port was exercised.
  Offline guards pass: PU overhead 116 checks, ToLiss WinCtrl/AGP 88, throttle
  calibration 58, starter retract, PU lights, aircraft profiles and mandatory
  known regressions; `launch.py --check` also passes without opening hardware.
  The repository-wide output inventory still reports only
  its two pre-existing MOZA blackout declarations; neither MOZA path changed.
  Backup: `Backup/toliss_pu_gpu_engine_start_20260910_131500/`.

## 2026-09-10 - BUG-51 PU overhead controls and APU gauge for ToLiss

- Added an isolated Airbus PU dispatcher to the existing ToLiss reader. PU
  selector 1 now writes IR 1; selector 2 writes IR 2 and IR 3 together. The
  physical OFF/ALIGN/NAV/ATT positions translate to Airbus OFF/NAV/NAV/ATT.
- Wired every safe logical counterpart: both wipers, six fuel pumps, FAC 1/2,
  probe/window heat, anti-ice, four hydraulic pumps, batteries, external/
  engine/APU generators, both landing lights, turnoff/taxi/beacon/wing and
  NAV/STROBE lighting, signs, both packs/flow, X BLEED and all three bleed
  switches, panel brightness and APU master/start.
- The APU gauge now uses native `APUN`, `APUEGT`, `APUEGTLimit` and `APUAvail`
  rather than stale generic X-Plane APU fields. It rises from real start EGT
  and settles exactly at physical mark 4 when ToLiss annunciates AVAIL.
- Preserved the read-only startup baseline, Hardware Lab remap/Test precedence,
  one SDL owner and one COM5 writer. Output power now follows the energized
  `DCBusVoltages` array rather than charged battery terminals. COM5 writes have
  a bounded timeout, and shutdown sends its final safe-dark frame/closes the
  port only after the sole writer has exited.
- Landing-light commands now take bounded endpoint steps; TAXI first converges
  to OFF and then selects the Airbus TAXI middle detent. The first post-baseline
  movement is therefore exact even when ToLiss began in another detent.
  `--no-agp-display`, a missing AGP HID, or unavailable AGP-only telemetry no
  longer disables the PU overhead/other resolved WinCtrl inputs.
- Live verification was GET-only: all 28 distinct datarefs and 29 command ids resolved
  in the loaded A321. Offline guards passed: new PU overhead 68 checks,
  ToLiss WinCtrl/AGP 88, throttle calibration 58, and known regressions.
  Backup: `Backup/toliss_pu_airbus_overhead_20260910_083500/`.

## 2026-09-10 - BUG-50 restored ToLiss brakes and cruise SPD/MACH state

- Restored the B930 maintained parking-brake switch with post-baseline absolute
  writes to writable `AirbusFBW/ParkBrake`: RELEASE sends 0 and SET sends 1.
  Native commands remain a fallback if that dataref is unavailable; startup
  contact discovery remains observation-only.
- Replaced momentary autobrake button animations with ToLiss's XP12 ATA 32
  annunciator array. LOW/MED/MAX ON now latch with the aircraft and extinguish
  when ToLiss disarms them; the three DECEL lamps are wired independently.
- Wired the AGP amber HOT lamp on confirmed selector 6 from ToLiss's own HOT
  annunciator. It therefore follows the aircraft's brake logic and light test,
  while every new lamp is explicitly dark on cold start, power loss and exit.
- Corrected both ToLiss physical FCU speed-mode feeds to
  `sim/cockpit/autopilot/airspeed_is_mach`. Selecting SPD at cruise now renders
  knots immediately instead of formatting the knot target as Mach `.99`, and
  selecting MACH restores the real Mach target.
- Live work was GET-only. Offline guards passed: ToLiss WinCtrl/AGP 88 checks
  and FCU/EFIS 116 checks. Backup:
  `Backup/toliss_brake_fcu_state_fix_20260910_041638/`.

## 2026-09-10 - BUG-49 split altitude cradle/drum and aligned PFD information

- Replaced the single surrounding hammer with the exact two-part structure
  requested from `ALT.png`: an open-left/open-right horizontal amber cradle for
  the larger three digits, connected at the right scale wall to a tall boxed
  smaller 20-ft drum that projects into black.
- The main digits now use the visibly larger established slot-6 face; the two
  rolling digits retain slot 4. The open cradle never crosses the grey tape's
  left edge, while the drum is the only yellow structure beyond its right edge.
- Right-aligned Mach and Mach preselect beneath the speed tape. Right-aligned
  STD/QNH, elevation and DME beneath the altitude/drum edge.
- ToLiss display verification passes at 319 recovery / 244 moving reports.
  Backup: `Backup/toliss_pfd_alt_drum_layout_20260910/`.

## 2026-09-10 - BUG-48 calibrated ToLiss A321 PFD geometry

- Narrowed both side tapes from the generic 78-pixel first pass to the
  56-pixel proportions measured from the supplied ToLiss references.
- Rebuilt altitude around the single right-side white scale wall: leftward
  100-ft ticks, `>335`/`>325` 500-ft labels, centred amber hammer, fixed live
  hundreds, and a smaller continuously rolling 00/20/40/60/80 native drum.
- The cyan selected-altitude box now has the tall rectangular body and inward
  nipple from `ALT.png`; it moves from live target/current altitude difference.
- Replaced the oversized white speed box with the narrow grey Airbus datum,
  restored an in-scale magenta selected-speed triangle, shortened the heading
  strip, added bilateral 5-degree pitch marks and a stepped aircraft reference,
  and corrected the sky/ground/tape palette against `PIC/BARO.png`.
- No telemetry source, simulator command, power authority, ND/CDU/ECAM route or
  live process changed. Backup: `Backup/toliss_pfd_airbus_rebuild_20260910/`.
- Offline verification: `tools/test_toliss_displays.py` passed at 333 recovery /
  249 moving reports; `tools/test_known_regressions.py` passed.

## 2026-09-10 - BUG-47 complete ToLiss ND route and discontinuities

- Replaced the active-leg-only limitation with a read-only parser for ToLiss's
  existing `A321_AUTOSAVED_SITUATION.qps`. It structurally locates matching
  latitude/longitude/waypoint arrays from the live WPT ID; no record number,
  photographed coordinate or decorative route is hard-coded.
- BB35 and BB36 now receive the expanded SID, enroute, STAR and approach fixes.
  Visible waypoint names render in ROSE NAV, ARC and PLAN, and blank FMGS slots
  are retained as explicit breaks instead of being silently joined.
- The 3.8 MB autosave is parsed only when its size/mtime changes; normal display
  frames reuse one shared immutable cache. Path discovery is throttled to one
  second and verifies the loaded aircraft against X-Plane's installer list.
- Live read-only proof found 33 route slots with active `TXO` at index 7 and a
  real discontinuity before `ICKEL` at index 20. No plugin injection, simulator
  write, MCDU command, HID open or live-flight reload was needed.
- Tests: `tools/test_toliss_displays.py` passed at 434 ND full-repaint / 364
  turning reports; `tools/test_known_regressions.py` passed. Backup:
  `Backup/toliss_nd_full_route_20260910_011634/`.

## 2026-09-10 - BUG-46 ToLiss ND navigation route missing

- Fixed an impossible subscription: the installed A321 1.8 catalogue does not
  publish the configured `toliss_airbus/flightplan/*` coordinate arrays, so the
  existing route renderer always received an empty plan.
- Added `AirbusFBW/WPT_Crs` and combines it with live `WPT_Dist`, active WPT ID
  and own-ship position to compute/draw the current FMGS leg in ROSE NAV, ARC
  and PLAN. `FlightPlanDashed` still controls selected-vs-managed line style.
- Full arrays remain preferred automatically if another ToLiss version exports
  them. No decorative route, simulator command, CDU key or aircraft write.
- Live GET-only proof captured `IWANS`, course 90.09°, distance 4.94 NM; the
  renderer emitted `FLIGHT_PLAN_SOLID` and `IWANS 4.9NM`.
  Snapshot: `diagnostics/toliss-ecam/20260910_004312_bug46_nd_active_leg.json`.
  Backup: `Backup/toliss_nd_active_route_20260910_064100/`.

## 2026-09-10 - BUG-45 working ECAM systems painted failed or unknown

- A live engines-running capture showed about 65 psia raw BLEED pressure
  (approximately 51 PSI gauge), both FADECs active and
  all three hydraulic systems at 3000 PSI while the renderer kept BLEED/HYD
  valves amber. Effective bleed-open state now uses live switch plus manifold
  pressure; normal closed HP valves remain green, and pressurised HYD fire
  valves render green/vertical.
- BLEED now receives live/derived temperature fields; ENGINE now receives oil
  quantity and provisional moving vibration values; ELEC now receives battery
  and TR amps, generator load/voltage/frequency and provisional IDG temperature.
- Corrected current-A321 fuel pump code 3 on a full operating wing tank from
  amber `LO` to a green square with vertical line.
- Proof snapshot/render: `diagnostics/toliss-ecam/20260910_000816_bug45_engines_working.json`
  and `PNG/toliss-ecam-telemetry/20260910_000816_bug45_engines_working/`.
  Backup: `Backup/toliss_ecam_working_systems_20260910_001210/`.

## 2026-09-09 - BUG-44 remaining ECAM telemetry was masked or unsubscribed

- Reversed the over-conservative adapter policy that erased live ECAM footer
  TAT/SAT/GW, both BLEED pressures and plausible page-specific telemetry.
  Values remain simulator-driven; no number from a reference image is used.
- Added page-scoped live mappings for all six WHEEL tire pressures, FUEL tank
  temperatures, COND selector pointers/cargo temperatures, PRESS active SYS,
  APU bleed pressure, cockpit oxygen pressure, ELEC TR/bus-derived voltages,
  and all 90 ToLiss `SDline1..18` colour layers. Empty native STATUS layers
  now produce NORMAL; populated layers render their native text/colour.
- Exact but undocumented array/code interpretations are marked provisional in
  code and tests. A missing signal is still XX; no commands, HID access,
  aircraft writes or unsafe Studio restart were performed.
- GET-only proof: `diagnostics/toliss-ecam/20260909_234552_current_observed_bug44.json`;
  rendered proof: `PNG/toliss-ecam-telemetry/20260909_234552_current_observed_bug44/`.
  Backup: `Backup/toliss_ecam_provisional_telemetry_20260909_234036/`.

## 2026-09-09 - BUG-43 ELEC live telemetry restored

- Fixed the ELEC page's audited adapter, which was forcing every electrical
  source and bus to unknown after invalid page-flag mappings were removed.
  Batteries now use ToLiss `BatVolts`; AC/DC bus colours use the actual voltage
  arrays; engine-generator connection, APU/external source and bus tie use the
  published SD connection fields. Both BB35 and BB36 share this page-local path.
- Battery amps, TR amps/volts, generator load/volts/frequency and IDG temperature
  remain XX because current ToLiss values/indices are not proven. Generic
  X-Plane electrical readings were observed disagreeing with ToLiss and are not
  substituted. No screenshot number is a telemetry fallback.
- The source bitfields are corroborated by the public XHSI QPAC decoder. Array
  ordering and all abnormal electrical configurations still require supervised
  native-display acceptance; the audit states that limit explicitly.
- Existing display BLACK/OFF and self-test gates, FCU/CDU/keypad and other ECAM
  pages are unchanged. No simulator command, HID access or Studio restart.
  Backup: `Backup/toliss_elec_telemetry_20260909_232652/`.
- Fresh GET-only proof: `diagnostics/toliss-ecam/20260909_232907_current-observed-elec-fix.json`
  captured 568 actual fields. The rendered ELEC page shows BAT 1/2 at the live
  rounded 27 V and all presently powered primary buses green. The adapter
  snapshot also confirms disconnected engine feeds and the current APU/tie
  source state. Passed telemetry,
  page-scoping, all 12 reference/delta frames, display performance and mandatory
  known regressions; maximum remains BLEED 310 reports.

## 2026-09-09 - BUG-42 WHEEL/BLEED detail correction and valve watchdog

- WHEEL now has a full-height uppercase W without changing the shared font,
  three telemetry-dependent hatched down-lock triangles, the Y N/W STEERING
  indication and centre ANTI SKID / G NORM BRK / Y ALTN BRK / ACCU ONLY /
  AUTO BRK block. Low hydraulic supply drives the limited braking model;
  this is NOT a verified full ToLiss BSCU/fault decoder. Tire PSI stays XX
  until its array mapping is proven. No reference-picture numbers are used.
- BLEED now has four pack arcs, left-foot valve connections and separate
  IP/HP branches when engine bleed is closed. Actual engine valve indication
  connects each branch independently. The isolated centre symbol follows
  XBleedInd provisionally (horizontal closed, vertical open), NOT its switch.
- Corrected FUEL pump layering so opaque LO text cannot erase its amber box
  and the tank outline cannot cross through the pump interior.
- At the owner's request, a temporary GET-only watchdog samples both actual
  X/APU bleed indications and their switches every 0.5 s, for four hours.
  Only baseline/changes/errors are logged; a five-minute task follow-up stays
  quiet on unchanged state. A dataref edge alone NEVER validates the native
  symbol mapping; both orientations require native-display confirmation.
  See `docs/TOLISS_BLEED_WATCHDOG.md` for scope, evidence and stopping.
- Existing BLACK/OFF gating, FCU/CDU/keypad/PFD/ND ownership and startup
  reconciliation are unchanged. No existing Studio/simulator process was
  restarted; the sole new process is the requested read-only diagnostic.
- Same offline fixture: BLEED full redraw 266 -> 310 HID reports (400 ceiling);
  PFD 274/180, ND 427/356 and F/CTL 260/114 full/moving remain unchanged.
  The watchdog's fixed five-field work does not grow with the device catalogue.
  WHEEL/BLEED full and incremental frames match pixel-for-pixel; idle is silent.
- Guards: `test_toliss_wheel_bleed_details.py` is included in known regressions;
  all detail, telemetry, twelve-page pixel, display and known-regression tests
  passed, as did BB35 keys (71/142), FCU (110), aircraft isolation, BB36 recovery
  (26), and launch --check. Native-display/live all-state acceptance is pending.
- Backup: `Backup/toliss_wheel_bleed_20260909_223510/`. The recorded-telemetry
  PNG review was regenerated; reference photographs and sample values are untouched.

## 2026-09-09 - BUG-41 audited ECAM sources and simulator-owned self-test

- Audited the running ToLiss A321 through GET-only telemetry, installed
  manuals and public Airbus integration source. Removed SDFUEL/SDELEC page
  flags masquerading as quantities/volts; corrected measured cabin sources,
  A321 tank mapping, actual pack valves, FADEC/APU validity, surface availability,
  additional doors/windows/slides and low-pressure colours. Unsupported
  engineering values stay unknown, never photo-derived. Exact parity is NOT
  complete: see `docs/TOLISS_ECAM_TELEMETRY_AUDIT.md` for every remaining page.
- Both LCD owners now follow ToLiss's real DU countdown and brightness for
  SELF TEST IN PROGRESS / (MAX 40 SECONDS). No app-owned 40-second timer.
  Missing/disconnected data, no AC supply, or display brightness OFF produces
  the existing BLACK/OFF output. Charged batteries alone no longer prove
  display power. Per-DU supply routing still needs live acceptance.
- No running process restarted, hardware opened or aircraft controls changed.
  FCU/keypad/PFD/ND rendering and aircraft ownership boundaries are preserved.
- Performance: PFD 274/180 and ND 427/356 full/moving reports unchanged;
  F/CTL 255/113 before, 260/114 after; maximum SD BLEED 266 unchanged on the
  same offline fixture. Per-tick snapshot work now covers the selected page
  (CDU 3, ENGINE 23, FUEL 20, F/CTL 34 fields), not all 247 prior feed fields.
  A 10,000-unrelated-field guard passes. One shared telemetry connection remains.
- Passed telemetry/self-test tests, all twelve layouts/full-vs-delta pixels,
  display regressions, BB35 71-key/142-phase checks, FCU 110 checks, aircraft
  isolation, BB36 26 recovery checks, known regressions and launch --check.
  Battery/APU/engine/flight native-display acceptance remains outstanding.
- Backup: `Backup/toliss_ecam_telemetry_20260909_220055/`. Snapshot-rendered
  previews are separate from samples; the renderer requires an explicit mode.

## 2026-09-09 - BUG-40 reference-shaped ToLiss ECAM pages

- Replaced the twelve generic SD page bodies on BOTH BB35 and BB36 with
  code-native synoptics based on the owner's `PIC/` screenshots: ENGINE,
  BLEED, CAB PRESS, COND, ELEC, HYD, FUEL, DOOR/OXY, WHEEL, APU, F/CTL and
  STATUS. Shared white title rules and TAT/SAT/ISA, clock and GW footer.
  The photographed perspective/bezel is not baked into the instrument face.
- F/CTL keeps all ten actual ToLiss spoiler outputs, separate ailerons and
  elevators, rudder, trim and hydraulic colours. WHEEL reuses those spoiler
  outputs. Supplemental inputs add cockpit temperature and explicit kg/sec
  fuel flow converted to kg/min; cabin delta-pressure, landing elevation and
  vent positions reuse existing subscriptions. No second telemetry/HID owner.
- Unmapped engineering values are amber XX. STATUS does not infer NORMAL
  from acknowledged master alerts. Full STATUS text, ISA deviation, oil quarts,
  fuel used, oxygen/tire pressures and several electrical/duct/pump/door
  variant states still need verified mappings; this is NOT a claim of complete
  ToLiss telemetry or pixel-perfect live parity. Older SD-array mappings remain
  documented legacy assumptions, not newly verified by these screenshots.
- All existing font resources, PFD/ND/CDU renderers, FCU and keypad command
  routes are unchanged. The existing connection/power gate still blacks both
  displays for unpowered/unknown/disconnected aircraft and on normal shutdown.
  No running bridge was restarted and no live simulator command was issued.
- Measured native reports, same offline fixture: maximum ECAM full redraw
  299 -> 266; F/CTL 229 -> 255 full and 79 -> 113 moving (additional reference
  brackets, hydraulic boxes and rudder geometry). New narrow F/CTL guards are
  270/125; the existing 400-report overall SD ceiling is unchanged. PFD stays
  274/180; ND stays 427/356. Immutable line runs are cached, same-value frames
  remain delta-suppressed, and only the selected page is rendered.
- Passed: `test_toliss_ecam_reference.py`, `test_toliss_displays.py`,
  `test_known_regressions.py`, `test_toliss_bb35_keys.py` (71 keys/142 phases),
  `test_fcu_efis_toliss.py` (110 checks), `test_aircraft_isolation.py`,
  `test_bb36_recovery_v7.py` (26 checks), and `launch.py --check`.
  Native-glyph previews were reviewed and border/label collisions corrected.
  All twelve native-font frames also match pixel-for-pixel between full and
  incremental redraws after telemetry changes; idle updates emit no redraw.
  Physical BB35/BB36 visual/telemetry acceptance remains pending a safe restart.
- Backup: `Backup/toliss_ecam_reference_20260909_211024/`.
  Offline example images: `PNG/toliss-ecam-reference/`; sample values, not a
  captured flight. The originals in `PIC/` were not modified.

## 2026-09-09 - BB35 ToLiss CDU keypad restored

- The previous BB35 page-deck change left input display-only and discarded
  every key except the slash shortcut. The owner's requested keypad now reads
  all 71 captured BB35 positions and sends the corresponding real ToLiss
  MCDU1 commands. It operates with BB36 absent. Both screens still mirror the
  captain CDU, so either keypad's page changes appear on both.
- Reused the existing ToLiss command/gesture loop with default-preserving
  parameters for BB35's distinct physical indices (decimal 38, slash 69).
  Single decimal/slash taps reach the CDU; triple-period toggles CDU/PFD and
  double-slash cycles the complete deck. Boeing-only key legends are translated
  in the explicit table in DEVICE_REFERENCE.md; EXEC is DIR TO, never a fake
  Airbus INSERT. BB36 and all Boeing command maps retain their defaults.
- The existing BB35 HID reader queues only changed key edges. Studio observes
  them with route=False, preventing duplicate dispatch. Initial held keys are
  baseline-only, repeated reports do not add presses, restart drops old queued
  events, shutdown releases commands still held by this keypad, and unresolved
  commands/connection failures have a visible keypad status field.
- No new renderer, telemetry subscription or power output was added. The
  shared aircraft-power gate still blacks BB35/BB36 when unknown, disconnected
  or unpowered, and their normal shutdown still clears and darkens the panels.
  Command IDs resolve once per connection (69 unique IDs); the recorded
  71-key sweep produces exactly 142 command phases despite duplicate reports.
- Backup: `Backup/toliss_bb35_keypad_20260909_204718`. The new BUG-39 guard
  passes all key/gesture cases and actual startup/shutdown with fake hardware
  and no BB36. Passed: ToLiss display/power guard, BB36 recovery (26 checks),
  aircraft isolation, known regressions and launcher check. An all-key replay
  against the rollback copy proves BB36 is identical before/after (144 command
  phases, 72 resolved IDs across its 74 positions). Display report budgets
  remain PFD 274/180, ND 427/356 and F/CTL 229/79, with ECAM maximum 299.
  The running Studio uses this source tree; restart it when convenient, then
  physically check BB35 INIT REF, letters/numbers, LSKs, CLR and page gestures.

## 2026-09-09 - BB35 gains the complete ToLiss CDU and ECAM deck

- Removed the ToLiss-only BB35 two-page restriction. BB35 now starts on CDU;
  double-SLASH cycles PFD, ND, ENG, BLEED, PRESS, COND, ELEC, HYD, FUEL, DOOR,
  WHEEL, APU, F/CTL, CRUISE, STATUS and back to CDU. Captured ECAM32 page
  buttons now select their matching system page on both BB35 and BB36.
- BB35 remains display-only. It consumes the already shared, deduplicated
  ToLiss feed and keeps its existing sole HID/canvas/diff-cache owner, so no
  second MCDU key dispatcher, simulator writer, WebSocket or fixed-rate scan
  was added. BB36 command ownership and its double-SLASH/triple-PERIOD behavior
  are unchanged.
- The BB35 ToLiss opener opts into the combined coded-display font containing
  the isolated slot-2 CDU glyphs. Its default parameter remains the former
  PFD/ND font, preserving every non-ToLiss BB35 caller. The combined resource
  is still the byte-identical established font prefix plus the CDU slot.
- `AirbusFBW/BatVolts` remains the authority for both panels. Unknown,
  disconnected, unpowered and shutdown states still clear the retained BB35
  framebuffer and switch its own brightness channels off.
- Rollback backup: `Backup/toliss_bb35_full_display_deck_20260909_201903`.
  Passed offline: `tools/test_toliss_displays.py` (BUG-38 page-cycle, direct
  selection, BB35 CDU/system painter and blackout ownership, and combined-font
  guards; PFD 274/180, ND 427/356, ECAM maximum 299, F/CTL 229/79 reports),
  BB36 recovery (26 checks), aircraft isolation, known regressions, ToLiss
  WinCtrl/AGP (69 checks), native PFP self-test and `launch.py --check`. A full
  Studio restart and live BB35 hardware check remain required.

## 2026-09-09 - ToLiss FCU altitude follows the selected dial

- Replaced the ToLiss physical-FCU and WinCtrl CTRL-page altitude source with
  `sim/cockpit2/autopilot/altitude_dial_ft`. A read-only live snapshot proved
  the fault exactly: the former PFD/internal target remained `22000` while
  both X-Plane selected-altitude datarefs and the virtual FCU were `8000`.
- No input mapping, encoder, display formatter, managed-dot state, VOR/ADF
  selector or Boeing path changed. This swaps one existing 0.2-second read,
  adds no polling, and retains delta-only output plus the complete power-off
  blackout.
- Rollback backup: `Backup/toliss_fcu_selected_altitude_20260909_193929`.
  Passed offline: 110-check ToLiss FCU/EFIS guard, BA01 Zibo semantic guard,
  ToLiss WinCtrl/AGP, aircraft isolation, known regressions and
  `launch.py --check`. A Studio restart and live selected-altitude sweep remain
  required.

## 2026-09-09 - ToLiss managed FCU windows and Mach source corrected

- Corrected the BA01 Airbus managed presentation so `SPD/MACH` and `HDG/TRK`
  show three dashes plus their large managed dots, while `V/S/FPA` shows its
  five-dash neutral field. ToLiss `SPDdashed` and `VSdashed` are presentation
  states, not commands to electrically blank those windows.
- Added ToLiss-only dashed fields to the shared BA01 renderer. They default
  off, so the existing selected-number presentation and exact Zibo/legacy
  packets are unchanged. Aircraft power loss still blanks every digit, title,
  dot, lamp and backlight.
- Replaced the ToLiss FCU/AGP speed input with the unit-aware
  `sim/cockpit/autopilot/airspeed`. A live cruise read proved the old PFD
  source was `257.7408` knots-equivalent while MACH was active and the real AP
  dial was `0.7781`; treating the former as Mach caused the observed `.99`
  saturation. Heading managed state now suppresses its stale selected number
  and shows the same dashed/dot convention as the virtual FCU.
- The capture-proven VOR/ADF selector writes were not changed. The exact twelve
  ADF/OFF/VOR mappings remain pinned by the FCU test. A direct comparison with
  the rollback copy confirmed four legacy, selected-Airbus and power-off
  states remain byte-for-byte identical. The fix swaps one existing polled
  source and adds no fixed-rate work; stable frames remain delta-suppressed.
- Rollback backup: `Backup/toliss_fcu_managed_windows_20260909_185101`.
  Passed offline: 108-check ToLiss FCU/EFIS guard, BA01 Zibo semantic guard,
  ToLiss WinCtrl/AGP, aircraft isolation, known regressions and
  `launch.py --check`. The Tk faceplate test skipped because the bundled
  Python runtime has no Tcl. The older generic `test_agp_radio_page.py`
  remains stale against its unrelated RADIO/NAV V2 expectations; none of its
  failing mode/text helpers changed here. A Studio restart and live cockpit
  comparison remain required.

## 2026-09-09 - BB36 gains the complete ToLiss display deck and live F/CTL

- Expanded the BB36 ToLiss route to `CDU`, `PFD`, `ND`, `ENG`, `BLEED`,
  `PRESS`, `COND`, `ELEC`, `HYD`, `FUEL`, `DOOR`, `WHEEL`, `APU`, `F/CTL`,
  `CRUISE` and `STATUS`. CDU remains the startup page; double-SLASH walks the
  graphical deck and triple-PERIOD retains the direct CDU/PFD toggle. BB35 is
  deliberately unchanged and still alternates only PFD/ND.
- Replaced the F/CTL placeholder with an Airbus-shaped code-native synoptic.
  All ten spoilers, both ailerons, both elevators and the rudder now follow the
  exact `anim/*` outputs used by the installed ToLiss A320 and A321 exterior
  models. Pitch/yaw trim and Green/Blue/Yellow hydraulic pressure are live as
  well. ELAC/SEC are fixed page labels only; no false green computer status is
  invented because this aircraft build exposes no reliable status array.
- Added the automatic Airbus CRUISE summary and made the permanent
  TAT/SAT/GW/UTC strip part of every lower-SD page. System titles now use a
  clean centered Airbus-style heading and status rows retain a full character
  gap between labels and values.
- Preserved the existing `AirbusFBW/BatVolts` authority, disconnect handling,
  differential repaint, page-cache invalidation and shutdown blackout. Runtime
  output remains native F0 graphics/text; PNG files are QA previews only.
- Synchronized two stale ECAM32 guards with the already capture-proven panel
  definition: eighteen labelled Airbus keys plus four physical blank keycaps,
  two of which are deliberately available only from the inspector because no
  panel location was captured. This is test-only; no ECAM32 runtime mapping or
  output changed.
- Rollback backup: `Backup/toliss_bb36_ecam_fctl_20260909_170727`. The expanded
  display guard checks the entire BB36 cycle, exact A320/A321 surface sources,
  translator contracts, page geometry and output traffic. Measured recovery
  traffic is at most 299 reports across the ECAM deck; F/CTL is 229 full / 79
  moving reports, below its 250 / 100 ceilings. The guard-only sync is backed
  up at `Backup/ecam32_guard_sync_20260909_174111`.
- Passed offline: ToLiss display, FCU/EFIS, shared-PFD telemetry, BB36 recovery,
  aircraft isolation, complete WinCtrl controls, ECAM32 capture/layout, PFP
  native self-test, PDC output authority, known regressions and
  `launch.py --check`. A powered BB36/ToLiss control sweep remains the required
  live-cockpit check.

## 2026-09-09 - ToLiss PFD silhouette, native FMA and EFIS bearing sources

- Rebuilt the 640 x 480 ToLiss PFD proportions from the installed ToLiss
  manuals and the owner's valid/invalid screen crops: three-row FMA, narrow
  speed/altitude tapes, stepped-rounded attitude aperture, split red ALT
  failure boxes, tapered V/S scale/failure flag, low heading strip, Airbus
  hundreds labels and a shaped green/yellow current-altitude window.
- Replaced the partial FMA enum presentation with ToLiss's nine native
  full-width colour layers (`FMA1*`, `FMA2*`, `FMA3*`). The aircraft now owns
  active/armed text and colour; older captures retain a narrow fallback.
- Wired all four physical three-position EFIS bearing selectors through the
  loaded A320/A321 `ckpt/fcu/adf*{Left,Right}/anim` controls using the proven
  absolute sequence ADF=0, OFF=1, VOR=2. Zibo/LevelUp dispatch was not edited.
- Added native VOR/ADF identifiers, validity, bearings and VOR DME to the ND.
  NAV1 draws the single pointer, NAV2 the double pointer; source labels occupy
  the lower corners and PLAN correctly suppresses heading-relative needles.
- Corrected the ToLiss active flight-plan route from magenta to green, clips it
  at each mode's selected-range boundary, and follows `FlightPlanDashed` when
  selected heading takes the aircraft off the managed path. The loaded plan is
  guarded in ROSE NAV, ARC and PLAN.
- Rollback backup: `Backup/toliss_pfd_nd_efis_20260909_154432`. Offline guards
  currently measure 274 full / 180 moving PFD reports and 427 full / 356
  turning ND reports, below the existing 290 / 450 / 375 ceilings. Preview
  PNGs remain QA-only; runtime still sends code-native F0 primitives.

## 2026-09-09 - ToLiss takeoff, flap-limit and ILS symbols become real PFD features

- Added live V1 and V2 subscriptions alongside the existing VR source. The PFD
  now renders Airbus takeoff symbols as cyan `1`, cyan ring and magenta target
  triangle, and obeys ToLiss's explicit `show_to_speeds` visibility output.
- Completed the configuration-speed layer: green F/S and green-dot cues, amber
  VFE-next double bar, VLS/alpha-protection regions and a red/black VMax strip.
  VMax stays driven by ToLiss's display-ready value, so flap/gear and aircraft
  structural limits change the strip without a second hard-coded calibration.
- Replaced the first-pass square LOC/G/S markers with clean native magenta
  diamond glyphs and retained the LS-gated white deviation scales. Added native
  ring/triangle glyphs to the isolated slot-3 coded-display font; runtime still
  loads no PNG.
- Added `docs/TOLISS_DISPLAY_COVERAGE.md` and removed an inaccurate reference
  claim that treated unimplemented PFD/ND features as complete. The matrix now
  separates rendered/guarded features from the remaining Airbus/ToLiss backlog.
- Rollback backups are
  `Backup/toliss_pfd_speed_ils_20260909_143044` and
  `Backup/toliss_pfd_diamond_glyph_20260909_145415`. Offline ToLiss display
  checks pass at 286 full / 195 moving PFD reports and 424 full / 353 turning
  ND reports. Code-native takeoff, approach-ILS and clean-limit previews were
  visually checked. A powered live ToLiss/BB35/BB36 comparison remains required.

## 2026-09-09 - ToLiss PFD/ND and full-size MCDU reach both colour displays

- Reworked the existing code-native ToLiss PFD instead of replacing it. It now
  uses the compact per-character native-font packing proven on the Zibo PFD,
  cleaner symmetric bank marks, a thin right-pivoting V/S needle and independent
  Airbus validity zones. Invalid captain IAS, attitude, altitude or heading now
  produces the matching red `SPD`, `ATT`, `ALT`, `V/S` and `HDG` presentation;
  valid telemetry restores the normal tapes without restarting Studio.
- Rebuilt the ToLiss ND around Airbus ARC, ROSE and true north-up PLAN geometry.
  ARC and PLAN have two scale rings, range responds to the live EFIS selector,
  active route/waypoint data is projected at that scale, and compact top/bottom
  text stays inside the 640 x 480 safe area. `CaptMAPAvail` now produces the red
  `HDG` / `MAP NOT AVAIL` presentation. `GPSPrimMessCapt` independently produces
  green `GPS PRIMARY` or amber `GPS PRIMARY LOST`, and stale GS/TAS/wind values
  are replaced by dashes while the map source is invalid.
- Added a persistent BB35 ToLiss display owner. BB35 double-SLASH switches PFD
  and ND while BB36 retains its MCDU and full Airbus secondary-page sequence.
  Both LCDs share one deduplicated ToLiss WebSocket feed but retain separate HID
  handles, native canvases and dirty-region caches. A duplicate-dataref fan-out
  fix ensures captain heading/validity updates reach both PFD and ND consumers
  instead of silently freezing whichever local key lost the reverse lookup.
- Enlarged the ToLiss MCDU to the physical 24 x 14 grid using an isolated native
  23 x 29 font slot. The existing Zibo/LevelUp font resource remains the exact
  prefix of the combined resource and is not changed. Runtime PFD, ND and MCDU
  pages remain native drawing/text commands; preview PNGs are offline QA only.
- `AirbusFBW/BatVolts` is shared output authority for BB35 and BB36. Unknown or
  unpowered state clears both retained framebuffers and turns brightness off;
  reconnect/page changes invalidate the differential cache; shutdown blacks
  both displays. Production BB36 also stays black when its optional live mirror
  is disabled, because no telemetry worker remains to prove electrical power.
- Created rollback backup
  `Backup/toliss_display_refinement_20260909_122801`. The new display guard,
  ToLiss FCU/EFIS, complete WinCtrl controls, throttle calibration/probe,
  faceplate readability, aircraft isolation, shared PFD telemetry, BB36 recovery,
  PDC authority, native PFD self-test, known regressions and `launch.py --check`
  pass. Measured native costs are PFD 288 reports for recovery / 202 for a moving
  frame and ND 424 for recovery / 353 for a turn. The repository-wide authority
  inventory still reports only its recorded untouched MOZA declaration gaps.

## 2026-09-09 - ToLiss now has two trim roles, two AGP utility modes and paced RST tuning

- Removed the invented AILERON role from the ToLiss WinCtrl cycle. The
  IGN/START knob push now alternates only PITCH and RUDDER, RESET centres only
  rudder, and the B930 LCD follows only those two real Airbus roles. The
  established Zibo/LevelUp three-role data and commands remain untouched.
- Removed NAV from the ToLiss AGP gesture. CLOCK remains home and successive
  TERR ON ND holds now cycle CLOCK -> RADIO -> CTRL -> CLOCK. The ToLiss NAV1
  datarefs, transfer command, state and unreachable render branch were removed;
  Zibo retains its independent RADIO -> CTRL -> NAV order.
- Rechecked `captures/knobs.pcapng`: the RST signed counter advances losslessly
  one count at a time. The apparent five-value jumps came from several native
  commands being issued between LCD readbacks, so ToLiss RADIO now retains all
  pending RST counts in order and drains one native fine command every 0.06 s.
  Fast rolls remain queued instead of being divided or discarded, while each
  intermediate radio step gets a display opportunity. Deliberately leaving
  RADIO cancels only commands that have not yet been sent.
- Updated the ToLiss Studio faceplates: the trim practice push has two roles,
  the AGP title and windows distinguish CLOCK/RADIO/CTRL, and the TERR label
  reports the terrain switch itself rather than pretending it is a NAV mode.
- Created rollback backup
  `Backup/toliss_two_trim_two_agp_modes_20260909_113441`. The dedicated ToLiss
  guard passes 69 checks. FCU/EFIS, ToLiss throttle calibration/probe, throttle
  and AGP faceplates, AGP quick reference, FCU lab/layout, both startup/Practice
  authority guards, known regressions and `launch.py --check` all pass. The
  repository-wide authority inventory still reports only the same two recorded
  MOZA blackout declaration gaps (`moza_a210_ffb`, `moza_ab6_ffb`); neither
  device or output path was touched here.

## 2026-09-09 - Complete ToLiss WinCtrl quadrant, AGP modes and fixed-width FCU

- Wired the WinCtrl B930 quadrant to native ToLiss A320/A321 controls beyond
  the already-working thrust levers: both engine masters, the three-position
  CRANK/NORM/IGN-START selector, speedbrake including the Airbus `-0.5` ARM
  gate, all five flap detents, parking brake and both red thrust-lever
  A/THR-disconnect buttons. No Laminar/Zibo command enters this profile.
- Decoded the separate IGN/START knob push from the owner's `MODE.pcapng`.
  Its only change is report byte 3 mask `0x80`, or one-based B930 button 24.
  Each press advances the RUD TRIM rocker through STAB, RUDDER and AILERON;
  the physical four-cell window briefly names the role and then shows its live
  value. CRANK/NORM/IGN-START remain real engine-mode contacts and no longer
  double as trim selection in ToLiss.
- Kept CLOCK as the normal AGP display. Holding TERR ON ND for 0.65 seconds
  cycles CLOCK -> RADIO -> NAV -> CTRL -> CLOCK without changing the terrain
  switch. RADIO drives ToLiss RMP1, NAV drives captain NAV1 standby/transfer,
  and CTRL moves the ToLiss FCU speed, altitude and heading rotary inputs.
  A short TERR press retains its real terrain-toggle action.
- Added a ToLiss-only FCU numeric option so IAS and HDG are always three
  digits (`001`) and ALT is always five (`00001`). The legacy/Zibo packet is
  byte-for-byte unchanged.
- Preserved one HID/SDL owner and Hardware Lab binding precedence. Startup
  maintained contacts are observation-only; thrust, flap and speedbrake use
  independent read-current/reach-or-cross pickup. `AirbusFBW/BatVolts` is the
  single output authority: AGP, B930 backlights/trim window and BA01 lamps and
  digits are dark cold-and-dark, stale prior-aircraft digits are erased, and
  shutdown explicitly blacks the panels out. The new fixed-rate work is
  bounded at four power reads per second and one trim read per second while
  idle (ten only while the rocker is held); it adds no catalogue scan, full
  state redraw or second input reader.
- Added `tools/test_toliss_winctrl_controls.py` (59 hardware-free checks) and
  extended `tools/test_fcu_efis_toliss.py` to 83 checks with exact fixed-width
  and unchanged-legacy display packets. ToLiss throttle/calibration, faceplate,
  AGP/FCU layout, launch and known-regression guards also pass. Two older tests
  still contain recorded stale Zibo expectations: the smooth-axis/trim test
  expects an old double-escaped Studio caption and historical selector order,
  while the AGP test expects the pre-three-page sequence/formatter. This change
  does not rewrite working Zibo behavior to satisfy them.
- Both bridge-only startup/Practice authority guards pass. The repository-wide
  authority inventory still reports the same two pre-existing MOZA declaration
  gaps (`moza_a210_ffb`, `moza_ab6_ffb`) already recorded on 2026-09-08; no
  MOZA file or output path was changed here, and the new ToLiss blackout is
  pinned independently by BUG-30's guard.

## 2026-09-09 - WinCtrl ToLiss throttle faceplate is clean and readable

- Rebuilt the crowded top section into three separate visual bands: title and
  calibration action, a dedicated calibration-status strip, and the two-engine
  ruler. The instruction under the WinCtrl title can no longer sit behind the
  first slider.
- Replaced twelve repeated `raw -> target` micro-labels with larger two-line
  detent labels containing the gate name and saved raw value. The fixed ToLiss
  output targets remain unchanged in the calibration code; repeating them on
  every ruler tick added clutter without changing operation. Close REV IDLE and
  IDLE labels are anchored on opposite sides of their ticks.
- Established an 8-point minimum for every visible item on this faceplate,
  enlarged output tiles, detent labels, engine contacts, trim selector labels,
  flap buttons and parking labels, and shortened the footer. Removed redundant
  paragraphs and micro-headings from the lower panels.
- Gave OUTPUT TESTS its own non-overlapping card and tightened the lower layout
  without removing a control. Fixed the trim selector's literal `\n` text so
  CRANK/PITCH, NORM/RUD and IGN-START/AIL render as true two-line labels. The
  speedbrake's close DOWN/ARM positions no longer draw colliding text; DOWN is
  already shown as the live state while the ARM gate remains labelled.
- Added `tools/test_winctrl_throttle_faceplate_layout.py`. Its 187 off-screen
  render checks enforce the 8-point floor, panel bounds, clear status/ruler
  separation, two complete non-overlapping six-gate rows, absence of literal
  newline escapes and removal of the old microcopy. The existing ToLiss probe
  guard now passes 57 checks.
- No calibration math, saved raw value, ToLiss target, simulator dispatch,
  hardware input ownership or physical output authority changed.

## 2026-09-09 - ToLiss calibration saves the physical resting detents

- Corrected the guided probe's physical-side sampling. It previously saved the
  first raw count seen when a detent contact closed, while the thrust lever was
  still travelling into the notch. The owner's screenshots proved the error:
  for example CL was labelled near raw `43710` although the lever rested near
  `45370`, and FLEX/MCT was labelled near `53305` although it rested near
  `55452`.
- A contact edge now starts a candidate rather than saving it. The expected
  contact must remain continuously closed and the raw axis must remain below
  the 40-count motion threshold for 0.30 seconds; only the final resting value
  is committed. Releasing the contact cancels the candidate. Studio displays
  `HOLD <DETENT> STEADY` and the remaining dwell time.
- Added a bounded main-loop service tick using the existing latest Raw Input
  snapshot. This lets the dwell finish after the delta-filtered hardware stream
  becomes quiet without adding a second SDL/HID reader or changing physical
  output authority.
- Bumped the saved raw-gate schema to version 2 while keeping its narrow JSON
  shape. Version 1 represented leading-edge samples and is deliberately ignored;
  the safe fallback is used until one new sweep is saved. Version-2 gates remain
  persistent in the active ToLiss hardware profile. Fixed aircraft-side targets
  remain FULL REV `-1.00`, REV IDLE `-0.10`, IDLE `0.00`, CL `0.70`, FLEX/MCT
  `0.875`, and TOGA `1.00` regardless of unit-specific raw counts.
- Expanded `tools/test_toliss_throttle_probe.py` to 53 checks, including
  leading-edge rejection, settled-value capture, contact-release cancellation,
  exact save/reload persistence, profile-version rejection, independent
  engines, periodic servicing and the Studio hold message. The 58-check ToLiss
  mapping/isolation guard also passes.
- Zibo and LevelUp calibration, constants and dispatch are unchanged. Live
  acceptance requires one parked six-gate sweep after restarting Studio.

## 2026-09-09 - ToLiss detent calibration now drives the aircraft-side detents

- Corrected the missing second half of WinCtrl calibration. The guided probe
  had accurately saved all twelve physical raw gates, but the runtime then
  treated ToLiss's ISCS IDLE/CL/MCT sliders as if they were final
  `AirbusFBW/throttle_input` values. Those sliders belong to the upstream raw
  0..1 joystick layer; MuslimSim bypasses that layer and writes the signed
  cockpit-lever input directly.
- Replaced that double conversion with the aircraft's canonical direct lever
  targets: FULL REV `-1.00`, REV IDLE `-0.10`, IDLE `0.00`, CL `0.70`,
  FLEX/MCT `0.875`, and TOGA `1.00`. The installed A321 cockpit object supplies
  the signed REV-IDLE/IDLE/CL/TOGA geometry, and its own FMOD conditions define
  the CL `0.68..0.72` and FLEX `0.86..0.90` windows.
- Bumped only the runtime mapping identity to
  `toliss-a320-a321-winctrl-v2`. The saved physical-gate schema remains version
  1, so the owner's existing left/right calibration is reused without another
  sweep. `revOnSameAxis`, both physical reverse handles, contact snapping,
  startup pickup, and independent engine calibration remain intact.
- Studio's ToLiss ruler now shows both sides of every anchor as
  `raw -> direct input`, making it visible that calibration controls the
  aircraft rather than merely recording counts. The bridge status publishes
  the same direct-target table.
- Expanded the hardware-free throttle guard to 58 checks and the guided-probe
  guard to 37. They pin all six direct targets, the installed-aircraft detent
  windows, independence from arbitrary ISCS raw-axis ratios, unchanged Boeing
  constants, reverse gating, safe pickup, saved raw profiles and Studio's
  two-sided ruler.
- No Zibo/LevelUp converter, constant, profile or dispatch path changed. No
  physical output authority changed. Live acceptance requires restarting
  Studio, moving both levers through the six gates, and confirming ToLiss
  announces IDLE, CL, FLX/MCT and TOGA at the matching physical detents.

## 2026-09-09 - ToLiss throttle gains a guided six-detent Studio calibration

- Replaced the WinCtrl faceplate's fixed Boeing-style ruler with a ToLiss-only
  ruler whenever the detected/selected workspace is ToLiss. Engine 1 and
  engine 2 now show their own saved raw FULL REV, REV IDLE, IDLE, CL,
  FLEX/MCT and TOGA gates and the live raw axis count. Zibo and LevelUp retain
  the unchanged previous ruler and calibration paths.
- Added a `CALIBRATE DETENTS` action to the ToLiss WinCtrl faceplate. The probe
  starts at FULL REV and advances only when the matching captured physical
  contact closes, so it does not infer detents from noisy motion. Both levers
  may be swept together or independently through REV IDLE, IDLE, CL,
  FLEX/MCT and TOGA; Studio reports the next required gate for each engine.
- Persisted the validated result in the active ToLiss hardware profile under
  an explicit `toliss-a320-a321` family/version marker. The schema requires
  all twelve raw gates in increasing order and rejects foreign-aircraft,
  incomplete, out-of-range, or collapsed calibrations. The existing separate
  `hardware_profiles_toliss.json` boundary prevents any write to the Zibo or
  LevelUp profile files.
- Fixed the reverse-to-IDLE latch in two complementary places. Physical
  thrust-detent contact edges now force a simultaneous axis snapshot even if
  the ADC did not move past its deadband, and the IDLE contact explicitly wins
  a brief IDLE/REV-IDLE overlap. Reaching IDLE therefore commands exactly
  `0.0` immediately rather than requiring a push above IDLE and a return.
- The calibration sweep temporarily owns only the two ToLiss thrust inputs;
  it leaves the simulator at its existing thrust values while gates are being
  captured. Starting the sweep disarms both pickup gates, so save, cancel, or
  a persistence error all require the established read-current/cross-target
  safe pickup before live writes resume. On save, the new interpolation tables
  are swapped atomically. No second SDL/HID reader was added.
- Kept fixed-rate work bounded to the changed two-lever frame. A same-loop
  benchmark of 200,000 paired conversions measured 1.1153 s before inactive
  probe bookkeeping and 1.4699 s with it, an added 1.77 us per changed frame;
  full validation/table construction and profile saving happen only on probe
  completion.
- Added `tools/test_toliss_throttle_probe.py` (35 checks) and expanded
  `tools/test_toliss_throttle_calibration.py` to 49 checks. The two guards,
  known-regression suite, WinCtrl self-test, LevelUp guard, aircraft-profile
  and isolation guards, Hardware Lab self-test, Studio live-feedback guard,
  ToLiss FCU/EFIS guard, launcher check, panel check, and six-file AST syntax
  check all pass without opening X-Plane or hardware.
- This changes no lamp, backlight, display or motor output. Existing
  aircraft-unpowered and shutdown blackout authority is unchanged. Live
  acceptance still requires one parked ToLiss calibration sweep and a check
  of every gate on both physical levers.

## 2026-09-08 - ToLiss A320/A321 engine throttles receive an isolated calibration

- Replaced the ToLiss throttle branch's reuse of the Zibo/LevelUp
  `_winctrl_throttle_values()` path with a dedicated
  `toliss-a320-a321-winctrl-v1` calibration. The established Boeing raw
  constants, 737 reverse threshold, converter and live dispatch were not
  changed.
- Hard-coded six physical anchors independently for engine 1 and engine 2:
  FULL REV 0, REV IDLE 14115, IDLE 20165, CL 45371, FLEX/MCT 55453 and TOGA
  65535. Each corresponding detent contact now snaps exactly, eliminating ADC
  jitter while a lever is seated in a gate.
- Read the loaded ToLiss aircraft's own IDLE/CL/FLEX-MCT ratios once at profile
  startup (live A321: 0.3000 / 0.6915 / 0.8412), then precomputed the signed
  `AirbusFBW/throttle_input` interpolation tables. This adds three one-time
  reads per bridge generation and zero additional fixed-rate work; live axis
  frames remain O(the two changed levers).
- Measured 100,000 paired engine conversions: the former shared converter took
  0.2502 s and the isolated six-anchor converter took 0.5729 s, or 5.73 us per
  complete two-lever frame (3.23 us added). The lookup tables are still built
  only once, so this constant-time cost is negligible at the bridge's 25 Hz
  input rate.
- Kept reverse travel doubly guarded by ToLiss's `revOnSameAxis` setting and
  the matching physical reverse handle. Kept the existing current-simulator
  readback and cross-target safe pickup before the first write, so a Studio
  restart does not intentionally apply a stationary lever position.
- Restored the ToLiss owner's read-only `left_thrust` and `right_thrust` raw
  telemetry to Hardware Lab before the simulator-dataref gate. Taking SDL
  ownership from the preflight reader can no longer freeze Studio's throttle
  sliders, including while ToLiss reloads and temporarily invalidates its
  throttle dataref. These observations use `route=False`, so they cannot add
  a second simulator write or alter any aircraft calibration.
- Added `tools/test_toliss_throttle_calibration.py`; its 46 hardware-free
  checks cover both engines and all six detents, ADC-jitter snapping,
  monotonic interpolation, reverse gates, per-engine independence, exact
  unchanged Boeing constants/outputs, startup-pickup ordering, and continued
  raw Studio telemetry from the ToLiss reader.
- This is an aircraft-input calibration only: it adds no light, backlight,
  screen, motor or other physical output. Existing unpowered-aircraft and
  shutdown blackout behavior is unchanged.

## 2026-09-08 - ToLiss FCU MACH and HDG/V/S-TRK/FPA states completed

- Encoded the four supplied virtual-FCU references for the physical BA01.
  MACH now renders its lit leading zero and separate decimal (`0.77`) instead
  of passing an unmapped dot as a digit.
- Added the complete paired annunciator states. HDG mode lights HDG/LAT,
  HDG/V/S and V/S; TRK mode lights TRK/LAT, TRK/FPA and FPA.
- Added `AirbusFBW/HDGTRKmode` and `sim/cockpit2/autopilot/fpa` to the existing
  five-Hz ToLiss snapshot. FPA is signed and shown in tenths (`+0.0`, `-3.2`)
  using its real decimal segment and two blank unused cells.
- Kept both additions behind the existing ToLiss-only Airbus presentation.
  The exact legacy/Zibo packet is unchanged, stable values cause no additional
  hardware writes, and the existing power gate still sends all windows,
  annunciators and backlights dark.
- Expanded the offline FCU/EFIS guard from 72 to 80 checks, including exact
  packet slices for SPD, MACH, HDG/V/S, TRK/FPA and both signs. The 80-check
  guard, BA01 semantic test, FCU faceplate test, LevelUp integration guard,
  known-regression suite, three-file syntax compile and launcher check all
  pass without opening X-Plane or hardware.
- Compared the pre-change and post-change encoder over five representative
  legacy state sets (30 total value/commit packets): every byte is identical.
  The Airbus unpowered dynamic region is also explicitly pinned to 18 zero
  bytes.
- The repository-wide output-authority audit still reports its two existing,
  unrelated MOZA declaration gaps (`moza_a210_ffb` and `moza_ab6_ffb`). No
  MOZA or authority file changed in this task.

## 2026-09-08 - ToLiss FCU V/S presentation and EFIS filter lights corrected

- Replaced the inferred EFIS-filter lamp permutation with the order proven by
  the physical capture: CSTR=5, WPT=6, VOR.D=7, NDB=8 and ARPT=9 on both BA01
  EFIS units. ARPT stays on its already-correct channel.
- Added a ToLiss-only Airbus V/S presentation matching the real FCU: signed
  climb/descent indication, two main hundreds digits followed by BA01's two
  smaller zero glyphs, and the `ALT <- LVL/CH -> V/S` legend segments.
- Kept the new presentation opt-in. Existing Zibo and other callers retain
  their exact legacy display packet, and aircraft power loss still blacks out
  every window and integral light.
- Expanded `tools/test_fcu_efis_toliss.py` to 72 hardware-free checks at this
  stage (later extended to 80 by the complete mode-display guard). It pins
  every filter's exact on/off report on both sides, exact ToLiss `-4800` and
  `+4800` byte slices, and the unchanged legacy `-4800` bytes.

## 2026-09-08 - ToLiss FCU/EFIS physical controls, selected values, and lights repaired

- Accepted the BA01 firmware's captured 41-byte input report while retaining
  compatibility with HID stacks that pad it to 64 bytes. Only the first twelve
  payload bytes are decoded as the confirmed 96-control bitmap.
- Replaced the four ToLiss FCU rotary no-ops with the aircraft's own writable
  `FCU*KnobRotation` inputs and bound the 100/1000 selector directly to
  `AirbusFBW/ALT100_1000`.
- Preserved the already-working speed and altitude display sources. Heading and
  vertical speed now show the selected autopilot targets instead of current
  aircraft heading/V/S, which had produced the observed fixed `0` and `1`.
- Added live numeric BARO values, managed/dashed states, both EFIS sides' FD/LS
  and ND-filter lights, and the six captured FCU lamp channels (LOC, AP1, AP2,
  A/THR, EXPED, APPR). Power loss explicitly forces every integral light off.
- Added `tools/test_fcu_efis_toliss.py`, a simulator- and hardware-free BUG-22
  guard covering the captured input length, rotary wrap/steps, LED selectors,
  selected display datarefs, and blackout gate. Live physical acceptance is
  still required after restarting Studio with a ToLiss aircraft loaded.

## 2026-09-06 - The MOZA AY210's real force feedback now runs from scratch, no MOZA SDK, no FFB-Bridge

- "we have to build our own interceptor without using any of their sdk we
  gonna probe moza and every move she does" - after ruling out X-Plane's
  native FFB (MOZA doesn't expose the DirectInput interface it needs) and
  MOZA's official Flight SDK (unclear commercial licensing terms), the owner
  asked for the harder-but-cleaner path: MuslimSim driving the AY210's real
  spring motor directly, reverse-engineered from its own USB traffic rather
  than any vendor SDK.
- Captured FFB-Bridge (a free, MOZA-partnered app whose own EULA explicitly
  permits "monitoring... while FFB-Bridge is running") driving the AY210
  across five real flights, all 17 individual Flight Check bench tests, and
  a genuinely fresh device power-on. Found the AY210 speaks the public USB
  HID PID force-feedback spec on its main interface - not a MOZA invention -
  plus a second, undocumented channel: a Windows COM port that carries both
  a proprietary parameter-table protocol and the device firmware's own live
  debug log, in the clear.
- The real blocker turned out to be invisible in every capture except one:
  every earlier reference session had been taken from a device FFB-Bridge
  had already switched into active force-feedback mode earlier in the same
  power cycle. Only a capture starting from a genuine fresh replug showed
  the actual gate - a one-time serial command that flips the firmware's
  `steer` module from mode 1 to mode 2 (force-feedback-active), confirmed
  directly from the firmware's own debug log. Without it, every effect
  parameter writes and gets acknowledged correctly, and the motor never
  moves; it's a persistent per-power-cycle latch, which is exactly why nine
  earlier attempts - each one individually confirmed correct against the
  device's own log - still produced zero physical force.
- Built `tools/probe_moza_ay210_ffb_bench.py`: opens the AY210's existing
  read-only HID handle plus its serial port together, keeps the connection
  alive on a background thread, waits for the firmware's own "Host
  Connected" before arming force feedback, then replays one real, complete,
  verbatim capture across all three USB channels the device uses. Confirmed
  live by the owner: "yes the yoke feel exactly as i felt it earlier on
  ffb-bridge" - with FFB-Bridge and MOZA Pit House both closed.
- Full technical narrative - the four dead ends, what each one proved, and
  how the real gate was finally isolated - is in `BUG_REGISTER.md` under
  BUG-21's tenth follow-up.

## 2026-09-06 - The MOZA A210 yoke now assigns its own X-Plane axes automatically

- "the moza a210 its not moving the aircraft yoke ... it use to work b4 why i
  have to assign anything ... it should be automaticly assigned."
- Diagnosis: the MOZA A210's HID reader only ever fed Studio's 2D panel; it
  had never resolved a single X-Plane dataref, unlike every other analog
  control (WinCtrl throttle, pedals). Whatever moved the aircraft before was
  X-Plane's own native joystick binding, not MuslimSim.
- Built real routing instead of restoring native binding, mirroring the
  proven pedals pattern exactly: roll/pitch go to X-Plane's standard
  `sim/joystick/yoke_roll_ratio` / `yoke_pitch_ratio`, gated behind the same
  no-jump startup-safety pickup (a parked yoke cannot snap a live aircraft's
  attitude on bridge restart) and the same tolerance-cached write every other
  physical control already uses. No per-user function assignment needed.
- Roll direction is hardware-confirmed from earlier testing. Pitch direction
  carries the same open, already-disclosed assumption as Studio's own yoke
  visualization; if push/pull read backwards in X-Plane, it is a one-line
  sign flip, called out at both places in `bridge/final.py`.
- Found and closed a startup race while building this: the yoke's HID reader
  thread used to start well before the bridge's event queue existed, so its
  very first report could have raced the queue's creation. The queue is now
  created immediately before any reader starts, not just before the main loop.
- Follow-up: "it still show me that mouse square however when i move the
  yoke in and out i feel it want to move it chaky in the sim." That mouse
  square is X-Plane's own no-joystick-bound fallback, and X-Plane keeps
  recomputing roll/pitch from that fallback every frame - fighting the
  bridge's write on the very next frame, which is exactly what "chaky" looks
  like. Armed `sim/operation/override/override_joystick` once at startup so
  X-Plane trusts the bridge's writes instead of recomputing them itself.
- Second follow-up, after a diagnostic log confirmed routing was genuinely
  live (both roll and pitch reached their startup pickup and responded):
  "it respond it chacke very tiny ammount once i touch the yoke ... the
  chacking is not normal." Cause and effect was proven, but each raw HID
  report was relayed to X-Plane as an instant jump the moment it arrived -
  an irregular cadence with nothing filling the gaps, unlike a real
  joystick axis X-Plane polls continuously every frame. Moved the actual
  write off the HID-driven event entirely and onto a fixed ~50Hz timer that
  eases toward the yoke's latest known position, the same smoothing
  `_axis_ease` already does for Studio's own redraw, now applied to the
  simulator write itself. Still only writes an axis that has already
  passed the no-jump startup pickup gate.
- Third follow-up: "same problem" after that timer, then clarified while
  watching X-Plane's own 3D yoke model - "it chake very very tiny movement
  i concider chacking not movement." The ease tick was still gating its own
  35%-of-the-gap step through the general 0.0015 write tolerance meant for
  a settled axis; for a slow, tiny movement that step can land under 0.0015
  and get skipped, and a skipped write means the cached position never
  advances - so the real gap kept growing every tick until it finally
  cleared 0.0015 and dumped out as one visible jump, then went quiet again.
  Gave the ease tick its own much smaller floor (`MOZA_A210_EASE_WRITE_TOLERANCE`
  = 0.00005) so a genuinely tiny real step goes out every ~20ms instead of
  being silently absorbed.
- Fourth follow-up: "same result" even after a full X-Plane and Studio
  reboot. Three write-side fixes in a row with no change meant it was time
  for real evidence, not another guess - built
  `tools/probe_moza_yoke_dataref.py`, a standalone script with no bridge
  dependency that reads the live DataRef straight from X-Plane's own Web
  API on a timer. Run alongside the bridge during the same slow movement,
  it showed the ground truth: the value was snapping to exactly `0.00000`
  for one sample, then back near its real position on the next, over and
  over. Nothing else in the codebase writes to these DataRefs, so X-Plane's
  own flight-model frame must be resetting the value faster than the
  previous ~50Hz tolerance-gated write kept it refreshed - no amount of
  smoothing *what* gets written helps if the simulator discards it before
  the next write lands. The ease tick now writes unconditionally every
  tick via plain `set_dataref` (not the cache-skipping helper), at roughly
  125Hz instead of 50Hz, to stay ahead of X-Plane's own reset. Evidence-based,
  not yet confirmed - rerunning the same probe is the test.
- Fifth follow-up: the 125Hz unconditional write showed the exact same
  result. Four write-side fixes in a row with zero change meant the write
  path was never the actual problem, so this got researched instead of
  guessed a fifth time - an X-Plane.org forum thread documents the
  identical failure from a native SDK plugin writing on *every single
  flight-loop frame* (faster than any bridge could ever manage), still
  overridden by Zibo, concluding "I guess in Zibo you can't override the
  joystick value." Zibo's own control-loading system ignores external
  writes to the standard joystick-ratio DataRefs at any speed - a
  documented, unresolved limitation, not a bug in this bridge. Zibo's
  actual supported mechanism is native X-Plane joystick assignment with
  feel tuned through its own response/stability sliders, which is almost
  certainly what "used to work b4" really was. Flipped `--no-moza-yoke`
  (on by default) to `--moza-yoke` (opt-in, off by default) - the routing
  code stays available for a simpler aircraft that might respect the
  override, but is no longer silently active against an aircraft it
  cannot control. Reassigning the yoke in X-Plane's own Joystick settings
  worked as an interim confirmation, but was manual - not what was asked
  for from the start ("it should be automaticly assigned").
- Sixth follow-up, after being told plainly not to settle for the manual
  X-Plane step or a third-party virtual-joystick driver ("i want to build
  something unique for muslimsim studio ... creating something from
  scratch"): X-Plane exposes the native-assignment mechanism itself as an
  ordinary writable DataRef array, `sim/joystick/joystick_axis_assignments`
  - the same thing Settings > Joystick writes when a user clicks an axis.
  The bridge now finds which slot is the MOZA A210's roll/pitch itself, by
  elimination against the live `joystick_axis_values` array (a slot only
  counts once it's actually been seen moving, never merely by surviving
  through inaction), then writes that slot's assignment once, gated behind
  the same no-jump pickup check every other physical control uses. Fully
  automatic, no driver, no manual X-Plane step. Added a Studio dialog (an
  "AXIS ASSIGNMENT" button on the yoke faceplate) with live status per
  axis, refreshing every half second, and three correction actions - set a
  slot manually, clear a bad one, or redetect - for when the algorithm
  gets it wrong, since a human looking at what just moved is inherently
  more reliable than an algorithm guessing among ~500 slots. Needed a new
  `device_command` bridge RPC verb, since both existing device-control
  paths (`lab_output`'s fixed control catalog, `calibration_set`'s
  MOZA-specific FFB/spring schema) would have rejected this free-form
  correction payload before it ever reached a handler.
- Seventh follow-up: "i see the mouse square" after restarting through
  Studio as normal. `--moza-yoke` correctly defaults off in the bridge's
  own argparse, but Studio's own launch command (built in
  `muslimsim/gui/supervisor.py`) was written before that flag existed and
  never requested it - every earlier test had been run from a terminal
  with the flag typed by hand, which hid this gap completely. Added
  `--moza-yoke` to Studio's own X-Plane launch command, so the feature
  actually runs on a normal Studio launch instead of only a manual
  command-line test.
- Eighth follow-up: "wow u got it it turn left right but it does not do it
  backaward and forward" - roll auto-detected and assigned, pitch never
  did. A long, slow pitch sweep showed detection "lost track," which
  traced to a real asymmetry in the elimination logic: our own axis needed
  a meaningful ~2% movement to count as "moving," but X-Plane's slot only
  needed the tiniest flicker. During a slow, natural sweep there are always
  moments where a hand is still moving but slowly enough to read "not
  moving" on the coarse side while the real slot's own continuous creep
  still clears the near-zero threshold on the other - wrongly eliminating
  the correct slot. Roll likely survived only because it got tested with
  faster movements that never hit the gap. Made elimination one-directional
  (only eliminate a slot that stayed completely flat while our axis
  genuinely moved; the reverse direction was the bug, not a real signal).
- Ninth follow-up: detection state lived only in memory, so a confirmed
  roll/pitch slot had to be re-detected from scratch on every bridge
  restart - a much smaller inconvenience than the original manual X-Plane
  problem, but not the "automatic" that was actually asked for. A
  confirmed slot (auto-detected or manually corrected) is now persisted to
  a small sidecar journal next to the hardware profile, restored on
  startup exactly like a manual Studio correction, and removed from the
  journal when cleared or redetected.
- Once the yoke could actually fly the aircraft, real force feedback from
  the aircraft back into the yoke came up. Investigated why X-Plane's own
  Force Feedback tab never appeared for the AY210: MOZA implements FFB
  over the newer `Windows.Gaming.Input` API, not the legacy DirectInput
  interface X-Plane's tab checks for. Rather than build this into
  MuslimSim - which would mean either MOZA's proprietary SDK (licensing
  terms not publicly available, a real risk given MuslimSim's own
  commercial plans are still undecided) or reverse-engineering their
  protocol specifically to avoid needing that license - pointed to
  FFB-Bridge, a free, MOZA-partnered app that already does exactly this,
  confirmed from its own docs to need no MOZA Cockpit install, no
  X-Plane-side config, and no account. Its docs independently confirm the
  same Zibo joystick-override limitation found earlier in this file - a
  second vendor hitting the identical root cause. Not built into
  MuslimSim; a scope decision, not a bug.
- AB6 joystick axis routing was requested in the same message but is not yet
  scoped or started.

## 2026-09-06 - Three levers stopped hopping, and the throttle's MODE selector got its real roles

- "thrustmaster TCA and the winctrl Minor throttle and Moza ab6 they all
  choppy ... they have to move smoothly no shopping nothing at all."
- All three read their lever position straight off the last status poll
  (~10Hz) and drew it immediately, so continuous physical motion looked like
  discrete hops. Reused the MOZA yoke's own proven fix - a ~60fps eased
  redraw loop decoupled from the poll rate - as one shared `_axis_ease`
  helper, now wired into the throttle's four axes, the AB6's stick/slider/
  dial, and the TCA quadrant's three levers. Dragging a TCA lever by hand in
  Practice still tracks the pointer exactly; only the polled/live path eases.
- "change the pitch angle trigger to Crank ... make Mode Norm the rudder
  Trim ... change the IGN/ Strat to be aileron trim" - the MODE selector's
  three roles are now CRANK=pitch, NORM=rudder, IGN/START=aileron.
- Pitch does not get a new, disconnected number: CRANK now reuses "STAB",
  the value a separate, already-shipped fix already drives live from the
  real stabilizer-trim rocker - so the LCD keeps showing the number that
  already worked, instead of hiding it behind a fake local one. RESET has no
  real centre command for electric trim, so it stays a no-op for that role,
  live and in practice, exactly like the real hardware.
- Switching MODE now shows the newly selected role's name on the LCD for
  about a second before it starts showing that role's live number - Studio
  only, since the real physical window's glyphs are digits, L, R and blank
  only, and cannot spell out a mode name.

## 2026-09-05 - Grip pads reshaped, the yoke shifted down, and a real panel limit found

- "move left pad button and right pad button and change their shape to
  rounded rectangular and move each above the yoke than move the entire
  yoke down about 3 cm."
- The two grip clusters (19-22, 14-17) are now rounded rectangles instead of
  round rings - the same corner-rotation technique already used for the hub
  and grip housings, since a rounded rectangle is the same shape wherever it
  is drawn - moved to sit clearly above the rocker.
- The 3 cm shift does not fit as asked, and this was computed rather than
  eyeballed: at full zoom-in, the grip capsule alone (unchanged, existing
  geometry) already needs 227 px of clearance below the pivot, and a full
  113 px shift would leave only 207 px there. The cap is about 77 px
  (roughly 2 cm) before that capsule draws off the panel at full zoom.
  Applied 70 px (~1.9 cm) - the largest shift that keeps every element
  on-panel at every roll and pitch extreme actually tested - rather than
  force the full number or silently under-deliver without saying so.
- A mistake in the tests written to prove this, caught immediately by
  re-breaking the guards on purpose: the first checks compared one dot's own
  drawn position to a whole cluster's centre, as if they were the same
  point - they are not, a dot sits offset from its cluster's centre by that
  shape's own radial spread. Mutating the code did not change which
  assertion failed, which was the tell. Fixed by using the combined bounding
  box of a cluster's own contacts, the only reference point that is correct
  regardless of which dot happens to be checked.
- `tools/test_moza_yoke_faceplate.py` grew to eighteen checks. Re-broken
  four ways and all four were caught.

## 2026-09-05 - Select moved to the sides, and a dead axis found along the way

- "the select button they should be located on the side in the place of
  those two slides in the corner witch they don't give any feed back am
  not sure why."
- The two "corner slides" were the `axis_z` and `axis_dial` sliders. Checked
  both against the same capture before touching either, rather than assume
  the owner's "no feedback" covered both equally: `axis_z` held the exact
  value 32767 for all 76,345 reports in the file - the same idle pattern
  already documented for the AB6's own Z axis, now confirmed on the A210
  too, and the real reason it never looked live. `axis_dial` is not idle -
  it swept its full 0..65535 range in this same capture - so a genuine
  working control was removed here to make room for select, not a second
  dead one. Worth knowing if that axis belongs somewhere else on this panel
  later, since it was never proven broken.
- `_draw_moza_axis`, left with no callers anywhere in the file once both
  sliders were gone, was removed rather than kept as dead weight.
- Select's eight contacts now split 5-8 to the left and 9-12 to the right,
  further from the hub than the grips - and, unlike the sliders they
  replaced, computed through the same rotating transform as every other
  contact, so they turn with the wheel the way a crossbar-mounted control
  actually would; a raw panel position would have quietly undone that.
- `tools/test_moza_yoke_faceplate.py` grew to sixteen checks. Re-broken by
  moving select back to the centre crossbar, and caught.

## 2026-09-05 - The yoke's buttons, decoded from a fresh capture instead of guessed

- Having watched V2 and pressed the real controls while `yoke.pcapng` ran:
  "the right upper and the left upper its just one button not five
  buttons... you can tap it from multiple angle. the right and left grip
  text should be on the side. the select buttons missing too many... there
  is four buttons on each corner... they don't work at all."
- Decoded the capture with the exact same byte math
  `muslimsim/devices/moza_a210.py` already uses for report 01, contact by
  contact, rather than adjust the drawing and hope:
  - **Eleven contacts (31, 32, 53, 59, 62, 64, 66, 68, 70, 72, 74) read as
    permanently pressed for the entire 91.5 s capture** - a firmware idle
    pattern, not buttons. Six more (29, 28, 30, 27, 23, 26) never moved at
    all. Together these were the whole of the old "LEFT UPPER" and "RIGHT
    UPPER" guesses.
  - **24 and 25 asserted together for the whole ~0.9 s of one press**,
    across several hundred consecutive reports, released together. One
    switch, two bits - proven "one button, multiple angles," not described.
    RIGHT UPPER now.
  - The left-hand equivalent was never pressed in this capture. Drawn with
    nothing bound to it rather than mirrored from a guess.
  - 19/20/21/22 and 14/15/16/17: each a clean individual edge, nothing else
    moving at the same instant. The grips, replacing a five-a-side guess
    that included two numbers that never moved.
  - 5 through 12: eight contacts, each individually clean, in one
    continuous run. The owner's own diagnosis - "select buttons missing too
    many" - was exactly right; the old guess had five of these eight.
  - 1, 2, 3, 4: matched the old guess exactly. "Don't work at all" traced to
    layout, not identity - the catalogue declares all 128 contacts, the
    bridge forwards every one unfiltered, and the capture shows all four
    firing cleanly; two of them sat touching the hub's own edge once roll
    reached 90 degrees. Moved further out and given more separation.
- `_draw_moza_yoke_rocker` draws one switch that lights on *either* of its
  bound contacts, for the proven case and the honestly-unmapped one alike -
  the left rocker is drawn dashed with no control tag rather than guessing.
  `_draw_moza_yoke_ring` replaced the old fixed five-slot hat with one that
  lays out however many contacts it is given, serving both the four-contact
  grips and the eight-contact select cluster, and takes an explicit caption
  offset so a cluster's label can sit to the side instead of always above.
- Recorded as BUG-19. `tools/test_moza_yoke_faceplate.py` grew to fourteen
  checks. Re-broken five ways and all five were caught.
- Still open: the left rocker's real contact number(s) - not guessed, and
  only findable with a capture that actually presses it.

## 2026-09-05 - LevelUp BB35/BB36 and captain pitch-trim parity

- Audited the current September 4 project before editing and kept it as the
  authority; no older `final.py` or Point A copy was restored over newer work.
- Confirmed against the installed LevelUp 737NG files that MuslimSim's existing
  graphical routers have every FMC command/dataref they consume: 69/69 FMC1
  commands and 5/5 FMC1 datarefs are present.
- Added LevelUp to only the three gates required to start the existing display
  path: captain-PFD telemetry resolution, BB35 page routing and BB36 page/FMC
  routing. This removes the stale-Zibo BB35/black BB36 outcome without creating
  a second renderer or changing the current screen design.
- Mapped the WinCtrl RUD TRIM rocker to LevelUp's real captain-yoke command pair,
  `sim/flight_controls/pitch_trim_down/up`, through the LevelUp-only override
  dictionary. Zibo retains its original Laminar commands byte for byte. The
  existing stabilizer-units dataref and LCD path are reused unchanged.
- Added `tools/test_levelup_737_integration.py` as BUG-18's offline guard. Its
  eight checks pin all three display gates, both LevelUp commands, both original
  Zibo commands, and removal of the obsolete LevelUp BB36 skip.
- Verification passed: LevelUp integration (8), aircraft-profile self-test,
  WinCtrl trim-display self-test, aircraft isolation (22 workspaces), known
  regressions, shared PFD telemetry (40), BB36 recovery V7 (26), global output
  authority (71), PFD differential pixel equality across every synthetic frame,
  and `launch.py --check`.
- `tools/test_display_stall_recovery.py` continues to report its already-recorded
  untouched-tree assertion, "the supervisor must still record why the path
  failed". This patch does not edit that recovery module.
- Live LevelUp acceptance still requires X-Plane and the two physical displays:
  fresh BB35/BB36 startup, page switching, and both trim directions/readout.

## 2026-09-05 - What watching the yoke actually move caught

- Having watched the first rebuild turn: "from your localhost view the yoke
  is upside down and it should go up to 90degree on each side... git rid of
  this button design they all wrong and they all go by numbers wich does not
  make any sense... just move the yoke on its axel fixed in the middle when i
  turn right it turn up to 90degre and the same for the left and when i pul
  it zomm out and when i push it zoom in... still so slow it has to go
  smouth."
- **Upside down, confirmed against the same product photo already fetched:**
  the real MFY yoke's grips sit above its hub, not below. Every local
  y-coordinate mirrored to correct it.
- **A visible connecting rod where the owner wanted a fixed point:** removed
  entirely. The axle is now a single point, centred on the panel, that never
  moves - roll rotates the whole assembly around it up to 90 degrees each
  way (was 42); pitch scales the assembly larger or smaller around that same
  fixed point (push zooms in, pull zooms out) instead of sliding it.
- **A subtler bug the 90-degree change itself exposed:** each five-way
  cluster's dots were positioned as screen-fixed offsets from an already-
  rotated cluster centre, so the centre turned correctly while the buttons
  riding on it did not - measured directly as an 83.9-degree sweep where 90
  was commanded. Fixed by rotating those offsets through the same transform
  as everything else.
- **"they all go by numbers wich does not make any sense":** every contact
  used to be drawn with an arrow glyph and a printed diagnostic badge
  ("B029") next to it. Replaced with a plain dot or button carrying only live
  colour - the number still identifies the contact for calibration, on the
  same tag, it is simply not printed on the hardware's own face.
- **"still so slow... it has to go smouth":** physical status arrives ten
  times a second, fine for a switch, stutter for something watched turning
  continuously. Roll and scale now ease toward each new target across
  additional ~60 fps frames drawn between real telemetry replies, reusing the
  PDC panel's own proven eased-animation store rather than inventing a
  second one.
- **A test-writing lesson kept in the register:** the first version of the
  rotation guard asserted things that are not actually true of a rotation in
  general (that both coordinates of a point must change substantially, and
  that two left-right mirror points must swing opposite ways) - both held at
  the old 42-degree deflection by coincidence of geometry and broke the
  moment the angle changed to 90. Replaced with the one invariant that holds
  at any angle: the angle swept about the known, fixed hub, measured with
  `atan2`, must equal the commanded roll exactly.
- `tools/test_moza_yoke_faceplate.py` grew to ten checks against real
  rendered output. Re-broken six ways and all six were caught.

## 2026-09-05 - The yoke redrawn to look like a yoke, and turn like one

- The owner: "the yoke faceplate its not clear the design i so bad... rebuild
  it in a way it look like the original Moza yoke and also it move freely
  like a yoke."
- The old drawing was a flat bar with two rectangles on the ends, sliding
  sideways up to 19 px for roll and up or down up to 15 px for pitch - both
  too small to read as movement, and the wrong *kind* of movement besides: a
  real yoke's roll turns the wheel around its own hub, like a steering wheel;
  sliding the whole shape sideways is a different motion, not a smaller one.
- Fetched the manufacturer's own product photography for the MOZA MFY yoke
  before redrawing anything, rather than guess a shape from memory: a swept
  "gull-wing" silhouette, two horns curving down and outward from a central
  hub to a pair of vertical grips.
- Rebuilt as one rigid body: every point of both horns, the hub, the two grip
  capsules and every button mounted on them is defined once in a frame
  centred on the yoke's own hub, then carried through one shared transform -
  rotate for roll, translate and scale for pitch - so the whole assembly
  turns together the way the real bolted-together yoke does, buttons
  included.
- Full roll is now 42° each way; full pitch travel measures 76 px end to end
  on the actual rendered canvas, both confirmed by reading back real bounding
  boxes from a live Tk canvas rather than trusting the transform math by eye.
- All 29 of the original numbered HID contacts were relocated onto the new
  shape under their original tags and button numbers - none renumbered or
  dropped - and the axis-to-motion sign convention already proven from the
  owner's own capture was carried forward unchanged; only how the motion is
  drawn changed.
- Recorded as BUG-17. `tools/test_moza_yoke_faceplate.py` renders the real
  drawing function and checks the actual on-screen result: both grips move
  in both directions under roll (a rotation, not a slide) and swing opposite
  ways (one rigid body turning about its centre), the two roll directions
  mirror each other, pitch travel is now large, and the transform preserves
  every point's distance from the hub at every angle tested. Re-broken two
  ways and both were caught.

## 2026-09-05 - Why Studio was slow: a status poll that saved every device every time

- The owner asked for a thorough investigation into why Studio felt slow.
  Attached a sampling profiler (`py-spy`) to the actually-running Studio and
  bridge processes rather than guessing, and found the real cause in minutes:
  two request-handling threads answering Studio's status poll were spending
  95-99.7% of their own CPU time inside one SQL query.
- Measured directly: `SELECT COUNT(*) FROM outbox` cost **151 ms** on the
  live database, against the 100 ms poll interval Studio was waiting on.
  `outbox`, `device_sightings` and `audit_log` each held **3.68 million rows**
  in a **9.4 GB** file, growing at a measured, sustained 22-72 rows a second
  for 46.3 hours straight - since work on this machine began - never once
  pruned.
- The cause: every status poll (10 Hz) re-saved every currently-visible
  device to SQLite, whether or not anything about it had changed since the
  last poll. Confirmed directly against the live database - the last 2,000
  rows of both `outbox` and `audit_log` were the identical event,
  `device-saved`, for the same handful of already-known devices.
- A second, compounding bug in the same path: the exact expensive query was
  being run **three times** per single status reply - once inside
  `HardwareLab.snapshot()`, then twice more, redundantly, in `server_handle`.
- Fixed at the source: a sighting is now persisted only when it actually
  differs from the last one recorded for that device (an in-memory
  comparison, not a database read); the duplicate `runtime.snapshot()` calls
  are gone, down to one; the two `COUNT(*)` queries are now bounded to 5,000
  rows regardless of true table size, since nothing in the codebase even
  reads the numbers they produce; and a new `prune_history()` caps all three
  tables at 20,000 rows each, run automatically on every fresh startup as a
  second, independent line of defence.
- The device-online state Studio actually displays comes from
  `IdentityRegistry.observe()`, in memory, updated on every single sighting
  regardless of the new dedup gate - nothing about live device status changed.
- Recorded as BUG-16. `tools/test_platform_v7_discovery_dedup.py` - six
  checks. Re-broken three ways (no dedup, no startup prune, unbounded count
  restored) and all three were caught.
- **Restarting Studio is required** for the fix to take effect - the running
  bridge is a separate process already executing the old code - and that
  restart will automatically prune the existing 3.68-million-row backlog back
  to 20,000 rows per table the moment it reopens the database. No manual
  database surgery needed.

## 2026-09-05 - The recorded blink that should never have broken focus

- The owner ran `probe_tobii_focus.py --save gaze.txt` while staring at one
  spot and sent the trace back. It surfaced two real bugs that synthetic test
  traces could not have found, plus a gap in the tests written to prove the
  fix.
- **A blink read as looking away.** The tracker flags only three samples
  invalid per blink, but the *valid* samples on both sides of that flag are
  still corrupted by the eyelid - some of them a tenth of the screen off,
  every one saying `valid: true`. Added `recovery_seconds`: gaze is coasted,
  not believed, for a short window after any invalid reading.
- **The near side of a blink has no flag to gate on at all.** Fixed by
  requiring drift past the break radius to persist for `break_hold_seconds`
  before releasing, instead of releasing on the first sample over the line.
  A genuine look-away still leaves instantly - that is the independent speed
  check, not this one.
- **A second bug, found chasing the first one across a bigger gap:** the
  smoothing filter's `dt` was measured against a clock that advanced on every
  call to `update()`, including the coasted ones a blink produces - so the
  first real sample after any gap divided a real position change by one
  sample's worth of time instead of the true elapsed gap. An apparent speed
  roughly ten times too high, defeating the smoothing exactly when a spurious
  jump most needs to be damped. The filter now keeps its own clock, touched
  only on samples it actually sees.
- **A gap in the tests, caught by the tests' own mutation checks:** the first
  version of the drift-persistence guard checked "one sample past the break
  radius does not release" - but the filter smooths the very first sample of
  any jump so heavily that drift never even crosses the threshold on sample
  one, with or without the persistence code. Removing the mechanism entirely
  left that guard green. Replaced with a check that measures the real gap
  between drift crossing the threshold and release firing: 0.152 s against a
  0.150 s setting.
- Recorded as BUG-15. `tools/test_gaze_focus.py` grew from 12 checks to 14,
  including the owner's exact recorded blink replayed unedited. All three
  fixes were re-broken and caught; the two near-misses on the way there are
  in the register too, because "the test still passed" without "the code is
  still right" is exactly the trap rule 0.4 exists to keep out of a second
  session.

## 2026-09-05 - Eye focus, as a switch in Studio

- Added a toolbar toggle, off by default. The service is built on first click,
  so a machine with no eye tracker never loads the Tobii runtime at all, and
  with the toggle off Studio behaves exactly as it did before.
- `muslimsim/platform/gaze_service.py` joins the detector to the tracker and
  does something with the answer. Three rules govern how it touches the desktop:
  - **the pointer is warped, not driven.** Nothing happens until a fixation is
    established; then the pointer is placed once and left alone. One write per
    fixation, not thirty a second - a pointer that follows gaze continuously is
    the shakiness this exists to remove, only smoothed.
  - **the physical mouse always wins.** The real cursor is compared with the
    last position written here, and any discrepancy means the owner has the
    mouse, so the stabiliser stands back. That is also the escape hatch: moving
    the mouse takes control back without reaching for the toggle.
  - **nothing moves while the gaze is roaming.**
- Studio feeds it hardware activity from `_physical_telemetry_sequence`, one
  number that advances whenever any control anywhere reports, so the knob-hold
  costs O(1) however many panels are added later.
- The toggle label is written only when it changes. A label in the toolbar
  rewritten every tick is the flicker that was removed once already.
- **A bug worth remembering: two clocks.** `note_control_activity` first stamped
  the hold with `time.monotonic()`, while the detector compares it against
  sample timestamps - and the tracker stamps those with its own device uptime,
  a completely different base. The hold would have either never applied or
  never expired, and nothing about the code looked wrong. The service now
  timestamps against the newest sample, the test starts its fake tracker clock
  at 176544 s so the two bases cannot be confused, and re-breaking it is caught.
- `tools/test_gaze_service.py` - ten checks with a fake tracker and no desktop.
  Re-broken four ways (never yielding to the mouse, rewriting the cursor every
  sample, warping while roaming, the wrong clock) and caught four times.
- `tools/probe_tobii_focus.py` now measures honestly: steadiness is compared
  only while focus is *held*, since a roaming pointer is supposed to move, and
  it reports the tracker's own noise so the thresholds can be set from
  measurement rather than from the synthetic traces they were first tuned on.
- **Known and not yet settled:** on the owner's first live run the lock held for
  a median of 0.48 s while they were deliberately staring. The defaults were
  calibrated against synthetic tremor that is cleaner than a real 33 Hz consumer
  tracker, so `settle_radius` and `saccade_speed` need a tuning pass against a
  recorded trace.

## 2026-09-05 - Knowing when the owner is trying to focus

- The owner reported that looking at a tablet to read it, or at a knob to turn
  it several times, leaves the view shaking and the pointer wandering, because
  both follow every tremor of the head and eyes.
- That tremor is not a fault in the tracker. A steady human gaze is never
  steady - it drifts about a degree continuously - so no better hardware fixes
  it. What has to change is the interpretation: while somebody dwells, their
  small movements are noise; the instant they look away, the same movement is
  signal.
- Added `muslimsim/platform/gaze_focus.py`, built around one asymmetry: **slow
  to lock, instant to let go.** Half a second slow to settle is invisible; a
  tenth of a second slow to release reads as the pointer fighting you.
  - a speed-adaptive filter (the "one euro" filter) removes jitter without
    adding lag, because a plain low-pass filter buys one with the other;
  - dispersion over a short window decides when gaze is a fixation rather than
    drift;
  - an anchor with a dead zone means the output is genuinely frozen, not merely
    smoothed, and a bounded creep lets slow re-aiming follow without unlocking;
  - a hold, refreshed by physical input, keeps the lock open while a control is
    actually being operated. This is the one part only MuslimSim can do - a
    general eye tracker never knows a knob is mid-turn.
- Blinks are handled on purpose: invalid gaze freezes the output rather than
  dropping focus, or the lock would let go every few seconds.
- The creep was bounded only after the tests caught it defeating the break
  radius - the anchor chased a real move fast enough that the gap never widened
  enough to release, so the lock followed the owner somewhere they never
  dwelled. The creep is for drifting while reading, not for travelling.
- Added `muslimsim/platform/tobii_stream.py`: a direct `ctypes` binding to the
  installed `tobii_stream_engine` runtime. No wrapper package, no vendored SDK,
  no second process. The library is found through the Windows program
  environment, never a hardcoded path.
- Verified against the owner's own tracker: enumerated `tobii-prp://IS5FF-...`,
  gaze and head pose both subscribed, samples arriving at 33.5 Hz - the same
  rate measured independently from the calibration capture - with monotonic
  timestamps and Tobii's documented no-eyes sentinel decoded correctly.
- `tools/test_gaze_focus.py` - twelve checks at the tracker's real rate,
  measuring both halves of the asymmetry rather than asserting them loosely.
  On the seeded three-second dwell the eye travelled 0.686 screen widths and the
  pointer did not move at all - the tremor stayed inside the dead zone - while a
  deliberate flick released in one sample, 30 ms. The guard demands only 40x, so
  it stays meaningful if the tuning changes.
- `tools/probe_tobii_focus.py` reports the same numbers live.
- **Not yet wired to anything.** The detector and the transport are both proven;
  what consumes the stabilised point - the Windows cursor, the simulator camera,
  or both - is still an open decision.

## 2026-09-05 - MINS and BARO are two-stage detent knobs

- The owner reported that these two knobs do not behave the way they do in the
  aircraft: turning to the small dent should move the value one by one, and
  tugging past the notch should run fast. MuslimSim only ever did the first
  part.
- **The driver was reading four contacts where the panel has ten.** Both FULL
  PDC captures show five one-hot contacts per knob - rest, a detent each way,
  and a *held past the notch* contact each way. The two fast contacts were
  sitting unmapped between the mapped bits on both units.
- Read as bare detents, a deliberate fast turn produced **two** clicks, not a
  run: the detent on the way out, and the same detent again as the spring
  carried the knob back. That is why it read as "slow" rather than as broken.
- The bit numbers are taken from the owner's own captures - each direction of
  each knob worked five times slowly and five times past the notch - and the two
  units genuinely differ, so BB52 is read from its own capture rather than
  mirrored from BB61.
- Replaced the spring map with a three-phase state machine per knob:
  `rest -> detent -> fast`. Entering a detent from rest is one click; the fast
  contact starts a run at ten clicks a second, driven from the reader loop's
  existing non-blocking spin so a held knob costs no thread and no timer of its
  own however many panels are added later. Coming back through the detent emits
  nothing - that is the spring, not a turn. A stalled loop cannot bank a burst,
  unplugging stops the run, and a knob held at connect is adopted rather than
  replayed into the simulator.
- The repeat *rate* is a choice, not evidence: the panel says only that the knob
  is held. `PDC_KNOB_FAST_STEPS_PER_SECOND` is the one line to change.
- Each click is a press; the release comes when the knob returns to rest. The
  first attempt released immediately after each press, which every count-based
  test still passed while Studio's faceplate would have sat still - the lab
  keeps one record per control and Studio only animates a knob whose latest
  record is a press. There is now a guard for that shape.
- Recorded as BUG-14 with `tools/test_pdc_detent_knobs.py` - thirteen checks
  including the recorded gestures replayed at their real timestamps. Re-broken
  four ways and caught four times.
- The catalogue entries bound to the driver now describe all five contacts per
  knob instead of one.

## 2026-09-04 - Nothing shipped may assume this machine

- The owner asked whether the PDC serials just recorded are specific to his
  hardware. They are, and the audit that followed found the shipped code clean
  but one tool not.
- **Shipped code carries no machine-specific values.** `muslimsim/` and
  `bridge/` contain no serial, no drive letter and no user name; the PDC driver
  reads whatever `serial_number` the device reports, so another owner's units
  work unchanged. The serials appear only in documentation as evidence that the
  field exists, and in one test fixture.
- Added `muslimsim/platform/msfs_paths.py`: MSFS records its own packages folder
  in `UserCfg.opt` (`InstalledPackagesPath`), so the Community folder is read
  from the simulator rather than assumed. It covers the 2024 and 2020 builds in
  both their standalone and Microsoft Store locations, and reports nothing on a
  machine with no MSFS. The connector will need this too.
- `tools/probe_msfs_wasm_channel.py` had three hardcoded `D:\MSFS24` paths and
  would have failed for anyone whose simulator lives elsewhere. It now discovers
  the Community folder and reports which build it belongs to.
- The BUG-13 test fixture used the owner's real serials, which read as though
  the code cared what they are. It needs only two different strings and now uses
  obviously synthetic ones.
- Added `check_no_machine_specific_paths_in_shipped_code` to
  `tools/test_known_regressions.py`: no file under `muslimsim/` or `bridge/` may
  contain this machine's drive letters or user name. Tools may still carry a
  convenience default; the shipped package may not. The guard was re-broken in
  isolation and confirmed to fail.
- Offline proof: 11 suites pass, including known regressions (9 checks), PDC
  RANGE encoder, MSFS detection, connector and selector, live-feedback contract,
  status latch, aircraft isolation, PDC BB62, Hardware Lab and output authority.

## 2026-09-04 - Right PDC RANGE turns endlessly; PDC identity by serial

- The right PDC's RANGE is an endless encoder, not the left one's eight-way
  switch, but its Studio knob only nudged 18 degrees while a pulse flashed and
  then sprang back to centre. It now accumulates one 24 degree detent per
  `range_inc` / `range_dec` pulse and keeps turning for as long as the owner
  keeps turning, in either direction, past as many revolutions as they like.
- The accumulated angle is never wrapped for drawing - sine and cosine are
  periodic - but is folded back toward zero once past 3600 degrees, together
  with the animation's own stored value so the drawn marker cannot jump.
  Unbounded state on a path that runs forever is what rule 0.3 forbids.
- A pulse counter seen for the first time, or restarted by a bridge restart, is
  adopted rather than read as an enormous turn.
- Added `tools/test_pdc_range_encoder.py`, 7 checks including that the knob
  passes a full revolution and that folding never moves the drawn marker.

- BUG-13: `_FixedPDCBase._open` took `entries[0]` from `hid.enumerate` with no
  further check. The PDC role is carried by the product id, which SimAppPro
  reassigns, so if both units ever answered on one PID two owners raced for the
  same physical panel and the second was never identified at all - which is what
  the owner saw after flipping the roles. Nothing reported it.
- The stable identity is the serial, burned into each unit and unmoved by a role
  change: BB52 `F5EDF0690E57486133167062`, BB61 `CC35F0690E57487533167062`.
  `_open` now refuses an ambiguous PID and names both serials, and the service
  and diagnostic snapshots carry the serial so a role swap is visible instead of
  looking like unknown hardware.
- Mappings deliberately stay keyed to the role, not the box: the captain's EFIS
  is the captain's EFIS whichever unit is on that side, and the profiles are
  already keyed `pdc_bb61_left` / `pdc_bb52_right`.
- Added two BUG-13 guards to `tools/test_known_regressions.py` and recorded the
  entry in `BUG_REGISTER.md`, including what is still open: persisting
  serial -> role across sessions so a swap can be announced, not only refused.
- Offline proof: 15 suites pass, including PDC RANGE encoder, known regressions
  (8 checks), PDC BB62, PDC input transport V6, Studio physical visuals V4,
  Practice data plane V4, live-feedback contract, status latch, aircraft
  isolation, MSFS detection and connector, Hardware Lab and output authority.

## 2026-09-04 - BUG-12: WinWing PDC BARO and MINS were inverted on both units

- Turning BARO to HPA showed IN, and MINS to RADIO showed BARO, on both the
  3M PDC L and R.
- Four one-hot selector maps in `muslimsim/devices/pdc_bb61_bb52.py` paired a
  rising bit with a falling index. They were the only descending maps on either
  device - VOR1, VOR2, MAP MODE and MAP RANGE all ascend - and the bit ranges
  are contiguous only when these ascend too (BB61: mins 24-25, baro 26-27, then
  MAP MODE from 28; BB52: mins 25-26, baro 27-28, then MAP MODE from 29).
- Confirmed against `captures/3M PDC R.pcapng` and `captures/3M PDC L.pcapng`:
  those bit numbers do toggle on the real devices, and each pair is genuinely
  one-hot, never both set at once.
- This was not display-only. The same decoded index reaches X-Plane through
  `_set_maintained`, so the simulator was driven to the opposite position as
  well; only the panel had been noticed.
- All four maps corrected to ascending. No other selector, button, rotary or
  dispatch path changed.
- Added `check_bug12_...` to `tools/test_known_regressions.py`: no PDC selector
  map may pair a rising bit with a falling index, and each selector's lowest bit
  must map to its first catalogued choice.
- The BUG-10 control-character guard now scans `tools/` as well as the package.
  The same heredoc escape collapse recurred while writing this very test, in a
  file the guard did not cover.
- Offline proof: known regressions (6 checks), PDC BB62, PDC input transport V6,
  Studio physical visuals V4, Practice data plane V4, live-feedback contract,
  status latch, aircraft isolation, MSFS detection, Hardware Lab, input chains
  and global output authority all pass.

## 2026-09-04 - Bug register, and a guard for every bug already shipped

- Added `BUG_REGISTER.md`: all eleven defects this project has shipped and
  fixed, each with the symptom the owner actually saw, the real cause, the fix
  and the guard that stops it returning. Four known-but-unfixed items are listed
  separately so they are not rediscovered as if new.
- Added `tools/test_known_regressions.py`, one check per register entry that was
  not already guarded elsewhere: BUG-06 the `physical_telemetry` shape clash,
  BUG-07 the alternating header banner, BUG-08 the triple repaint per tick,
  BUG-10 control characters in source, BUG-11 the unindexed catalogue search.
  The five already covered by other suites are cross-referenced rather than
  duplicated.
- Each guard was re-broken in isolation and confirmed to fail: removing the
  `_status_seen` banner guard, restoring the three repaints, and reintroducing a
  backspace escape were all caught.
- Added `AGENTS.md` rule 0.4: read the register before hunting a familiar-looking
  fault, and add an entry plus a guard whenever a new one is fixed.
  `tools/test_known_regressions.py` is now named in the required completion
  steps as always relevant.
- The register records the two patterns behind these bugs. Six of eleven are
  **a failure with no signal** - nothing crashed, nothing logged, and the only
  symptom was something quietly not happening, which is why several guards
  assert that a failure is reported rather than that the happy path works. The
  second is **a diagnosis that was never proved**: BUG-07 was blamed on the
  telemetry counters and "fixed" twice before the real writer was traced.
- Offline proof: known regressions, live-feedback contract, status latch, MSFS
  detection, MSFS selector, MSFS connector, aircraft isolation, Studio live
  feedback, Hardware Lab and global output authority all pass.

## 2026-09-04 - Header flicker was a logic bug, not cosmetics

- Removing the telemetry counters did not stop the header flickering, because
  the real cause was elsewhere: the header was alternating between two
  different strings about fourteen times a second.
- The status-poll branch in `_tick_once` is an `if/elif` chain. Its first branch
  is skipped whenever a poll is already in flight **or** is not yet due - which
  is most ticks on a perfectly healthy bridge - and execution then fell through
  to `elif self.supervisor.running:` and wrote "Starting private hardware
  service...". The next status reply wrote the real line, and the two took turns.
- "A poll is in flight" never meant "the service is starting". That banner now
  appears only before the first successful status reply, tracked by a new
  `_status_seen` flag, which a workspace change resets so a genuine restart
  still shows it.
- Added `_set_connection_text`, which writes the header only when the string
  actually differs. Tk re-renders a label on every `StringVar.set` even with
  identical text, and `_receive_status` was setting the same string ten times a
  second. This follows rule 0.3: nothing on a fixed-rate path should do work
  that changes nothing.
- Offline proof: Studio live feedback, live-feedback contract, status latch,
  Studio physical visuals V4, Practice data plane V4, Platform V7, FCU and ECAM
  faceplate layouts, aircraft isolation, MSFS connector, Hardware Lab and global
  output authority all pass.

## 2026-09-04 - Rule 0.3 "build for a project twice this size", and two hazards it found

- Added Rule 0.3 to `AGENTS.md` at the owner's instruction: every change is made
  on the assumption MuslimSim keeps growing, and a design that is merely fast
  enough today is a defect if its cost grows with the project. The pattern to
  hunt is work that scales with the whole, repeated at a fixed rate - per tick,
  per poll, per keystroke.
- Applied it immediately and measured two hazards.
- **Function browser search was O(catalogue) per keystroke.** It rebuilt a
  lowercase search string for every entry on every query: 3-4 ms at 2,355
  entries and linear beyond that. The text is now built once when the cached
  catalogue loads. Measured 3-4 ms -> 0.30 ms for a typed query, and the index
  key is stripped from results so callers see no change.
- **A real bug behind 17% of the status payload.** Two producers wrote
  `physical_telemetry` with different shapes: `physical_telemetry.py` wrote the
  summary Studio reads (`devices` counts and a `sequence`), while the V7
  `bootstrap.py` overwrote it with the raw per-control mapping - 93 KB with no
  `devices` and no `sequence`. Studio's counters therefore always read zero,
  which is why the header showed "Physical 0 - #0". `studio_hooks.py` repeated
  the same overwrite on the client side after receipt.
- Both now write the summary shape. The counters carry real values again
  (sequence 805, per-device counts), and the duplicate leaves the wire: the
  status payload drops 537,417 -> 444,488 bytes at 805 recorded controls, on a
  reply fetched ten times a second.
- Recorded as the next scaling item: the `platform` block is still ~74% of the
  payload and carries `telemetry.latest`, a third copy of the same physical
  inputs. The data model already has a per-record `sequence` and a `cursor`, so
  the fix is for Studio to send its last-seen cursor and the bridge to reply
  with only newer records. That is a protocol change on both sides and is not
  attempted here.
- Offline proof: 13 suites pass - live-feedback contract, Studio live feedback,
  Studio physical visuals V4, Practice data plane V4, Platform V7, status latch,
  MSFS selector, MSFS detection, MSFS connector, aircraft isolation, Hardware
  Lab, input chains and global output authority.

## 2026-09-04 - Studio repaints only when the panel actually changed

- `_draw_faceplate` begins with `canvas.delete("all")` and rebuilds every item.
  studio.py has 520 `create_*` call sites and **zero** uses of
  `itemconfigure`, `itemconfig` or `coords`: the retained-mode Tk Canvas API is
  never used, so changing one lamp colour destroys and rebuilds the whole panel.
- A status reply arrives ten times a second whether or not anything drawn has
  moved, and each one repainted. The status trigger now compares a signature of
  what the faceplate actually draws from - the device mirror, its bridge state,
  the practice preview, the selection and the flash set - and repaints only when
  it differs. In a still cockpit that is zero repaints instead of ten a second;
  a physical input still appears on the very next reply, because that is exactly
  when the signature changes.
- The signature is deliberately generous. A false "unchanged" would freeze the
  panel, which is the failure mode this project keeps hitting, so it errs
  towards repainting: an unbuildable mirror returns a value that never compares
  equal.
- Flash-driven animation is untouched. All eight clock-reading draw methods read
  `_flash_until`, and the flash branch still marks the canvas dirty on every
  tick while any highlight is alive, so highlights fade at full rate.
- User actions still paint immediately; only the ten-per-second status trigger
  is gated.
- Offline proof: Studio live feedback, Studio physical visuals V4, Practice data
  plane V4, live-feedback contract, status latch, Hardware Lab, and the FCU,
  ECAM, TCA, AGP and FMC faceplate layout contracts all pass.
- Recorded as still outstanding: the real fix is retained canvas items - build
  the static panel once and mutate only the lamps, needles and digits that
  change. That is a staged conversion across every renderer, and each faceplate
  already has a layout contract to pin its picture during the change.

## 2026-09-04 - Studio tick paints once instead of three times

- Measured what one `_tick_once` actually does. It runs every 70 ms and could
  repaint the entire faceplate three times in a single pass: the practice
  preview step, the status reply through `_receive_status`, and the flash
  expiry each called `_draw_faceplate()` independently. At 14 Hz that is up to
  42 full canvas repaints a second where 14 produce the same picture.
- The three tick-path draws now mark the canvas dirty and the tick paints once,
  after every source has had its say. All three already shared the identical
  TCA-drag guard, so the guard still decides whether a repaint happens at all;
  only the number of repaints changed.
- Behaviour is unchanged by construction: same guard, same final frame, same
  tick. The 12 other `_draw_faceplate()` call sites - button presses, page
  changes, canvas resize - still paint immediately, because a user action
  should not wait for the next pulse.
- Offline proof: status latch, live-feedback contract, Studio live feedback,
  Studio physical visuals V4, Practice data plane V4, MSFS connector, aircraft
  isolation and Hardware Lab all pass.

## 2026-09-04 - Fleet corrected to the real install; MSFS dispatch path built

- **FSLabs is installed after all.** It does not live in the Community folder the
  earlier scan covered; it is package `fsl-a32x`, and the airframes present are
  A321-251N / -251NX / -271N / -271NX - the neo with LEAP (251) and PW (271)
  engines. Detection now matches it by title and package, and resolves to the
  `fslabs_a321neo` workspace.
- **iFly 737 MAX 8200 added** as its own airframe. It is installed alongside the
  MAX 8 (`ifly-aircraft-737max8200-*`) and was previously folded into it, so the
  two shared one mapping workspace. They now have separate workspaces and share
  the iFly function library, as the Fenix variants do. iFly renders as a
  drop-down rather than a single button.
- The selector now holds 18 aircraft in 18 isolated workspaces.
- **Defect fixed in the detection rules.** Four rules had their `` word
  boundaries collapsed into literal backspace characters by a shell heredoc, so
  the iFly MAX 8200 title rule never matched and folded into the MAX 8. All 13
  corrupted escapes were repaired and the file now contains no control
  characters. The regression is covered by real-title samples.
- Added `muslimsim/platform/msfs_connector.py`, the MSFS dispatch seam. Every
  layer above it speaks `MsfsTransport`; what carries the traffic below it -
  a third-party WASM module today, MuslimSim's own later - is swappable without
  touching the bridge. The default `NullMsfsTransport` accepts nothing and
  explains why, so a mapping can never look delivered when nothing carried it.
- Protocol translation follows the form each source already used: `rpn` targets
  pass through as executable gauge code, `lvar` becomes
  `<value> (>L:<name>, number)`, PMDG `hevent` becomes `(>H:<EVT_...>)`, and
  `simconnect` routes to an event rather than calculator code.
- The MSFS aircraft gate now mirrors X-Plane's: a mapping reaches the simulator
  only while its own aircraft is loaded, an unrecognised aircraft is refused
  rather than guessed, and a momentary command fires on press only.
- `bridge/final_msfs24.py::_binding_sink` now routes through that seam instead
  of raising a hard-coded refusal. Installing a proven transport there is the
  single change that turns MSFS dispatch on.
- Added `tools/test_msfs24_connector.py` (5 checks) and extended
  `tools/test_msfs24_detection.py` to 15 real installed aircraft.
- Offline proof: 11 suites pass - MSFS connector, MSFS detection, MSFS selector,
  aircraft isolation, live-feedback contract, status latch, Studio live feedback,
  Platform V7, Hardware Lab, input chains and global output authority.

## 2026-09-04 - Standalone MSFS aircraft detection, built from the real install

- Added `muslimsim/hardware/msfs24_detect.py`, the MSFS counterpart of the
  X-Plane `.acf` path detection. It resolves the loaded aircraft from what
  SimConnect already reports - the `TITLE` simvar and the `aircraft.cfg` path
  from `AircraftLoaded` - to one of Studio's isolated MSFS workspaces. No
  third-party module, connector or helper is involved.
- Every rule was read from the owner's actual installation under
  `D:\MSFS24\Community`, and the evidence is recorded on each rule.
- The survey produced a design conclusion that a guess would have got wrong.
  Fenix and PMDG need opposite treatment: `fnx-aircraft-319-321` ships A319 and
  A321 airframes plus an A320 livery, so only the title separates them, while
  PMDG titles carry no vendor name at all (`737-900 PAX BW SC`, `777-200ER GE`)
  and only the package name identifies them. Detection uses the title where it
  discriminates and the package where it does not.
- An unrecognised aircraft resolves to `None`, never a default. Guessing would
  point the hardware at another airframe's mappings.
- Added `tools/test_msfs24_detection.py`: 4 checks against 11 real installed
  aircraft, including the A320 livery hidden inside the Fenix 319-321 package
  and both PMDG airframes.
- **Data conflict found and fixed.** The consistency check caught a detection
  rule resolving to `pmdg_777_200er`, which the selector did not offer. The
  PMDG 777 actually installed is the **777-200ER** (`pmdg-aircraft-77er`), not
  the 777-300ER, so loading it would have detected an aircraft with no workspace
  to switch to. The 777-200ER is now offered; the selector holds 17 aircraft.
- Offline proof: MSFS detection, MSFS aircraft selector, aircraft isolation,
  live-feedback contract, status latch and Hardware Lab all pass.

## 2026-09-04 - MSFS connector scoped; PU Air Korea WASM protocol decoded

- Surveyed what an MSFS 2024 connector actually requires. Plain SimConnect
  cannot write an LVAR or execute calculator code, which is what nearly all
  2,355 imported functions are, so a WASM module in the simulator is mandatory.
- Both candidate modules are already installed under `D:\MSFS24\Community`,
  confirmed as the active package path by `UserCfg.opt`: MobiFlight's
  `mobiflight-event-module` v1.0.1 and PU Air Korea's `WASM_PU.wasm`.
- Decoded the PU Air Korea module's protocol from the binary itself rather than
  guessing it: `WASM_PU.wasm` carries its own log format strings, naming the
  `PU_WASM.Command` / `.Acknowledge` / `.LVars` / `.Result` channels and the
  `HW.Reg.` / `HW.Exe.` / `HW.Set.` verbs, with `execute_calculator_code("%s")`
  behind `HW.Exe.`. Recorded in `SYSTEM_ARCHITECTURE.md`.
- Added `tools/probe_msfs_wasm_channel.py`, a read-only probe that asks the
  module whether it answers and changes no aircraft state, following the
  established `probe_mobiflight_boards.py` methodology. It reports both modules
  as present and needs MSFS running to complete.
- Nothing was dispatched and no connector was written. `bridge/final_msfs24.py`
  still refuses MSFS mappings with its existing message.
- Open decision recorded: the connector needs the `SimConnect` package in the
  pinned Python 3.11 runtime. It exposes the required client-data API and ships
  its own DLL, but installing into the runtime that owns the hardware is the
  owner's call.

## 2026-09-04 - Swallowed-exception triage: two silent failures made visible

- Triaged all 241 `except Exception: pass` sites across the 218 live files.
  Most are legitimate: 103 guard cleanup/shutdown paths where a failure must
  not stop the rest of the teardown, and 13 guard diagnostic writes that must
  never break a device path. Those were deliberately left alone.
- The dangerous shape is narrower and different: an error captured into a name
  that nothing ever reads, so an optional feature fails to install and execution
  continues as if it had. Three candidates were found; one was a false alarm.
- **Not a defect** - `bridge/final.py:76`, the Platform V7 bootstrap, already
  prints a `WARNING:` line, and the supervisor surfaces bridge WARNING lines in
  the Studio footer. Left unchanged.
- **Fixed** - `bridge/final.py:486`. A failed `device_manager` /
  `product_registry` import installed no-op lifecycle fallbacks and printed
  nothing, so USB plug/unplug tracking went inert in silence. It now prints the
  same style of `WARNING:` line the bootstrap uses.
- **Fixed** - `muslimsim/gui/studio.py:7148`. The Platform V7 Studio hook stored
  its failure in `_MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR` and set the installed
  count to 0, and *nothing anywhere read either*. That hook merges the bridge
  telemetry driving live physical feedback, so a failed install silently reduced
  the panel with no message. Studio now reports it once in the footer on the
  first tick. The report is one-shot and only fires on failure; the healthy path
  is unchanged.
- Neither fix converts a swallowed exception into a raise. An optional product
  layer must still not stop Studio or the bridge from starting; the change is
  that the failure is now visible instead of invisible.
- `tools/test_live_feedback_contract.py` gained a sixth check: the Studio hook
  error must be read somewhere, not merely assigned, and both bridge startup
  warnings must still exist.
- Offline proof: live-feedback contract (6 checks), status latch, aircraft
  isolation, MSFS aircraft selector, Studio live feedback, Platform V7, Hardware
  Lab, input chains and global output authority all pass.

## 2026-09-04 - Latch audit complete: all 14 single-flight flags reviewed

- Audited every `*_pending` flag in the live tree (225 files, 107,906 lines).
  Sixteen matches, of which two were test fixtures, leaving fourteen real ones:
  five in `muslimsim/gui/studio.py` and nine in `bridge/final.py`.
- Studio (5): `_status_pending` was the one genuine defect and is fixed and
  guarded. The other four are safe, and for different reasons worth recording:
  `_pdc_flat_frame_pending` already wraps its `after()` in try/except and
  releases in the callback; `_output_sync_pending` checks the bridge client
  *before* setting the flag, so it cannot hit the race that broke the status
  poll; `_discovery_pending` and `_bridge_discovery_pending` both go through
  `_submit`, which has no early return, and `_collect_future` always posts a
  result whether the work returns or raises.
- Bridge (9): these are not single-flight request latches at all and cannot
  produce the "Studio silently stops until restart" failure. Eight are
  convergence loops - `irs_pending`, `wiper_pending`, `stage3_selector_pending`,
  `stage5_ign_pending` and `winctrl_stab_trim_readout_pending` - which mean
  "keep stepping the simulator until it matches the physical control" and are
  released by the value converging, plus a defensive reset of all of them when
  Practice mode is entered. The ninth, `agp_xpdr_spring_return_pending`, is
  event-state memory released by the next physical event.
- Two theoretical weaknesses recorded and deliberately NOT changed, under the
  rule against disturbing working code: the convergence loops have no attempt
  cap, and their `except Exception: print(...)` paths do not clear the flag, so
  an unreachable target would retry at the step interval indefinitely. Both are
  gated behind `*_commands_ready` and `not practice_mode_active`, so they only
  run on an aircraft that supports the command, and the step rate is bounded.
  Changing tuned convergence behaviour in the bridge carries more risk than the
  fault it would prevent.
- Residual, low severity, not changed: `_submit`/`_submit_output` can raise
  `RuntimeError` while the worker pool closes, leaving a discovery latch set.
  That happens only during Studio shutdown.

## 2026-09-04 - Quiet Studio header; telemetry counters moved behind the scenes

- The header was rewritten on every 10 Hz status reply by two stacked writers,
  and the incrementing sequence number made it flicker constantly in the corner
  of the owner's eye:

      Zibo 737-800X connected - Test mode - Physical OFF - Platform V7 -
      Practice - Physical 0 - #0

  It now reads simply `Zibo 737-800X connected - Test mode`, which changes only
  when the aircraft, connection or mode actually changes.
- `muslimsim/gui/studio.py` (MUSLIMSIM_PHYSICAL_TELEMETRY_V6) keeps its counts
  on the instance as `_physical_telemetry_online`, `_physical_telemetry_count`
  and `_physical_telemetry_sequence` instead of appending them to the label.
- `muslimsim/platform/studio_hooks.py` no longer writes to `connection_text` at
  all; it stores `_platform_v7_mode`, `_platform_v7_control_count` and
  `_platform_v7_sequence` on the instance.
- The V7 telemetry merge is untouched. `_merge_inputs` and `_platform_v7` still
  run on every status reply, so live physical feedback is unaffected - only the
  display of the counters was removed.
- Offline proof: live-feedback contract, status latch, aircraft isolation, MSFS
  aircraft selector, Studio live feedback, Platform V7, Hardware Lab and global
  output authority all pass.

## 2026-09-04 - Fixed: changing aircraft killed live feedback until restart

- Root cause was a race, not a device fault. `_tick_once` read
  `supervisor.client`, found it alive, set the `_status_pending` single-flight
  latch, then called `_request` - which reads `supervisor.client` a second time.
  A workspace change tears the bridge down on its own thread, so the client
  could become `None` between those two reads. `_request` then returned early
  without submitting anything, no result ever arrived, and the latch stayed set
  for the rest of the session. Studio never polled the bridge again, `self._lab`
  was never refreshed, and live feedback stopped until Studio was closed and
  reopened.
- `_request` now returns whether it submitted, and the status poll releases its
  latch when nothing was sent. `_request` also reports a closing worker pool
  instead of raising during shutdown. Every other caller ignores the return
  value and behaves exactly as before.
- Added `tools/test_studio_status_latch.py`: a dropped client and a closed
  worker pool are both reported to the caller, the healthy path still submits
  and delivers its result, and `_tick_once` still releases the latch. The
  release check was re-broken in isolation and confirmed to fail the test.
- Offline proof: status latch, live-feedback contract, aircraft isolation, MSFS
  aircraft selector, Studio live feedback, Hardware Lab, input chains, global
  output authority and the ECAM protected contract all pass.

## 2026-09-04 - Professional Faceplates V2.1 rolled back at the owner's request

- Ran the package's own rollback. `muslimsim/gui/studio.py` was restored to its
  exact pre-install bytes (SHA-256 a699440e...), the patch markers are gone, and
  all five payload files were removed: the renderer module and its four tests.
- The nine redesigned pages are back on their established Studio renderers.
- Everything built earlier today survives the rollback and was re-verified: the
  MSFS 2024 aircraft selector, the Practice APU EGT tap and its handler, and the
  function-browser aircraft filtering.
- The `test_ecam32_faceplate_layout.py` harness fix is deliberately kept. It was
  never part of the faceplate package and is not a rollback target: it repairs a
  pre-existing `AttributeError` that failed on the unmodified tree, where the
  harness lacked the `_live_control_active` that `_draw_ecam32` calls unguarded.
  The test passes after the rollback.
- Offline proof after rollback: live-feedback contract, aircraft isolation, MSFS
  aircraft selector, ECAM protected contract and Hardware Lab all pass.

## 2026-09-04 - Professional Faceplates V2.1 installed

- Installed MUSLIMSIM_PROFESSIONAL_FACEPLATES_V2_1_PACKAGE after review. Six
  targets written: `muslimsim/gui/studio.py`, the new
  `muslimsim/devices/professional_faceplates_v2.py`, and four test files.
  Installer backup: `Backup/professional_faceplates_v2_1_20260904-125054`.
- Reviewed before running. The package is presentation-only: it opens no
  HID/SDL/COM, writes no dataref, starts no device owner and emits no output
  packet. It reads the same `_device_mirror` state Studio already uses, and it
  carries the Practice APU EGT tap forward - the installed renderer re-tags the
  EGT gauge `pu_egt_test`, so that control keeps working.
- Its declared `studio_before_sha256` matched this tree exactly, confirming the
  package baseline was captured after the MSFS aircraft selector, the APU EGT
  tap and the function-browser filtering, so none of that was overwritten. All
  three were re-verified present after the install.
- Nine pages are redesigned: fcu_32_efis, pdc_bb62, pdc_bb61_left,
  pdc_bb52_right, pap3_mag, pu_overhead, winctrl_pedals, moza_a210, moza_ab6.
  ECAM/ECAM32, the WinCtrl throttle and every TCA page stay on their
  established renderers, and bridge, status cache, supervisor timeout,
  HardwareLab and catalog are untouched.
- Fixed a pre-existing failure that blocked the install and was not caused by
  the package: `tools/test_ecam32_faceplate_layout.py` built a `FaceplateHarness`
  without `_live_control_active`, which `_draw_ecam32` calls unguarded, so the
  test raised `AttributeError` on the unmodified tree. The harness now carries
  the `_lab` and `_control_kinds` attributes that method needs and borrows the
  real implementation rather than a stub, so the layout check exercises the
  same live-feedback path Studio uses. The first install attempt rolled back
  cleanly on this failure and restored all six targets before the fix.
- Offline proof: the installer's own 21 tests all pass, including the
  live-feedback contract, ECAM/TCA protected contracts, bridge control channel,
  HardwareLab and global output authority. Aircraft isolation and the MSFS
  aircraft selector re-run clean afterwards.
- Still needs a live check: opening the nine redesigned pages in Studio.

## 2026-09-04 - MobiFlight .mfproj support; PMDG 777 import

- `tools/import_msfs24_functions.py` now reads MobiFlight's newer JSON project
  format (`.mfproj`) from any file sitting loose in the scanned folder. Actions
  are found by walking the config item rather than assuming one device shape, so
  `inputMultiplexer`, `button` and encoder layouts all work, and a future device
  type needs no change. Output items contribute the LVAR that drives their lamp.
- Widened the PMDG filename patterns: both `PMDG-777` and `PMDG777` spellings
  appear in the owner's files, and only the hyphenated one was recognised.
- Imported 36 entries from `Backup/PMDG777-300ER_v1.mfproj`. PMDG 777
  804 -> 840; the catalogue now holds 2,290 functions.
- Preserved the surviving import sources under
  `Backup/msfs24_import_sources_20260904-023000/` (31 files): the 20 Rowsfire
  `.mcc` files, the SPAD.neXt Honeycomb XML, the Stream Deck profiles/scripts
  and the iFly YourControls YAML. The originals were removed from the project
  root, and these were the only remaining copies.
- The iFly `RowsfireA107-IFlyB38M-Lejood.mfproj` import completed once the owner
  re-supplied the file: 65 entries, iFly 737 MAX 8 19 -> 84. The catalogue now
  holds 2,355 functions across 7 families. The `.mfproj` is preserved alongside
  the other sources in `Backup/msfs24_import_sources_20260904-023000/` so it
  cannot be lost again.
- Offline proof: MSFS aircraft selector, aircraft isolation, live-feedback
  contract, Hardware Lab, input chains and global output authority all pass.

## 2026-09-04 - iniBuilds A350 added and imported

- Added the iniBuilds A350 to the MSFS 2024 aircraft selector as a sixth brand,
  with its own isolated mapping workspace. It is one airframe in the imported
  Rowsfire panels; -900 and -1000 variants would share the same family, as the
  Fenix variants do.
- Imported its 61 functions from the Rowsfire `.mcc` set. The catalogue is now
  2,254 functions across 7 families; 16 isolated MSFS workspaces.
- `tools/import_msfs24_functions.py` now imports its family names from
  `muslimsim/hardware/msfs24_aircraft.py` instead of keeping a second copy, so
  the importer and the selector cannot disagree about a family's spelling.
- The selector test's brand-order and no-library expectations were updated
  deliberately; both had caught the intended change first.
- No device driver, simulator writer, output path or power rule changed.
- Offline proof: MSFS aircraft selector, aircraft isolation, live-feedback
  contract, Hardware Lab, input chains and global output authority all pass.

## 2026-09-04 - Imported owner command sources; FlyByWire A32NX gains a library

- Added `tools/import_msfs24_functions.py`, a dry-run-by-default importer for
  owner-supplied MSFS 2024 command sources. It backs up the catalogue before
  writing and records the originating file on every entry.
- Imported 603 new functions from the Rowsfire MobiFlight `.mcc` set (20 files,
  1,170 configs / 1,330 RPN actions), the SPAD.neXt Honeycomb profile (88
  SimConnect/LVAR targets) and the Stream Deck A320 script (22 A32NX LVARs).
  The catalogue grew 1,590 -> 2,193 functions.
- **FlyByWire A32NX went from 0 to 274 functions** and is no longer reported as
  having no imported library. Fenix 192 -> 400, FSLabs 18 -> 82, PMDG 737
  587 -> 614, PMDG 777 774 -> 804.
- The FBW A380X deliberately keeps no library: every imported FBW source
  documents the A32NX, and lending it those LVARs would map an airframe they do
  not fit. iniBuilds A350 functions (101) were skipped because Studio offers no
  A350 workspace.
- 706 duplicate entries across the Rowsfire products were deduplicated by
  (family, target) rather than imported twice.
- `RowsfireA107-IFlyB38M-Lejood_LsDUk.rar` could not be read: it is RAR5 and no
  RAR tool is installed on this machine. Nothing from it is included.
- No device driver, simulator writer, output path or power rule changed. MSFS
  dispatch stays off until its connector is built; these functions are
  mappable, not yet dispatchable.
- Offline proof: MSFS aircraft selector, aircraft isolation, live-feedback
  contract, Hardware Lab, input chains and global output authority all pass.

## 2026-09-04 - Aircraft isolation contract and family-safe mapping reuse

- Added `muslimsim/hardware/mapping_transfer.py`. A brand-new MSFS workspace
  inherits its catalogue-family siblings' mappings once, when its profile file
  is first created, and is independent afterwards. Across unrelated aircraft a
  binding transfers only when its exact target exists in the destination's own
  library; everything else is reported as skipped with a reason. No equivalence
  between aircraft is ever guessed.
- `BridgeSupervisor` seeds a first-time MSFS workspace through that path. It
  runs only when the profile file does not exist, so it can never overwrite
  saved work, and a workspace still opens if seeding fails.
- Added `tools/test_aircraft_isolation.py`, 5 checks: 19 aircraft each with
  their own profile; a mapping saved for one aircraft absent from another;
  family siblings inherit once then stay independent; unrelated aircraft never
  inherit a function they do not have; and the bridge keeps both dispatch
  guards plus its aircraft-scoped worker gates.
- No behaviour of the existing isolation changed. The audit confirmed the
  loaded-aircraft dispatch gate, the MSFS/X-Plane simulator gate and the
  per-aircraft telemetry worker gates were already in place; the test now fails
  loudly if any of them is removed.
- Offline proof: aircraft isolation 5 checks, MSFS aircraft selector 5 checks,
  live-feedback contract 5 checks, Hardware Lab and input chains all pass. Each
  isolation guard was re-broken in a subprocess and confirmed to fail.

## 2026-09-04 - MSFS 2024 add-on aircraft selector

- Added an MSFS 2024 aircraft selector grouped by developer, from one source of
  truth in `muslimsim/hardware/msfs24_aircraft.py`: Fenix (A320, A319, A321),
  FSLabs (A321, A321neo, A321 Sharklets), FlyByWire (A32NX, A380X), PMDG
  (737-600/700/800/900, 777-300ER, 777F) and iFly (737 MAX 8).
- Brands with several airframes are drop-down menus; iFly ships one airframe so
  it stays a plain button. The brand button shows the selected airframe, so the
  active workspace is readable without opening the menu.
- Each airframe has its own isolated MSFS mapping profile, as the X-Plane
  aircraft do. `hardware_profiles.json` (Zibo) and `hardware_profiles_msfs24.json`
  (default MSFS airframe) are deliberately unchanged, so no existing mapping is
  orphaned; other airframes use `hardware_profiles_msfs24_<key>.json`.
- The function browser now filters to the selected airframe's catalogue family,
  so a PMDG command cannot be offered inside a Fenix workspace. The library note
  names the airframe and its real function count instead of the fixed 1,590.
- FlyByWire has no functions in the imported workbook. Both FBW airframes are
  offered anyway at the owner's request, and the mapper states the catalogue has
  none for them rather than showing an unexplained empty list. No command was
  invented for them.
- `BridgeSupervisor.request_workspace_change` gained an optional third argument
  defaulting to the airframe already selected, so every existing two-argument
  caller behaves exactly as before.
- No simulator writer, device driver, HID/serial/SDL owner, output path, power
  rule or output-authority path changed. MSFS dispatch stays off until its
  connector is built.
- Offline proof: new MSFS aircraft selector test 5 checks pass (families matched
  against the real import, 15 isolated workspaces, legacy paths unchanged);
  live-feedback contract, Hardware Lab and input-chain suites all still pass.
  Still needs a live check: opening the new menus in Studio.

## 2026-09-03 - Studio live feedback restored and locked by contract

- Fixed the defect that stopped Studio showing physical movement. Device
  `status()`/`diagnostics()` callbacks were collected inside the status request,
  so one slow driver made the reply take 3.05 s against a 3.00 s control-client
  timeout. Every 0.10 s poll failed, `self._lab` was never refreshed, and the
  faceplates froze while the device list stayed on screen. Nothing raised.
- `ControlServer` now serves device status from a `DEVICE_STATUS_TTL_SECONDS`
  cache refreshed by a background sweep, the same pattern already used for
  hardware discovery. The first reply is still collected synchronously so the
  Studio device list is never empty. Measured on the live rig: status 3.05 s ->
  0.016 s, all 17 registered devices still reported.
- Any device callback over 0.25 s is now recorded as a `slow-device-status`
  diagnostic rather than silently delaying every poll.
- Studio's control-client timeout raised 3.0 s -> 8.0 s for headroom.
- Added `tools/test_live_feedback_contract.py`, which fails if live feedback is
  removed or slowed again, and which reads the device catalogue so a device
  adopted in future must also post live physical feedback.
- Added a Practice-only APU EGT tap on the PU Overhead faceplate. It steps
  0/25/50/75/100 through `lab_output` (one control), not `lab_output_test`
  with action "values", which would zero every output missing from the payload
  and blank the altitude windows, lamps and backlight. In Live the tap stays
  inert and only advises switching to Practice.
- No simulator writer, device driver, HID/serial/SDL owner, mapping, power rule
  or output-authority path changed. No new output path was added, so the
  unpowered-blackout rule is unaffected.
- Offline proof: live-feedback contract 5 checks pass, and each of its four
  guarded regressions was re-simulated and confirmed to fail the test.
  Still needs a live-cockpit check: the Practice APU EGT tap moving the
  physical gauge.

## 2026-09-03 - Performance Phase B: BB35/BB36 share graphical telemetry

- BB35 and BB36 graphical PFD/ND/ENG/MFD/HYD workers now acquire one
  ref-counted `_SmoothTelemetryHub` instead of opening one X-Plane WebSocket
  per physical display.
- The shared smoother consumes Phase-A telemetry listener updates, preserving
  the existing interpolation/prediction behavior without duplicate simulator
  subscriptions.
- Independent BB35 and BB36 HID/output/lifecycle ownership is unchanged. One
  display can restart/replug without stopping the shared data source still
  used by the other.
- BB36 graphical FMC text now consumes the Phase-A raw cache when available;
  its dedicated FMC WebSocket is compatibility fallback only.
- ND route data, TCAS arrays and NAV identifier/string caches now prefer the
  same raw shared telemetry and do not use periodic direct REST while the
  Phase-A hub exists.
- Smoothed display state follows telemetry connection generations; reconnect
  clears previous-aircraft values before fresh data is accepted.
- X-Plane session DataRef/command resolution cache is advanced on the already
  debounced simulator-disconnect edge.
- Telemetry diagnostics now report PFD pool instances and consumer reference
  count.
- No simulator writer, panel command mapping, HID/serial/SDL owner, or
  aircraft-power blackout path changed.
- Offline proof: shared display telemetry 40 checks, shared Phase-A telemetry
  47 checks, output authority 67 checks, Hardware Lab, AGP 80, Portable
  V1/V2/V3, runtime bundle, PDC, PAP3, FCU/EFIS, TCA, Studio check and launcher
  check all pass.


## 2026-09-03 - Shared X-Plane telemetry replaces repeated device REST reads

A performance audit of the owner's current `MuslimSim (2).zip` found that
otherwise-correct device loops could collectively issue roughly 600-700
individual X-Plane DataRef REST reads per second. The main cause was not one
panel: PU, AGP, FCU/EFIS, throttle feedback and other readers each sampled
aircraft state independently.

Performance Phase A adds `muslimsim/simulator/xplane_telemetry.py`:

- one bridge-wide read-only X-Plane WebSocket;
- additive whole-DataRef subscriptions and one latest-value cache;
- named distribution groups by device/feature;
- transparent shared-cache backing for the existing `read_dataref()` and
  `read_dataref_index()` APIs;
- scalar and array-index consumers share the same source value;
- batch subscription failure isolation so one invalid optional ID cannot starve
  a whole group;
- session DataRef/command ID cache;
- bounded exponential retry for resources temporarily missing while an
  aircraft/plugin loads;
- explicit `refresh=True` retained for established stale-ID recovery paths;
- single-flight, reusable, rate-limited REST fallback so a WebSocket outage
  cannot become another HTTP storm;
- `--diagnose-telemetry` 30-second cache/fallback/resolution metrics.

No simulator writer, HID/serial/SDL owner, aircraft mapping, or output-power
authority moved into the telemetry layer. Unknown/lost live data still follows
the existing safe-dark behavior.

Offline proof:
- shared telemetry contract/performance test: 47 checks;
- 1,000 repeated consumer reads from one cached streamed value: zero REST
  fallbacks;
- global output authority: 67 checks;
- Hardware Lab, AGP, Portable V1/V2/V3, runtime bundle, PDC, PAP3, FCU/EFIS,
  TCA, Studio check and launcher check all pass.

Live proof still required: run with `--diagnose-telemetry` on the cockpit and
compare REST fallbacks/cache hit rate and X-Plane frame-time behavior against
the pre-Phase-A session.


This is the short, date-ordered record of completed work. The full story is
in [PROJECT_HISTORY.md](PROJECT_HISTORY.md).

## 2026-09-02 - A footer banner that could be raised but never taken down

The owner reported "Hardware is still connected; waiting for its live update"
permanently pinned to the bottom of Studio. **The hardware was fine and the
status poll was working.** The banner simply had no way to come down.

`_control_failures` counts failed status polls, and three of them raise that
line. Three is reached in 0.3 s at ten polls a second, which every bridge
startup does before the control channel is listening. `_receive_status` then
resets the counter on the next success - but the banner is footer *text*, and
nothing ever set it back. So a normal startup left a stale warning on screen
for the rest of the session, describing a failure that had ended seconds in.

- A recovered status poll now retires the banner its own failures raised.
- Only the three transient connection banners are cleared. A message the owner
  still needs - an output test result, a mapping confirmation, a panel fault
  location - survives an unrelated poll recovering, and that is asserted.
- The three strings became `BANNER_WAITING_UPDATE`, `BANNER_STILL_CONNECTED`
  and `BANNER_SERVICE_STOPPED`, used at their call sites. They were literals in
  two places, so editing the wording would have silently stopped the clearing;
  the test now also fails if a hard-coded banner literal reappears.

Measured while looking for a real fault first: the status snapshot builds in
0.08 ms and serialises to 102 KiB in 0.73 ms against a 1.0 s client timeout,
about 0.7% of a core at ten polls a second. Nothing was actually failing.

- Tests: `tools/test_moza_ab6_capture.py` 106 -> 116 checks. All 26 suites pass
  and `python launch.py --check` passes.

## 2026-09-02 - The AB6 had three selectable controls, not 137

"It works for a couple of seconds then stops." Three more pre-capture
assumptions were still in Studio, and together they meant the AB6 could show a
brief flicker of life and then nothing that could be acted on.

- **`_visual_controls()` returned three hard-coded "visual practice pose" axes**
  for the AB6 - `axis_x`, `axis_y`, `axis_z` - written when its catalogue held
  nothing else. Its 128 contacts, hat, slider and dial were not selectable at
  all, so **no function could be assigned to any of them**. It now reads its
  own catalogue exactly as the A210 does: **3 controls -> 137**.
- **`_learned_source()` returned `""`** for the AB6, on the reasoning that "an
  AB6 preset provides settings, not a verified HID identity". True before the
  capture, false after it, and it made every control an invalid mapping source.
- **The capture-proven selection description was A210-only**, so selecting an
  AB6 contact fell through to "Moza visual calibration control" and never said
  it was mappable. The calibration drag pose also still claimed the base had no
  physical HID axis report.

### Why it looked like it "stopped"

The reader emits the full axis set once on its first report, then **only
changes**. A stationary force-feedback base therefore emits nothing, the
selection flash expires after 1.1 s, and the panel goes quiet. That part is
correct behaviour, not a fault - but with only three selectable controls there
was nothing to interact with afterwards, so it read as having stopped.

### Panel faults now name their own location

The tick swallows any exception from a draw and printed only
`Panel update recovered: {type(exc).__name__}`. A KeyError from a faceplate and
one from a status payload looked identical, which is why the previous round was
diagnosed by inference rather than evidence. It now reports the exception type,
its message and the failing `studio.py:line`, and writes the full traceback to
`logs/studio_panel_faults.log` - once per distinct location, because a draw that
fails once fails every 70 ms.

- Tests: `tools/test_moza_ab6_capture.py` 83 -> 106 checks, asserting both bases
  offer the same 137 controls, that AB6 contacts are valid mapping sources, that
  the placeholders are gone, and that a fault report names a file and line.
  All 26 suites pass and `python launch.py --check` passes.

## 2026-09-02 - "Panel update recovered: KeyError" - a three-key seed

The AB6 page was still blank after being pointed at the right device, and the
screenshot carried the answer in its footer: **Panel update recovered:
KeyError**. The draw was raising, the tick was swallowing it, and an empty
faceplate was the visible result.

`_moza_practice_axes` seeds each base's stored pose. The A210's listed all
eight axes. **The AB6's listed three** - `axis_x`, `axis_y`, `axis_z` - left
from when those were the only axes its preset had named. The lookup then did:

```python
fallback[key] = self._axis_fraction(self._number(item, "value", fallback[key]))
```

The reader publishes **all eight axes on its very first report**, so the moment
live data arrived, `fallback["axis_rx"]` raised `KeyError` and took the whole
panel down with it. Nothing about the reader, the catalogue or the device was
wrong; the page simply could not survive its own hardware working.

- The lookup now fills in whatever the stored pose is missing instead of
  trusting its shape, and reads through `.get(key, .5)`.
- `MOZA_AXIS_KEYS` is defined once, so a seed and a reader cannot disagree
  about how many axes a base has again.
- The AB6's seed carries all eight, matching the A210's.

- Tests: `tools/test_moza_ab6_capture.py` 70 -> 83 checks. The new one
  reproduces the exact failing condition - a three-key seed against a reader
  publishing eight - and also covers a device with no stored pose at all.
- Backup: `Backup/moza_ab6_studio_live_v1_20260902-225902/` holds the
  pre-change file for this and the previous entry.

## 2026-09-02 - "nothing" - the AB6 page was reading the A210

The reader was running and the bridge was on the new code, verified by process
start time. The lab accepted AB6 input and the device was enabled. Studio still
showed nothing, and the reason was three floors up in the GUI.

**Studio's AB6 surface was authored when the AB6 had no captured report**, so
it was written to show nothing on purpose - and every one of those decisions
was still in force:

1. `_moza_a210_live_axes()` was hard-wired to `moza_a210` and returned early
   with `seen=False` on any other page. The AB6 page therefore drew the A210's
   fallback dict - a dead centre pose - whatever the physical base did.
2. The status pill read `"LIVE HID" if live_axes and not is_ab6` - the AB6 was
   explicitly excluded from ever showing live, and labelled REFERENCE/PRACTICE.
3. The eight console contacts were drawn `enabled=False`, with a caption
   stating the button protocol was not captured yet.
4. `_moza_pressed` and `_draw_moza_hat` read `"moza_a210"` unconditionally.
5. **The MAX3 grip tab read the A210's contact pool** while being drawn on the
   AB6 page. The grip is mounted on the AB6 on this rig, and the capture
   observed contacts 1 and 10 closing there - this grip's own TRIGGER and TOP -
   so its presses were arriving on a base the page was not reading.

### What changed

- `_moza_live_axes(device)` replaces the hard-wired helper.
  `_moza_a210_live_axes()` is kept as a wrapper returning
  `self._moza_live_axes("moza_a210")`, so the A210 page is untouched.
- `_moza_pressed`, `_draw_moza_push`, `_draw_moza_raw_badge`, `_draw_moza_hat`
  and `_draw_moza_max3_layout` take a `device` argument **defaulting to
  `moza_a210`**, so every existing call site keeps its exact behaviour.
- The AB6 faceplate now draws from live HID: the stick tracks X/Y, the eight
  console contacts light on press, and the MAX3 tab reads the AB6.
- **SLIDER and DIAL are drawn as axes**, with a live position and percentage.
  They were previously six guessed contacts, `B057`-`B062`, invented from the
  reference drawing; the capture proved both sweep the full 0..65535 range.
- Captions rewritten. They asked for a capture that has now happened, and the
  panel says what is true instead: the base prints no button names, so
  functions are assigned to numbered contacts; Z/Rx/Ry/Rz are declared but
  idle; and nothing is ever sent to this base.

- Tests: `tools/test_moza_ab6_capture.py` 62 -> 70 checks, asserting the AB6
  page reads the AB6, the live-HID exclusion is gone, the contacts are no
  longer disabled, and every helper still defaults to the A210. All 26 suites
  pass and `python launch.py --check` passes.
- Backup: `Backup/moza_ab6_studio_live_v1_20260902-225902/`.
- Live acceptance: restart Studio, open the AB6 page. The header should read
  LIVE HID, the stick should follow the base, SLIDER and DIAL should track, and
  pressing a console contact or a MAX3 button should light it.

## 2026-09-02 - The AB6 capture finished: live axes established, and a reader

The owner ran `--watch` and exercised the base. 28669 frames settled the
question the descriptor could not: **which of the eight declared axes the AB6
physically carries.**

| Axis | Observed | |
| --- | --- | --- |
| X, Y | `0 .. 65535` | full sweep |
| Slider, Dial | `0 .. 65535` | full sweep |
| Z | pinned `32767` | idle |
| Rx, Ry, Rz | pinned `0` | idle |

Hat positions `0, 2, 4, 6, 7` plus the `8` null, and 14 contacts seen closing.

The four idle axes are **kept and marked observed-idle, not deleted.** The
report field exists and decodes; one session showing no motion is evidence, not
proof of absence, and a note costs nothing while a deletion cannot be undone by
the next person who fits a different grip.

### The gap this exposed

The owner said the buttons have no printed names and they would assign
functions in Studio - which is right, and is the honest end of the capture.
But nothing was reading the AB6. Its catalogue entry said `implemented` while
no reader existed, so Studio would have had no input to assign. That would have
been a broken promise the moment they tried it.

- `MuslimSimMozaA210` gained optional `vid`/`pid`/`label` parameters, **all
  defaulting to the A210**, so every existing caller opens the same device and
  behaves exactly as before. Only `_open()` and two log strings were touched.
- The bridge now starts an AB6 reader beside the A210's, in its own `try`, with
  its own device registration, diagnostics and power-cycle entry. One Moza base
  being absent never silences the other.
- Verified live against the connected base: status `connected`, report id 1,
  length 34, events flowing, axes/hat/contacts all decoding.

### Studio's AB6 page now has real controls to bind

137 inputs - 8 axes, hat, 128 contacts - streaming from the base, replacing
three preset-derived `unknown` axes that could never be mapped to anything.

- Tests: `tools/test_moza_ab6_capture.py` extended 50 -> 62 checks, asserting
  the live/idle axis split is recorded and that the idle four stay catalogued.
  All 26 suites pass, `python launch.py --check` passes.
- Backup: `Backup/moza_ab6_reader_v1_20260902-225003/`.
- Live acceptance: restart Studio so the bridge reloads, open the AB6 page, and
  confirm the stick, slider and dial move and that pressing a contact registers
  for **Learn physical control**. No force-feedback output exists, so nothing
  on this base should ever light or resist.

## 2026-09-02 - The MOZA AB6 has a real identity now, read off the base

The AB6 was never captured. It entered the catalogue from an owner-supplied
A320/MSFS2024 `.preset`, and a preset carries calibration numbers rather than a
USB identity or a report layout - so the AB6 sat at `status: unimplemented`,
with no VID/PID, three axis names taken from the preset, and nothing Studio
could actually read.

### The tool

`tools/capture_moza_ab6.py`, in three phases: `--report` for identity and
protocol, `--watch` for live decode and which axes really move, `--capture` for
guided one-control-at-a-time naming.

**It is read-only by construction.** This is a force-feedback base, so the tool
opens the HID handle, reads the report descriptor, reads input reports, and
never calls `write`, `send_feature_report`, or any Moza SDK entry point. The
test asserts that against the parsed AST rather than the source text - the
first version of that check failed on the docstring promising it, which is
exactly the kind of false pass worth avoiding.

### What the base actually said

- **Identity**: VID `346E` / PID `1002`, `Gudsen` / `MOZA AB6 FFB Base`,
  interface 2, Generic Desktop / Joystick.
- **Report descriptor**: 1259 bytes, SHA-256 `d6749e44…4edbdd15` - **byte for
  byte the A210's own descriptor.** The AB6 was *not* assumed to match its
  sibling because they share a vendor id; both descriptors were read and
  compared, and the equality is what licenses reusing the A210's decode.
- **Input**: report `01`, 34 bytes at about 975 Hz - eight unsigned 16-bit
  axes, a four-bit hat, 128 generic HID contacts. The existing capture-proven
  `decode_moza_a210_report` accepts a live AB6 frame unchanged.
- **At rest**: stick near centre, `Rx/Ry/Rz/Slider` flat at zero, `Dial` 773,
  hat 8 (the descriptor's null state), contact 3 closed.

### What landed

- The catalogue entry is rewritten from the capture: `USB HID`,
  `VID 346E / PID 1002`, `implemented`, and 137 real inputs in place of three
  preset-derived `unknown` axes.
- Registered where identity matters: product registry (`346E:1002`), the USB
  lifecycle presence monitor, and `usb.py` so `Power cycle` can restart it -
  keyed separately from the A210 so restarting one never restarts the other.
- **Removed a stale duplicate.** A second, preset-derived `moza_ab6`
  `ProductSpec` existed only because the AB6 had no captured USB identity.
  Leaving both made `product_for_runtime_text("MOZA AB6")` ambiguous and it
  started returning `None`; the platform-V2 suite caught it immediately.

### What was deliberately not done

**Which physical control is which contact number is still owner work.** A
generic HID button number does not say what legend is printed above it, and the
A210 carries the same honest limitation. Same for which of the eight declared
axes the AB6 physically has - `Rx/Ry/Rz/Slider` read flat at rest, but flat at
rest is not proof of absent. `--watch` and `--capture` exist for exactly this
and need the owner at the hardware.

**No force-feedback output was invented.** No Moza output protocol was supplied
or inferred, so `force_feedback_profile` stays `unimplemented` and untestable,
Practice drives nothing on this base, and Studio sends no motor command.
`tools/probe_moza_flight_sdk.py` remains the open line of enquiry.

- Tests: new `tools/test_moza_ab6_capture.py`, 50 checks. All 24 other suites
  pass and `python launch.py --check` passes. Two existing suites failed on
  first run and were corrected rather than worked around: `test_hardware_lab.py`
  asserted the AB6 had no VID/PID, which is now false, and the platform-V2
  ambiguity above.
- Backup: `Backup/moza_ab6_capture_v1_20260902-223755/`.
- `test_bridge_control_channel.py` fails while Studio is open - it launches a
  second bridge - and Studio is running again on this machine.

## 2026-09-02 - Practice mode did nothing on twelve of seventeen devices

The owner reported it plainly: "i can enter any controller page and start mess
with it and it never post anything and all the screen don't react at all and
some other don't even wakeup if i touch them."

That was accurate, and worse than it sounded. `tools/probe_practice_coverage.py`
was written to measure it rather than argue about it - it drives the real
`HardwareLab` and the real `ControlServer.apply_practice_snapshot` with
`apply_lab_output` recorded, so it reports the shipping path's own behaviour.

**Before: 5 of 17 devices posted anything at all.** The PU Overhead's 32 lamps,
ECAM32's 19 LEDs, the throttle's 7 backlights and fault lamps, and the two
HOWALT panels' 17 indicators were all dark no matter what you pressed. With the
simulator off, a working panel and a dead one looked identical - which makes
Practice useless for the one job it has.

The cause was not subtle. `VirtualZiboPreview` only ever modelled five devices,
and `apply_practice_snapshot` only knew those same five by name, so
`only_device=` scoping filtered every press on the other twelve down to nothing.

### What changed

- **New `muslimsim/hardware/practice_echo.py`** holds the policy and no state:
  which controls Practice may drive, and when a device goes back to sleep.
- **Every device now responds when practised.** Its capture-proven lamps and
  LEDs light through `apply_lab_output` - the same single safe path Studio's
  existing output test already uses, which refuses any control the catalogue
  has not marked `implemented` **and** `testable`. **No vendor packet is
  invented anywhere in this change.**
- **New `practice_wake` control command.** Opening a device's page in Practice
  is also asking it to prove itself. This is the only way ECAM32 can respond at
  all: it has 19 proven LEDs and still no catalogued input to press. Studio
  sends it on page change and re-asserts it every 6.7 s while the page is open.
- **Rule 0.1 is honoured, and amended.** A practised device goes dark on its
  own 20 s after you stop using it, and leaving Practice darkens everything at
  once. The rule's old "lights only the one output being tested" wording is now
  "lights the device being practised", recorded in `AGENTS.md` as a deliberate
  amendment at the owner's instruction.

**After: every device that has something driveable posts.** The remaining seven
are correct: `pdc_bb62`'s sole output is `unmapped_vendor_output` with an
`unknown` protocol, both Moza units expose only an `unimplemented` force-feedback
profile, and `tca_boeing`, `winctrl_pedals`, `pdc_bb61_left` and
`pdc_bb52_right` have no output controls at all - they post to Studio, not to
themselves.

### What Practice deliberately still will not do

Displays and actuators are excluded on purpose. Every display adapter takes its
own shape, so a sixth practice page has to be authored, not guessed. Gauges and
solenoids are real actuators here - the throttle's two vibration motors and the
PU's timed starter retract - and Practice lights panels rather than shaking
hardware. Both exclusions are asserted by the tests.

### Practice never passes to Live

Stated by the owner and now enforced and tested: "what you practice never pass
to live... in order for my assigned function to be saved it has to be done in
live. practice only for experiment." The practice path touches inputs, outputs
and diagnostics only; it never reaches `profile_store`. A practice wake is
refused outright while the lab is in Live mode.

- Tests: new `tools/test_practice_all_devices.py`, 277 checks. All 24 suites
  pass, `python launch.py --check` passes, and Studio imports cleanly.
  `test_global_output_authority.py` still passes unchanged at 67 checks.
- New diagnostic: `tools/probe_practice_coverage.py`.
- Backup: `Backup/practice_all_devices_v1_20260902-222134/`.
- **Live acceptance still required.** Restart Studio, turn Practice on, and
  walk the device list: each page should light that panel and only that panel,
  and it should go dark about twenty seconds after you move on. Note that a
  device the bridge never opens with X-Plane off still cannot respond - the
  throttle, TCA, both HOWALT panels and the AB6 have no simulator-down reader
  yet, which is a separate piece of work and is not addressed here.

## 2026-09-02 - The MCDU32 froze, and nothing was watching the PFP3N at all

The owner reported two things: the MCDU32 freezes after a while, and after
closing and reopening Studio neither the PFP3N nor the MCDU32 comes back -
both just stay frozen. `logs/bb36_live_owner_takeover_v3.log` had been
recording the answer for three days: **3556 health failures, 2211 firmware
recovery attempts, and every single one of them failed the same way.**

### What the log actually says

The recorded staleness separates into two clean populations, and that is the
whole diagnosis:

- **5561 stalls read 8.0 or 8.1 s.** The startup grace is 8.0 s, so these
  paths published no heartbeat at all after starting. That is a panel whose
  firmware has stopped acknowledging, and reopening HID cannot reach it.
- **~104 stalls read 3.0 to 3.6 s**, clustered just above the old 3.0 s
  threshold. Those are live panels having one slow frame.

The second population precedes the first. On 2026-09-02 a lone 3.1 s stall at
18:14 tore down a working panel; another at 19:19; at 19:24:59 the write
returned `-1`, and from 19:25 the 8.1 s cascade ran continuously. Overnight on
2026-09-01 the same cascade ran from 00:00 to 09:30 - one teardown and reopen,
font upload included, every twelve seconds, for nine and a half hours.

### Five separate defects, each fixed in the smallest place

1. **The BB36 stall threshold was inside the slow-frame population.** 3.0 s ->
   6.0 s. It clears the worst recorded slow frame with margin and still sits
   below the 8.0 s grace, so a real wedge is still caught on the first check
   after the grace - the wedges report 8.0/8.1 s, which fails either value.
   This is the change that stops working hardware being torn down.
2. **BB35 had no output watchdog at all.** `_active_is_healthy` was thread
   liveness alone, and a worker parked inside a native F0 write to a stalled
   panel stays alive forever - so a frozen PFP3N was reported live and never
   reopened. It now reads the same frame-start heartbeat BB36 reads, seeded in
   `start()` so a worker that blocks on its very first write is still seen. A
   build that publishes no heartbeat keeps its old is_alive()-only contract.
3. **BB35's teardown wrote on a handle its worker might still own.** The three
   darkening reports were sent after a bounded 6.0 s join with no liveness
   guard, so they could interleave with an in-flight native F0 burst and leave
   the panel holding a torn transaction - which outlives the handle close, and
   is still there after a Studio restart. **This is the best candidate for why
   a restart did not help.** BB36 already guarded its teardown exactly this
   way; BB35 now does too. When the worker exits normally, which is the
   established case, the writes are unchanged and still sent.
4. **BB36 retried an impossible recovery forever.** Every attempt failed with
   `LabError: Restart screen/device requires Administrator rights`, because
   `pnputil /restart-device` refuses a non-elevated session - so the one
   recovery this panel responds to was never available. Retries now back off
   1.5 -> 3 -> 6 -> 12 -> 24 -> 30 s and stop there, the first three attempts
   are logged verbatim and then one in twenty, and the first failure prints
   the thing the owner actually needed to know: **a Studio restart cannot clear
   a wedged BB36; run Studio as Administrator, or replug the panel.** A path
   that recovers clears the backoff, so a later unrelated wedge still gets its
   fast first retry.
5. **Studio's status polls were writing the supervisor's health verdict.**
   `live_snapshot` runs the same predicate from HTTP request threads - the log
   carries `PFD HEALTH FAILURE` lines attributed to `process_request_thread` -
   racing the supervisor into reporting the wrong recovery reason. The check
   takes `record=False` now; the supervisor's own call is unchanged.

### What was deliberately not changed

The trigger for the very first wedge is still unproven. The leading remaining
suspect is the ENG PRI / MFD / HYD REST fallback, which issues up to 24
sequential dataref reads at `PFP_PFD_HTTP_TIMEOUT` = 0.25 s inside one frame -
enough to produce exactly the 3.0-3.6 s slow frames above. Raising the
threshold removes the harm without touching that working telemetry path, per
rule 0.2; bounding the fallback itself is a separate decision and is not made
here.

Rule 0.1 note: on a stalled teardown the blackout write is now skipped rather
than raced. A write that interleaves with an in-flight transaction darkens
nothing anyway, and the handle close still happens - this is the same trade
BB36 and PAP3 already made.

- Tests: new `tools/test_display_stall_recovery.py`, 29 checks. All other
  suites re-run unchanged - global output authority 67/67, hardware lab, FMC
  authored faceplates 45/45, portable device platform 11/11, input chains
  28/28, AGP radio 80/80, TCA Boeing 158/158, plus both module self-tests and
  `python launch.py --check`. `tools/test_bridge_control_channel.py` cannot
  pass while Studio is open - it launches a second bridge - and was failing
  for that reason before this change.
- Backup: `Backup/bb35_bb36_freeze_recovery_v1_20260902-214339/`.
- **Live acceptance still required, and it needs a full Studio restart so the
  bridge reloads.** If the MCDU32 is wedged right now, replug it first - no
  amount of restarting will clear it. Then confirm: the MCDU32 no longer
  restarts itself every twelve seconds; a frozen PFP3N is reopened instead of
  reported live; and closing Studio still leaves both panels dark.

## 2026-09-02 - Portable Device Platform V1: product identity replaces COM/index identity

MuslimSim now has one stable physical-product registry and one runtime locator
service. Supported products are identified by VID/PID, product strings and,
where necessary, a read-only protocol identity. Unit serial numbers, COM
numbers, HID paths, SDL indices and install paths are explicitly runtime-only
and are not valid product identity. A replacement D201/D203/BB35/BB36/PAP3/etc.
of the same supported model therefore inherits the same MuslimSim device key
and profile.

The first active owner migrated is the PU Overhead serial side. `--port` now
defaults to `auto`: MuslimSim resolves the present PU serial endpoint from its
`3561:8561` product identity/product strings and resolves again on reconnect.
The historical COM5 text is retained only as an internal interception token for
the established Serial() call; automatic mode never opens COM5 by guess when
the product resolver has not identified the PU. If Windows re-enumerates the same supported PU as COM27/COM44 on
another PC or after replug, the existing reconnectable PU owner opens the new
locator without changing the device profile. An explicit `--port COMx` remains
a diagnostic override only. No PU packet, timing, starter, lamp, input, or
aircraft-control behavior was changed.

Read-only Studio discovery now sources its established WinCtrl/generic USB map
from the shared product registry and adds an additive platform snapshot for
serial endpoints/runtime readiness; existing callers that read only `devices`
retain the same contract. HOWALT remains safer than a raw USB match: D201 and
D203 share the WCH bridge and are still separated by their existing read-only
MobiFlight firmware name, never by the captured serial number.

The PyInstaller recipe was also tightened for an end-user, no-pip build. It
now explicitly bundles `pu_physical_authority.py`, websocket-client, all
MuslimSim hardware/device/control submodules, X-Plane/MSFS command catalogues
and the PFP bank plan. `build_exe.py` runs the new portable product/locator and
runtime-bundle tests before packaging.

Tests: `tools/test_portable_device_platform.py` 11/11, portable runtime recipe
19 checks, global output authority 67/67, Hardware Lab self-test pass, AGP radio
119/119, TCA Boeing catalogue 158/158, PDC BB62 pass, PAP3 MCP pass, FCU/EFIS
BA01 pass, and `python launch.py --check` pass. The changed source plus existing
Python source parses cleanly. No hardware or simulator was opened. Live
acceptance still required on Windows: start with the PU on its current COM,
unplug/replug if Windows changes the COM number, then prove the same PU owner
recovers without `--port`; separately confirm all existing HID/HOWALT panels
retain their current behavior.

## 2026-09-02 - The AGP radio page now operates the aeroplane

The radio page is wired: the window follows the aircraft, the knobs tune it,
and SET swaps the standby in. This is the change that reverses the AGP's
display-only contract, so it was done on its own with its own tests.

### What the windows show

- **CHR** names the selected radio. Seven segments have no diagonals, so a true
  "V" cannot be drawn - `U` is the only form the hardware can render, and the
  window reads **U1 / U2 / U3**. A "V" mask was deliberately not invented; the
  test asserts one never appears.
- **UTC** is the frequency of that radio, read from the aeroplane: 120.900 MHz
  reads as `120900` across the six digits.
- **ET** is the transponder code, replaced by the mode - ALoF / ALon / tA /
  tArA - for 1.5 s whenever it moves, because a spring switch returns to centre
  and would otherwise leave no confirmation it was seen.

### The switches

- **GPS / INT / SET** picks the radio: V1, V2, V3. On every other page that
  switch still selects the display page exactly as before.
- **CHR** is the outer knob, whole megahertz. **RST** is the inner one, 25 kHz
  channels. The two descriptions given for this were opposite, so both live in
  `AGP_RADIO_OUTER_KNOB`/`AGP_RADIO_INNER_KNOB` and swapping them is one edit.
- Turning either knob **enters standby**, because tuning the live frequency is
  not something a radio lets you do. CHR then reads **Sb1 / Sb2 / Sb3** so the
  window says which frequency is on it.
- **The SET knob** commits: it writes the tuned standby and fires the
  aeroplane's own swap command, so the aircraft performs the exchange rather
  than MuslimSim writing an active frequency directly. Pressing it again steps
  back into standby to tune the next one. That is the whole of "SET makes this
  active, tap again to edit".
- **RUN** turns the transponder on; the spring **RST** steps ALT OFF -> ALT ON
  -> TA -> TA/RA, driven through Zibo's own `transponder_mode_up`/`_dn` to the
  target position rather than by writing a mode value.

### The sluggishness

Every radio branch sets `next_agp_display_read = 0.0`, so a knob refreshes the
window on the same pass instead of waiting out `AGP_DISPLAY_INTERVAL`. That
0.25 s wait was the entire reason the numbers felt like they lagged the knob.

### Safety and limits

- **V3 is not tunable and does not pretend to be.** Every Zibo com3 DataRef is
  read-only, proven by `tools/probe_howalt_live_targets.py`, so V3 displays the
  aeroplane and the knobs and SET decline to act on it.
- A standby being tuned is the owner's, not the aeroplane's: the refresh never
  overwrites it mid-edit.
- The radio commands resolve exactly like the gear commands - optional, warned
  about once, and an unavailable one leaves that action inert rather than
  stopping the panel.
- The page is reached by the CHR knob like every other page, and the existing
  CHR press still means "back to flight", so there is always a way out.
- Studio's faceplate now follows the bridge's published page, so the drawn
  panel cannot drift out of step with the physical windows.

### Tests

`tools/test_agp_radio_page.py` extended to **119 checks**. It does not check
that a legend exists - it encodes each one into a real packet and asserts every
character lights at least one segment, the only thing separating a legend from
a blank window. Stepping is checked at the band edges and from junk input, and
a full turn of the outer knob must leave the channel part alone. The wiring is
checked at the source: the switch picks the radio, the knobs step the standby,
SET writes and swaps, V3 is excluded, the refresh is forced, and the display
pass does not overwrite a standby being edited.

15 of 16 suites pass; `test_bridge_control_channel.py` fails only because
Studio is running and owns the loopback port. `python launch.py --check`
passed. Backup: `Backup/agp_radio_page_wiring_20260902-135305/`.

**Live check needed, after a full Studio restart:** turn the CHR knob past
NAVIGATION to reach RADIO, confirm U1/U2/U3 follow GPS/INT/SET, tune with CHR
and RST, press SET and confirm the standby becomes active, then RUN and the
spring RST for the transponder modes.

## 2026-09-02 - Why the AGP radio legend showed nothing, and the font that fixes it

- **The window showed a blank, not an error.** The AGP is a real seven-segment
  display driven by packed bitplanes, and `AGP_SEGMENT_MASKS` defined only the
  ten digits, `-` and space. `_agp_encode_segments` falls back to `0x00` for
  anything else, so every letter of a radio legend lit **zero segments** and
  the digit simply went dark. Nothing failed and nothing was logged.
- Added the letters seven segments can actually form - A b C d E F H L n o P r
  S t U y - each derived from the masks already in the table in the same bit
  order, not guessed. The ten digits, `-` and space are byte-identical, and a
  regression check pins them.
- **There is no V on seven segments.** `U` is the long-established stand-in, so
  the selected radio reads **UHF1 / UHF2 / UHF3** with a rounded V. A "V" mask
  was deliberately *not* invented, and the test asserts it stays absent.
- The standby legend does double duty as the edit indicator, which answers the
  third request without spending a window on it: **UHF2** means the frequency
  below is the live one, **Stb2** means it is a standby being tuned. Tapping
  SET moves between them, so "SET makes this the active frequency" and "tap
  again to edit standby" are the same control.
- ET carries the transponder code, which is what is wanted at a glance, and is
  replaced by the mode - **ALoF / ALon / tA / tArA** - for 1.5 s whenever the
  mode moves. A spring switch returns to centre, so without that flash there
  would be no confirmation the switch was seen.
- New suite `tools/test_agp_radio_page.py`, 108 checks. It does not check that
  a legend exists; it encodes each one into a real packet and asserts **every
  character lights at least one segment**, which is the only thing that
  distinguishes a legend from a blank window. It immediately earned that: it
  caught `Stb1` using an `S` that had no mask, before any of it reached the
  panel. `S` now reuses the digit `5` mask, which is the same shape.
- Tests: 15 of 16 suites pass. `test_bridge_control_channel.py` fails only
  because Studio is running and owns the loopback port - confirmed in the
  process list - and `python launch.py --check` passed.
- Backup: `Backup/agp_segment_letters_20260902-134100/`.
- **Still to wire, and deliberately not rushed:** `_agp_radio_page_text` is the
  content model and is proven, but nothing calls it yet. The remaining work is
  the display hook, an immediate refresh on a knob event rather than waiting
  out `AGP_DISPLAY_INTERVAL` (0.25 s, which is the sluggishness reported), and
  routing GPS/INT/SET to the radio selection, the CHR and RST encoders to the
  frequency, SET to the active/standby swap, and RUN/STP/RST to the
  transponder. That last part reverses the AGP's display-only contract and
  writes to a live aircraft, so it is being done as its own change with its own
  tests rather than folded in behind a font fix.

## 2026-09-02 - An authored AGP faceplate, drawn the HOWALT way

- The AGP faceplate was generated inline in `muslimsim/gui/studio.py` from
  proportional boxes. It is now authored the same way MUSLIMRTP and MUSLIMATC
  are: `muslimsim/devices/agp_faceplate.py`, one fixed 900x660 reference space
  taken from the owner's photograph, reserved label and control regions checked
  against each other **at import**, and a single uniform scale so nothing
  reflows into anything else.
- That validator earned its place immediately: it caught the CHR encoder and
  the GPS/INT/SET paddle authored on top of each other before anything was
  rendered. The right column was respaced and both fit.
- Drawn from the photograph: the LDG GEAR green window with its three
  gear-down arrows, BRK FAN, the LO/MED/MAX autobrake blocks, the A/SKID &
  N/W STRG bat toggle with its ON/OFF legends, TERR ON ND, the amber
  separators, the recessed CHR/UTC/ET windows with their MIN/SEC and
  HR/MO-MIN/DY-SEC/Y sub-legends, the three white press-encoders with a
  travelling ball in a channel, both three-position paddles, and the UP/DOWN
  gear lever panel alongside.
- All 24 catalogue controls the panel offers keep a clickable tag, checked
  across both switch positions because some are only drawn in one.
- **Window modes.** The three windows now have two pages, chosen by a button on
  the faceplate itself: `clock` is the panel exactly as it has always been, and
  `radio` re-labels the windows RADIO / FREQ / SQUAWK for the radio and
  transponder head described below. The mode is Studio view state and never
  changes what the hardware reports.
- Three additive edits to `studio.py`: the mode's initial value, the dispatch
  to the new module, and an intercept so the mode button does not fall through
  to select-or-activate - it is not a catalogue control, and in Practice that
  fallthrough would try to operate something that does not exist. **The
  original `_draw_agp` is kept as the fallback**, so a drawing error can never
  leave the panel unusable. One line removed, 31 added.
- New suite `tools/test_agp_faceplate_layout.py`, 50 checks: both modes render,
  every catalogue control is clickable, the printed legends are present, the
  window legends actually change with the mode, and every authored region stays
  inside the reference space. **All 15 suites pass** and `launch.py --check`
  passed.
- Backup: `Backup/agp_faceplate_v1_20260902-132345/`.
- **Not yet done, and deliberately not half-done:** radio mode currently
  *draws* but does not yet *operate*. Wiring GPS/INT/SET to the VHF selection,
  the CHR and RST encoders to the frequency with SET to accept, and RUN/STP/RST
  to the transponder mode is bridge work, and it changes the AGP's standing
  contract - `bridge/final.py` says in as many words that CHR/UTC/ET are
  "intentionally display-only: they read the selected Zibo values and never
  write anything back". Making them write is a deliberate reversal of that,
  and it is the next task rather than something to slip in unannounced.

## 2026-09-02 - ATC source lamps back in Live, and a two-speed pitch trim

- **The ATC 1/2 lamps stopped showing.** They are the "1" and "2" lamps beside
  the XPNDR legend, and they were only ever driven by
  `_handle_howalt_practice_input` - practice/Test mode. In Live nothing wrote
  them, so they simply sat wherever they had last been left. That went
  unnoticed until the new aircraft-power blackout started clearing them on the
  way to dark, after which nothing ever lit them again. **This one is mine.**
  - Fixed at the cause rather than by not clearing them: in Live they are now
    driven from `laminar/B738/switch/xpndr_atc_pos`, the aircraft's own source
    position, which is the thing the lamps report. Dirty-only, and a manual
    Studio output on either lamp still wins.
  - They also come back after a blackout, because the power restore clears the
    live value cache.
  - The practice handler had the same polarity error the faceplate selector
    had: it lit "2" for a closed contact. The contact closes in position 1, so
    both now agree.
  - Proof: aircraft position 0 -> `1-LED=255, 2-LED=0`; position 1 ->
    `1-LED=0, 2-LED=255`; and unpowered -> ALL_OFF -> power restored ->
    lamps re-asserted.
- **Pitch trim was too slow.** One cadence cannot be both fast and accurate on
  a spring rocker, so there are now two, and holding the rocker chooses.
  - A short press keeps the proven fine cadence exactly as it was - 0.10 s
    interval, 0.10 s command duration - so a single nudge is still one small
    step. That is the accuracy half, and it is unchanged.
  - Holding past `WINCTRL_PITCH_TRIM_ACCEL_AFTER` (0.45 s) switches to the fast
    pair: a 0.04 s repeat interval with a 0.18 s command duration. The duration
    deliberately outlasts the interval so activations overlap and the trim
    wheel runs **continuously** instead of stepping, which is where the old
    "slow" feel came from - each activation ended before the next arrived.
  - All four values are named constants next to `WINCTRL_PITCH_TRIM_COMMANDS`
    so the feel can be tuned without touching the loop.
  - `winctrl_trim_hold_since` tracks the current hold and is cleared when the
    rocker returns home. It never influences direction.
- Rule 0.2: both are additive. The trim block's held-state latches, direction
  choice, error backoff and Studio-binding precedence are untouched, and the
  readout re-arm added earlier still fires.
- Tests: **all 14 suites pass**, including `test_bridge_control_channel.py`,
  which passes again now that Studio is closed. `python launch.py --check`
  passed.
- Backup: `Backup/atc_source_leds_and_trim_rate_20260902-131639/`.
- Live check: confirm the ATC 1/2 lamps follow the source switch, and that a
  tap on the trim rocker still gives one small step while a hold runs the wheel
  smoothly. If the hold is now too fast, lower `WINCTRL_PITCH_TRIM_FAST_DURATION`
  or raise `WINCTRL_PITCH_TRIM_FAST_INTERVAL`.

## 2026-09-02 - The blackout is back, and this time the trim LCD survives it

The owner asked for the working blackout returned, every device cold and dark
with an unpowered aeroplane, every device asleep after Studio closes - and the
pitch trim back when the aircraft is loaded. That last clause is the whole
reason this was reverted once, so it is the part that got the attention.

### Why it broke the trim LCD last time

The RUD TRIM number is **event-driven, not polled**. It is written only while
the rocker is moving, and the readout disarms itself on the settled reading
after release - `winctrl_stab_trim_readout_pending` is set when the rocker
moves and cleared when it stops. The bridge comment says it plainly: nothing
is read from the simulator unless the owner is actually trimming.

So a blackout takes `trim_display_backlight` to 0 and blanks the window, and
**nothing ever writes the number again** until the owner physically moves the
trim rocker. Restoring the backlight brings back a window that is lit and
empty. The AGP authority block had always got this right for its own display -
it clears `last_agp_display_text` and forces `next_agp_display_read = 0.0` on
restore - and the throttle block simply never had the equivalent.

**The fix is three lines in the restore branch:** re-arm
`winctrl_stab_trim_readout_pending = True` and make it due immediately with
`next_winctrl_stab_readout = 0.0`, so the stabilizer units come back with the
power. Guarded now by two new checks, with the reason written into the test, so
this cannot quietly return.

### What was restored

All of it byte-identical to the proven 2026-09-01 code, not rewritten:

- `_winctrl_throttle_blackout` / `_winctrl_throttle_restore_defaults`, which
  write the captured channel report at 0 and at the captured defaults. **How it
  goes dark:** `_winctrl_throttle_output_packet(key, 0)` - the protocol's own
  off, no invented packet.
- The aircraft-power authority block, beside the AGP one and behaving
  identically: only while the simulator is up, only outside Test mode, rate
  limited to 0.5 s, written only on a change of state.
- The simulator-offline blackout, which also resets the remembered state to
  unknown so recovery re-applies rather than trusting a stale belief.
- The Studio-shutdown blackout inside `_close_winctrl_trim_display`, under the
  existing lock while it is still the sole owner.

Insertion-only into `bridge/final.py`: 111 lines added, and the single removed
line is that function's docstring, reworded to say it now releases the handle
dark.

### D201 and D203 now inherit rule 0.1

They had no power path at all - no avionics or battery DataRef anywhere in the
stack, `all_off()` reachable only through a display command string, and
`stop()` closing the port with the panel lit.

- `_all_panels_dark` calls each router's own `all_off`: `set_output(name, 0)`
  for every declared output and a blank through the same masked display writer
  normal output uses. **No vendor packet was invented to force this dark.**
- Aircraft power is read from the same candidates `bridge/final.py` uses for
  the PU and the throttle - `dc_stdbus_status`, then `battery_on`, then
  `avionics_on` - because rule 0.1 is one rule about the aeroplane, not a
  per-device opinion.
- The two kinds of "no reading" are told apart, matching
  `_agp_aircraft_output_powered`: no ref resolved at all means the aircraft
  publishes none, so preserve what was working; a ref that resolved and cannot
  be read is live data lost, which goes dark.
- Both shutdown paths darken before the ports close - `stop()` and the
  monitor's own exit when the bridge's shutdown event fires.
- Proof: unpowered -> both panels ALL_OFF with nothing lit; powered -> normal
  display; ref unreadable -> ALL_OFF; no ref published -> preserved; and
  `stop()` -> ALL_OFF on both before either port closes.

### The PU is still the exemption, and that is not a gap

The owner asked for every device, and the PU cannot comply with the shutdown
half: it has no off state, returning to its physical knob brightness about a
second after anything stops sending it frames. Five attempts were made and
removed on 2026-09-01. `AGENTS.md` records the exemption and
`DEVICE_REFERENCE.md` records the measurements. **It does go dark when the
aircraft is unpowered, which is the half that works and the half that matters.**
The two stale test checks guarding the removed exit blackout were dropped, with
the reason written where they stood.

### Tests

`tools/test_global_output_authority.py` was still the pre-revert version,
asserting PU dim code the owner had deleted. Trimmed exactly as the 2026-09-01
entry describes - the PU shutdown-dimmer checks and the dim-holder/COM5
handover checks, both of which only guarded removed code - then extended with
the HOWALT coverage entries and the three new trim-recovery checks.

**It passes at 67 checks. It was failing when this session started.** 13 of 14
suites pass; `test_bridge_control_channel.py` fails only because Studio is
running and owns the loopback port, the documented cause, confirmed by finding
`MuslimSim Studio.pyw` and its bridge live in the process list.
`python launch.py --check` passed.

Backup: `Backup/winctrl_blackout_restored_with_trim_recovery_20260902-122416/`.

**Live check needed, and it needs a full Studio restart:** with the aircraft
cold and dark confirm the throttle backlight, the flaps/airbrake backlight, the
RUD TRIM window and both HOWALT panels are all off; switch the battery on and
confirm they come back **and that the RUD TRIM window shows the stabilizer
units again without touching the rocker**; then close Studio and confirm
everything stays dark except the PU, which returns to its knob brightness.

## 2026-09-02 - ATC source and ALT source reach the aircraft

The last two unmapped D203 controls now have measured targets. The earlier
searches missed them because the names use `xpndr_`, not `transponder_` or
`atc_`, and because the switch is moved by a **command** while its position is
published as a separate read-only DataRef.

- Measured in `B737-800X/b738_4k.acf`:
  - position, read-only: `laminar/B738/switch/xpndr_atc_pos` and
    `laminar/B738/switch/xpndr_alt_pos`
  - movement, commands: `laminar/B738/toggle_switch/xpndr_atc` and
    `laminar/B738/toggle_switch/xpndr_alt`
- The mismatch that needed solving: the D203 switch is **absolute** - it is
  either in position 1 or position 2 - while the aircraft offers only "flip
  it". Firing the toggle on every event would make the aircraft switch follow
  the *number of events* rather than the physical position, and the two would
  drift apart the first time either side moved alone.
- `_set_atc_source` reads the aircraft's position, compares it with the
  physical one, and fires the toggle **only when they disagree**. Repeated
  events are absorbed, and moving the switch re-asserts its position after the
  aircraft was changed from the cockpit.
- Both edges are dispatched. `_dispatch_atc_live` discards `release` for
  everything else, so the source branch is decided ahead of that guard -
  moving a two-position switch to position 2 is a release, not nothing.
- Proof: from sim position 1, "switch to 1" is handled with no toggle, again
  with no toggle; "switch to 2" toggles once and the position follows; again
  with no toggle. ALT behaves the same. On an aircraft publishing neither
  DataRef, both return False and stay remappable.
- **One live check needed, and it is a coin flip that the hardware settles.**
  The physical contact closes in position 1 and Zibo counts its position from
  0, so pressed maps to position 0. If the switches turn out reversed, it is
  one edit: `ATC_SOURCE_PRESSED_POSITION`, kept as a single named constant for
  exactly this reason.
- Tests: 13 of 14 suites pass, unchanged, with the same deliberate
  `_winctrl_throttle_blackout` failure. `python launch.py --check` passed.
- Backup: `Backup/howalt_v4_atc_alt_source_20260902-115632/`.

## 2026-09-02 - VHF3 follows Zibo's third COM, DATA and all

The aircraft answered the VHF3 question directly, so it is now wired from
measured names rather than guessed ones.

- `tools/probe_howalt_live_targets.py` against `B737-800X/b738_4k.acf`
  (13534 DataRefs) found Zibo's third COM published in parts:
  `laminar/B738/comm/com3/act_freq_MHz` and `_kHz` with an `act_freq_data`
  flag, and the matching `stdby_freq_*` trio.
- The `_data` flag is the interesting one. It is what puts **DATA** in the
  window instead of a number, which is exactly what the owner reported seeing
  in the sim - DATA in the active window, 118.800 in the standby.
- Added `_zibo_com3_window`, which returns "DATA" when the flag is set, else
  `MHz.kHz` zero-padded to three places, else "" when the aircraft publishes
  no third COM at all.
- All six DataRefs are **read-only**, so VHF3 stays display-only. There is no
  writable third-COM target, so the panel does not pretend to tune it.
- Proof: vhf1 -> 120.900/129.875, vhf2 -> 121.500/118.250,
  **vhf3 -> DATA/118.800**, hf1 -> blank; and on an aircraft with no third
  COM, vhf3 falls back to blank rather than showing COM1.
- The letters go to the firmware's own MAX7219 font, so how cleanly D-A-T-A
  renders on the physical 7-segment window still needs a look on the hardware.
- Backup: `Backup/howalt_v4_vhf3_zibo_com3_20260902-115338/`.
- Still open: ATC source 1/2 and ALT source 1/2. Neither `transponder_source`,
  `xpdr_source`, `atc_source` nor `alt_source` exists anywhere in those 13534
  DataRefs, and the `laminar/B738/toggle_switch/` sweep was truncated at 40
  entries. The probe now prints up to 250 per group and also sweeps every Zibo
  knob/selector and anything mentioning ATC or XPDR.

## 2026-09-02 - D201 selector windows, and the inverted D203 source switches

Two defects reported from the hardware after the Live routing fix.

- **VHF3/HF1/HF2/AM showed VHF1's frequency.** `_sync_live_displays` chose its
  DataRef pair with `if self._rtp_live_radio == "vhf2": ... else: COM1`, so
  every selector position that was not VHF2 - including VHF3, HF1, HF2, AM and
  OFF - fell into the COM1 branch. The panel confidently displayed COM1 under
  a selector that was not COM1.
  - Replaced the two-way branch with `LIVE_RTP_RADIO_SOURCES`, which maps only
    the positions that have a verified aircraft source: VHF1 to COM1, VHF2 to
    COM2. A position absent from that table now **blanks** SMG-1/SMG-2 rather
    than showing another radio's frequency. Wrong data is worse than none, and
    this matches the panel's existing rule that unverified controls are not
    redirected to a guessed target.
  - Proof: vhf1 -> 120.900/129.875, vhf2 -> 121.500/118.250, and vhf3, hf1
    and am -> blank. NAV and squawk paths untouched.
  - VHF3 does not yet *follow* the aircraft. Doing that needs the aircraft's
    own VHF3 source, which is not guessed here; see the open question below.
- **XPNDR source and ALT source read backwards in practice mode.** Both
  selectors were drawn with `1 if _pressed(...) else 0` against labels
  `("1","2")`, so a pressed contact rendered as position 2. On the hardware
  the closed contact is position 1, so both read inverted. Flipped both to
  `0 if _pressed(...) else 1` - one expression each, two lines total, no other
  behaviour changed.
- Neither source switch is dispatched in Live: `_dispatch_atc_live` returns
  False for `xpn_1_2` and `alt_1_2` by design, because no verified aircraft
  source-selection target has been established. They remain remappable. This
  is unchanged here and is the second open question below.
- Tests: 13 of 14 suites pass, unchanged. `tools/test_global_output_authority.py`
  fails identically before and after on `_winctrl_throttle_blackout`, which is
  absent by the owner's deliberate revert to the working trim LCD.
  `python launch.py --check` passed.
- Backup: `Backup/howalt_v4_radio_select_and_source_switch_20260902-114248/`.
- Added `tools/probe_howalt_live_targets.py` so those two questions are
  answered by the aircraft rather than guessed. It searches the loaded
  aircraft's DataRefs and command inventory for VHF3/third-COM, transponder
  source and altitude source, prints each match with its current value and
  whether it is writable, and re-checks the five NAV commands the D201 lower
  encoders and transfer key already use - because "the NAV knobs do nothing"
  and "these command names are not in this aircraft" look identical from the
  cockpit. Read-only: it writes nothing, opens no serial port and is safe to
  run beside a live bridge.
- First run of that probe found nothing at all, and the reason is worth
  writing down: `filter[name]` on the `datarefs` endpoint is an **exact-match**
  filter that answers HTTP 404 for a partial name. It cannot discover anything.
  That is why `resolve_dataref_id` works - it only ever passes full names - and
  why every substring search in the first version returned 404 while the
  command inventory, which is paged rather than filtered, worked fine. The
  probe now pages the whole DataRef inventory and filters locally, the same
  shape as `_muslimsim_list_live_commands`.
- The same run confirmed the NAV command names are correct: all five of
  `sim/radios/nav1_standy_flip` and `stby_nav1_coarse_up`/`_down`/`fine_up`/
  `_fine_down` are present in `B737-800X/b738_4k.acf`. So the NAV knobs doing
  nothing was the dead write path, not a wrong name. Zibo also publishes its
  own `laminar/B738/push_button/switch_freq_nav1_press`, which is the better
  transfer target if the stock command turns out to be ignored - not changed
  yet, pending a live retest with the write path restored.
- Open, pending the owner's capture or confirmation:
  1. the aircraft's VHF3 active/standby source, so VHF3 can follow the sim;
  2. a verified target for ATC source 1/2 and ALT source 1/2 - the aircraft
     labels these ATC 1/2 and ALT 1/2, so they are expected to appear in the
     `laminar/B738/toggle_switch/` sweep the probe now prints.

## 2026-09-02 - D201 and D203 reach the aircraft in Live mode

- **Symptom:** MUSLIMRTP (D201) and MUSLIMATC (D203) behaved correctly in
  practice mode but controlled nothing in Live. Panels lit, displays tracked,
  and the radio selector moved, but no COM/NAV transfer, no tuning, no
  ATC/TCAS mode change, no IDENT/TEST and no squawk edit ever reached the
  simulator.
- **Cause:** `install_howalt_v4` accepts five simulator helpers. The bridge
  call site passed only the two read helpers, `resolve_dataref_id` and
  `read_dataref`. `HowaltV4Bundle.__init__` tried to recover the three write
  helpers with `getattr(__main__, ...)`, which cannot work in this process:
  `muslimsim/core/engine.py` loads `bridge/final.py` under the module name
  `_muslimsim_bridge_engine`, so `__main__` is `launch.py` and all three
  lookups returned `None`. `_command_once` and `_write_ref` both open with a
  `callable(...)` guard, so every live control returned False without ever
  attempting a write. Reads worked, which is why the displays looked healthy.
- **Fix:** pass the three helpers `bridge/final.py` already defines, at the
  existing HOWALT call site, exactly as the PDC BB61/BB52 dispatchers and
  three other installers in the same file already do - `set_dataref`,
  `resolve_command_id` and `activate_command`. Insertion-only: 3 lines added,
  0 removed, confirmed by diff against the backup. No existing caller changed
  and no working code was restructured.
- Signatures were checked against the call sites before wiring:
  `set_dataref(api_version, dataref_id, value)` against
  `self.set_dataref(version, ref, float(value))`;
  `resolve_command_id(api_version, name)` and
  `activate_command(api_version, command_id, duration)` likewise.
- **Proof, offline with fake helpers, before vs after.** Before, only `vhf1`
  was handled, and that is a local selector state change that sends nothing.
  Every simulator-touching control returned False with zero calls: `tfr1`,
  `tfr2`, `bmq2_1`, `bmq2_2`, `bmq3_1`, `stby`, `ta_ra`, `ident`, `atc_test`
  and `bmq1_1`. After, all of them dispatch - the ten above issue their
  command, and `bmq1_1` issues the squawk DataRef write.
- Tests: 13 of 14 suites pass, unchanged from before this fix.
  `tools/test_global_output_authority.py` fails identically before and after,
  on `_winctrl_throttle_blackout`, which is absent by the owner's deliberate
  revert to the state where the trim LCD works. Not touched here.
  `python launch.py --check` passed.
- Backup: `Backup/howalt_v4_live_write_helpers_20260902-112239/`.
- **Known gap, not addressed here:** the HOWALT V4 stack has no rule 0.1
  power path. There is no reference to any avionics or battery DataRef in it.
  `all_off()` exists at `howalt_v4_protocol.py:791` but its only reachable
  caller is a display command string of "all off"/"blackout", and `stop()`
  closes the port without darkening. D201/D203 are also absent from the
  device-coverage table in `tools/test_global_output_authority.py`. This
  change adds no output path; it only restores the input path.
- Live check still needed: with the aircraft powered, confirm VHF1/VHF2
  select COM1/COM2, the transfer keys flip active/standby, the four encoders
  tune, the five ATC detents drive the Zibo transponder mode, and each of the
  four encoder sections edits its own squawk digit.

## 2026-09-01 - Every PU overhead shutdown attempt removed

- None of them worked, and the owner asked for them out. Removed from
  `bridge/final.py`, restoring the original code exactly:
  - the extended pre-stop wait, back to `max(0.15, interval * 3.0)`
  - the COM5 owner's exit blackout
  - the `P2=1,P3=1` shutdown dim frame, with the optional `p2`/`p3` parameters
    and `PU_DIMMER_*` constants added for it. `build_packet` is byte-identical
    to before and `_pu_safe_dark_packet` is back to `OVHD,0,4,4,0,...`
  - `_pu_release_dim_holder` / `_pu_start_dim_holder` and both call sites
- Deleted four dead-end tools: `pu_dim_holder.py`,
  `probe_pu_shutdown_relight.py`, `probe_pu_dark_frame.py`,
  `probe_pu_vendor_minimum.py`.
- **What is kept is the part that works: when the aircraft is unpowered, every
  device goes dark.** `_pu_output_mode` still returns `aircraft-unpowered` and
  drives the PU dark; the throttle blackout still fires on aircraft power loss,
  simulator loss and handle release; AGP, ECAM, FCU/EFIS, BB35, BB36 and PAP3
  are untouched.
- The PU is now exempt from the shutdown half of rule 0.1, recorded in
  `AGENTS.md` and `DEVICE_REFERENCE.md` so it is not attempted a sixth time. It
  has no off state: it returns to its physical knob brightness about a second
  after anything stops sending it frames. Established by driving the panel
  directly three ways - closing the port, varying the frame, and sending PU
  CONNECT's own minimum - and in every case the dim lasted exactly as long as
  the stream.
- Tests: `tools/test_global_output_authority.py` trimmed 72 -> 52 checks,
  dropping everything that only guarded the removed code. The device-coverage
  table, the throttle blackout checks and the AGP power checks all remain. All
  14 suites passed and `python launch.py --check` passed.
- Backup of everything removed:
  `Backup/pu_shutdown_attempts_removed_20260901-221822/`.

## 2026-09-01 - A holder keeps the PU dim after Studio closes

- The PU has no off, and no shutdown frame can leave it dark: it returns to its
  physical knob brightness about a second after anything stops sending it
  frames. Tested against the port closing, the frame contents, PU Korea's own
  minimum, and the stream length; the dim always tracked the stream.
- The owner asked for a helper anyway, and asked the right question of it -
  if we are paying for a helper, make it hold. One correction went with that:
  a helper can hold the **dim floor**, not darkness. `P2=1,P3=1,P8=0` is as far
  as this protocol goes; only the knob reaches true off.
- Added `tools/pu_dim_holder.py`. It streams the captured vendor minimum at the
  bridge's own cadence and does nothing else. Confirmed on the hardware: the
  panel holds dim, and releases the moment PU CONNECT MSFS starts.
- **It holds COM5, which is its entire cost**, so it yields to anything with a
  better claim: PU CONNECT starting, a stop file, or Ctrl-C. It refuses to
  start while Studio or the bridge is running.
- The handover is a race, and the rate is a straight trade rather than a free
  win. Each scan enumerates every process at about 10 ms, so the 1 s default
  costs roughly 1% of one core and leaves a 1 s window; `--scan 0.2` closes the
  window at 5%. Measured, not estimated.
- Wired into the bridge, two calls and nothing else touched:
  - `_pu_release_dim_holder()` before the COM5 open at line 18997, ahead of the
    open at 19006. It asks rather than kills, and the wait is bounded: a stuck
    holder cannot hang every Studio start.
  - `_pu_start_dim_holder()` after `ser.close()`, at 24755 against the close at
    24746, so the two never hold the port at once. Launched detached so
    Studio's exit is not blocked, and told `--wait-for-exit 20` because
    MuslimSim is necessarily still alive at the moment it is launched.
- The holder gained `--wait-for-exit` for that reason: launched from a running
  Studio, it must wait for MuslimSim to disappear rather than refuse, and it
  never opens COM5 while MuslimSim still holds it.
- Tests: `tools/test_global_output_authority.py` extended 65 -> 72 checks - the
  release must precede the open, the start must follow the close, the release
  must be bounded, and the holder must be launched detached and told to wait.
  Two of those checks were wrong on the first attempt, matching the function
  definitions rather than the call sites; they now locate the call lines. All
  14 suites passed and `python launch.py --check` passed.
- Backup: `Backup/pu_dim_holder_wiring_v1_20260901-221103/`.
- Live check still needed: restart Studio so the bridge reloads, close it, and
  confirm the PU drops to dim and stays there - then start Studio again and
  confirm it takes COM5 back without complaint.

## 2026-09-01 - PU dims to the vendor's own minimum when Studio closes

- The owner captured PU CONNECT MSFS deliberately, moving its LCD and backlight
  dimmer sliders, and supplied `PU_Brightness.pcapng` so the real minimums would
  be known rather than guessed.
- The capture settles what the PU protocol is. PU CONNECT speaks the same
  `OVHD,` frames MuslimSim does, on device 49 endpoint 0x02, and its brightness
  UI moves **three** fields:
  - `P2` over 1..14
  - `P3` over 1..14
  - `P8` over 0..250
  Its all-the-way-down frame is `OVHD,0,1,1,0,12345,12345,0,0`.
- **MuslimSim has always sent a fixed `4` for P2 and P3.** They are hard-coded
  constants that the bridge header does not document - it explains P4 through
  P8 and skips straight past them - so every "dark" frame we have ever sent had
  two dimmer channels sitting at 4 while only P8 went to zero. That is why the
  panel dimmed but never went as far down as the vendor's software could take
  it.
- `build_packet` gained optional `p2`/`p3` parameters defaulting to `None`,
  which keeps the module constants. Every existing caller therefore emits
  byte-identical output; verified, a normal frame is still
  `OVHD,0,4,4,...`. Only `_pu_safe_dark_packet` passes the minimum, and the
  shutdown frame is now `OVHD,0,1,1,0,<blank>,<blank>,0,0`.
- Values are clamped to the captured 1..14 range, so a future caller cannot
  drive these fields somewhere the vendor never went.
- **The PU has no off, and that is now recorded rather than chased.** Measured
  across three probes: the panel dims but never extinguishes, and PU CONNECT's
  own minimum leaves it dim too. Rule 0.1 is satisfied for this device as far
  as the protocol allows and no further. The three probes written while
  establishing that are kept - `probe_pu_shutdown_relight.py`,
  `probe_pu_dark_frame.py`, `probe_pu_vendor_minimum.py` - because the next
  person to doubt it can re-run them instead of re-deriving it.
- Also recorded: the PU is made by **PU Korea**, not WinCtrl. The vendor was
  written down nowhere, and `PFD_PROJECT_HISTORY.md` grouped it as "or other
  WinCtrl". The catalogue now names it and carries the no-off finding.
- Noted, not changed: `P8_MAX = 125` while the vendor drives P8 to 250, so
  MuslimSim's brightness range is half the hardware's. `build_packet` already
  clamps P8 to 255, so the cap is only in `brightness_to_p8`. Raising it would
  make every panel brighter than the owner is used to, so it waits for an
  explicit decision.
- Tests: `tools/test_global_output_authority.py` extended 62 -> 65 checks. It
  asserts the shutdown frame carries the captured vendor minimum on both
  dimmers, and that a normal frame still carries the established constants so
  the shutdown values cannot leak into live output. All 14 suites passed and
  `python launch.py --check` passed.
- Backup: `Backup/pu_shutdown_dim_v1_20260901-214158/`.
- Live check still needed: close Studio and confirm the PU drops to the dim
  state rather than staying at knob brightness.

## 2026-09-01 - The throttle stayed lit because MuslimSim never darkened it on the way out

- The owner reported the PU, the throttle and the PAP3 all lighting up when
  Studio closes, and reasoned correctly that nothing else could be doing it:
  those panels reach X-Plane only through Studio, and X-Plane does not drive
  them directly.
- Three devices with separately verified blackouts lighting at the same instant
  is not three bugs. It is one cause acting after all three, and the obvious
  candidate was panel firmware returning to a lit power-on state when the last
  HID handle closes - which no amount of "write dark, then close" could fix.
- Added `tools/probe_shutdown_relight.py` to separate the two possibilities
  rather than guess between them: wake the panel, black it out with the handle
  still open, pause to look, close the handle, pause to look again.
- **Measured on the hardware: it lit, went dark, and did not relight.** The
  firmware holds the dark state after release. So the panels really were ours
  to darken and something in our shutdown simply was not doing it.
- **Found it.** `_close_winctrl_trim_display()` releases the sole B930 output
  handle and closed it without darkening anything. The throttle blackout had
  been wired to two of the three cases that need it - aircraft power lost, and
  simulator gone - but not to the third, MuslimSim itself exiting. That third
  case is the one the owner was reporting.
- Fixed inside that function, under the existing lock while it is still the
  sole owner, using the same captured `_winctrl_throttle_blackout`. All four
  callers are process-exit paths, each followed by `control_server.stop()`, so
  unlike the BB36 handoff there is no transient release here to flash.
- The other two were already handled and need only a Studio restart to take
  effect: the PU COM5 owner blacks out as it exits (fixed earlier today), and
  PAP3 blacks out when its manager-level stop event is set. Both were verified
  present again while chasing this.
- Tests: `tools/test_global_output_authority.py` extended 60 -> 62 checks. It
  now asserts that releasing the B930 handle darkens it first, and that the PU
  COM5 owner blacks out on exit. All 14 suites passed and
  `python launch.py --check` passed.
- Backup: `Backup/winctrl_close_blackout_v1_20260901-211113/`.
- Live check still needed, and it needs a full Studio restart so the bridge
  reloads: close Studio and confirm the throttle backlight, the PU overhead and
  the PAP3 all stay dark.

## 2026-09-01 - BB36 blackout gated to the final teardown; it was flashing

- The BB36 shutdown blackout added an hour earlier made the MCDU flash. The
  owner reported it immediately: "it keep flashing if we stop that flashing it
  will work".
- The blackout was put in `BB36PFDPath.stop()`, on the assumption that stopping
  a path means shutting down. It does not. That path is torn down on every
  FMC/PFD handoff and on every recovery - `_stop_active_path` alone has six
  call sites, five of which are not shutdown - so the screen was darkened and
  relit constantly.
- This is exactly the lesson `pap3_mcp.py` already carries, and it had been
  quoted in the previous entry while writing the bug: "Preserve the last valid
  frame through a short reconnect. Repeated blackouts were perceived as PAP3
  flashing." PAP3 blacks out only when its manager-level stop event is set,
  never on a transient teardown. BB36 now does the same.
- `BB36PFDPath.stop()` and `BB36FMCPath.stop()` take `final: bool = False`, and
  `_stop_active_path` forwards it. The default is off, so all five handoff and
  recovery callers keep their existing behaviour byte for byte. Only the
  supervisor loop's own exit - which happens once, when `stop_evt` is set -
  passes `final=True`.
- `BB36FMCPath` behaviour is deliberately unchanged. It already blanks its page
  on every teardown, and that blank is a handoff blank the incoming native-F0
  PFD session depends on, as its own comment says. It accepts `final` only so
  the router can stop either path the same way.
- Tests: `tools/test_global_output_authority.py` extended 57 -> 60 checks. It
  now asserts the blackout is gated - `if final and output_device is not None`
  must appear in the teardown - and that exactly one of the several
  `_stop_active_path` call sites is final. More than one means a handoff
  darkens the screen and it flashes again. All 14 suites passed and
  `python launch.py --check` passed.
- Backup: `Backup/bb36_shutdown_blackout_v1_20260901-205527/` still holds the
  pre-blackout file.
- Live check still needed: confirm the MCDU no longer flashes during FMC/PFD
  handoffs, and still goes black when Studio closes.

## 2026-09-01 - Rule 0.1 audited across every device, and made enforceable

- The owner asked for the guarantee in full: every single device dark when the
  aircraft has no power or the software is off. That deserved an audit rather
  than an assurance, so every catalogue device with implemented, testable
  outputs was checked for both a power gate and a shutdown blackout.
- Eight devices can light something: `pu_overhead` (37 outputs), `ecam32` (19),
  `winctrl_throttle` (11), `agp_bb80` (5), `fcu_32_efis` (4), `pap3_mag` (4),
  `pfp3n_bb35` (1) and `mcdu32_bb36` (1). Three more declare outputs that are
  not implemented - `pdc_bb62` and both Moza bases - and rule 0.1 leaves those
  alone rather than forcing them dark with a guessed packet.
- **`pap3_mag` was already covered, and nearly got "fixed" anyway.** Its
  `stop()` looked bare - set the event, join, set status - but `_blackout` is
  called from the session teardown when `stop_event` is set, deliberately not
  on a transient reconnect because repeated blackouts were perceived as the
  panel flashing. Its power gate is already there too:
  `display_enabled = transport_connected and avionics and ...`, and
  `lcd_backlight = 180 if avionics else 0`. Rule 0.2 is what stopped a
  pointless edit to working code.
- **`mcdu32_bb36` was the real gap.** Its router closed the output handle
  without darkening it, while the BB35 sibling immediately above it in the same
  codebase zeroes both brightness channels and the EXEC light before releasing.
  So the MCDU screen stayed lit after Studio exited.
- **How it goes dark:** the darken sequence this module already uses elsewhere
  - black background packet, `BB36_EXEC_DASH_LIGHT_CHANNEL` to `EXEC_LIGHT_OFF`,
  then brightness channels 1 and 0 to zero. Not a new sequence. It runs only
  when the worker has actually stopped; a stalled worker may still be mid-write
  on that handle, and the handle is closed underneath it exactly as before.
- **Made enforceable for devices that do not exist yet.**
  `tools/test_global_output_authority.py` now carries a blackout coverage
  table, and fails in both directions: a catalogue device with implemented
  outputs and no declared blackout fails, and a declared blackout for a device
  that no longer has outputs fails as stale. Adding a new output device now
  forces someone to say how it goes dark, which is exactly what rule 0.1 asks
  for. "It probably inherits it" is how the throttle and the BB36 were each
  missed once.
- The test additionally pins the two that were missed: the throttle blackout
  must use the captured channel report, and the BB36 router must darken between
  `def stop(` and `output_device.close()`.
- Tests: `tools/test_global_output_authority.py` extended 39 -> 57 checks. All
  other suites passed and `python launch.py --check` passed.
  `test_bridge_control_channel.py` fails only because Studio is running and
  owns COM5/HID/SDL; confirmed three times today that it passes with Studio
  closed.
- Backup: `Backup/bb36_shutdown_blackout_v1_20260901-205527/`.
- Live check still needed: close Studio and confirm the MCDU BB36 screen goes
  black rather than staying on the last page.

## 2026-09-01 - PU stayed lit at Studio shutdown: the dark frame was never sent

- The owner reported the PU Overhead lighting up when Studio is closed, lamps
  and LCD both, when rule 0.1 says a normal shutdown leaves every panel dark.
- The shutdown design was right and the packet was right. `force_dark` is
  checked first in `_pu_output_mode`, ahead of Test mode, and
  `_pu_safe_dark_packet` really is dark - verified as
  `OVHD,0,4,4,0,<blank>,<blank>,0,0`: P1 off, EGT zero, both altitude windows
  blanked, all-dark P7 mask, zero P8 brightness.
- **The dark frame was simply never written.** Switching to forced-dark also
  switches the altitude windows to their native ----- control-line state. That
  transition sets the line, then parks the writer in
  `stop_evt.wait(PU_SERIAL_DASH_LATCH_SECONDS)` - 1.50 s - and reaches
  `ser.write(packet)` only afterwards. The shutdown gave it
  `max(0.15, interval * 3.0)` first, which is **0.15 s** at the default 0.05 s
  interval, then set `stop_evt`. The wait returned early, the writer broke out
  of its loop before writing anything, and the panel kept its last lit mask.
  Ten times too short, and only on the one transition that shutdown always
  triggers.
- The caller's own backstop could not cover it either: the final
  `_pu_write_safe_dark_frame` is deliberately skipped while the writer thread
  is still alive, because two writers on COM5 is the one thing that must never
  happen.
- Two fixes, both additive, nothing existing restructured, per rule 0.2:
  - The pre-stop wait now outlasts the latch:
    `max(0.15, interval * 3.0) + PU_SERIAL_DASH_LATCH_SECONDS +
    PU_SERIAL_VALUE_SETTLE_SECONDS`, so 1.70 s instead of 0.15 s. The latch
    itself is capture-proven and untouched; only the wait around it changed.
  - `_serial_output_worker` now writes the safe dark frame as it exits.
    However the loop ended, that thread is the sole COM5 owner right up to the
    moment it returns, so it is the one place a final blackout needs no
    two-writer guard at all. It closes the gap the caller cannot reach.
- **How it goes dark**, as rule 0.1 now requires every output path to state:
  the existing captured `_pu_safe_dark_packet`, written three times at cadence
  by `_pu_write_safe_dark_frame`, with the serial line forced to the dash
  state first. No new packet and no new value.
- Tests: `tools/test_global_output_authority.py` extended to 39 checks. It
  asserts the dark packet really is dark field by field, that the pre-stop wait
  outlasts the dash latch - the exact arithmetic that was wrong - and that the
  COM5 owner blacks out as it exits. All 14 suites passed and
  `python launch.py --check` passed.
- Backup: `Backup/pu_shutdown_dark_latch_v1_20260901-204821/`.
- Live check still needed: close Studio with the PU lit and confirm the lamps,
  the backlight and both altitude windows all go dark before the port closes.
  Shutdown now takes about 1.6 s longer, which is the latch being allowed to
  finish.

## 2026-09-01 - Rule 0 added, and the throttle now goes dark with the aircraft

- The owner made two standing rules, and asked for them to outrank everything
  else in `AGENTS.md`. Both are now `Rule 0`, at the top of that file, to be
  checked before starting a task and again before calling one finished.
- **Rule 0.1 - no output lights while the aircraft is unpowered.** Screens
  black, lamps dark, backlights off, windows blank. It covers the WinCtrl
  throttle backlight, every panel currently connected through Studio, and every
  device added in future - a new device inherits the rule the day it is added,
  without being named. Test mode still lights only the output under test. A
  device with no capture-proven safe OFF is left alone and flagged, never forced
  dark with a guessed packet. Unknown counts as unpowered. Any new output path
  must state in its changelog entry how it goes dark.
- **Rule 0.2 - never disturb something that already works.** Fix the smallest
  broken part; do not restructure working code around a defect. Prefer a new
  parameter whose default preserves current behaviour over editing an existing
  path, so every existing caller behaves exactly as before. Prove it where the
  proof is cheap. If a fix appears to require changing a working part, stop and
  ask first.
- **The throttle was the gap in rule 0.1.** Its wake sequence lights the
  backlight when the HID handle opens, regardless of whether the aeroplane has
  any electrical power, and the existing authority work covered the AGP, ECAM,
  FCU/EFIS and BB36 but never the B930.
- Added `_winctrl_throttle_blackout` and `_winctrl_throttle_restore_defaults`.
  **How it goes dark:** both write the captured channel report built by
  `_winctrl_throttle_output_packet`; only the value differs, and 0 is that
  protocol's own off. Verified every blackout report is byte-identical to
  `_winctrl_throttle_output_packet(key, 0)` and keeps the captured 14-byte
  length. No packet was invented. The numeric window needed no blank glyph mode
  either: `trim_display_backlight` is itself a captured channel, so taking it to
  0 darkens the window.
- The power source is the PU aircraft-power dataref, not anything
  throttle-specific, because rule 0.1 is one rule about the aeroplane rather
  than a per-device opinion. Any future device should read the same value.
- The authority block follows the existing AGP one deliberately, so both
  devices behave identically: only while the simulator is up, only outside Test
  mode, rate limited to 0.5 s, and written only on an actual change of state.
  A lost simulator also blacks the throttle and resets the remembered state to
  unknown, so recovery re-applies rather than trusting a stale belief.
- Rule 0.2 was followed here: nothing existing was edited. Two new helpers, one
  new authority block beside the AGP one, and one blackout call added to the
  offline path. The wake sequence, the display writer, the trim paths and every
  other output are untouched.
- Tests: `tools/test_global_output_authority.py` extended to 30 checks - the
  blackout must cover every declared channel, each report must equal the
  captured builder at 0, reports must keep the captured length, and both the
  throttle backlight and the window backlight must be covered. All other suites
  passed and `python launch.py --check` passed.
  `test_bridge_control_channel.py` fails only because Studio is running and
  owns COM5/HID/SDL; it passes with Studio closed, as confirmed twice today.
- Backup: `Backup/winctrl_throttle_output_authority_v1_20260901-203704/` and
  `Backup/AGENTS_before_output_power_rule_20260901-203505.md`.
- Live check still needed: with the aircraft cold and dark, confirm the throttle
  backlight, the flaps/airbrake backlight and the RUD TRIM window are all off,
  and that they come back when the battery is switched on.

## 2026-09-01 - The stabilizer readout was refused silently, and Practice was gated on the wrong thing

- The owner reported the RUD TRIM window blank, having worked in Practice
  before. Reading found nothing: the practice handler was byte-identical to the
  version that worked, the catalogue control, profile switch, device
  registration and startup init were all intact, the output authority never
  touched that region, `device_lifecycle` wraps only the AGP opener, and the
  display packets were proven byte-identical before and after the recent work.
- So the display was driven directly instead, through the bridge's own opener
  and writer (`tools/probe_winctrl_trim_display.py`, new). The window showed
  every value: `L 2.5`, `R 1.0`, `0.0`, then `4.9` and `15.8` in the new units
  mode. The driver accepted all writes, returning 64 bytes each, and the packet
  header matched the capture. The display path was healthy; the fault was in
  what reached it.
- **Bug found, introduced earlier the same day.** `stab_trim_display` was
  written through `control_server.apply_lab_output`, which validates every
  control against the catalogue - and it had deliberately been given no
  catalogue entry, on the reasoning that a bridge-owned readout does not need a
  Studio-mappable control. That reasoning was wrong for the routing path
  chosen: `lab.output` raises `Unknown control`, the Practice sink swallows the
  error into a diagnostic, and the live loop catches it, so **both** stabilizer
  readout paths failed completely silently.
- Added the `stab_trim_display` output to the catalogue. It is the same
  physical window and the same two captured reports, declared as the unsigned
  units mode. Keeping it in the catalogue also keeps the device-enabled and
  profile checks that bypassing the lab would have skipped.
- **Practice no longer gates the rocker on the MODE trim role.** The rocker is
  hard-wired to the stabilizer in Live, so Practice now moves a simulated
  stabilizer value and writes it to the window in units, 0.1 per press. The old
  path read `if role not in winctrl_trim_values: return`, which returns
  silently whenever MODE sits in IGN/START - indistinguishable from a dead
  display. Only the reset contact stays role-owned, because centring is what
  MODE actually selects.
- `winctrl_trim_values` gained a `STAB` entry starting at 4.9, a normal
  on-ground setting rather than 0.0, which is not a trim position a 737 is
  found in. The existing `RUDDER` and `AILERON` entries and the status mirror
  are unchanged.
- Extended `_run_winctrl_trim_display_self_test` to close the hole for good: it
  now asserts that every window mode the bridge writes exists as a catalogue
  control and is implemented and testable. Verified it catches the exact bug -
  removing the entry fails with "written by the bridge but is not a catalogue
  control, so every write to it is refused silently".
- Tests: all 14 suites passed and `python launch.py --check` passed.
- Backups: `Backup/winctrl_practice_stab_trim_v1_20260901-202617/`.
- Live check still needed: in Practice, hold the rocker and confirm the window
  now counts in trim units regardless of where MODE is sitting.

## 2026-09-01 - RUD TRIM window reads out the stabilizer trim it is setting

- Follow-up to the rocker hard-wire. The rocker moved pitch while the numeric
  window beside it still read rudder trim, which was recorded at the time as an
  inconsistency rather than smoothed over. The owner asked for the window to
  work while trimming, so it now shows live stabilizer units.
- Source: `laminar/B738/flight_model/stab_trim_units`, the same units the real
  737 trim indicator shows, read from the running aircraft (4.899 at the time).
  Zibo publishes its own travel limits beside it - `def_elevator_trim_dn` 4.8
  and `def_elevator_trim_up` 15.8 - which is what proved the signed rudder
  scale could not carry it.
- The window is four cells: a direction glyph, tens, ones and tenths. The
  captured glyph table holds only digits, `L`, `R` and blank. A trim setting is
  not a left or a right, and no honest U/D glyph can be built from that table
  without inventing segment patterns the capture never proved, so the units
  readout leaves the leading cell **blank**: `4.9` renders as `"  49"` and
  `15.8` as `" 158"`.
- The signed rudder path is untouched. `_winctrl_trim_segment_planes`,
  `_winctrl_trim_display_packets` and `_winctrl_write_trim_display` gained a
  `signed=True` keyword, so every existing call behaves exactly as before:
  `-2.5` still renders `"L 25"` and `1.0` still renders `"R 10"`.
- Bounds are separate rather than widened. `WINCTRL_TRIM_DISPLAY_MIN/MAX` stay
  at +/-10.0 for rudder and aileron; the units readout uses
  `WINCTRL_STAB_TRIM_DISPLAY_MIN/MAX` of 0.0 to 19.9, which is what three digit
  cells can physically render. Above that it saturates rather than wrapping to
  a smaller, believable, wrong number.
- `stab_trim_display` is accepted by the existing single writer as a second way
  to address the same window. **Correction, same day:** it was first left out of
  the catalogue on the reasoning that a bridge-owned readout needs no
  Studio-mappable control. That reasoning was wrong and is recorded here
  because it caused a silent failure - see the entry above.
- The readout is tied to the trim repeat, not polled. Nothing is read from the
  simulator unless the rocker is actually being held, and one final reading is
  taken after release so the settled trim stays on the window instead of
  stopping at whatever was mid-movement. A read error backs off to 0.5 s and
  gives up once the rocker is home.
- Extended `_run_winctrl_trim_display_self_test` again: no stabilizer value may
  light the direction cell, the units mode must not reuse the clamped signed
  scale, and the readout must saturate at the window maximum. Verified it
  catches a regression - pointing both rocker directions at one command fails
  with "directions must be opposite".
- Tests: all 14 suites passed, `python launch.py --check` passed.
  `test_bridge_control_channel.py` passes again now that Studio is closed,
  confirming its earlier failure was environmental - it starts a second bridge
  that cannot take COM5/HID/SDL while Studio holds them.
- Backup: `Backup/winctrl_trim_lcd_stab_units_v1_20260901-200602/`.
- Live check still needed: hold the rocker and watch the window count in trim
  units alongside the stab trim wheel, then confirm the settled value stays
  after release.

## 2026-09-01 - RUD TRIM rocker hard-wired to the Zibo stabilizer trim wheel

- The owner asked for the physical RUD TRIM knob on the WinCtrl URSA MINOR to
  drive the Zibo pitch/stabilizer trim wheel, hard-coded, independent of the
  MODE rudder/aileron trim-role selector.
- Confirmed the hardware first rather than assuming it: the rocker is a
  three-contact spring switch on B930 buttons 26 (LEFT), 27 (spring centre)
  and 28 (RIGHT), already mapped in both bit tables. Only 26 and 28 latch a
  held state; 27 needs no action because releasing 26/28 already stops the
  repeat.
- Confirmed the commands against the running aircraft rather than guessing
  names: `laminar/B738/flight_controls/pitch_trim_up` and `pitch_trim_down`
  exist in the loaded Zibo's inventory and resolve to command ids 4475 and
  4476. These are Zibo's own captain-side electric trim commands - the pair
  the yoke trim switches use, which is what turns the stab trim wheel. The
  `fo_pitch_trim_*` pair is deliberately not used: this is the captain's
  quadrant.
- The repeat loop previously built its command as
  `f"{role.lower()}_{direction}"` from the MODE selector, and did nothing at
  all when MODE sat in IGN/START. It now reads
  `WINCTRL_PITCH_TRIM_COMMANDS[direction]`, so the rocker trims pitch in every
  MODE detent including IGN/START.
- The repeat cadence (0.10 s held, 0.25 s backoff), the held-state latches and
  the mutual-exclusion between left and right are the proven rudder/aileron
  ones and are unchanged. Only the command chosen differs.
- Direction follows the convention already used everywhere else on this
  quadrant - left decreases, right increases - so LEFT is nose down and RIGHT
  is nose up. `WINCTRL_PITCH_TRIM_COMMANDS` is the single place that decides
  it; swapping its two values is the whole change if it feels backwards on the
  physical unit.
- A Studio binding on these contacts still wins. `_muslimsim_observe_lab_event`
  consumes the event and the live loop does `continue`, so the native
  hard-wired path never sees a contact the owner has remapped. No double
  command is possible.
- Deliberately left alone, and worth knowing: the MODE selector, the RUD TRIM
  numeric window, and the reset contact (button 25) keep their existing
  rudder/aileron behaviour. Only the rocker moved. That means the numeric
  window still reads the selected role's trim, not stabilizer units.
- Extended `_run_winctrl_trim_display_self_test` so this cannot drift silently:
  it now asserts both pitch command names, that the rocker maps exactly `left`
  and `right`, that the two directions are not the same command (which would
  trim one way only and look like a stuck switch), and that both resolve to
  real keys in `WINCTRL_COMMANDS`.
- Updated the catalogue's `default_role` text for the two contacts to say
  plainly what they now do. The printed face label still reads RUD TRIM.
- Tests: `python launch.py --check` passed, which runs the extended self-test.
  Full suite re-run - 13 of 14 passed. The single failure,
  `test_bridge_control_channel.py`, is environmental and pre-existing: it
  starts a second bridge, which cannot take COM5/HID/SDL while Studio is
  running, so it never reports a loopback port. It passes with Studio closed
  and is unrelated to this change.
- Backup: `Backup/winctrl_rud_trim_to_pitch_trim_v1_20260901-194945/`.
- Live check still needed: hold the rocker each way and confirm the stab trim
  wheel turns and `sim/cockpit2/controls/elevator_trim` moves in the expected
  direction. It read `-0.390` before this change.

## 2026-09-01 - False green altitude-tape hatch removed

- Traced the bright green horizontal bands on BB35/BB36 to the renderer's
  destination-field-elevation hatch, not to the diagonal-line/font trials.
- Zibo's `laminar/B738/fms/dest_runway_alt` supplies an FMC elevation value,
  but no matching PFD visibility state. The renderer no longer treats that
  value alone as permission to cover the altitude tape with a green/black
  pattern.
- Preserved the altitude drum, target-altitude bug, trend vector, tape labels,
  V/S geometry and differential report counts unchanged.
- Saved the prior renderer as
  `Backup/pfp_renderer_before_field_elevation_gate_20260901-203000.py`.
- PFD, simulator-offline and all 15 output-authority checks pass.

## 2026-09-01 - Automatic LevelUp, ToLiss and C172 NG Digital workspaces

- Added read-only `.acf` path classification for the installed LevelUp
  `737NG_Series_V2`, all ToLiss family folders, and the AirfoilLabs
  `C172 NG DIGITAL`; the default Laminar C172 remains generic and cannot be
  mistaken for the AirfoilLabs aircraft.
- Published the confirmed aircraft identity through the private Studio status
  channel. Studio now moves to the matching isolated mapping/profile file
  automatically after X-Plane loads an aircraft, including when Studio was
  started first.
- Added the `C172 NG DIGITAL` Studio workspace and its independent
  `hardware_profiles_c172ng.json` profile.
- Imported `2,380` applicable standard X-Plane commands from the owner's
  installed `Resources/plugins/Commands.txt`, including `237` G1000 commands.
  When the C172 is live, its Web-API command inventory replaces this offline
  list so newly registered aircraft-plugin commands can also be assigned.
- Kept Zibo-only commands and axes out of the C172 catalogue. C172 saved
  mappings may use its generic hardware readers only after both the selected
  workspace and loaded AirfoilLabs aircraft match; Boeing defaults remain off.
- Added C172 catalogue, aircraft status and isolation coverage to the hardware
  self-test and added real/fallback C172 path cases to the aircraft-profile
  self-test.
- Preserved the prior state at
  `Backup/aircraft_autodetect_c172_catalog_before_20260901-202500/`.
- Passed aircraft-profile, Studio handoff, hardware-lab, startup-safety,
  simulator-offline, PFD, launcher and all 15 output-authority checks.

## 2026-09-01 - Live zoom, compact text and two-circle ND PLAN page

- Added Zibo captain range-detent input and normalized all eight EFIS ranges;
  the generic X-Plane NM value remains the fallback.
- Put the range detent on the immediate ND snapshot, so MAP and PLAN react as
  soon as the hardware zoom selector moves.
- Corrected PLAN route projection to use the same centred north-up geometry as
  its visible rings instead of expanded MAP's low aircraft origin.
- Replaced BB35/BB36 ND text with the PFD's tightly packed slot-3 micro glyphs.
  Joined GS/TAS and range/NM, guarded every character inside the bezel-safe
  area, and used true compact widths for waypoint labels.
- Replaced PLAN's crowded compass rose with exactly two clean distance circles
  for half/full selected range, plus `N`, route legs and waypoint names.
- Added hidden three-band construction for page entry, MAP/PLAN changes and
  scheduled recovery.
  Only the complete page receives the LCD refresh; the largest burst is `272`
  reports and no partial band is shown.
- Added `tools/check_nd_zoom_compact.py`. MAP zoom costs at most `225` reports,
  PLAN zoom at most `173`, and a steady page sends zero.
- Preserved the prior state at
  `Backup/nd_before_zoom_compact_plan_20260901-191500/`.
- Passed compact-ND, PFD, startup, simulator-offline, launcher and all 15
  output-authority checks.

## 2026-09-01 - Complete MAG arc no longer alternates between halves

- Removed the timed left/right PFD healing swaps after the physical BB35/BB36
  showed that an untouched half is not retained reliably.
- Kept full, atomic recovery on PFD page entry, simulator reconnect and return
  from standby. Normal live movement remains differential and immediate.
- Kept compact text phase stable; elapsed time alone can no longer widen text
  or replace half of the visible MAG arc.
- Added a 122-frame long-hold regression. It remains pixel-identical to a full
  repaint with a median of one report.
- Preserved the prior state at
  `Backup/pfd_before_full_compass_healing_20260901-185200/`.
- Passed the PFP self-test (`287` page entry, `266` maximum refinement, `1`
  steady and `1` elapsed-hold report), pixel-identical differential suite,
  hybrid-transparency verification, startup safety, simulator-offline reset,
  launcher validation and all 15 output-authority checks.

## 2026-09-01 - Clean banked lines with software-transparent text cells

- Kept the proven clean native 10/20-degree rung glyph when its complete cell
  is safely over one sky/earth colour.
- Replaced only a boundary-crossing cell with foreground-only rectangles from
  that exact glyph mask. The live sky/earth field is therefore untouched even
  though WinCtrl firmware ignores native text alpha.
- Applied the same conditional foreground-only fallback to slot-3 pitch
  numbers and letters. Normal cells retain the fast native path.
- Extended the generated plan with exact masks for all 183 line glyphs and all
  95 printable slot-3 characters; the uploaded font binary is unchanged.
- Added `tools/check_pfp_hybrid_transparency.py`. It validates every mask
  pixel, rejects any opaque cell that crosses the moving background, and
  exercised 336 masked rung cases across the pitch/bank grid.
- Preserved the prior state at
  `Backup/pfd_before_hybrid_transparency_20260901-183400/`.
- Passed the PFP self-test (`287` page entry, `266` maximum refinement, `1`
  steady and `267` healing reports), hybrid transparency check, pixel-identical
  differential suite, startup safety, simulator-offline reset, launcher
  validation and all 15 output-authority checks. No banking QA image was kept.

## 2026-09-01 - Settled PFD numbers no longer widen during healing refreshes

- Fixed the reported size pulse after several seconds. The 120-frame healing
  refresh was resetting compact typography to phase zero for one visible LCD
  swap, then rebuilding it over the next refinements.
- Kept phase zero only for genuine page entry. Once the compact text has
  settled, every later healing pass retains phase three, so values never
  change width or spacing.
- Split settled healing into alternating exact left/right half-screen passes.
  Dirty live regions in the other half are included immediately, so speed,
  altitude and attitude changes never wait for the next healing pass.
- Added a regression that forces both healing halves, requires the compact
  phase to remain settled and enforces the 290-report BB36 ceiling. The
  worst half is `267` reports.
- Preserved the prior state at
  `Backup/pfd_before_stable_compact_recovery_20260901-174849/`.
- Passed the PFP self-test (`283` page entry, `265` maximum refinement, `1`
  steady and `267` maximum healing reports), the pixel-identical differential
  suite, startup safety, simulator-offline reset, launcher validation and all
  15 output-authority checks.

## 2026-09-01 - Bottom PFD values aligned beneath their tapes

- Moved the complete BARO/HPA value from y=435 to y=404, directly beneath
  the altitude tape at x=480..552.
- Moved the RADIO/BARO minimums annunciation to the next line at y=435 and
  right-aligned it to the same altitude-tape edge. RADIO therefore appears
  below `1013HPA` instead of taking its position above it.
- Moved both left-side rows from x=14 to the speed tape's x=90 edge. The Mach
  readout now keeps its leading `M` visible (`M.62` rather than a detached
  `.62`), and `LS113.3` starts on the same vertical line immediately below.
- Preserved the prior state at
  `Backup/pfd_before_bottom_strip_alignment_20260901-174040/`.
- Passed the PFP self-test (`283` full, `265` maximum refinement and `1`
  steady report), the pixel-identical differential suite, startup safety,
  simulator-offline reset, launcher validation and all 15 output-authority
  checks. The retained four-value QA is level-wing only.

## 2026-09-01 - Altitude box right wall moved another two millimetres inward

- Kept the altitude box nipple, left edge, compact digits and overall anchor
  fixed. Moved only its right wall another 12 LCD pixels left, from x=578 to
  x=566, which is approximately two physical millimetres on the panel.
- Kept the V/S silhouette and its needle fixed. The centre notch remains at
  x=586, so the clean black separation from the altitude box is now 20 pixels.
- Left the rolling altitude cells at their proven positions ending at x=551;
  altitude movement therefore remains isolated from the V/S redraw region.
- Preserved the complete previous state at
  `Backup/pfd_before_altitude_wall_2mm_inward_20260901-172940/`; Point A,
  Point B and all earlier restores remain untouched.
- Passed the PFP self-test (`283` full, `265` maximum refinement and `1`
  steady report), the pixel-identical differential suite, startup safety,
  simulator-offline reset, launcher validation and all 15 output-authority
  checks. The retained QA is level-wing only.

## 2026-09-01 - White aircraft contour and compact PFD value typography

- Added a thick white contour around the complete black aircraft reference:
  both wings, inner hooks and the centre square. The contour is installed on
  the precision frame so the BB36 page-entry frame keeps its protected budget.
- Moved the BARO value/unit zone to exactly the altitude tape's 72-pixel span
  at x=480..552. Values such as `1013HPA` and `29.92IN` now sit directly below
  the grey altitude tape rather than extending toward the V/S display.
- Rebuilt slot 3 with every micro value glyph left-aligned inside the proven
  17x29 opaque cell. Digits, decimal points and value letters are advanced only
  after their visible ink ends, applying compact spacing across PFD value
  fields without clipped characters or a new font header.
- Staged the compact value groups over three refinement frames. The final
  appearance is unchanged, while no individual refinement exceeds the full
  frame traffic guard. Tests pass at `283` full, `265` maximum refinement and
  `1` steady report.
- Preserved the complete previous state at
  `Backup/pfd_before_white_reference_and_packed_type_20260901-171924/`.
  Differential output remains pixel-identical; startup, simulator-offline,
  launcher and all 15 output-authority checks pass without hardware.

## 2026-09-01 - Altitude box shortened only from its right end

- Kept the established nipple, left edge and entire box position fixed.
  Shortened only the outboard end by moving the right wall six pixels left,
  from x=584 to x=578.
- Kept the V/S silhouette at x=586. The corrected geometry now has eight
  black pixels between the white altitude-box wall and the grey V/S shape,
  comfortably exceeding one physical millimetre on the PFP LCD.
- Left every compact altitude digit and rolling-cell position unchanged, so
  altitude motion remains isolated from the V/S redraw region.
- Preserved the prior state at
  `Backup/pfd_before_shorter_altitude_right_wall_20260901-171210/`; Point B
  and all earlier restores remain untouched.
- Passed the PFP self-test (`281` full, `220` refinement, `1` steady), the
  pixel-identical 12-frame differential suite, startup and offline-reset
  tests, launcher validation and all 15 output-authority checks. The QA frame
  is level-wing only; bank-angle previews are no longer used for this work.

## 2026-09-01 - Altitude-box outboard wall refined without V/S coupling

- Extended the live-altitude box two pixels outboard, moving its right wall
  closer to the simulator proportion.
- Rebuilt the native slot-3 V/S silhouette around the new edge. The V/S grey
  shape still begins after a two-pixel black gap, so it never touches the
  white altitude-box outline.
- Kept the compact rolling altitude cells unchanged: their final cell still
  ends at x=551 inside the altitude-tape dirty column, so altitude changes do
  not drag the V/S tile into the same redraw region.
- Preserved the exact post-banking, pre-refinement state at
  `Backup/pfd_before_altitude_box_outboard_20260901-170044/`; Point B and every
  earlier restore remain available.
- Passed the PFP self-test (`281` full, `220` refinement, `1` steady), the
  pixel-identical 12-frame differential suite, startup safety,
  simulator-offline reset, launcher validation and all 15 output-authority
  checks without opening X-Plane or hardware.

## 2026-09-01 - Black aircraft reference now banks with the aeroplane

- Changed the complete black aircraft reference from level-fixed to one rigid
  roll-following assembly. In a left bank its left wing moves down and its
  right wing moves up; a right bank mirrors that motion.
- The two thick wings, inner hooks and hollow centre square all rotate around
  the centre together. The white natural-horizon separator keeps its existing
  opposite movement.
- Added a layout regression for the left-bank direction. A low-command
  recovery silhouette protects the BB36 USB budget, followed immediately by
  the exact continuous scanline geometry.
- Preserved the previous state at
  `Backup/pfd_before_banking_aircraft_reference_20260901-165125/`. Point A,
  Point B and all earlier restores remain untouched.
- Verification passed: PFP PFD self-test (`281` full, `220` refinement and
  `1` steady report) plus the 12-frame differential repaint suite.

## 2026-09-01 - Black fixed aircraft reference matched to the simulator PFD

- Corrected the initial interpretation of the simulator photograph. The black
  reference is not the moving blue/brown separator; it is the fixed aircraft
  symbol made from two opposed thick wings and the small hollow centre square.
- Restored the moving natural-horizon separator to white. Changed only the
  fixed aircraft wings, inner hooks and centre square from white to black.
  Their position remains fixed while the horizon and pitch indications move.
- Added a layout regression that keeps the natural-horizon separator white.
  The pre-change state is in
  `Backup/pfd_before_black_horizon_and_full_clean_ladder_20260901-174100/`;
  Point A and Point B remain untouched.
- Verification passed: renderer syntax, the PFP PFD protocol self-test
  (`280` full, `191` refinement and `1` steady report), and the 12-frame
  differential repaint suite. The generated normal and high-bank QA frames
  also keep the moving separator white and only the fixed aircraft reference
  black.
- Confirmed from the emitted command stream that labelled 10/20-degree lines
  are using native slot 8. Added an offline full-ladder sizing tool; the
  unfinished appearance is from the still-coded 2.5/5-degree marks, not a
  silent fallback of the labelled lines.

## 2026-09-01 - Continuous background-matched pitch rungs for BB35/BB36

- Preserved the complete pre-integration state in
  `Backup/pfd_before_masked_continuous_rungs_20260901-161500/`; Point A,
  Point B and every earlier restore remain untouched.
- Completed the physical background investigation on BB35. Alpha, shortened
  background commands and alternate font-header fields all remained opaque.
  The successful card drew two clean white continuous diagonals: one wholly
  over blue and one wholly over brown, with each opaque native text cell set
  to the exact local field colour. Both cell rectangles disappeared while
  both lines remained clean. This is now the production method.
- Replaced the rejected individual 24 x 20 segment glyphs with complete paired
  10/20-degree rungs rasterised once and cut into 40 x 40 native cells. The
  generated table covers an exact level line, two-degree steps, and exact
  -45/+45 endpoints. Its 183 unique tiles fit in proven slots 7 and 8 (95 and
  90 glyphs including each blank), and the 64,689-byte slot-3/4/5/6 resource
  remains the exact prefix of the live resource.
- Added `pfp_bank_line_plan.json`, which groups adjacent tiles into at most
  three native text runs per complete rung. The renderer tests all four
  corners of every opaque 40 x 40 cell against the moving natural horizon and
  rounded attitude shell, then uses the exact production sky or earth colour.
  The existing exact coded path remains only as a geometry safety fallback
  when an entire native cell cannot be admitted.
- Updated the resource self-test and offline frame emulator for both variable
  native slots. Generated normal and 45-degree QA frames contain no black
  cells, color crossings or broken tile joins. No PNG is used at runtime.
- Passed syntax parsing, resource round-trip and prefix validation, the PFD
  packet/layout self-test (280 full, 190 refinement, one steady report),
  normal and extreme offline rendering, pixel-identical differential motion
  through all suites, launcher integrity, startup safety, simulator-offline
  recovery and all 15 global output-authority checks. Current differential
  medians are 70 reports in cruise, 218 while turning, 64 under jitter, 247
  through mode/extreme changes and one when steady. Remaining check: restart
  Studio so the new resource uploads, then inspect live banking on BB35 and
  BB36.

## 2026-09-01 - Clean native pitch-line glyphs with opaque-cell safety

- Preserved the complete pre-integration state in
  `Backup/pfd_before_bank_line_font8_20260901-143357/`; Point A, Point B and
  every earlier restore remain unchanged.
- Completed the physical fallback experiment after the undocumented line
  commands failed. A tiled text-glyph diagonal appeared clean on both BB35
  and BB36, and a corrected 128 x 128 single-glyph diagonal also appeared on
  both. An alpha-zero background test produced a white line inside a black
  box, proving that the controller always paints the complete text cell and
  does not support transparent glyph backgrounds.
- Added `tools/build_pfp_bank_line_font.py` and generated
  `winctrl-pfp-b737-cockpit-font3-4-5-6-8.xpwwf`. Its first 64,689 bytes are
  the current slot-3/4/5/6 resource byte-for-byte. Slot 8 adds 5,952 bytes of
  glyph memory (7,605 resource bytes including command/report framing): blank
  space plus 92 clean 24 x 20 pitch-segment glyphs covering -45 through +45
  degrees in two-degree steps and two background-side anchors.
- The live renderer uses slot 8 only for the separated left/right segments of
  labelled 10/20-degree pitch rungs. Before every draw it checks all four
  corners of the opaque cell against the rounded attitude window and the
  moving natural horizon. A cell wholly above receives the exact sky colour,
  a cell wholly below receives earth, and a cell that could touch or cross the
  boundary falls back to the existing exact rectangle raster.
- Clean glyph cells draw first; exact 2.5/5-degree rungs and numerical labels
  draw afterward, so an opaque background cannot erase a nearby minor line.
  The horizon, bank ticks, pointer and every other PFD element keep their
  proven code-drawn paths. No PNG is loaded at runtime and no rejected
  `0x115`-`0x117` function entered production.
- Updated the offline frame emulator for variable native cell sizes and added
  `assets/pfp-bank-line-font8-preview.png` plus
  `PNG/pfp-slot8-check-extreme.png`. The extreme preview contains no black
  cell, sky-over-earth cell or earth-over-sky cell.
- Passed the resource/prefix guard and PFD self-test at 280 full, 190
  refinement and one steady report. Differential output was pixel-identical
  to a forced repaint through cruise, turning, jitter, mode/extreme, periodic
  recovery and live/offline/live sequences; traffic medians were 70, 203, 64,
  246 and one report. Launcher integrity, startup safety, simulator-offline
  reset and all 15 global output-authority checks also passed without opening
  X-Plane or hardware. Remaining check: restart Studio and inspect the live
  PFD on BB35 and BB36.

## 2026-09-01 - BB35/BB36 native-line experiment completed (no primitive found)

- Preserved the exact current renderer and documentation in
  `Backup/pfd_before_undocumented_line_experiment_20260901-133542/`. The
  owner's Point A and Point B restores remain untouched.
- Confirmed why the temporary 45-degree recovery frame looks blocky: its
  exact scanline spans are compressed into a few bounding rectangles. The
  settled refinement is exact, but the moving/recovery approximation is not
  visually acceptable and has not been declared finished.
- Added read-only inspectors for SimAppPro's Electron archive, native WinCtrl
  modules and cached firmware. SimAppPro exposes rectangle, font, colour,
  text and refresh commands (`0x110` through `0x114`) but leaves `0x115`
  through `0x117` unused in JavaScript; its next exposed command is the text
  grid at `0x118`.
- Found the downloaded `MCDU-32` and `PFP-3N` firmware containers. Their
  235,230-byte bodies are identical and only the clear one-byte panel
  identifier differs. The common body is block-encrypted; an exhaustive
  2,961,270-key-window AES check found no key in `WWTHID_JSAPI.node` or
  `WWTHID.dll`, so no command meaning was guessed from encrypted bytes.
- Added `tools/probe_pfp_native_line.py`, an isolated display-only test for one
  candidate function and payload at a time. It never contacts X-Plane or other
  controls, draws four known witness blocks, and refuses to open BB35/BB36
  while MuslimSim Studio or `launch.py` is running. It is not wired into the
  production renderer.
- Physically tested the same 15 combinations on both BB36 and BB35 (30 cards
  total): candidate IDs `0x115`-`0x117` with endpoint16, endpoint16 plus
  16/32-bit thickness, endpoint32 and origin/size payloads. Every card received
  F0 acknowledgements and displayed its four cyan witness blocks, but none
  produced a white diagonal. These IDs/layouts are therefore rejected on both
  panels and will not be added to production.
- The probe now performs Studio's proven F2 blank + F0 clear + HID reopen
  reinitialization before each card, then wakes only the selected screen. This
  removed the need for a manual unplug between later tests. A real Windows USB
  restart remains Administrator-only and is never falsely reported as done.
- Restored BB36 and BB35 to clean dark pages after their final tests. Python
  compilation passed for the updated probe. The safe rectangle/text renderer,
  Point A, Point B and the pre-experiment backup remain unchanged.

## 2026-09-01 - Replace block-built angled marks with solid rotated strokes

- Preserved the preceding radially aligned version in
  `Backup/pfd_before_solid_angled_ladder_20260901-132715/`. Point A, Point B
  and every earlier rollback point remain untouched.
- Split the two bank slopes that had incorrectly been tied together. The
  moving triangle and every small numbered pitch-ladder rung now bank together
  by the aeroplane's angle, while the thick sky/earth horizon banks in the
  opposite direction.
- Rotated the numbered ladder as one rigid assembly instead of merely tilting
  every rung around a fixed x-coordinate. Every rung centre now lies on the
  radial centreline of the small upward-pointing triangle that moves along the
  bank arc. The downward-pointing triangle that remains at the top centre is
  only the fixed zero-bank index and no longer appears to control the ladder.
- Replaced the pitch ladder's major-axis square-run raster with a true rotated
  rectangle. Its thickness is measured perpendicular to the requested angle,
  its ends are extended to their pixel centres, and each LCD row receives one
  unbroken scanline span. Shallow, steep and exact 45-degree strokes are now
  edge-connected rather than corner-connected diamond chains.
- Kept the labelled 10/20 rungs split around the reference centre, but made
  every unlabelled 2.5/5-degree mark one continuous centred two-pixel stroke.
  The controller has no proven native line command, so this uses only the
  established safe colour/fill protocol and no PNG.
- In a right bank the triangle moves right and the 10/20 ladder has its left
  side up and right side down; the bold horizon has its left side down and
  right side up. A left bank is the exact mirror. The layout regression now
  locks all three relationships independently.
- Kept the moving pointer as a filled radial triangle aimed at the fixed bank
  scale. The slip/skid marker rotates beneath that pointer, aligns with it in
  coordinated flight and moves tangentially for slip or skid.
- Retained the clean code-drawn attitude geometry: paired continuous ladder
  lines with a centre gap, solid radial bank ticks, no lower hooks and a white
  sky/earth separator. No PNG is loaded by the live display.
- Kept the V/S needle's fixed pivot at `(626,226)`, the centre of the V/S
  strip's far-right edge. Its inboard end follows climb/descent while the
  outboard pivot stays centred.
- Passed at 286 full, 204 refinement and one steady report. Differential
  output remained pixel-identical to full repaints; traffic medians were 70
  reports in cruise, 205 while turning, 64 under jitter, 249 in
  modes/extremes and one at steady state. Startup, simulator-offline reset,
  launcher and all 15 output-authority/blackout checks passed offline. Live
  BB35/BB36 inspection remains required after restarting Studio.

## 2026-09-01 - Aircraft-shaped PFD altitude and V/S right strip

- Preserved the complete post-Point-B starting state in
  `Backup/pfd_right_strip_before_20260901-115333/`; the owner's named Point A
  and Point B restores were not modified.
- Corrected the selected-altitude bracket so its top, bottom and right sides
  stay straight while the left notch folds inward into the magenta box. The
  live-altitude box moved right to `480,200`, became ten pixels narrower, and
  now has a tape-contained left nipple. Its black interior follows that
  outline instead of spilling over the white edge.
- Tightened the five live-altitude positions to a safe ten-pixel visual pitch
  inside their unchanged 17 x 29 native cells. The final rolling cell remains
  inside the altitude-tape dirty region, so altitude changes do not force the
  V/S background to redraw.
- Rebuilt the V/S strip with its straight outer body, 34-pixel outer chamfers,
  true 45-degree transitions and a vertical void around the altitude box. Its
  needle now emerges from the box edge. Eleven unused slot-3 glyphs carry this
  static silhouette, preserving the full slot-4/5/6 resource byte-for-byte.
- Passed the PFD/resource contract at 287 full, 196 refinement and one steady
  report. Differential frames stayed pixel-identical to forced repaints;
  medians were 70 reports in cruise, 165 while turning, 64 under jitter, 250
  in modes/extremes and one at steady state. Launcher, startup-safety,
  simulator-offline reset and all 15 global output-authority/blackout checks
  passed without opening X-Plane or hardware. The remaining check is visual
  inspection on BB35 and BB36 after a normal Studio restart.

## 2026-09-01 - Point B PFD proportions, tighter joins and cleaner Boeing geometry

- Preserved the physically approved compact slot-3 PFD as the owner's named
  `Point B` in `Backup/point_b_pfd_slot3_20260901-110843/`. The snapshot holds
  the exact bridge, both display renderers, all three compatible font
  resources, builders/tests, histories, SHA-256 restore note and baseline PNG.
  Point A remains untouched.
- Kept the controller's proven 17 x 29 native cell and the measured slot-3
  upload, then used 12 otherwise-unused slot-3 characters as safe visual
  boundary aliases. Their ink moves four pixels inside its own cell, so
  `LS113.3`, `1013HPA`, `29.92IN` and `335H` close the number/letter boundary
  without overlapping opaque cells, changing a font header or adding a draw
  command.
- Widened the attitude sphere from 252 to 272 pixels into the protected black
  gutters while keeping its proven height and tape coordinates. The right edge
  now continues ten pixels behind the opaque altitude readout, matching the
  simulator's layered construction without crossing either tape body.
- Reworked the selected-altitude bracket to the simulator's left-facing notch
  and moved both MCP target outlines after tape text, so their complete
  magenta edges remain visible. The fixed-aircraft symbol is now the thinner
  Boeing wing/hook shape with a hollow centre reference; the bank index is a
  compact stepped triangle.
- Kept the fast two-pixel native stair steps where a mathematically continuous
  line would have exceeded the protected USB budget. The official PFD test
  passes at 288 full, 209 refinement and one steady report. Differential frames
  are pixel-identical to full repaints; medians are 60 reports in cruise, 169
  while turning, 56 under jitter, 250 in modes/extremes and one at steady state.
- Passed launcher check, startup-safety and simulator-offline reset tests, plus
  all 15 global output-authority/blackout checks. No physical panel or
  simulator was opened. Remaining live check: restart Studio and inspect this
  geometry on BB35 and BB36.

## 2026-09-01 - PFD values reduced again with native slot 3

- Added `tools/build_pfp_quad_font.py`, an offline builder that preserves the
  entire approved slot-4/5/6 font resource byte-for-byte and appends a new
  slot-3 transaction cloned from the same measured WinCtrl font upload.
- Generated `winctrl-pfp-b737-cockpit-font3-4-5-6.xpwwf`. Slots 4, 5 and 6
  are byte-identical to the previous live resource; only 95 newly rasterised
  printable glyphs were added in slot 3. Point A remains the unchanged prefix
  beneath both generations.
- Reduced PFD value runs from slot 4 to slot 3. The new 14-point centred
  artwork produces digits roughly 4..8 pixels wide by 10 high, compared with
  slot 4's roughly 5..9 by 13. BB35 ND stays on slot 4, PFD operational words
  stay on slot 5, and BB36 ND/systems stay on slot 6.
- Updated the exact offline emulator to decode slot 3 from the four-slot
  resource. Before/after frames remain 436 fills, 53 text runs and 31 colour
  changes; the smaller result changes glyph pixels only, not cell positions or
  instrument geometry.
- Passed: four-slot prefix/resource guard; PFD layout and launcher self-test
  (285 full, 198 refinement, one steady report); complete differential suite
  with pixel-identical forced repaints; safe launcher check; and all 15 global
  output-authority checks. Traffic is unchanged from the approved slot-4
  version: cruise median 62, turning 171, jitter 56 and steady state one.
- Backup and exact slot-4/slot-3 comparison renders:
  `Backup/pfd_even_smaller_numbers_before_20260901-105133/`.

## 2026-09-01 - Smaller PFD numbers on BB35 and BB36

- Added a separate PFD value-font path: numerical/value runs now select the
  already-proven native slot 4 (10 x 15 ink), while FMA words, `CMD`, marker
  beacons and other PFD labels retain slot 5 (13 x 19 ink).
- Applied the smaller value glyphs to selected speed/altitude, both live
  rolling readouts, tape and pitch numbers, vertical-speed and compass values,
  selected heading, Mach/radio altitude/minimums, the joined ILS frequency,
  speed-bug labels and the joined barometer value/unit. Their existing 17 x 29
  controller cells, positions and opaque backgrounds did not move.
- BB35 and BB36 now receive the same established slot-4/5/6 resource. It is
  Point A's exact slot-5/6 byte stream with the already-measured slot-4 upload
  appended; the immutable Point A file and rollback remain untouched. BB35 ND
  already used slot 4, while BB36 ND and all systems pages remain on slot 6.
- Before/after emulation kept exactly 436 fills, 53 text runs and 31 colour
  changes. Differential frames stayed pixel-identical to forced full repaints:
  cruise median 62 reports, turning 171, jitter 56 and steady state one. The
  small extra font selection costs at most one or two reports in the measured
  moving suites, not another drawing pass.
- Passed: PFD layout/font-resource contract; launcher PFD self-test (285 full,
  198 refinement and one steady report); full differential suite including
  live/offline/live recovery. Remaining live check: restart Studio normally
  and review the smaller values on BB35 and BB36.
- Backup and exact before/after renders:
  `Backup/pfd_smaller_numbers_before_20260901-104221/`.

## 2026-09-01 - Zibo PFD armed-mode arrays use their published names

- Fixed the startup warning for the nonexistent
  `laminar/B738/autopilot/pfd_alt_mode_armed[0]`. The running Zibo catalogue
  publishes `pfd_alt_mode_arm` (singular `arm`), and Studio now resolves that
  exact captain-side array.
- Corrected the companion roll-mode source at the same time. There is no
  `pfd_spd_mode_armed` array in the loaded aircraft; the published armed roll
  source is `pfd_hdg_mode_arm`. The internal value is now named
  `fma_lateral_armed` and decoded with lateral FMA labels instead of
  autothrottle labels.
- Preserved the existing PFD text-cell geometry, dirty regions, polling rates,
  hardware ownership and global output authority. This repair changes only
  which read-only simulator values feed the two existing armed-mode fields.
- Added an offline guard that fails if either published singular `_arm` name
  is replaced or an incorrect armed-FMA key is added again.
- Proved both corrected names against the running X-Plane v3 catalogue and
  resolved captain index 0 successfully. Passed the PFP PFD self-test (283
  full, 197 refinement, one steady report), pixel-identical differential
  suite, safe launcher check, and all 15 global output-authority checks. No
  simulator value or hardware output was written. Restart Studio once to load
  the corrected bridge.
- Backup: `Backup/zibo_pfd_fma_arm_ref_before_20260901-102715/`.

## 2026-09-01 - PFD values and units read as one group

- Removed the artificial native-cell gap between PFD values and their units
  on both BB35 and BB36. Barometric settings are now one text run, such as
  `1013HPA` or `29.92IN`, instead of separate number and unit runs.
- Removed the explicit space and redundant trailing frequency zero from the
  lower-left navigation readout, so the user's example is rendered exactly as
  `LS113.3` rather than `LS 113.30`.
- Tightened selected heading to `335H` and moved `MAG` to the right side of the
  live heading box. The two labels now flank the box with equal eight-pixel
  clearances instead of placing MAG underneath it.
- Added layout guards for all four exact strings and for the left/right heading
  relationship. Exact native-font before/after rendering changed 1,951 pixels,
  all confined to the protected ILS, heading and barometer zones; the rest of
  the PFD stayed pixel-identical. The grouped barometer also removes one native
  text transmission.
- Passed: modified-file syntax; PFD layout contract; exact pixel-isolation
  check; PFP display self-test (283 full, 197 refinement and one steady report);
  global output authority (15 checks); and safe launcher check. No hardware or
  simulator was opened. Live check remaining: confirm joined unit spacing and
  the balanced `335H`/`MAG` row on both physical displays.
- Backup: `Backup/pfd_unit_spacing_before_20260901-101055/`. The earlier named
  Point A rollback remains unchanged.

## 2026-09-01 - BB35-only tiny ND font experiment, with named Point A

- Preserved the complete working Boeing-organized ND as the owner's named
  `Point A` in `Backup/point_a_bb35_boeing_nd_20260901-011500/`, including the
  renderer, bridge, font builder, exact font resource, offline renderer and
  documentation. `POINT_A_README.txt` records what that rollback means.
- Added a dedicated native font slot 4 for BB35 ND text. Its printable ink is
  10 x 15 inside the controller's required opaque 17 x 29 cell, compared with
  Point A slot 5's 13 x 19 artwork. PFD text remains on slot 5 and BB36 ND/
  systems remain on slot 6.
- Built BB35's separate
  `winctrl-pfp-b737-cockpit-bb35-font4-5-6.xpwwf` resource by preserving all
  37,779 Point A bytes as an exact prefix and appending the measured `0x106`,
  `0x107`, `0x105` font-definition/chunk/commit sequence for slot 4. No new
  vendor command was invented.
- Kept BB36 on the exact Point A
  `winctrl-pfp-b737-cockpit-dual-font5-6.xpwwf`; it does not receive the
  experimental font slot. Its 37,779 font bytes and representative 630-command
  ND frame both compare exactly with Point A.
- Passed: modified-file syntax; contiguous 10,556-byte font memory for each of
  BB35 slots 4/5/6; exact Point A prefix and BB36 resource checks; exact native
  font-4 offline render; BB35/BB36 layout and live-identifier contracts; PFP
  display self-test (284 full, 197 refinement and one steady report); global
  output authority (15 checks); and safe launcher check. No hardware or
  simulator was opened. Live check remaining: fully restart Studio so BB35
  receives slot 4, then confirm the smaller ND type is readable. If firmware
  rejects or mishandles slot 4, restore Point A.

## 2026-09-01 - BB35 gets its own Boeing-organized Navigation Display

- Split ND presentation by the physical WinCtrl display identifier. BB35
  (`0x31`) now receives a Boeing-organized page, while BB36 (`0x32`) retains
  its established Airbus-panel presentation and larger native font.
- Reused the dual-font resource already uploaded to the panels: BB35 ND text
  now uses compact native slot 5. No PNG, scaled bitmap, new font upload or
  framebuffer was added to the live path.
- Reorganized BB35's live information to match the simulator's priorities:
  combined GS/TAS and wind at left; green TRK with the live track boxed at
  centre; active waypoint, ETA, distance, mode and range at right; vertical
  EFIS overlay labels; a bracketed right-side RNP/ANP block; and `FMC L` when
  real route data is present. The selected heading remains the magenta compass
  bug instead of competing for the top band.
- Changed only BB35's range guides to the solid white Boeing arcs and reserved
  the new side zones from route/database labels, preserving all existing route,
  traffic, bearing-pointer, failure and live-data drawing functions.
- Passed: syntax; BB35 and BB36 layout contracts including live hardware-ID
  routing and shift bounds; BB36 renderer comparison against the backup (four
  representative modes byte-for-byte, plus a 630-operation live-style frame);
  exact native-font offline renders of both panels; direct and launcher PFP
  display self-tests (284 full, 197 refinement and one steady report); global
  output authority (15 checks); and safe launcher check. No hardware or
  simulator was opened. Live check remaining: open ND on BB35 and confirm the
  compact Boeing organization is readable through its physical bezel at the
  user's usual 20/40 NM ranges.
- Backup: `Backup/bb35_boeing_nd_before_20260901-004004/`.

## 2026-09-01 - Live CDU EXEC reminders on BB35 and BB36

- Added the captain-side Zibo EXEC annunciator as a read-only display signal.
  The preferred source is `fms_exec_light_pilot`, with Zibo's shared
  `fmc_exec_lights` indication retained as a compatibility fallback.
- BB35 now drives its Boeing-labelled EXEC top window on the established
  WinCtrl light channel 16. BB36 uses channel 15, the second top window from
  the right requested by the owner. The supplied SimAppPro update capture
  proves the existing `0x49` light command and the five-window channel bank
  `12..16`; no new vendor packet was invented.
- Wired the reminder into both native-FMC and graphical PFD/ND/system/FMC
  owners, so it follows the pending EXEC state whichever page is displayed.
  It is kept outside the LCD draw stream and therefore adds no PFD redraws or
  refresh traffic.
- Preserved global output authority: the reminder can illuminate only with a
  connected simulator and powered Live display. It is explicitly cleared on
  startup ownership transfer, simulator loss, aircraft power loss, path
  handoff and normal Studio shutdown before the HID handle is released.
- Passed: modified-file syntax; BB35 and BB36 separate-path self-tests; full
  PFP/BB36 coded-display self-test (284 full, 197 refinement and one steady
  report); startup safety; simulator-offline reset; hardware laboratory; and
  safe launcher check. No simulator or physical hardware was opened. Live
  check remaining: create a CDU modification, confirm BB35 EXEC and BB36's
  second dash from the right light together, then press EXEC and confirm both
  extinguish immediately.
- Backup: `Backup/cdu_exec_alert_before_20260901-002521/`.

## 2026-08-31 - Studio detects an aircraft loaded after Studio starts

- Split X-Plane Web-API readiness from aircraft readiness. Studio no longer
  commits permanently to the generic/read-only path just because X-Plane's
  capability endpoint appeared before the aircraft path and plugin DataRefs.
- Kept global Live output authority offline, and retained the existing
  simulator-down hardware owners, until the loaded aircraft supplies its path
  and the established required Boeing feedback set. The wait remains
  interruptible by a normal Studio shutdown.
- Added a slow read-only aircraft-profile watcher for automatic mode. If
  X-Plane first exposes a default/generic aircraft and Zibo, LevelUp or ToLiss
  becomes ready later, the bridge performs its normal black/off teardown and
  Studio starts one clean child generation with the correct profile. No input
  or output owner is duplicated.
- Fixed Studio's child supervisor so an exited bridge's old loopback port is
  never returned as a live client. This lets the existing exited-child restart
  path actually run after the profile watcher requests the clean recycle.
- Made the generic PFP loop observe authenticated Studio shutdown and send its
  established black/off display state before releasing the HID handle.
- Passed: modified-file syntax; late-aircraft/profile isolation and same-path
  compatibility-upgrade checks; watcher stop/recycle check; stale child-port
  recovery check; startup safety; simulator-offline reset; PFP PFD output
  handoff (284 full, 197 refinement and one steady report); safe launcher
  check; panel check; hardware laboratory; and global output authority (15
  checks). No simulator, serial port or cockpit hardware was opened. Live
  check remaining: start Studio with X-Plane closed, then start X-Plane and
  load Zibo/LevelUp/ToLiss; Studio should connect automatically without being
  closed and reopened.
- Backup: `Backup/xplane_late_aircraft_detection_before_20260831_233452/`.

## 2026-08-31 - Pixel-identical PFD command reduction and smoother IAS drum

- Confirmed that the live BB35/BB36 PFD is already entirely code-drawn. PNG
  files are offline previews only and are never loaded or transmitted by the
  live display path.
- Coalesced only consecutive, same-colour native fill rectangles whose exact
  edge-touching union is another rectangle. Draw order, geometry, colours,
  fonts and final pixels are unchanged; gaps, non-rectangular overlaps, text
  boundaries and colour changes remain separate commands.
- Reduced measured differential traffic without lowering visual quality:
  ordinary speed/altitude motion fell from a 75-report median to 62 reports,
  and combined turning/climbing motion fell from 201 to 170 reports. Jitter
  motion fell from 65 to 56 reports.
- Tightened BB36's outer airspeed duplicate threshold from 0.20 knot to 0.05
  knot. The native units drum now keeps about 1.5-pixel intermediate positions
  instead of skipping roughly six pixels, while its normal dirty-region path
  still prevents unchanged physical frames.
- Passed: modified-file syntax; direct and launcher PFP PFD self-tests (284
  full, 197 refinement and one steady report); full pixel-for-pixel
  differential equivalence across cruise, turns, jitter, extremes and recovery;
  PFD/ND/systems layout contracts; safe launch check; hardware-lab; and global
  output authority (15 checks). No hardware or simulator was opened. Live check
  remaining: observe BB36 bank, IAS drum and altitude drum motion in flight.
- Backups: `Backup/bb36_command_stream_before_20260831_232222/` and
  `Backup/bb36_speed_drum_before_20260831_232500/`.

## 2026-08-31 - BB36 capture-proven LCD-refresh completion guard

- Analysed the supplied 310 MB `mcdu_update.pcapng` by the enumerated BB36
  identity (`4098:BB36`, USB address 49), rather than assuming which busy USB
  endpoint belonged to the display.
- The recorded PFD update contained 368 consecutive F0 output reports and 368
  consecutive device acknowledgements: zero USB status errors, zero invalid
  payload lengths, and zero sequence gaps. The visible missing/pixelated lines
  were therefore not missing host packets.
- Reassembled all 20,566 payload bytes into 829 complete native commands: 771
  fills, 15 foreground changes, 22 background changes, 20 text runs and one
  LCD refresh. The refresh header began at the end of report 367 and completed
  in report 368, while the last drawing report was still outstanding.
- Ordinary drawing acknowledgements measured 1.606-11.957 ms for 95 percent
  of reports; the final drawing acknowledgement took 2.951 ms. The refresh
  itself took 29.911 ms to acknowledge, proving a separate LCD-swap phase.
- Retained the earlier BB36-only four-millisecond quiet period before the now
  isolated refresh, and added a 35-millisecond completion guard afterwards.
  A large page-entry frame can no longer start its next update while firmware
  0x0104 is still swapping the previous frame onto the glass. BB35 and the
  established every-eight-report BB36 burst pacing are unchanged.
- Passed: in-memory syntax; direct and launcher PFP PFD self-tests (285 full,
  200 refinement and one steady report); full differential equivalence; PFD,
  ND and systems layout contracts; safe launch check; hardware-lab; and global
  output authority (15 checks). No captured packet was replayed and no physical
  device or simulator was opened. Live check remaining: restart Studio, cycle
  BB36 between PFD/ND/MFD repeatedly, and watch fine attitude/tape lines during
  both a full page entry and subsequent motion.
- Backup: `Backup/bb36_pcap_refresh_completion_before_20260831_230053/`.

## 2026-08-31 - BB36 PFD marker flash and page-entry refresh repair

- Fixed the exact BB35/BB36 difference seen in the cockpit. BB36 suppresses
  duplicate graphical frames to protect its slower MCDU endpoint, but that
  comparison predated the completed PFD and did not contain marker beacons or
  the other later approach/flight-path indications. `IM` changing by itself
  was therefore discarded on BB36 while BB35 continued to flash correctly.
- Extended BB36's visual-state comparison with every added PFD indication,
  including OM/MM/IM, minimums, raw ILS, armed FMA, FPV, pitch limit, rising
  runway and the navigation identifier. The existing dirty-region renderer
  still sends only the pixels that changed; a settled IM flash measured 15
  reports on and 14 reports off rather than a complete PFD.
- Protected BB36 page entry from command-boundary sensitivity. Its proven
  native `0x103` LCD refresh is now emitted in a separate F0 burst after a
  four-millisecond controller settle, so the optional IM text command cannot
  shift the refresh into a still-processing full-frame burst. BB35 retains its
  established combined batching. No vendor command or packet was invented.
- Added offline guards for marker-only state changes, small IM on/off dirty
  frames, and BB36-only refresh isolation while confirming BB35 batching is
  unchanged.
- Passed: in-memory syntax; direct and launcher PFP PFD self-tests (285 full,
  200 refinement, one steady report; IM 15 on/14 off); full differential
  equivalence; PFD, ND and systems layout contracts; safe launch check;
  hardware-lab; and global output authority (15 checks). No test opened a
  simulator or physical device. Live check remaining: fully restart Studio,
  cycle BB36 through ND/MFD/PFD while over the inner marker, and confirm IM
  flashes without a torn or pixelated PFD entry.
- Backup: `Backup/bb36_pfd_marker_refresh_before_20260831_224643/`.

## 2026-08-31 - Smaller PFD-only native font

- Added a dual-size native font resource. Slot 5 now contains moderately
  smaller 17 x 29 artwork for the PFD text and numbers; slot 6 remains
  byte-for-byte identical to the proven compact resource, including its
  embedded static shape tiles.
- PFD selected values, FMA, tape numbers, live speed/altitude, heading,
  minimums, barometer, radio altitude and ILS text use the smaller slot 5.
  Cell geometry and every protected PFD zone are unchanged.
- ND, ENG PRI, MFD and HYD explicitly retain the previous larger slot-6 font.
  The graphical FMC continues to use its separate established font resource.
- Added `tools/build_pfp_dual_font.py` and taught the offline PFP emulator to
  decode the font ID selected by each native text command.
- Passed: dual-font isolation; 95 printable slot-5 glyphs; syntax; PFD, ND,
  systems and HYD marker-motion layout contracts; installed-runtime PFP PFD
  self-test; launcher PFD self-test; full differential equivalence; safe
  launch check; hardware-lab; global output authority (15 checks); and offline
  rendering of all coded pages. No hardware or simulator output was opened.
  Live check remaining: completely restart Studio so it uploads the new font,
  then inspect PFD readability on BB35 and BB36.
- Backup: `Backup/pfd_smaller_font_before_20260831_223012/`.

## 2026-08-31 - HYD control motion and physical-bezel safe text

- The HYD/FLT CTRL page now reads the already-established X-Plane pilot
  control positions for roll, pitch, yaw, and independent left/right toe
  brakes. Aileron, elevator, rudder, and brake markers therefore remain
  visible during a control test even if unpowered hydraulics keep the actual
  aircraft surfaces still. Existing surface outputs remain the fallback.
- Added a moving green brake marker inside each left/right wheel symbol while
  retaining all four aircraft brake-temperature values.
- Reflowed each crowded `FLT SPLR` caption into separate `FLT` and `SPLR`
  lines. The verified 17 x 29 controller font remains unchanged; no guessed
  font packet or bitmap image was added.
- Moved ENG PRI/HYD left titles and the right `MUSLIMSIM` mark into a 34..606
  bezel-safe band. Moved the PFD top-right selected-altitude and vertical-FMA
  text into the same safe right edge.
- Added an offline marker-motion contract for roll, pitch, yaw and both toe
  brakes, plus neutral and deflected HYD review renders.
- Corrected a stale installed-runtime assertion that expected a failed display
  refresh to re-light the panel. The test now enforces the current blackout
  rule: a failed restart leaves both brightness channels at zero until
  Live/Test authority explicitly permits output. Runtime behavior was already
  dark and was not weakened.
- Passed: in-memory syntax compilation; systems layout/marker-motion and PFD
  layout contracts; `bridge/final.py --test-pfp-pfd`; `launch.py
  --test-pfp-pfd`; `launch.py --check`; differential-frame equivalence;
  pedal mapping; hardware-lab; global output authority (15 checks); and coded
  page rendering. The simulator-down control-channel test was correctly
  refused because the user's already-running Studio owned the bridge
  singleton; it was not stopped. Live check remaining: restart Studio, move
  roll/pitch/yaw and each toe brake on HYD, then confirm both physical display
  edges are visible.
- Backup: `Backup/display_motion_safe_area_before_20260831_215756/`.

## 2026-08-31 - BB35/BB36 coded PFD, ND, engine and hydraulic suite

- Expanded the shared BB35/BB36 graphical worker into an explicit coded page
  suite: PFD, ND, futuristic `ENG PRI`, secondary engine `MFD`, and `HYD`.
  BB36 retains its separate graphical FMC handoff. Existing captured HID
  input, controller, motor, solenoid and selector paths were not replaced.
- Completed the PFD with Mach, radio/barometric minimums, ILS identifier and
  frequency, localizer/glideslope scales, marker beacons, armed FMA modes,
  field-elevation hatch, slip/skid, exact Zibo FPV, stall/pitch-limit cue,
  rising runway, and a six-second altitude trend. The new FPV/stall/runway
  positions come from datarefs explicitly present in the installed Zibo
  aircraft rather than guessed calculations.
- Rebuilt the ND as code-native APP, VOR, MAP, PLAN and VSD pages with all EFIS
  ranges, centred/expanded geometry, active/modified/missed/alternate/offset
  routes, waypoint constraints/ETA, RF legs, holds, track trend, altitude
  intercept, RNP/ANP, terrain/weather inputs, TCAS classes, VOR/ADF pointers,
  fuel-range ring, marker/glideslope presentation and failure annunciations.
  Opaque waypoint labels now collision-test against protected map zones.
- Route strings and arrays use exact installed Zibo FMS datarefs. They refresh
  through a bounded daemon cache so an unavailable or slow X-Plane Web API
  cannot stall the physical display loop. No fictitious route, navigation or
  failure value is drawn when the aircraft does not publish one.
- STA, WPT and ARPT now draw real nearby entries from the installed X-Plane
  `earth_nav.dat`, `earth_fix.dat` and Global Airports `apt.dat`. Each database
  loads only after its EFIS switch is selected, on a daemon thread, into a
  one-degree spatial index. Repeated display queries use a movement/range cache
  (3,000 cached queries measured about 0.003 seconds), so no frame scans the
  full database. Minor WPT entries suppress automatically at 80 NM and above.
- Added aircraft-style secondary engine and hydraulic pages plus a new
  futuristic ENG PRI, all drawn from native fills/text. No PNG is loaded by a
  live display path. `tools/render_coded_display_pages.py` creates offline PNG
  snapshots only for visual QA.
- Preserved global output authority: unavailable/unpowered Live output goes
  black, Test permits only its selected output, and normal shutdown blackens
  before releasing the panel. The renderer never keeps ownership afterward.
- Passed: syntax and all three layout contracts; `bridge/final.py
  --test-pfp-pfd`; differential-frame equivalence (cruise, turning, jitter,
  modes/extremes, recovery); `launch.py --check`; global output authority (15
  checks); bridge simulator-down control channel; input-chain self-test (28
  checks); and offline rendering of all nine coded scenarios. No simulator or
  hardware was opened. Installed database parsing also passed for 7,523
  stations, 240,642 fixes and 38,359 airports, including KDFW. Live check
  remaining: run X-Plane/Zibo, cycle every
  page on BB35 and BB36, and compare live route, TCAS, FPV, approach, engine
  and hydraulic indications against the aircraft.
- Backup: `Backup/coded_complete_displays_before_20260831_204903/`.

## 2026-08-31 - FCU/EFIS typography enlarged and separated

- Preserved the existing captain EFIS / four-column FCU / first-officer EFIS
  design and every existing control tag.
- Enlarged the main headings, FCU/EFIS titles, digital values, toggle labels,
  selector labels, knob captions, PULL controls, and lower FCU action buttons.
- Gave the central knob captions, PULL row, and two action rows independent
  vertical bands. On both EFIS wings, STD/QNH, BARO, unit, MAP MODE, RANGE,
  NAV 1, and NAV 2 now have explicit spacing between text and guide lines.
- Added `tools/test_fcu_faceplate_layout.py`, which renders the actual Tk
  faceplate, verifies each typography band is separated, enforces the larger
  selector/button font sizes, and confirms every FCU/EFIS control remains
  clickable. The test caught and removed a final one-pixel STD/BARO collision.
- Offline rendered-layout, BA01 semantic/Zibo routing, syntax, and global
  output-authority checks passed. No hardware or simulator was opened. Live
  check remaining: reopen Studio at the normal window size and visually review
  the larger labels.
- Backup: `Backup/fcu_text_spacing_before_20260831-194213/`.

## 2026-08-31 - ECAM measured-name box moved below the faceplate

- Moved the two-line `MEASURED BUTTON NAMES` guidance box out of the ECAM
  button bay and into the unused dark-blue area below the physical panel. It
  no longer covers the bottom CLR control or its click target.
- Moved the colour/state legend into the unused lower trim of the physical
  panel so both pieces remain fully visible on the fixed 980 x 680 Studio
  design surface.
- Added an offline rendered-layout check that verifies the complete guidance
  box is below the panel, remains inside the canvas, and does not overlap any
  of the 18 physical button tags.
- Offline ECAM layout and syntax checks passed; no hardware or simulator was
  opened. Live check remaining: reopen Studio and confirm the placement at the
  user's normal window size.
- Backup: `Backup/ecam32_status_box_layout_before_20260831-192751/`.

## 2026-08-31 - ECAM32 button names changed from guessed order to guided capture

- Fixed the cause of physical ECAM buttons selecting the wrong Studio name
  (for example BLEED appearing as ELEC). Studio had zipped the 18 raw BB70
  contacts from a packet recording onto the 18 Airbus labels by recording
  order. That order did not prove which legend was pressed, so it was removed.
- Studio now uses only a user-measured `visual name -> raw contact` relation
  for ECAM32. Unmeasured buttons show `CAPTURE` and cannot masquerade as a
  different button or be routed under a semantic key that the hardware never
  reported.
- Added `CAPTURE_ECAM32_BUTTON_NAMES.cmd`. With Studio closed it asks for ENG,
  BLEED, PRESS, ELEC, HYD, FUEL, APU, COND, DOOR, WHEEL, F/CTL, ALL, left CLR,
  STS, RCL, right CLR, T.O CONFIG, and EMER CANC one at a time. It accepts only
  one clean press plus its release, rejects duplicate/ambiguous contacts, and
  requires `SAVE` after showing all 18 results.
- The wizard is a temporary sole HID owner and refuses to run while Studio or
  the bridge is active. It keeps the panel dark, never connects to a simulator,
  sends capture-proven OFF on exit, releases the HID handle, rechecks that
  Studio is still closed, and only then writes profiles.
- The physical name map is copied to every named profile in every existing
  `hardware_profiles*.json` file because PCB contact identity does not change
  with aircraft or simulator. Simulator-function bindings are preserved.
  Each profile file receives a timestamped backup and the complete measured
  map is retained as `ecam32_button_names_*.json`.
- Added `tools/test_ecam32_button_capture.py`. Offline checks passed for syntax,
  18-name completeness, clean press/release, missing/duplicate/ambiguous
  rejection, two profile files, multiple named profiles, binding preservation,
  backup/audit creation, and the Studio-owner process guard. Hardware Lab,
  global output authority (15 checks), the TCA rendered faceplate (89 checks),
  `muslimsim_panel.py --check`, and `launch.py --check` also passed. No test
  opened the ECAM or a simulator. Live check still required: run the new CMD,
  capture all 18 real buttons, restart Studio, and verify each physical label.
- Backup: `Backup/ecam32_guided_button_mapping_before_20260831-173901/`.

## 2026-08-31 - TCA Practice levers rebuilt from the proven live axis path

- Before editing, the already-running bridge was observed read-only. The real
  TCA reported continuous values roughly every 15-32 ms, not button edges;
  rest is raw `+1.0`, full travel is `-1.0`, and the existing faceplate uses
  `(1.0 - raw) / 2.0`. That physical polling, deadband, pickup baseline, and
  sole SDL ownership remain unchanged.
- Practice no longer treats a TCA axis click as `value=1` / `phase=press`.
  Pressing a handle or any point in its slot starts a continuous drag. Every
  pointer sample moves only the tagged handle group with `Canvas.move`; the
  whole Studio canvas is not deleted and rebuilt during the drag.
- Loopback posting uses one coalescing background drain. It keeps only the
  newest raw value, preserves the live reader's `0.0015` meaningful-change
  threshold and 15 ms cadence, and always sends the final release position.
  A server-side `practice_only` gate holds the Lab mode lock across the Test
  check and input, so a delayed drag packet cannot cross into Live routing.
- Practice draws both physical-style quadrants together as six independent
  slides: AIRBRAKE, THRUST 1, THRUST 2, THRUST 3, THRUST 4, FLAPS. Both units
  include all three axes, five side buttons, six handle contacts, the
  three-position select knob, both encoder directions, and its pushbutton.
- The same one-quadrant physical interface is now selectable and remappable
  after it enumerates as bank 1&2 or bank 3&4. Bank 1&2 keeps its existing Zibo
  defaults. Bank 3&4 gets no invented aircraft defaults; the owner chooses its
  assignments in Studio.
- The sole physical SDL reader still opens one TCA quadrant, exactly as it did
  before this work. Simultaneously opening a second physical unit was not mixed
  into this smoothness repair because that reader also owns PU, WinCtrl
  throttle, and pedals; it needs a separately approved live-hardware change.
- The complete `_pu_controller_reader` block is byte-identical to the backup:
  both hash to `40F63B8D...F8E81`. This is the direct check that the working
  physical polling and pickup code was not rewritten during the retry.
- Offline tests passed: Practice mechanics 20 checks, catalogue 158, knob 39,
  real hidden-Tk faceplate rendering 89, Hardware Lab, global output authority
  15, syntax compilation for all changed Python files, and `launch.py --check`.
  No test opened SDL hardware or a simulator.
- Backup: `Backup/tca_verified_smooth_baseline_20260831-165409/`.

## 2026-08-31 - TCA faceplate: a real 2D quadrant that is live and clickable

- The owner reported that moving the slides in Studio "don't post on the
  software". The cause was not the mapping layer, which was already correct:
  `_draw_tca_boeing_combined` contained **zero `_tag()` calls**, and
  `_faceplate_click` only reacts to a `control:<key>` tag. With no tags nothing
  on the panel could ever be selected, so "Choose simulator function" could
  never leave its disabled state and the footer stayed on "Choose a visual
  control first".
- The same function also read no live values. Every lever handle was drawn at
  `(lane_top + lane_bottom) / 2` - a hardcoded mid-lane - which is why all six
  sliders in the owner's screenshots sat dead centre regardless of the
  hardware. Its "AXIS 0/1/2" captions were `enumerate()` ordinals that matched
  no hardware at all; the three levers are SDL axes 3, 4 and 5.
- Replaced it with `MUSLIMSIM_TCA_BOEING_2D_FACEPLATE_V3`: one quadrant drawn
  as the single physical unit it is, rather than two side-by-side bank cards.
  Every control from the 2026-08-31 capture is in its physical place - three
  levers labelled LEFT/MIDDLE/RIGHT with their AIRBRAKE/THRUST/FLAPS roles,
  reverse levers on the middle and right handles, a button on each of those two
  handles, five side buttons down the captain edge, the continuous top knob
  with its two direction contacts, the PUSH/SELECT button, and the
  three-position select knob captioned IAS/MACH, HDG/TRK and ALTITUDE.
- Handles now track the live bridge mirror through `_device_mirror`. Travel is
  drawn as `(1.0 - raw) / 2.0`, which is deliberately the same expression the
  binding uses, so rest sits at the bottom stop and means idle thrust,
  speedbrake in, flaps up. The panel and the aircraft cannot disagree about
  which way a lever is pointing.
- Every control is tagged with its catalogue key, so clicking one selects it
  and enables the mapper. Pressed contacts light, the selected control takes
  the standard highlight ring, and a control the catalogue has not verified is
  drawn muted rather than offered as mappable.
- Added `tools/test_tca_boeing_faceplate.py`, 43 checks. It draws the panel
  onto a real off-screen Tk canvas and then interrogates the result: every
  captured control carries a `control:` tag, no tag names anything that is not
  a catalogue control, the middle lever actually moves between rest and full
  travel and moves *upward* for full travel, moving one lever does not move
  another, selecting adds geometry, and a press changes fill colours. A syntax
  check cannot catch a bad colour literal or a static handle; drawing it can.
  On a machine with no display the test reports that and exits 0.
- Also fixed a collision found by rendering it: the handle button sat below the
  handle, which overlapped the axis caption once a lever reached its bottom
  stop - which is exactly where a throttle rests. It now sits beside the handle.
- Tests: `tools/test_tca_boeing_faceplate.py` passed (43 checks). Full suite
  re-run and passed unchanged - `test_global_output_authority.py` (15),
  `test_tca_boeing_knob.py` (39), `test_tca_boeing_catalog.py` (127),
  `test_chains.py` (28), `test_hardware_lab.py`,
  `test_bridge_control_channel.py`, `test_fcu_efis_lab.py`, plus
  `python launch.py --check`.
- Backup: `Backup/tca_faceplate_2d_v1_20260831-145535/`.
- Preview of the rendered panel: `PNG/tca_faceplate_2d.png`.
- Live check still needed: open Studio, select the quadrant, and confirm the
  handles follow the physical levers and that clicking one enables "Choose
  simulator function".

## 2026-08-31 - Global output authority, rebased onto the TCA work instead of over it

- The owner supplied an externally generated package,
  `MUSLIMSIM_GLOBAL_OUTPUT_AUTHORITY_V1.zip`, and asked for it to be checked
  before use. **It must not be applied as shipped.** It is locked to
  `final.py` SHA `e1a6a65d...`, which is the revision from *before* the TCA
  knob dispatcher, and it ships whole-file payload replacements rather than
  diffs. Its payload contains zero occurrences of
  `MUSLIMSIM TCA BOEING KNOB DISPATCH V1`, `_tca_boeing_knob_observe`, or
  `pap3_next_speed_value`, and its `lab.py` contains no `DEFAULT_BINDINGS`.
  Applying it would have deleted both the knob dispatcher and the
  out-of-the-box lever rules. Its installer refuses on hash mismatch, which is
  correct behaviour and the only reason the risk was contained.
- Its actual changes were extracted by diffing the payload against its own
  declared base, then rebased onto current. All 20 `final.py` hunks and all 3
  `lab.py` hunks applied cleanly with offsets; nothing it changes overlaps the
  TCA work. The other four files were untouched by MuslimSim work and were
  installed from the payload directly.
- The design is sound and matches the owner's clarified rules: Live enforces
  aircraft power, Test is active-test-only, a normal shutdown sends proven
  OFF/BLACK before releasing hardware, and no vendor packet is invented -
  ECAM32, FCU/EFIS and BB36 all reuse already-captured writes.
- **Correction 1 - a scoped mirror instead of a severed one.** The package
  removed all three call sites of `_emit_practice_snapshot`, which satisfied
  "entering Test mode must not wake everything" by also losing "the thing you
  are testing lights up". Pressing a control *is* asking to test it. The
  mirror is kept and restricted: `_advance_practice` now emits with
  `only_device=<the device pressed>`, and `ControlServer.apply_practice_snapshot`
  takes an `only_device` filter. `only_device` is part of the cached
  signature, because the same snapshot scoped to a different device is a
  different physical write and must not be suppressed as a duplicate.
- This also removed the dead code the package would have left behind:
  `_emit_practice_snapshot`, `_practice_output_sink` and
  `apply_practice_snapshot` would all have had zero callers while
  `bridge/final.py` still registered a sink that could never fire.
- Scoping additionally fixes a violation the package only hid. Every mirror
  wrote `("fcu_32_efis", "backlight", 180)` and `("pap3_mag", "backlight", 1)`
  unconditionally - one of the "woken with non-zero brightness before power is
  known" cases this work exists to stop. Those writes are still needed to see
  the device under test, so they are kept and the update list is filtered.
- **Correction 2 - the AGP power judgement no longer fails open.**
  `_agp_aircraft_output_powered` returned True whenever it collected no
  values, conflating two opposite situations. It now separates them: no
  electrical ref configured means the aircraft does not publish one, so
  established behaviour is preserved; refs configured but unreadable means
  live data was lost while Studio is in Live mode, which must go dark rather
  than hold a stale indication. This was the one place the package's code
  disagreed with its own stated rule.
- Added `tools/test_global_output_authority.py`, 15 checks: registering a sink
  writes nothing, entering Test mode writes nothing, a press emits scoped to
  exactly the pressed device, a release emits nothing, the mirror never runs
  in Live mode, the server honours the scope it is given, and the four AGP
  power cases resolve the way the rule requires.
- Tests: all seven suites passed - `test_global_output_authority.py` (15),
  `test_tca_boeing_knob.py` (39), `test_tca_boeing_catalog.py` (127),
  `test_chains.py` (28), `test_hardware_lab.py`,
  `test_bridge_control_channel.py`, `test_fcu_efis_lab.py`, plus
  `python launch.py --check`. Both feature sets verified present afterwards.
- Backup: `Backup/global_output_authority_v1_rebased_20260831-144232/` holds
  all six files as they were.
- Live check still needed, and none of this has been flown: cold and dark
  should give dark screens and no lit lamps in Live mode; losing the simulator
  in Live mode should go black rather than showing a standby card; Test mode
  should light only the output being tested; and a normal Studio shutdown
  should leave the panels dark.

## 2026-08-31 - TCA Boeing knob: select picks a function, the top encoder adjusts it

- The owner corrected the earlier guess: the select knob has three positions,
  not four, and they name what the top encoder controls - left IAS/MACH, middle
  HDG/TRK, right ALTITUDE. The knob pushbutton engages whatever that window is
  showing.
- This could not be a `MappingBinding`. A binding is static per control, and
  here encoder-clockwise means a different thing at each select position. It is
  therefore real code: `MUSLIMSIM TCA BOEING KNOB DISPATCH V1` in
  `bridge/final.py`, added directly after the existing V5 block, plus one hook
  in `_muslimsim_observe_lab_event`.
- HDG and ALT step through commands. Heading uses the generic
  `sim/autopilot/heading_up` / `_down` for the same reason PAP3 does - one
  degree per detent instead of Zibo's accelerated knob behaviour. Altitude uses
  `laminar/B738/autopilot/altitude_up` / `_dn`.
- IAS/MACH deliberately is not a command. PAP3 already established that Zibo
  owns its MCP speed dial and immediately overwrites X-Plane's generic airspeed
  dial, so the dispatcher does a read-modify-write on
  `mcp_speed_dial_kts` / `mcp_speed_dial_kts_mach`, choosing the dial that
  matches `sim/cockpit/autopilot/airspeed_is_mach`. The step arithmetic is
  `pap3_next_speed_value` imported and reused, not reimplemented, so the two
  MCP speed paths cannot drift apart. An unreadable Mach flag falls back to
  IAS: a knot step on a Mach dial is visible and harmless, the reverse is not.
- Precedence is unchanged and explicit. The dispatcher checks
  `profile_store.has_binding()` first and yields to any saved binding, so a
  rebound encoder behaves the way the owner set it. When the dispatcher does
  act, the same contact is still recorded for the Studio but `route=False` is
  passed, so one detent never acts twice.
- Nothing is assumed before the select knob has been seen in a detent: with no
  position known, the encoder does nothing rather than guess which function to
  move. The detent is tracked in the baseline phase sampled at connect, so the
  first step after a reconnect already knows where the knob is.
- Added `tools/test_tca_boeing_knob.py`, 39 checks, which loads `bridge/final.py`
  through `importlib` (its entry point is `__main__`-guarded and it executes
  nothing at module level) and replaces the five simulator helpers with
  recorders. It proves the direction of every step, that Mach mode writes the
  Mach dial, that a release does not repeat a press, that a baseline sample
  does not write, that a saved binding wins, and that non-knob contacts are
  left alone.
- Tests: `test_tca_boeing_knob.py` (39) and `test_tca_boeing_catalog.py` (127)
  passed. Existing suite re-run and passed unchanged - `test_chains.py` (28),
  `test_hardware_lab.py`, `test_bridge_control_channel.py`,
  `test_fcu_efis_lab.py`. `python launch.py --check` passed with no simulator,
  serial port, WinCtrl, or PU hardware opened.
- Backup: `Backup/tca_boeing_knob_dispatch_v1_20260831-142925/` (bridge/final.py
  at 22265 lines before the change).
- Live check still needed, and not yet flown: turn the select knob to each
  position and confirm the top encoder moves the matching MCP window, then
  press the knob button and confirm it engages.

## 2026-08-31 - TCA Boeing quadrant: the owner's lever rules as out-of-the-box defaults

- The owner asked for the quadrant to follow their rules straight out of the
  box, while still letting any lever be reassigned. Precedence is now:

  ```text
  saved user binding  >  declared device default  >  bridge dispatcher / nothing
  ```

- `DEFAULT_ROLES` in `muslimsim/hardware/catalog.py` could not carry this. It
  is descriptive only: a control with no saved binding falls through to the
  bridge dispatcher that already owns that hardware. The TCA has no
  dispatcher - the bridge tracks it for display and routes nothing on purpose -
  so "no saved binding" meant "does nothing at all".
- Added `DEFAULT_BINDINGS` beside it: executable defaults, consulted by
  `HardwareLab._binding()` only when `profile_store.has_binding()` is False.
  That method already existed for exactly this question, so the meaning of an
  absent entry is unchanged for every other device. The table names
  `tca_boeing` and nothing else, and a test fails if that ever stops being true.
- The rules, for one quadrant: left slide is the airbrake, right slide is the
  flaps, and the middle slide drives every engine through
  `sim/cockpit2/engine/actuators/throttle_ratio_all`. That target is
  engine-count agnostic, so the middle slide is correct on a twin and on a four
  with no branching - the owner's rule 1 layout generalises. The middle and
  right reverse levers drive `reverse_lever1` and `reverse_lever2`.
- Axis scaling needed no bridge change. The binding sink computes
  `(1 - raw) * scale`, and the levers report -1.000..+1.000 resting at +1.000,
  so `invert` with a 0.5 scale maps rest to 0.0 and full travel to 1.0. Rest
  meaning 0.0 is deliberate: idle thrust, speedbrake retracted, flaps up - the
  safe end whichever way round the levers are physically oriented.
- Added two entries to `SAFE_AXIS_FUNCTIONS` in
  `muslimsim/hardware/zibo_library.py`: the Zibo flap lever and the all-engine
  throttle. Both were confirmed writable against the running aircraft before
  being offered. Without them the owner could rebind a lever away from its
  default and have no way to pick the default back.
- Note the deliberate change of posture: `bridge/final.py` carries the comment
  "Once live, only a user-saved HardwareLab mapping may route this raw source."
  Shipping defaults means the quadrant now routes without a saved mapping. That
  is what was asked for, and it is recorded here rather than left implicit.
  `bridge/final.py` itself was not modified.
- Tests: `tools/test_tca_boeing_catalog.py` extended to 127 checks - every
  default is a valid binding on an implemented control, every default axis
  target is offerable in `SAFE_AXIS_FUNCTIONS`, a saved binding beats a
  default, an explicit `disabled` is honoured rather than resurrecting the
  default, restoring a profile brings the rules back, and no other device gains
  a default. Existing suite re-run and passed unchanged: `test_chains.py` (28),
  `test_hardware_lab.py`, `test_bridge_control_channel.py`,
  `test_fcu_efis_lab.py`.
- Backup: `Backup/tca_boeing_default_rules_v1_20260831-141729/`.
- Live check still needed, and nothing here has been flown: start Studio,
  confirm the three slides drive speedbrake, thrust and flaps, and confirm the
  direction. If a lever works backwards, the fix is one `invert` flag in the
  default, not a code change.
- Not built, and still needed for the rest of the owner's rules: the two-knob
  mechanism (select knob picks, encoder adjusts - the four target functions are
  not yet decided), and rules B and C, which both need two physical quadrants
  connected at once. The current `_TCA_BOEING_STATE` tracks one unit at a time.

## 2026-08-31 - TCA Boeing quadrant: captured, catalogued, and its keys made routable

- The Studio drew the Thrustmaster TCA Boeing quadrant and the quadrant sent
  nothing to X-Plane. Three faults were stacked in
  `muslimsim/hardware/catalog.py`, and every one of them was silent:
  - The catalogue described axes 0..2. Capture proved the three levers are on
    axes 3, 4 and 5, and that axes 0, 1 and 2 never leave their rest value. The
    real levers therefore had no catalogue entry at all.
  - The catalogue spelled button keys zero-padded (`bank12_button_00`), while
    `_tca_boeing_control_aliases()` in `bridge/final.py` looks up
    `bank12_button_4` and twelve other unpadded spellings. Every button lookup
    missed. `_tca_boeing_lab_input()` caches a miss and returns None so that a
    static catalogue is not re-walked at joystick poll rate, so nothing was
    ever logged.
  - Every control was `status="unknown"`, and `_input()` sets
    `remappable = (status == "implemented")`. So even a correctly spelled key
    could not have been bound from the Studio.
- Added `tools/capture_tca_boeing_one_unit_both_banks.py`: a read-only SDL
  capture that refuses to start while Studio or the bridge is running, per the
  no-second-SDL-reader rule. It runs a discovery sweep, then names each control
  by prompting for it and recording whichever axis or contact actually moves.
- Captured the owner unit on bank 1&2 - axis pass twice, button pass once.
  Three levers on axes 3/4/5 left to right, full -1.000..+1.000 travel resting
  at +1.000. Buttons 1/2 on the middle and right slides, reverse levers 4/5 on
  the same two slides (owner-confirmed), five side buttons 6-10, a
  three-position select knob on 11/12/13, a direction-coded continuous encoder
  (CW 15, CCW 14), and a knob pushbutton on 16.
- No slide has a detent switch: nothing closed during a full sweep of any
  lever. Reverse is the separate lever contact, not a below-idle band, so this
  quadrant does not need the WinCtrl URSA MINOR idle-gate treatment.
- Rewrote the catalogue block as `MUSLIMSIM_TCA_BOEING_SINGLE_UNIT_CATALOG_V3`
  with the captured labels, the correct axis indices, and unpadded keys. Bank
  1&2 now has 18 controls at `status="implemented"`, so they are remappable and
  every alias the bridge asks for resolves. Buttons 0 and 3 complete the
  slide-button and reverse-lever runs but were not isolated by a prompt, so
  they stay `unknown`. Bank 3&4 is the same unit but was not captured, so it
  stays `unknown` until the selector is moved and the capture re-run.
- Added `tools/test_tca_boeing_catalog.py`, which fails if a key is padded, if
  a captured control is not `implemented`, if a phantom axis is promoted, or if
  bank 3&4 claims to be verified. The original bug produced no error anywhere;
  this turns it into a failing test.
- Tests: `tools/test_tca_boeing_catalog.py` passed (97 checks). The existing
  suite was re-run and passed unchanged - `test_chains.py` (28 checks),
  `test_hardware_lab.py`, `test_bridge_control_channel.py`,
  `test_fcu_efis_lab.py`. `bridge/final.py` was not modified.
- Backup: `Backup/tca_boeing_catalog_capture_v3_20260831-140645/`.
- Live check still needed: bind a slide in Studio and confirm it moves the
  aircraft. Not yet done.
- Still to do, and not started: the Studio faceplate is a static picture -
  `_draw_tca_boeing_combined()` reads no live value and draws every lever at
  mid-lane, and its "AXIS 0/1/2" labels are loop ordinals that match no
  hardware. The owner engine-count rules also need
  `sim/aircraft/engine/acf_num_engines`, which nothing reads yet.

## 2026-08-31 - Project root settled: `D:\MuslimSim` is canonical, the Howalt folder is a working copy

- The user confirmed they work in `D:\MuslimSim` and keep
  `D:\Howalt d203 requre signature\MuslimSim` only as a working copy. The two
  had drifted apart: the code was newer in `D:\MuslimSim` (`bridge/final.py`
  about 12 KB larger, plus `muslimsim/devices/pdc_bb61_bb52.py` and
  `muslimsim/hardware/device_lifecycle.py`, which existed nowhere else), while
  every specialist document still lived only in the working copy.
- This mattered for the rules, not just for tidiness. `AGENTS.md` rule 4
  requires updating `PROJECT_HISTORY.md` and the relevant specialist document
  on every material change, and rule 1 named the Howalt folder as the only
  place to work. Working in `D:\MuslimSim` meant rule 4 could not be followed,
  because those documents were not present there.
- Copied the missing documentation and diagnostics into `D:\MuslimSim`:
  `PROJECT_HISTORY.md`, `PFD_PROJECT_HISTORY.md`, `DEVICE_REFERENCE.md`,
  `SYSTEM_ARCHITECTURE.md`, `CONTROL_PANEL.md`, `HARDWARE_LAB.md`,
  `MCDU_BB36_INVESTIGATION.md`, `README.txt`, `diagnose_bb36_lifecycle.py`,
  `diagnose_bb36_live_freeze.py`, and `PU_SOURCE_EVIDENCE_DASHES_V9_1.zip`.
  Nothing was overwritten - none of these existed in `D:\MuslimSim` before the
  copy - and each was verified byte-identical to its source afterwards.
- Updated `AGENTS.md` rules 1 and 2 to name `D:\MuslimSim` as the only place
  to work and to back up, and to state that the Howalt folder is a working
  copy that must not be edited or trusted as the source of truth. The previous
  file is kept at `Backup/AGENTS_before_root_relocation_20260831-123137.md`.
- Verified afterwards with a full-tree comparison (ignoring `__pycache__`,
  `build`, `dist`, `Backup`, `backups`, `logs`) that nothing remains in the
  working copy which is missing from `D:\MuslimSim`.
- No renderer, bridge, or hardware-mapping behaviour changed, and nothing was
  run against the rig. Tests: none applicable - this was a file relocation and
  documentation change only.

## 2026-08-29 - MOZA Flight SDK probe: first live run, both bases confirmed visible with real parameter/command IDs

- The user ran `tools/probe_moza_flight_sdk.py` on the real hardware (via
  `& "C:\Users\noureddine aidoudi\AppData\Local\Programs\Python\Python311\python.exe" probe_moza_flight_sdk.py`,
  since plain `python` was not on PATH in their PowerShell - documented for
  next time). No code change in this entry; recording what the probe proved.
- `Moza_Initialize` returned `NO_ERROR(0)`. The forwarded SDK log shows the
  device service process was NOT already running (`设备服务进程未启动，第1次尝试启动`)
  and the SDK started it itself by a registry lookup, resolving to
  `C:/Program Files (x86)/MOZA Cockpit/bin/MOZADeviceService.exe`. That is
  `MOZADeviceService.exe`, a background service binary that lives inside the
  Moza Cockpit install folder - not the Cockpit GUI process itself. This is
  the strongest evidence yet for the user's requirement ("even if mozasoftware
  is closed"): the SDK can locate and launch the device service on its own
  via the registry, independent of whether Cockpit's window is open. Still
  need the user to confirm explicitly whether Cockpit's GUI was open or
  closed for this particular run, and ideally get a second run in the other
  state for a clean before/after (see Live check below).
- 4 devices discovered, all `MOZA_DC_AS`: `AY210 Yoke Base` (id=1, COM4,
  PID 0x1001) with child `MFY Yoke Handle` (id=4, a detachable stick device
  on the yoke base's own port); `AB6 Base` (id=2, COM6, PID 0x1002) with
  child `Stick` (id=3, on the AB6's own port). This confirms the AB6 is the
  base with a plain stick attached and the AY210 is the yoke base with its
  own detachable handle - useful context for the Studio UI grouping.
- Full parameter and command lists were dumped for every device (387
  parameters / 735 commands for AB6, 361 parameters / 681 commands for
  AY210, 29/47 and 12/16 for the two stick devices). Confirmed concrete IDs
  for the SAVED CALIBRATION fields, present on both AY210 and AB6:
  - `overall_strength` -> parameter `Main_Steer_AllStrengthCoefficient` (id 86),
    commands `MainSet_Steer_AllStrengthCoefficient`/`MainGet_...` (212/213)
  - `max_torque` -> parameter `Main_Steer_TorqueMax` (id 79), commands 198/199
  - `damper` -> parameter `Main_Steer_DampCoefficient` (id 88), commands 216/217
  - `friction` -> parameter `Main_Steer_FricCoefficient` (id 90), commands 220/221
  - `inertia` -> parameter `Main_Steer_InertiaCoefficient` (id 89), commands 218/219
  - `spring` -> parameter `Main_Steer_SpringCoefficient` (id 87), commands 214/215
  - `game_force_feedback` -> parameter `Main_Steer_GameForceFeedbackCoefficient`
    (id 63), commands 166/167
  - the FFB master switch `Main_CtrlFfbEnable` (id 312) is present on both
    bases, matching the id already documented in
    `docs/Flight_Base_Force_Feedback_Command_Guide.md`.
  - The `MainCtrl_Ffb*` command family (603-610: NewEffect/Constant/Ramp/
    Periodic/Condition/Envelope/EffectOperation/Control) is present as real
    commands on both AY210 and AB6, confirming the FFB Command Guide's
    documented protocol matches what these specific units actually expose.
  - `background_led_brightness`/`gear_led_brightness` and related LED
    parameters exist only on the AY210 (ids 22-28), not the AB6 - matches
    `moza_presets.py`'s existing preset structure exactly (those fields are
    only in the `a210_*` presets, never `ab6_*`).
  - No device-side parameter corresponds by name to the FLIGHT EFFECTS
    toggles (g-force, stall buffet, runway rumble, gear/flaps motion, jet
    rumble, turbulence, speedbrake buffet). The closest relatives are
    `Main_DynamicConditionForceBind_Aileron/Elevator`,
    `Main_DynamicConditionForceEnable_Aileron/Elevator`, and the
    `Main_VariablePointCurve_*` curve parameters. This means those effects
    will most likely have to be synthesized bridge-side as FFB periodic/
    envelope commands driven by X-Plane telemetry, not simply toggled as a
    device parameter - important for scoping the next implementation step.
  - The single read-only value read succeeded on 3 of 4 devices (`Main_YawConnected`
    on AB6, `Main_PanelRawData` on AY210, `Stick_Data` on the yoke handle) and
    timed out on the fourth (`Stick_Data` on the AB6's stick) - the script
    reported the timeout cleanly (`TIMEOUT(11)`) instead of crashing, and no
    `SetValue`/`CommandSend`/FFB call was made anywhere in the run.
  - The script completed cleanly end to end with no crash: `Moza_ValueDestroy`,
    `Moza_DeviceClose` x4, and `Moza_Shutdown` all ran, confirmed by the
    trailing SDK log lines (`已关闭ZMQ消息处理线程池`, `设备服务SDK资源已关闭`).
- **Live check still needed** - confirm whether Moza Cockpit's GUI was open
  or closed for this run, and get one run in the other state to close out
  the dependency question cleanly. After that, the next step is deciding
  scope for the actual write path: wiring the six confirmed calibration
  parameters to real `Moza_DeviceParameterSetValue(Sync)` calls, and
  separately scoping the FFB command work for the flight-effects toggles -
  not started yet, pending user direction given this next step will be
  capable of driving real hardware torque.

## 2026-08-29 - Added a read-only MOZA Flight SDK discovery probe (`tools/probe_moza_flight_sdk.py`)

- New file, not an edit of an existing one, so no backup entry applies (AGENTS.md
  rule 2 covers changes to existing material files).
- Purpose: the user wants Studio's SAVED CALIBRATION values (OVERALL/MAX
  TORQUE/DAMPER/FRICTION/INERTIA/SPRING/flight-effects) to actually drive the
  physical MOZA AY210 yoke base and AB6 base, with force feedback and
  vibration working even when Moza Cockpit's own window is closed. Today
  those values are only ever written to a local JSON profile
  (`muslimsim/hardware/moza_presets.py`) - no Moza output protocol exists in
  this project yet, by design (see that file's own docstring).
- Confirmed which vendor SDK is the right one: MOZA's Racing SDK
  (`RS21_sdk`, previously downloaded) has zero flight-base awareness and its
  own readme requires "MOZA Pit House (SDK version)". The Flight SDK
  (`MOZA_SDK` 1.0.0.4) covers `MOZA_DC_AS` aircraft devices - wheelbase,
  stick, throttle, control panel, screen - and its docs only ever mention a
  generic background "device service", never Cockpit/Pit House. Confirmed
  via `include/moza/moza.h`, `include/moza/private/macros.h` (plain
  `__declspec(dllexport/dllimport)`, no `__stdcall` - so Python `ctypes.CDLL`
  is the correct binding, not `WinDLL`), `docs/MOZA_SDK_Developer_Guide.md`,
  `docs/MOZA_SDK_API_Reference.md`, `docs/Flight_Base_Force_Feedback_Command_Guide.md`,
  and `examples/c_api_example.c` (the discover -> open -> list-parameters ->
  list-commands -> close -> shutdown flow this probe follows).
  The SDK download itself now lives at
  `C:\Users\noureddine aidoudi\Downloads\MOZA_Flight_SDK_1.0.0.4 - enUS\MOZA_SDK\`,
  with `x64-release\bin\MOZA_SDK.dll` (14 MB) as the runtime library and an
  included `tools\SdkDebugTool\ApiDebugTool.exe` GUI for manually
  cross-checking the same parameter/command lists.
- The probe: initializes the SDK, registers the SDK's own internal log
  callback (useful when init fails, since MOZA_ERR_SERVICE_NOT_FOUND is
  exactly the "is the device service even running" signal this is meant to
  test), waits (default 5s, matching the vendor's own example's `Sleep(5000)`)
  for the device service to enumerate, lists every device, and for each
  `MOZA_DC_AS` device opens it and prints its full parameter list and
  command list with real IDs and names from
  `Moza_DeviceParameterGetList`/`Moza_DeviceCommandGetList` - not guessed.
  It cross-references each parameter name against Studio's own calibration
  field names from `moza_presets.MOZA_EDITABLE_KEYS` and flags a likely
  match inline, to locate the concrete parameter IDs behind OVERALL/MAX
  TORQUE/DAMPER/FRICTION/INERTIA/SPRING.
- Strictly read-only: only `Moza_Initialize`, the `*_GetList` functions, and
  (unless `--skip-value-read`) one `Moza_DeviceParameterGetValueSync` read of
  a single already-readable parameter are called. No `Moza_DeviceParameterSetValue(Sync)`,
  no `Moza_DeviceCommandSend(Sync)`, and no `MainCtrl_Ffb*` command exists
  anywhere in this file - no torque, effect, vibration, or motor motion is
  possible from running it.
- ctypes struct layouts were built directly from `moza.h`: `MOZA_LOG_CONTEXT`
  is declared before the header's `#pragma pack(push, 1)` so it uses natural
  alignment (no `_pack_`); `MOZA_VALUE`, `MOZA_DEVICE_INFO`,
  `MOZA_PARAMETER_INFO`, and `MOZA_COMMAND_INFO` are declared inside that
  packed region, so each ctypes `Structure`/`Union` sets `_pack_ = 1` to
  match.
- Also gives the user the concrete two-run test for the open question of
  whether device discovery needs Moza Cockpit's GUI open or just a
  background service: run once with Cockpit fully closed, once with it
  open, and compare.
- Tests run: `python -m py_compile` and `python -m pyflakes` on the new
  file, both clean. No live run - this session has file access to
  `D:\MuslimSim` but no shell on the machine that owns the hardware, and the
  DLL is a Windows PE binary that cannot be loaded from this session's Linux
  workspace either.
- **Live check still needed** - the user needs to actually run
  `python tools/probe_moza_flight_sdk.py` on their PC (once with Moza
  Cockpit closed, once with it open) and share the output. Nothing further
  is implemented until that confirms the AY210/AB6 are visible to this SDK
  and clarifies the service-vs-Cockpit dependency; this is deliberately only
  the discovery step, not yet the parameter-set or FFB-command wiring.

## 2026-08-29 - Moza Studio: fixed FLIGHT EFFECTS/disclaimer overlap, moved MAX3 GRIP to the AB6 tab set

- Fixed a layout bug in `muslimsim/gui/studio.py`'s `_draw_moza_calibration`
  (the shared MOZA A210/AB6 SAVED CALIBRATION panel): the FLIGHT EFFECTS
  section's third row used the same 52px row step as the first two sections,
  which put its bottom edge past the disclaimer text below it. Reduced the
  FLIGHT EFFECTS row step to 44px, which reclaims enough room that the last
  row (TURBULENCE/SPEEDBRAKE) no longer runs into the "Preset values are
  saved..." disclaimer text underneath it. Confirmed the box math by hand:
  the third row's bottom edge now sits well clear of the disclaimer's text
  block instead of a few pixels inside it.
- Moved the MAX3 GRIP tab from the A210 tab set to the AB6 tab set, per the
  user: the MAX3 grip mounts on the AB6 base on this rig, not the A210 yoke
  base. `_draw_moza_max3_layout` itself is untouched - same faceplate, same
  live TRIGGER/TOP button state, still read from the A210 HID contact pool
  per the existing capture (that part of the comment on the function is
  still accurate; the grip's electrical contacts are proven to enumerate
  through the A210's HID pool regardless of which tab surfaces the
  faceplate). Only the tab bar and the click handler's page whitelist moved:
  A210 keeps A210 BASE / DETACHABLE YOKE, AB6 gets AB6 BASE / MAX3 GRIP.
- Updated `_activate_moza_visual`'s tab-click guard, which previously only
  accepted page clicks when `device == "moza_a210"` - AB6's single tab was
  effectively decorative. It now looks up a per-device set of valid pages,
  so AB6's two tabs are both clickable.
- Nothing else in `studio.py` was touched - no other device's panel, no
  other Moza layout function, no calibration values or presets.
- Tests run: `python -m py_compile` on the changed file, and a full diff
  against the pre-change backup confirming the change is confined to the
  three edited spots above.
- **Live check still needed** - this was verified by reading and compiling,
  not by opening the Studio window (no shell/GUI access from this session).
  Please open Displays/Calibration for both Moza devices and confirm: no
  text/button overlap at the bottom of either panel, and the AB6 screen now
  shows AB6 BASE and MAX3 GRIP tabs, both clickable, with MAX3 GRIP no
  longer appearing under A210.

## 2026-08-29 - BB35/BB36 path routers: restored auto-restart on a dead display worker

- Today's undocumented BB35/BB36 separate-paths edit (made ~26 minutes after
  the `bb35_bb36_restart_mode_fix_20260829` backup, with no backup of its own
  and no changelog entry) changed the router's dead-worker handling from a
  same-mode restart to `self.stop_evt.set()`. That does not just skip one
  restart: it ends the router's `_run()` loop permanently. Nothing calls
  `.start()` again afterward, so the panel stops receiving frames and is left
  showing whatever was already on the glass - explaining the frozen BB35
  ENG PRI and BB36 "PRACTICE COCKPIT" pages reported after the last fix.
- Restored the pre-edit behaviour on both panels: a dead display-worker
  thread sets `restart_dead_path = True` and the router loops back to
  recreate and restart the same-mode path, instead of shutting itself down.
  This re-enables logic that was already present but had gone dead
  (`restart_dead_path` was declared and read downstream on both files but
  never set `True` any more).
- Deliberately left everything else from today's edit alone: PERIOD x3 stays
  disabled as a display-mode handoff on both panels (matches
  MCDU_BB36_INVESTIGATION.md's finding that repeated F0/F2 handoffs degrade
  this firmware), `toggle_evt.clear()` in `start()` stays, and the
  `live_plane_refresh_pending` removal stays.
- Backed up the two pre-fix files to
  `Backup/bb35_bb36_worker_restart_regression_fix_20260829_131043/` before
  writing the change.
- Tests run: `python -m py_compile` on both changed files (clean), and a
  line-by-line diff against `Backup/bb35_bb36_restart_mode_fix_20260829/`
  confirming the restored block is byte-identical to the last version that
  was actually exercised on hardware, with only today's other, intentional
  changes remaining as differences.
- **Live-cockpit check still needed** - this fix was written and verified by
  reading, not by running the bridge or touching the panels: no shell/HID
  access from this session. Please restart the bridge, confirm BB35 and BB36
  both come up live (not on a stale frame), and if either was already stuck
  before this fix was installed, do a real "Restart screen" (USB
  re-enumeration, Administrator) first - a soft Redraw will not clear a
  frame the firmware is already holding.

## 2026-08-28 - Throttle below-idle split, forced per-unit calibration

- Added a Throttle tab that draws the WinCtrl quadrant as the two bands a 737
  actually has: IDLE to TOGA, and IDLE through REV IDLE to full reverse. Each
  band is drawn only over its own travel, so both read 0.0% at the idle
  detent and there is no ambiguity about which side of it the lever is on.
- Established that the hard-coded detents are wrong on this hardware. The
  left lever reads 20165 against an assumed 19308, which is 1.85% commanded
  thrust with the lever in its own idle detent. Confirmed through the
  bridge's own `_winctrl_throttle_values`, not a re-derivation.
- Added `--throttle-left-idle`, `--throttle-left-rev-idle`,
  `--throttle-right-idle` and `--throttle-right-rev-idle`. The control panel
  passes measured values on every start. An impossible calibration (REV IDLE
  above IDLE) is refused with exit 2 rather than clamped: a silently
  corrected throttle would command thrust the pilot did not ask for.
- The quadrant is read over raw HID, matching the bridge's Raw Input decode.
  Calibrating through SDL would have produced values the bridge never sees.
  The preview borrows the bridge's mapping function rather than copying it.
- Two safety checks added: thrust is exactly zero at IDLE and anywhere below
  it whatever the reverse handle does, reverse is inert with the handle down,
  and an invalid calibration never reaches the bridge. 16 checks now pass.
- Offline tests passed: `--test-winctrl-throttle`, `--test-pfp-pfd`,
  `--test-aircraft-profiles`, `--test-startup-safety`, `launch.py --check`,
  `muslimsim_panel.py --check`. Live cockpit check still needed: capture both
  detents and confirm idle settles at zero on both engines.

## 2026-08-28 - MuslimSim.exe: a real application, no console and no batch file

- Packaged the control panel as `dist/MuslimSim.exe` (27 MB, one file,
  windowed via pythonw). Built by `build_exe.py` from `MuslimSim.spec`.
- The manifest requests Administrator, because a real screen restart
  re-enumerates the USB device and Windows refuses that silently otherwise.
- Rebuilt the panel as tabs: Devices, Calibration, Throttle, Displays, Output.
- Live axis calibration for pedals, throttle and yoke with a bar per axis,
  range capture, centre capture and invert. Read through SDL because SDL is
  what the bridge reads these devices through. Keyed by controller name, not
  index, because SDL renumbers devices when one is unplugged.
- Live display mirror of the PFP and MCDU at about 12 ms per frame, drawn by
  the same renderer the bridge uses from the values it drew its last frame
  with. The bridge now records those values and serves them over the control
  channel; a second dataref reader was rejected because it would show live
  numbers while the panel showed standby.
- A frozen exe has no interpreter to start the bridge with, so it re-runs
  itself with `--run-bridge`. Settings are written beside the exe, not into
  the unpacked bundle, which Windows deletes on exit.
- Fixed two bugs that only a frozen build exposed: the self-test read .py
  files that do not exist inside a bundle, and asserted the bridge starts via
  `launch.py`. Added a check that the files loaded by path are bundled.

## 2026-08-28 - USB power cycle: stop trusting the exit code

- Measured that `pnputil /restart-device` exits 0 without elevation and does
  nothing at all: after a reset reporting success, the bus was polled at
  50 ms for 3.5 s with 0 absent samples out of 80. The device never left.
- `reset_device` now checks for Administrator up front, targets the USB
  parent PnP node rather than the HID child, and verifies the device really
  left the bus and came back before reporting success.
- Fixed `present()`: `hid.enumerate(0, 0)` treats zero as a wildcard, so a
  presence check for a nonexistent device returned True. It now verifies the
  returned entries rather than trusting the filter.

## 2026-08-28 - Control panel and the in-bridge control channel

- Added a control panel that owns the bridge as a child process and can stop,
  start or reset one device without restarting the others. Previously the
  only granularity was Ctrl+C.
- Added a loopback JSON-line control channel inside the bridge
  (`--control-port`, `--control-token`), bound to 127.0.0.1 and carrying a
  per-run token. Off unless the panel passes it, so terminal launches are
  unchanged.
- The channel opens BEFORE the wait for X-Plane. The first version opened it
  after the managers exist and so never came up with the simulator down,
  which is exactly when the panels may need resetting. Stop went from a
  Ctrl+Break kill (0xC000013A) to a clean unwind in 1.9 s, exit code 0.
- Added `muslimsim/hardware/catalog.py`: every device declaratively, so
  adding a panel is one entry rather than changes spread across the launcher,
  the GUI and the bridge. The ECAM (BB70) is listed with `implemented=False`.
- Corrected the PFP catalogue entry to use launcher vocabulary: `launch.py`
  strips a bare `--pfp-pfd` unless its own `--with-pfd` was given, so the
  engine flag would have been silently deleted. A self-test check pins this.

## 2026-08-28 - MCDU speckles investigated; no fix applied

- The reported black specks on the MCDU PFD are NOT in the rendering.
  Counting gaps pixel by pixel over three attitudes: the PFP, which has no
  speckle complaint, has 108; the squeezed MCDU has 69. Drawing 300
  successive frames onto one canvas gave zero wrongly-black pixels and two
  stale white pixels, fixed and non-growing.
- Two changes made on the false hypothesis were reverted: the vertical
  compression back to the known-good 0.10, and an erase-rounding change whose
  stated rationale had been disproved. A note at the constant says not to
  re-tune it chasing these specks.
- Added `tools/probe_mcdu_speckle.py`, which paints flat fields to settle
  whether the panel speckles with no PFD on screen at all. Not yet run.

## 2026-08-27 - PAP3 MCP speed dial and annunciator-power correction

- Replaced the PAP3 SPEED rotary's generic X-Plane commands with writes to
  Zibo's verified writable MCP selector through the PAP3 manager's existing
  Web API socket. IAS writes the underlying `mcp_speed_dial_kts` control,
  rather than its combined display mirror, which Zibo restores to 100 each
  frame; Mach retains the combined dial representation.
- Removed the false `electric/main_bus` output gate. The current Zibo reports
  that value as zero while avionics are powered and MCP statuses are active;
  it had held the PAP3's global LED brightness at zero, making every MCP and
  A/T annunciator appear dark. Avionics state is now the power gate.
- Added `tools/test_pap3_mcp.py`, which verifies speed bounds, the WebSocket
  write packet, active annunciators with a zero main-bus reading, and the
  magnetic A/T solenoid output.

## 2026-08-27 - BB62 MINS and BARO rotary controls bound from raw trace

- The focused physical trace proved that the apparent shared HID axis was
  background movement, not a common rotary source. MINS clockwise and
  counter-clockwise pulses are bits 41 and 39; BARO clockwise and
  counter-clockwise pulses are bits 44 and 42.
- Bound MINS direction pulses to Zibo CAPT minimums up/down and BARO direction
  pulses to the Zibo pilot barometer up/down commands. The existing no-write
  baseline still prevents a stationary panel from changing the aircraft at
  startup or after reconnect.
- Offline mapping/dispatch tests, syntax compilation, and launcher checks
  passed. Live confirmation remains limited to one parked rotary detent at a
  time after a bridge restart.

## 2026-08-27 - BB62 VOR/ADF reliability fix and focused knob trace

- Replaced the VOR/ADF selector's inferred numeric-state logic with absolute,
  saturating Zibo command sequences. Each physical VOR, OFF, or ADF position
  now first reaches the appropriate endpoint and, for OFF, takes one step
  back to centre. This avoids the previous failure where only the OFF position
  could be applied reliably.
- Added the read-only `tools/probe_pdc_bb62.py --knob-trace` mode. It records
  four labelled raw HID traces: MINS clockwise/counter-clockwise, then BARO
  clockwise/counter-clockwise. The two rotaries remain deliberately unbound
  until that source/direction evidence separates them safely.
- Offline PDC mapping and command-sequence tests, syntax compilation, and
  launcher checks passed.

## 2026-08-27 - BB62 CAPT EFIS controls bound from physical capture

- Applied the captured 64-button/axis map from the connected `4098:BB62`
  panel. CAPT MINS mode, BARO unit selector, VOR/ADF selectors, MODE, RANGE,
  RST/STD, TFC/WXR/STA/WPT/ARPT/DATA/POS/TERR/FPV/MTRS now dispatch only after
  a no-write startup baseline.
- Verified the active Zibo/X-Plane v3 API exposes the required CAPT datarefs
  and command names; the manager uses the bridge's existing REST helpers,
  resolves IDs lazily, and refreshes one stale ID after an aircraft reload.
- MINS and BARO knobs both captured as HID axis 0. They are deliberately
  ignored rather than being allowed to move both settings together. Run
  `--diagnose-pdc` and capture each knob's raw direction/source separately.
- Offline tests passed: expanded `tools/test_pdc_bb62.py`, syntax compilation,
  and launcher checks. Live confirmation is still required one EFIS control at
  a time, parked, with `--diagnose-pdc`.

## 2026-08-27 - WINCTRL 3N PDC / EFIS BB62 capture-first integration

- Added an independent PDC BB62 (`4098:BB62`) manager to the same standalone
  MuslimSim process. It owns only its own non-blocking HID reader; absent,
  unplugged, or malformed PDC reports cannot stop the PU, throttle, PAP3,
  AGP, pedals, PFD/BB35, or MCDU/BB36 paths.
- The current device is deliberately capture-only: its first valid 64-button,
  two-axis report is a no-write baseline, later raw report deltas are available
  with `--diagnose-pdc`, and it sends no aircraft command or dataref change.
  No PDC display/LED selector is guessed or written.
- Added generic, PID-parameterised (`62 BB`) 0x02 and 0xF0 packet builders as
  offline-only protocol support. A future mapped action is designed to use the
  bridge's existing `set_dataref` / `activate_command` helpers rather than a
  separate PDC WebSocket stack.
- Registered the PDC in `ALL_DEVICES` and `DeviceSelection`; `--without-pdc`
  maps to `--no-pdc`, and `--without-winctrl` also disables the PDC like PAP3.
- Corrected the read-only probe's selector flow: every held position is now
  compared with a different position on the same selector, so an initial
  resting position can be captured accurately.
- Offline tests passed: `tools/test_pdc_bb62.py`, syntax compilation of the
  touched modules/bridge, and `launch.py --check`. Live cockpit confirmation
  still required: run the supplied physical-control capture sequence before
  adding any semantic PDC mapping.

## 2026-08-26 - PFD differential output completed and live recovery fixed

- Replaced unconditional whole-screen PFD transmission with a persistent
  24-pixel dirty-region grid. Only cells whose final pixels changed are sent
  to the PFP, while a periodic complete recovery frame protects against a lost
  USB update.
- Fixed the opaque-font overlap case found by the differential checker: a text
  run is expanded to its complete native cell bounds before dirty output, so a
  partial repaint cannot erase an unchanged neighbouring symbol.
- Added quantised attitude/heading inputs and motion-adaptive geometry. A
  moving or recovery horizon uses economical two-row bands; a stationary
  follow-up restores the one-pixel detail.
- Fixed live -> offline -> live recovery. Boot and offline pages now invalidate
  the renderer's persistent state, so reconnecting with unchanged aircraft
  values still sends a complete live PFD instead of leaving the standby page.
- Split live telemetry into a 0.25-second fast flight sample and a 1.0-second
  complete sample for slower FMA/barometer values. This improves motion updates
  without multiplying every X-Plane read.
- Added `tools/check_pfd_differential.py`, which proves the differential canvas
  pixel-identical to a forced full repaint through cruise, turns, sensor jitter,
  display modes/extremes, periodic recovery, and live/offline/live sequences.
- Measured results over the 120-frame suite: cruise median 75 reports, turning
  median 201, jitter median 66. The banked recovery self-test is 248 reports,
  its stationary refinement is 183, and an unchanged frame is one refresh
  report.
- Tests passed: syntax compilation; the expanded differential suite;
  `--test-pfp-pfd`; `--check`; `--test-pu-lights`;
  `--test-starter-retract`; `--test-pedals`; and
  `--test-winctrl-throttle`.
- Live cockpit confirmation still needed: PFP motion smoothness and X-Plane
  frame pacing during a real turn, with PU CONNECT's PFP output closed.

## 2026-08-27 - The PFP page fix was lost and restored

- The PFP lost its page cycling again. The BB35 file had reverted to the
  repair package's `lambda: "pfd"`, undoing the fix made earlier the same
  session. It was lost while proving the guard bites: the file was copied to
  a temporary path, deliberately broken, and the copy-back did not take.
- The guard worked exactly as intended and named the fault immediately:
  "The BB35 worker's page getter does not follow the router: it still reports
  'pfd' after a cycle". Writing it was worth more than the fix itself.
- Restored from `pfp_bb35_separate_paths_KNOWN_GOOD_20260827_184552.py`, which
  differed from the live file in nothing but that fix. Verified the getter
  follows the router again: reports pfd, then nd after one cycle.
- Lesson recorded: never verify a guard by breaking the live file. Break a
  copy and run the test against the copy.

## 2026-08-27 - The PFP's page fix does not apply to the MCDU

- Checked whether the MCDU carries the same fault the PFP had, and it does
  not. The PFP's pages were pinned because the PAP3 repair replaced its path
  methods and handed the worker `lambda: "pfd"`. The MCDU router:
  - has no repair block and nothing replaces its methods;
  - already passes its own `get_display_page` in the nine-argument call;
  - stores `display_page` on the same instance the slash detector cycles,
    behind the same lock, exactly as the PFP does;
  - cycles page names the worker accepts -- both lists are
    ("pfd", "nd", "eng_pri", "mfd").
- So there is no equivalent fix to apply. Every static check says the wiring
  is right, which points at the slash not being detected at all rather than
  the page not being picked up. The worker prints GRAPHICAL PAGE -> on every
  change, and in the logs so far it has only ever printed PFD.
- Added live key diagnostics instead of guessing again: with
  `--diagnose-mcdu`, the MCDU's PFD path names every button it sees and marks
  which one is bound to the page trigger and which to the path toggle. A
  trigger bound to a wrong index fails silently, and this is what makes it
  visible without stopping the bridge.

## 2026-08-27 - MCDU display behaviour restored to its pre-session state

- Walked every backup and built a timeline. The MCDU ran on offset 10,
  compression 0.10, starting on FMC for the whole project. All three of the
  display behaviours that differ today were changed during this session, and
  the panel was reported working before any of them.
- Restored all three:
  - the viewport maps every fill again, instead of passing a full-screen fill
    through unmapped and banded;
  - compression back to 0.10 from 0.0512;
  - the startup refresh sends the MCDU no character-plane configuration. That
    was added so its startup blank would land, and it puts the panel into
    character mode before the PFD path ever opens.
- The shutdown restore still sends that configuration, which is correct: it
  hands the panel back to WinCtrl equipped as WinCtrl expects.
- Removed two self-test guards that enforced the reverted behaviour: the
  full-plane clear coverage check, and a cap on the compression. That cap
  encoded a measured preference for keeping more of the picture, and the panel
  contradicts it -- 0.10 is what it ran on. The guard that ordinary fills are
  still fitted stays.
- Kept from this session: the MCDU starting on the PFD (asked for), the
  standby pages, the page-getter fix, and the geometry guards.

## 2026-08-27 - The PAP3 package pinned the PFP to its PFD page

- Page cycling stopped working on the PFP after the PAP3 repair was installed.
  The cause is in that package's BB35 handoff patch:

      if needs_page_getter:
          path._repair_page_getter = lambda: "pfd"
          args.append(path._repair_page_getter)

  It hands the display worker a constant getter. SLASH x2 still advances the
  router's page, the worker just never asks it, so the display stays on the
  PFD for the life of the session. ND, ENG PRI and MFD become unreachable with
  nothing in the log to say why. Their README documents this as intended
  ("additionally receives a callback returning \"pfd\"") -- which is wrong for
  any build that has page cycling, and this one has had it for a while.
- Fixed to pass the router's own `get_display_page`, keeping the constant only
  as a fallback for a router that genuinely lacks the method. Verified the
  getter now follows the router: reports `pfd`, then `nd` after one cycle.
- Guarded it in `--test-pfp-pfd`: the worker must receive a page getter, and
  that getter must change after a cycle. Proved it bites by restoring the
  package's version -- "does not follow the router: it still reports 'pfd'".
- Note for future installs: re-running the PAP3 repair will overwrite this,
  because the marker block is replaced wholesale. The self-test will catch it.

## 2026-08-27 - The MCDU page cycle is correct; verified rather than changed

- Checked the ND / ENG PRI / MFD cycle end to end against the PFP 3N and found
  nothing to fix. Reporting that rather than changing something that works.
  - The trigger listens on button 70, and the panel's own key map calls that
    index `('/', laminar/B738/button/fmc1_slash)`.
  - Two presses within 0.55 s, the same as the PFP.
  - The cycle produces pfd -> nd -> eng_pri -> mfd -> pfd, the same order.
  - The PFD path hands `get_display_page` to the worker in the nine-argument
    call.
  - The detector and the cycle function differ from the PFP's only in their
    docstrings.
  - All four pages render through the MCDU's viewport with essentially the
    same ink as the PFP: pfd 75150 vs 78704, nd 4008 vs 4099, eng_pri 9072 vs
    9051, mfd 8945 vs 9023. The ND draws its compass, range, ground speed,
    wind and mode correctly.
- So the pages do not appear on the panel for the same reason the PFD does not
  after a handoff: the graphics plane stops displaying. It is the known fault
  in MCDU_BB36_INVESTIGATION.md, not a second problem.
- Added a parity guard to `--test-pfp-pfd`: the MCDU's trigger index must be a
  key the panel actually calls "/", both panels must cycle the same pages in
  the same order with the same press count, and the real detector is driven
  against the real cycle callback so an order that looks right but does not
  advance is still caught. Proved it bites by setting the index to 69, which
  the panel calls Z.

## 2026-08-27 - PAP3 repair package v2 applied

- Installed `MuslimSim_PAP3_BB35_PFD_PFP_Repair_2026-08-27_v2`. Its 26-test
  suite passed, both patch targets validated, and every installed file
  compiles.
- Caught a real hazard in its default behaviour first. The installer picks the
  newest `final*.py` carrying the PAP3 marker, and the backup taken minutes
  earlier was newer -- its first dry run selected
  `Backup/pre_pap3_.../final.py` as the active bridge. Run unpinned it would
  have patched a backup and left the real bridge untouched. Both the dry run
  and the install pinned `--bridge` and `--bb35-module` explicitly.
- Verified the change by applying it to a throwaway copy and diffing before
  touching the installation. It is 14 lines, all PAP3: the LCD refresh floor
  moves 0.04 -> 0.12 s, a new `--pap3-start-delay` (default 3.0 s) lets the
  displays finish initialising before PAP3's first output burst, and that
  delay is passed to the manager.
- The BB35 router came out byte-identical; its handoff patch reported "already
  current" because an earlier version of this package was installed before.
  `pap3_mcp.py` and `winctrl_output_bus.py` were already present and identical.
- Confirmed none of this session's work was disturbed: MCDU viewport still
  10 / 0.0512, cell pitch 23x29, MCDU still starts on the PFD, standby pages
  intact, both handoff traces intact, and the dead functions removed earlier
  stayed removed. `launch.py --check` and `--test-pfp-pfd` both pass.

## 2026-08-27 - Tuned after the move to D:\MuslimSim

- Verified the move: launcher check, PFD self-test and the differential
  checker all pass at the new path, all five fonts sit beside final.py, and
  the 49 restore points came across. Nothing used absolute paths.
- Removed the two dead functions this investigation left behind,
  `_blank_mcdu_between_paths` and `_hard_reset_mcdu_display` (71 lines). The
  second is the one that painted the panel dark on every trigger; leaving it
  in the file was a trap for whoever read it next.
- Removed `DISPLAY_HANDOFF_BLACKOUT_SECONDS` and the `blackout_seconds`
  parameter, which existed only for that reset.
- `_winctrl_background_packet` now uses `WINCTRL_BACKGROUND_FUNCTION` instead
  of repeating 0x104 as two loose bytes. Verified the packet is still
  byte-identical to the proven one.
- Rewrote `MCDU_BB36_INVESTIGATION.md`. Several of its conclusions had been
  disproven by later testing and it would have sent the next reader down the
  same dead ends. It now separates what is established from what was claimed
  and later broken, and marks as *untested* the recovery commands that were
  only ever tried on an already-dead panel.
- Audited every top-level function: 10 unreferenced ones remain, all
  pre-existing (1226 lines, mostly superseded PFD and cockpit page drawing).
  Left alone rather than removed unasked; reported for a decision.

## 2026-08-27 - MCDU investigation handed over

- Wrote `MCDU_BB36_INVESTIGATION.md`: what is established by measurement, the
  panel's real geometry, the seven approaches ruled out and why, the two
  questions still open, and the one mechanism not yet tried. Written so a
  fresh attempt does not repeat any of today's dead ends.
- The tree is verified clean: nothing added during the investigation still
  paints the MCDU between paths.

## 2026-08-27 - The black screen was the hard reset painting it

- Found what was actually darkening the MCDU on every trigger, and it was the
  hard reset added earlier today. It fills the whole graphics plane with the
  background colour (6, 7, 13), which on this panel reads as black, and the
  incoming PFD then cannot draw over it.
- Unwired it. The toggle is a plain handoff again, with nothing painting the
  plane between paths. Confirmed nothing else remains: no blackout on stop,
  no clear on FMC entry, no hard reset from the router.
- The startup refresh keeps its own clear, which is correct there and is what
  the BB35 panel visibly restarts from.
- This also explains the report that BB35 restarts at startup while BB36 does
  not: the visible part of that refresh is its brightness blackout, and this
  panel does not appear to respond to it. Both panels run the same code and
  both report success, which is why it looked identical in the log.

## 2026-08-27 - Reverted the handoff blackout; what the attempt did establish

- Reverted the whole handoff blackout. It made the PFD unreachable: after the
  flash the panel stayed dark and the returning PFD never appeared, which is
  worse than the border it was meant to replace. The router is back to its
  2026-08-27 13:50:56 state; the regression is kept beside it as
  `mcdu_bb36_BLACKOUT_regression_*`.
- What the attempt did establish, and it is the most useful fact of the day:
  a long-running PFD session's writes reach the glass -- the black fill was
  plainly visible, the first whole-screen change anything produced on this
  panel all session. A freshly opened PFD session's writes, after the FMC
  path has run, do not: its own background restore lands, but nothing the PFD
  draws afterwards appears.
- So the split is not between planes or coordinates. It is between a session
  that has been drawing and a session that has just opened. Every clear that
  "succeeded" and did nothing was issued from a freshly opened session; every
  write that visibly worked came from one already running.
- That also explains the power cycle: it is the only thing that returns the
  panel to a state where a fresh session can draw.

## 2026-08-27 - The blackout was a state, not a flash

- The handoff blackout worked -- the screen visibly goes black, which is the
  first time anything in this session has produced a visible reset on this
  panel. But it was left there: the graphics plane stayed black, so when the
  PFD came back its own page was hidden underneath.
- The plane is now returned to its normal background after the hold, so the
  blackout is a flash rather than a state. Verified the colours are used in
  order (0,0,0) then (6,7,13), both covering all 480 rows.
- Also confirmed, by comparing the two panels, that the character-plane blank
  is byte-identical between them: spaces at COLOR_WHITE, same encoder. That
  had been a suspect for the black sitting on top and it is not one.

Needs a look in the cockpit: whether the trigger now flashes black and then
shows the incoming page, in both directions.

## 2026-08-27 - Brightness cannot blank this panel; its own PFD session can

- Measured against the panel: setting the MCDU's screen brightness channel to
  zero and holding it for two seconds did not blank the screen. The packet is
  byte-identical to the one the FMC path uses successfully to set 128 and 220,
  so the command is right and this panel simply does not black that way.
- That rules out the blackout the handoff reset was built on, and explains why
  lengthening it from 60 ms to 0.45 s would not have helped either.
- The handoff blackout now comes from the outgoing PFD session instead, which
  is the one place on this panel proven to write the graphics plane -- it has
  been drawing the PFD there all along. It fills the framebuffer black, holds
  it 0.45 s, then hands over. Verified the fill covers all 480 rows.

Needs a look in the cockpit: whether the MCDU now visibly goes black on each
trigger.

## 2026-08-27 - The hard reset was running invisibly

- The handoff reset blacked the panel out for 60 ms, which is below what the
  eye registers. It has run correctly on every trigger and looked like a page
  flip, which is exactly what was reported.
- The flicker the PFP 3N shows on a handoff is not a blackout either: it is
  its 0.89 s font upload, during which the character grid is configured but
  not yet written, so a bare grid is on the glass. That is what reads as a
  reset there.
- The handoff now holds its blackout for 0.45 s, separate from the 0.06 s the
  startup refresh uses, so a reset is visible as one.

Needs a look in the cockpit: whether the MCDU visibly goes dark on each
trigger, and separately whether a brightness of zero blanks this panel at all.

## 2026-08-27 - The border was geometry: the PFD drew where the page cannot reach

- With both PFD paths finally visible, the traces are equivalent. BB35's PFD
  entry is 2 reports, BB36's is 5 -- the same clear, banded. FMC entry and
  closing match phase for phase. Nothing about what is sent differs.
- The fault was where the PFD draws. It drew into rows 10..449 while the FMC
  page covers only 37..443, so 27 rows at the top and 6 at the bottom held PFD
  content the incoming page could never paint over: the selected speed and
  altitude along the top, a strip along the bottom. Exactly the photographs.
- The PFD's viewport is now confined to the page's own area. Nothing is drawn
  where the FMC page cannot cover it, so no clear is needed and none of the
  clearing this session attempted was ever going to work.
- Offset 10 -> 37, compression 0.10 -> 0.20. Not the 0.1805 the arithmetic
  gives: fills round outward and that still spilled four rows past the page.
  Measured through the offline emulator across level, banked and descending
  frames -- all three paint rows 46..440, inside the page's 37..443.
- The PFD loses 33 rows of height. That is the cost, and it buys a border that
  cannot come back rather than one being chased with clears.
- `--test-pfp-pfd` fails if the viewport ever starts above the page or reaches
  below it. Proved by restoring the old values: it names row 10 against the
  page at 37.
- This is also why the PFP 3N never had the problem: its FMC page covers
  everything its PFD draws.

Needs a look in the cockpit: whether the border is finally gone, and whether
the slightly shorter PFD reads acceptably.

## 2026-08-27 - Traced both panels: the FMC paths match, the PFD paths do not

- Added `--trace-pfp-handoff`, a pass-through wrapper on both panels' HID
  handles that reports what each path sends at entry and at close. Verified
  byte-identical pass-through and off by default.
- The FMC paths are the same, measured rather than read:
    BB35 entry: 597 F0 | ch1=255 | 42 F0 | 16 F2 | ch0=128 | ch1=220 | 1 F2
    BB36 entry: 541 F0 | ch1=255 | 42 F0 | 16 F2 | ch0=128 | ch1=220 | 1 F2
  Same phases in the same order; the 597 against 541 is only BB35's font
  rebuild sending more packets. Both closings are F2 page traffic followed by
  a single F0 packet. So the FMC side needs nothing further.
- The PFD paths are not the same, and the trace showed it by capturing
  nothing at all: BB35 reported 3396 reports while leaving its PFD, and BB36
  reported none, despite its PFD visibly running at 12.6 fps.
- The cause is structural. BB35's PFD draws through a `_PfpNativeCanvas`
  directly. BB36's draws through `_McduPfdFittedCanvas`, a vertical viewport
  wrapping a native canvas, so the handle the writes actually go through sits
  one level further in. The trace now walks the canvas chain to find it.
- That viewport is also mis-set against this panel. It maps 0..480 onto rows
  10..449, while the test card measured the visible glass as rows 10..469 --
  so twenty rows of visible screen are never drawn on. A compression of
  0.0512 rather than 0.10 would use the full height.

Needs one more run with the trace to see what the MCDU's PFD path actually
sends, now that its writes are visible.

## 2026-08-27 - Triple-PERIOD hard resets the MCDU screen

- Every triple-PERIOD now hard resets the panel before the incoming path is
  created: blackout, both plane configurations rewritten, character plane
  blanked, graphics plane cleared, brightness restored, handle closed. The
  next path then opens a completely fresh session.
- It runs with no path holding the panel, and settles on both sides so
  Windows has released the handle before another session claims it.
- Brightness is restored even when a step fails, so a reset that does not
  complete cannot leave the panel dark. That failure is what made an earlier
  attempt at this black the screen.
- Measured live against the panel: 0.18 s per reset.

## 2026-08-27 - The MCDU now comes up on the PFD, like the PFP 3N

- The MCDU came up on its FMC menu while the PFP beside it came up on the
  PFD. The PFP 3N router hardcodes `self.mode = 'pfd'`; the MCDU router took a
  `start_mode` that defaulted to `"fmc"`, and start_muslimsim.cmd passes no
  override. Both defaults are now `pfd`.
- Comparing the paths step for step never showed this, because the difference
  was never in the paths -- they were already identical. It was one line in
  the router, and it took being told to look there.
- Compared the two routers behaviour by behaviour rather than one difference
  at a time: retry on start failure, toggle wait, toggle clear, full teardown,
  handoff settle, mode flip, handoff print, active-path stop and supervisor
  join all matched already. The starting mode was the only difference in the
  whole class.
- `--test-pfp-pfd` now reads the router's own signature and fails if its
  default view ever stops matching the PFP's.
- The option itself is kept, unlike the PFP which has none, because starting
  the MCDU on its FMC page is a reasonable thing to want. Only the default
  changed.

Also recorded, from reading the PFP 3N's font code: the .xpwwf resource is
authored at 23x29, which is the MCDU's own pitch. The PFP rebuilds it to
23x32 so its six line-select rows meet its physical LSK keys. So on geometry
the MCDU is the native case and the PFP is the adaptation -- copying the
PFP's rebuild would misalign the MCDU's rows against its own keys. Its
measured screen characteristics are now named constants in its module, with a
self-test guard against exactly that change.

## 2026-08-27 - BB36 runs the PFP 3N lifecycle, and nothing else

- Removed everything this session added to the BB36 paths, on the grounds that
  the PFP 3N works and the MCDU should do what it does. Gone: the PFD path's
  clear on stop, the FMC path's clear on entry, the handoff restart session,
  the injected native canvas and the banded clear helper. BB35 has none of
  them and never needed them.
- Each of those was added to remove the stale border, and each was reasoned
  from evidence that turned out not to mean what it appeared to: the wear test
  showed the panel accepts every write whether or not it acts on it, so no
  clear could ever be confirmed from this side. The additions could not be
  shown to help, and the panel degraded across handoffs while they were in.
- Verified step for step against BB35 rather than asserted: PFD start, PFD
  stop, FMC start and FMC stop are now all IDENTICAL in sequence, and BB36
  carries zero of the extras.
- The stale border is expected to return. It is the known cost of the MCDU's
  page covering less glass than the PFP's, and it is a better state than a
  panel that stops drawing after two handoffs.
- The self-test guards for the deleted feature were removed with it; the
  standby-page and viewport guards remain.

Needs a look in the cockpit: whether the handoff is stable again over several
triggers, which is what this trades the border for.

## 2026-08-27 - The panel fails silently, and that invalidates the evidence

- Repeated the handoff's HID work eight times against the real MCDU, counting
  every write and timing every phase: 589 writes per cycle, zero short, zero
  failed, font upload 0.582-0.584 s and clear 0.005 s on every single cycle.
  Nothing at the USB level changes as the panel degrades.
- So the panel keeps acknowledging writes it no longer acts on. Every
  "success" this bridge printed about a clear was evidence of nothing, and so
  was all the packet-level verification -- it only ever proved the packets
  were well formed, which was never in question. Added
  `tools/probe_mcdu_handoff_wear.py`, which is what established this.
- Combined with the photographs, the shape of the fault is now clear and it is
  not a clearing problem: the first handoff after startup is clean, the second
  leaves a frame of the previous page, and by the third the PFD will not draw
  at all. A power cycle restores it completely. Something in the handoff is
  progressively disabling the display.
- The startup refresh therefore looks reliable only because it runs on a panel
  that has just been connected, not because of anything it does differently.
- Withdrew the font-precondition conclusion entirely. The test that produced
  it ran immediately after a power cycle, so the power cycle explains it just
  as well; it was a confound, and building on it corrupted the glyph table.
- The MCDU is addressable to Windows as
  `USB\VID_4098&PID_BB36®5D1217760606282261023`, so a software power
  cycle through Disable-PnpDevice/Enable-PnpDevice is possible in principle,
  but the bridge does not run elevated and cannot do it as things stand.

## 2026-08-27 - Reverted: uploading a second font corrupts the glyph table

- Reverted the whole font-precondition change. It corrupted the FMC page's
  text and left the PFD black -- both far worse than the border it was meant
  to remove. Both files are back to their 2026-08-27 12:07:05 state and the
  broken pair is kept beside them as `*_BROKEN_font_upload_*` for reference.
- What it got wrong: the panel's font is not a value that a later upload
  replaces. Uploading the native font and then re-uploading the FMC font left
  the glyph table mixed, so the page rendered with characters missing and
  wrong. Re-uploading afterwards does not undo it.
- This was a known risk in this project -- handing an FMC path the PFD font
  has corrupted its text before -- and it was flagged before the change went
  in. It should have been tested on one path before being applied to three.
- What survives the revert, and is still true: the panel answered that fills
  do reach the whole visible glass (rows 10-469; rows 0-9 and 470-479 are
  outside the viewable area), and that a session which has uploaded a native
  font can clear it while one that has not cannot. The conclusion was sound;
  acting on it by uploading a font into a session that already had one was
  not.
- Back to the known behaviour: the handoff restart, the PFD path's clear and
  the FMC path's entry clear all run, and the border remnants remain. That is
  the state to work from, with the panels otherwise correct.

## 2026-08-27 - Font before config, or the panel draws a bare grid

- Fixed a regression from the font-precondition change: adding the native
  font upload had pushed it after the config packets, so the grid was being
  configured while no font was loaded. The PFP showed exactly that -- a bare
  grid where its page should be.
- BB35's own FMC path has always done font, settle, then background and grid.
  Both the shutdown restore and the startup refresh now follow that order
  again. Verified by capturing what each routine actually writes:
  - restore: blackout, native font, F0 clear, WinCtrl font, config, F2 blank,
    brightness
  - refresh: blackout, native font, config, F2 blank, F0 clear, brightness
- The graphics clear stays with the native font, which is what makes it
  reach the glass at all, and a fill needs no grid configured -- so in the
  restore it can happen before any character-plane setup and leave the
  panel's final font and grid exactly as WinCtrl expects them.
- The restore now takes 2.98 s for both panels, up from well under a second:
  it uploads two fonts to each. That is shutdown, so the time costs nothing.

Needs a look in the cockpit: whether the PFP now comes back to a proper
WinCtrl page rather than a bare grid, and whether the MCDU does too.

## 2026-08-27 - The graphics plane needs a font loaded before it draws

- The panel answered it. A test card painted in labelled bands showed green at
  rows 10-36, blue through the middle and yellow at rows 443-469 -- the whole
  visible glass, including both bands where the remnants appear. Fills do
  reach those rows, so the coordinate model was never the problem.
- The difference between that working and every failure is one step: the
  session must have uploaded a native font before the graphics plane accepts
  drawing. An identical session without one painted nothing at all, not even
  a flicker; the same fills after an upload covered the screen.
- That is why every clear so far "succeeded" and did nothing. The startup
  refresh, the handoff restart and the FMC path's clear all skip the font
  upload, so their fills were accepted over USB and drew nothing. The first
  clean load was a freshly powered panel, not a working clear.
- Also learned: rows 0-9 and 470-479 are outside the viewable area. The MCDU
  shows roughly rows 10-469 of the 640x480 framebuffer, which is why the red
  and magenta edge bands never appeared.
- The handoff restart, the FMC path's entry clear and the shutdown restore now
  each load the native font before clearing. The FMC path and the restore then
  put their own font back, so the page still renders in its own glyphs --
  handing an FMC path the PFD font has corrupted its text before in this
  project.
- Cost: a font upload is 582 packets, about 0.58 s. The handoff restart went
  from roughly 0.1 s to 0.76 s measured, which is a visible blink, and the
  trigger was meant to visibly restart the screen.

Needs a look in the cockpit: whether PERIOD x3 both ways now leaves nothing
behind.

## 2026-08-27 - Correction: the cell-size difference is a font resize, not hardware

- Withdrew the 512x480 framebuffer hypothesis and the claim that the two
  panels differ in hardware cell size. Both are 640x480, and the config
  packets carry no screen-size or cell-size field: they differ only in device
  address and grid origin (bytes 4, 21, 23, 29).
- The cell size comes from the font, and both FMC paths load the *same*
  resource. BB35 resizes it -- "Critical PFP3N calibration: 23x29 authored
  font -> 23x32 cells" -- and BB36 loads it as authored. That, not the
  hardware, is why the two pages cover different amounts of glass.
- So the authored cell is 23x29, not the 17x29 quoted in the previous two
  entries, and the MCDU's page is 552x406 at (52, 37), not 408x406. Its
  exposed margins are top 37, bottom 37, left 52, right 36 -- wide top and
  bottom bands with thin sides, which is exactly where the remnants appear in
  the photographs. The geometry explains where they show; it still does not
  explain why three clears do not remove them.
- BB35's own margins are not zero either (top 24, bottom 8), so covering the
  glass is not the whole of why it stays clean.

## 2026-08-27 - Three clears run and the remnants survive all of them

- A run log now proves all three clears execute on a PFD -> FMC handoff: the
  PFD session's own, a full soft reboot reporting "F2 blank + F0 clear + HID
  reopen state reset", and the FMC session's on entry. The frame of the
  previous page survives all three.
- That rules out the explanation every fix so far has been built on. The
  remnants are not being addressed by a graphics-plane fill or a
  character-plane blank, so the model of this panel is wrong somewhere and a
  fourth clear would be the same mistake a fourth time. Stopped adding them.
- Standing hypothesis, from arithmetic rather than assumption: the MCDU's
  framebuffer may not be 640x480. Its character grid is 408x406 at (52, 37),
  which on a 512x480 screen gives margins of 52 left, 52 right, 37 top and 37
  bottom -- symmetric on both axes. The PFP's grid on its known 640x480 screen
  is not symmetric on either (50/38 and 30/2), so this is not a house style;
  it is what a centred grid on a 512-wide screen looks like. A 640-wide fill
  on a 512-wide framebuffer would not cover what the PFD drew.
- Rewrote `tools/probe_mcdu_graphics_plane.py` to settle it. It paints in
  colours that cannot be mistaken for flight information and waits for an
  answer at each step: the whole plane in one fill, the whole plane in bands,
  the four margins alone, and an oversized 1024x768 fill. Between them they
  say whether the graphics plane reaches those edges at all, and whether the
  framebuffer is wider than the fills being sent.

Needs a run in the cockpit: `python tools/probe_mcdu_graphics_plane.py` with
the bridge stopped. Its answers decide where the remnants actually live.

## 2026-08-27 - The triple-PERIOD trigger restarts the display

- The trigger is a display restart, not a page change. Every handoff now
  rebuilds both planes from nothing in a session of their own -- the same
  sequence the bridge runs at startup, which is the only one proven to clear
  this panel.
- Found why the earlier attempt at exactly this took the MCDU black, and it
  was a real defect in the restart routine, not in the idea. It blacks the
  panel out as its first act, and every failure path jumped straight to
  closing the handle without ever restoring brightness. At startup the device
  is free and it succeeds; at a handoff the device was just released by the
  outgoing session, so an open or a write can fail -- and the blackout stayed.
- Brightness is now restored on the failure path too. Proved it both ways
  against a device that accepts the blackout and then fails every other
  write: the version that shipped leaves brightness at 0 (dark), this one
  restores 220 (lit).
- `--test-pfp-pfd` now fails if a failed restart leaves the panel dark.
- The handoff also settles on both sides of the restart rather than opening a
  new session the instant the old one closes. Opening too early is what made
  those writes fail in the first place.

Needs a look in the cockpit: whether PERIOD x3 now visibly restarts the panel
and leaves no trace of the previous path.

## 2026-08-27 - The clear has to run where F0 is known to work

- A run log settled what three rounds of reasoning could not. Between
  `BB36 HANDOFF: PFD -> FMC` and `BB36 PATH -> FMC` no warning appears, and
  the FMC path prints one if its graphics clear throws or cannot run. So that
  clear executed, inside the FMC session, without error -- and the border
  survived it. An F0 clear issued from the FMC session does not reach the
  glass.
- So the clear now runs in the PFD path's own `stop()`, the one session that
  can prove it writes the graphics plane: it has been drawing the PFD on it
  all along. It settles 0.06 s before the handle closes, the same way the FMC
  path settles after blanking its page.
- This is a deliberate deviation from BB35, which closes its PFD path without
  clearing. BB35 does not need it: its 23x32 cells give an FMC page covering
  x 50..602, y 30..478, which hides whatever is underneath. The MCDU's 17x29
  cells cover only x 52..460, y 37..443.
- An earlier attempt put a clear in the same place and it did not work, for a
  different reason: it went through the PFD's vertical viewport as bands, and
  reached only rows 10..448. With the `native_canvas` unwrap it now covers
  0..479, verified against a mock device -- 5 reports, every row, ending in an
  LCD refresh.
- Both clears now name themselves in the log ("graphics plane cleared before
  handoff" / "on entry"), so the next run shows which ran instead of leaving
  it to be inferred from silence.

Needs a look in the cockpit: whether PERIOD x3 back to the menu is finally
clean, and which of the two clear lines the log prints.

## 2026-08-27 - BB36 given the same lifecycle as BB35

- Reverted the handoff blank added earlier the same day. It opened its own HID
  session between path teardown and startup and took the MCDU black; a second
  session in that window is not something the panel tolerates. The bridge no
  longer does it.
- Found why BB35 never had this problem, and it is not a missing step. Its
  character cells are 23x32, so its FMC page covers x 50..602, y 30..478 of
  the glass and hides whatever the PFD left underneath. The MCDU's cells are
  17x29, so its page covers only x 52..460, y 37..443 and leaves a frame of
  bare graphics plane on all four sides. BB35 never needed to clear that
  plane; the MCDU cannot avoid it.
- BB36's path lifecycle now matches BB35 step for step, and the alignment is
  checked rather than asserted:
  - PFD start: open, repaint the complete surface, start threads. It never
    sends F2 -- the outgoing FMC path blanks its own character plane.
  - PFD stop: close. A path clears what it owns when it starts; it does not
    tidy up for the path that follows.
  - FMC start: open, font, settle, background, grid, blank page, brightness,
    threads -- plus the graphics clear the MCDU's geometry requires, placed
    with the other background work, before any text is written.
  - FMC stop: blank the page, send the background packet, close. BB36 was
    missing that background packet, which BB35 has always sent.
- Both routers are now armed first and released together through a barrier
  rather than started sixty lines apart, so the two panels come up beside
  each other instead of in build order. Measured spread between the two
  starts: 0.078 ms. Each panel's first page still takes as long as its own
  font upload, which differs between them.

Needs a look in the cockpit: whether PERIOD x3 now resets cleanly in both
directions, and whether both panels come up together.

## 2026-08-27 - The PFD/FMC handoff, where the border actually came from

- Narrowed the stale border to the handoff itself: the MCDU comes up clean,
  the PFD is clean, and the border appears only on PERIOD x3 back to the FMC
  menu. So the fault is in the transition, not in either page.
- Reproduced it offline through the emulator rather than guessing. A PFD frame
  paints physical rows 19..451; the clear the handoff performed reached only
  rows 10..448, leaving 449, 450 and 451 -- the strip along the bottom of the
  photograph.
- Cause: the handoff clear issues eight bands, and it was issuing them through
  the PFD's vertical viewport. No single band is a full-screen fill, so none
  was recognised as a clear, and every one was fitted into the viewport
  individually. The two fixes were cancelling each other out.
- The viewport now exposes the unfitted canvas as `native_canvas`, and the
  clear unwraps it, so its bands reach the glass. Verified in the emulator:
  the same sequence now leaves nothing painted.
- `--test-pfp-pfd` fails if a clear issued through the viewport leaves any
  physical row untouched. Proved the guard bites by removing the unwrap: it
  named rows 0..9 and 449..479.
- Also added a blank between path handoffs from a fresh HID session, the same
  sequence that clears the panel at startup. An in-session clear depends on
  the plane still accepting drawing from a handle that is about to close;
  owning a session does not. It covers both directions, and it explains why
  the first load looked clean while a handoff did not -- the startup refresh
  was doing that work, not the FMC path's own clear.

Needs a look in the cockpit: whether PERIOD x3 in both directions now leaves
a clean panel.

## 2026-08-27 - Both panels are handed back to WinCtrl on exit

- Closing the bridge now returns both displays to their original WinCtrl
  state instead of leaving MuslimSim's last page on the glass. MuslimSim
  uploads its own glyph artwork and draws on both display planes, so simply
  exiting handed the WinCtrl software a panel carrying MuslimSim's font in
  its slot and a MuslimSim page on the screen.
- The restore puts back the manufacturer's font
  (`winctrl-pfp-b737-clean-font6.xpwwf`), the original plane configuration, a
  blank character page, a cleared graphics plane and normal brightness. It
  runs last in shutdown, after the routers and the PFP worker have released
  their HID handles, because it opens its own sessions. Verified against both
  panels: `{'bb35_restored': 1, 'bb36_restored': 1}`.
- Not yet restored: the factory WinCtrl logo. MuslimSim replaces it by
  sending native function 0x104 with selector byte 0x0E, but the value the
  panel starts with is recorded nowhere in this project, and guessing at
  firmware is how displays end up in modes nobody can explain. Added
  `tools/probe_winctrl_logo.py`, which steps the selector through its
  candidates so the panel itself can answer; setting
  `WINCTRL_FACTORY_BACKGROUND` then completes the restore.
- The MCDU no longer just goes black when it has nothing to show. It sat dark
  beside a PFP that explained itself, and a dark panel is indistinguishable
  from a broken one. The FMC path now draws a MuslimSim standby page in its
  own 24x14 character grid -- the proven page path, not graphics.
- It tells the two cases apart honestly: an FMC state that never arrived is a
  stopped simulator, while a populated but blank page is a CDU with nothing
  to show. A real CDU page is never replaced.
- `--test-pfp-pfd` covers the MCDU standby page's text, checks it survives the
  real packet encoder, and fails if a populated CDU page could ever be
  mistaken for a blank one.

Needs a look in the cockpit: whether both panels come back the way WinCtrl
expects after closing the script, and which selector value the logo probe
shows.

## 2026-08-27 - The MCDU starts in FMC mode, and nothing cleared its graphics plane

- Found the real cause of the stale frame around the MCDU's picture, from the
  observation that the two panels start differently: the PFP comes up showing
  the PFD, the MCDU comes up showing the FMC menu (`--mcdu-start-mode`
  defaults to `fmc`).
- The FMC path writes only the character plane. That plane covers just the
  middle of the glass -- 24x14 cells from (52, 37), so x 52..460 and y
  37..443 of 640x480 -- so anything a previous PFD session left on the
  graphics plane outside it stays visible as a frame around the page. The
  PFP never showed this because its PFD paints the whole screen.
- Neither BB36 path was clearing the graphics plane: the FMC path never
  touched it, and the PFD path closed its session without blanking it.
- Both now hand the glass over blank. The PFD path clears in `stop()`, with
  its worker stopped but the session still open -- the one moment the clear
  is certain to land, since that session has been drawing successfully all
  along. The FMC path clears on open, because its page owns the whole screen
  and anything underneath is stale by definition.
- The router does not carry a second copy of the native graphics encoding;
  `final.py` installs its canvas class into `NATIVE_CANVAS_FACTORY`, the same
  reasoning behind the router importing the FMC packet builders rather than
  reimplementing them. If it is ever missing, the FMC path says so rather
  than silently skipping the clear.
- `--test-pfp-pfd` now fails if the router loses that canvas, if the clear
  stops covering all 480 rows at full width, or if it never refreshes.
- Added `tools/probe_mcdu_graphics_plane.py`: fills the plane red without a
  native font upload and green after one, so the panel itself answers whether
  the font upload is a precondition for drawing. Diagnostic only -- it writes
  to the display, never to the simulator, and leaves the glass dark navy.

Needs a look in the cockpit: whether the border is finally clean, and which
colours the probe shows.

## 2026-08-27 - No page keeps flying after the aeroplane stops

- Every page now stands by when the information stops being real. Only the PFD
  noticed a stopped simulator before; ND, ENG PRI and MFD kept redrawing
  whatever they last held, so closing X-Plane left a plausible-looking
  navigation display on the glass indefinitely.
- Two triggers, both debounced over two samples so a dropped HTTP read or a
  switch caught mid-throw cannot flash the card:
  - the simulator going away -> "SIM STOPPED" / "START X-PLANE";
  - the aeroplane's own displays losing power -> "AIRCRAFT UNPOWERED" /
    "BATTERY SWITCH ON".
- Display power comes from `laminar/B738/electric/dc_stdbus_status`, the bus
  that feeds the captain's instruments. Confirmed by probing the running
  aircraft: X-Plane's generic electrical datarefs do not follow Zibo's
  switches -- with the battery off they still report 23.5 V on three buses,
  while every Zibo bus reads 0 and `hot_batbus_status` reads 1. That last
  value is what proves the 1 = powered convention rather than assuming it.
- The power check fails towards showing the flight display: a missing or
  unreadable bus value counts as powered. A wrong "off" would blank a working
  PFD in flight; a wrong "on" only leaves the previous behaviour in place.
  `--no-power-standby` switches the trigger off entirely.
- The card is drawn once and held, not repainted per frame: 13 reports on the
  PFP, 16 on the MCDU, then nothing until the state changes.
- Recovering from standby invalidates the renderer's dirty history and redraws
  the page's background. The card replaced the whole screen, so every
  dirty-region record described pixels that were no longer there.
- Entering a page and recovering from standby now share one
  `_cockpit_draw_page_static`, so they cannot drift apart.
- The standby card names the panel it is on -- WINCTRL PFP or WINCTRL MCDU.
- Fixed the centring on the standby and boot pages: both advanced 23 pixels
  per character while native font 6 draws 17-pixel cells, so every line sat
  left of centre. Only visible once the card carried longer lines.
- Telemetry budget raised 38 -> 39 for the bus, which rides the slow sample
  cycle; the self-test now fails if it is ever moved to the fast group.
- `--test-pfp-pfd` covers all four pages, both reasons, both panels, and all
  four power-gate cases. Differential checker still passes, including
  live-offline-live recovery. PFD budget unchanged: 265 full, 183 refine, 1
  steady.
- Previews: `PNG/nd_standby_sim_stopped.png`, `PNG/pfd_standby_unpowered.png`.

Needs a look in the cockpit: whether the bus reads 1 with the battery on. The
0 state was sampled directly from the cold aircraft; the powered state is
inferred from `hot_batbus_status` following the same convention. If a page
ever stands by while you are flying, `--no-power-standby` is the escape hatch.

## 2026-08-27 - The stale frame around the MCDU's picture

- Fixed the border of old PFD pixels that survived every restart on the MCDU.
  The character plane cleared (the previous fix), which is why only the middle
  of the glass went black; the frame around it is outside the 24x14 grid, so
  only a graphics-plane clear can reach it.
- Root cause: the BB36 viewport compresses Y, and it mapped a full-screen clear
  like any other fill. Mapped, `fill(0, 0, 640, 480)` covers physical rows
  10..448 and no further. Every renderer draw is mapped into that same
  viewport, so nothing ever repainted rows 0..9 or 449..479 -- whatever an
  older build left in those margins outlived every clear for as long as the
  panel stayed powered.
- A full-screen fill now means "scrub the glass" and is passed to the native
  plane unmapped, at full physical extent. Ordinary fills are still fitted.
- Whole-plane clears are now issued as eight horizontal bands rather than one
  640x480 rectangle, in the startup refresh and the MCDU's own open path. That
  single giant rectangle is the one shape nothing else in the protocol
  exercises; eight fills cost about 200 bytes, well under a millisecond, so the
  certain form is cheaper than proving the elegant one.
- `--test-pfp-pfd` now fails if a full-screen clear through the viewport leaves
  any physical row untouched, or if ordinary fills stop being fitted. Verified
  both ways: the guard names rows 0..9 and 449..479 when the fix is removed.
- The PFD's own budget is unchanged: 265 full, 183 refine, 1 steady.

Needs a look in the cockpit: whether the border around the MCDU's picture is
now clean after a restart.

## 2026-08-27 - Why only the MCDU did not refresh at startup

- The startup soft reboot cleared the PFP but appeared to do nothing on the
  MCDU, while reporting success on both.
- Ruled out first, by measurement rather than assumption: the MCDU enumerates
  normally (VID 0x4098 / PID 0xBB36, one interface); the call site does ask
  for it; the F2 blank packets are byte-for-byte identical between the two
  devices; both character grids are 24 x 14; and the routine's brightness and
  graphics-clear commands already carried the right device identifier.
- The cause is the character plane's configuration, which the routine never
  sent. That configuration is per display and differs in more than the
  address: the PFP and the MCDU use different text-grid origins, bytes 21 and
  23 of the grid packet - 0x32/0x18 against 0x34/0x25 - as well as different
  addresses at bytes 4 and 29. Without it the MCDU's F2 blank landed outside
  the visible grid and its old FMC page stayed on the glass, which is exactly
  what a display that "does not refresh" looks like.
- Each display's spec now carries its own proven background and grid packets,
  taken from that device's own module rather than patched copies of the PFP's,
  and the refresh sends them before blanking the character plane. The MCDU
  keeps graphics-only clearing if its packets cannot be imported, with a
  warning rather than silence.
- Tests run: the refresh executed against the real MCDU and reported 1 found,
  1 refreshed; PFD self-test; `launch.py --check`.
- Needs a look in the cockpit: whether the MCDU's page now actually clears.
  The mechanism explains the symptom, but only the panel can confirm it.

## 2026-08-27 - Display wiring rebuilt after an older final.py was restored

- An older copy of `bridge/final.py` was pasted in, which silently removed
  every piece of display wiring while all the renderers stayed in place. The
  symptom is quiet rather than loud: the ND falls back to its placeholder page
  and the speed tape loses its bands, because a renderer with no values simply
  draws nothing.
- Rebuilt on top of the restored file rather than over it, so the newer work
  in that copy - the startup display refresh, the BB36 path router and the
  MCDU vertical fitting - is untouched. Nine pieces were restored: the
  speed-awareness datarefs, the trend on the fast sample, change detection for
  all thirteen new values, the telemetry and frame budgets, the ND renderer
  import, the ND datarefs, the ND live snapshot, the ND page block replacing
  the placeholder, the ND states marked as states rather than motion, the
  per-display bezel shift, and the separate FMC font.
- The self-test now refuses to pass if the ND renderer is not wired, if the
  live ND snapshot does not supply every value the renderer declares, or if
  the FMC and PFD paths share one font. Losing this wiring again will fail
  `--test-pfp-pfd` loudly instead of showing a placeholder quietly.
- `Backup/final_KNOWN_GOOD_display_wiring_20260827_033409.py` is a complete
  working copy. If final.py is ever replaced again, copying that file back
  over `bridge/final.py` restores everything in one step.
- Verified: PFD self-test, both layout contracts, differential checker,
  `launch.py --check`, all 38 PFD datarefs and all 22 ND values resolved
  against the running simulator, and the other session's work confirmed still
  present.
- Noted, not changed: `_cockpit_draw_nd` is now dead code - the old full-page
  placeholder drawer, defined but called from nowhere.

## 2026-08-27 - FMC and PFD paths load separate fonts

- **A regression of mine, found while looking at the MCDU.** The navigation
  display's static shapes are stored in spare glyph codes of the PFD font.
  Both path routers were handing that same font to their FMC page, and an FMC
  page prints those codes as text: Zibo's CDU output contains lower case, and
  `_normalize_24` turns a degree sign into a lower-case "o". So compass tiles
  appeared in the middle of FMC lines. That is what the two paths were
  conflicting over - they each opened their own HID handle, but shared one
  font resource.
- The FMC/PFP text pages now load `PFP_FMC_FONT_FILENAME`, the factory
  resource, which keeps its own glyphs and its own 24-column grid geometry -
  what those pages were authored for. The PFD path keeps the cockpit font with
  the display shapes. Separate handle, separate font, separate state, on both
  BB35 and BB36.
- The PFD self-test now refuses to run if the two paths are ever pointed at
  one font, naming the reason.
- Verified rather than assumed: all 28 tile glyph codes were compared between
  the two font resources and differ in every one, so the FMC font keeps its
  real letters, including the lower-case "o" a degree sign becomes.
- Tests run: PFD self-test with the new font guard, both layout contracts,
  `launch.py --check`, and a direct glyph-by-glyph comparison of the two fonts.
- Not verified here: how the FMC page looks on the panel with the factory
  font's wider cells. Its grid is what that font was authored for, but it
  wants a look in the cockpit.

## 2026-08-27 - The ND on the MCDU 32

- Checked before building: the BB36 MCDU runs the same shared graphical
  worker as the BB35 PFP, with the same page order, so the new navigation
  display, its four modes, the EFIS switches and the route already reach it.
  Nothing needed porting.
- What does not transfer is the bezel. The horizontal shift is now a property
  of each display rather than of the renderer: every canvas can carry
  `_muslimsim_nd_shift_x`, and the two units are set separately as
  `PFP_ND_SHIFT_X` and `MCDU_ND_SHIFT_X`. Both start at 24; the PFP's was
  measured against the panel, the MCDU's is a starting value until it is seen
  in the cockpit.
- The MCDU's existing vertical fitting is inherited automatically: the BB36
  canvas compresses Y below the FMA region to keep content off its bottom
  bezel, so the ND is fitted the same way the PFD already is. The compass arc
  is slightly elliptical there as a result, which is the trade that fitting
  already makes.
- **A real fault the new guard caught.** Shifting the frame moved the
  full-screen background clear with it, leaving a strip of the previous page
  standing down the left edge. A fill spanning the whole width is now
  recognised as background and stays put; content shifts and clips. The
  layout contract additionally rejects any shift that would drop an item off
  the display - it accepts up to 72 px and refuses 96.
- Verified the MCDU path end to end offline, through its own fitted canvas
  rather than the renderer alone: a complete frame is 312 reports and an
  unchanged one is 1.
- Tests run: PFD self-test, both layout contracts, differential checker,
  `launch.py --check`, and an MCDU-fitted ND frame rendered from the live
  aircraft's own position and route.

## 2026-08-27 - ND shifted clear of the bezel

- The ND sat left of centre on the panel: the page was centred on the frame's
  own middle, but the PFP bezel masks a strip at the physical left edge, so
  the middle the pilot sees is further right.
- The whole page - compass, aeroplane symbol, route, and all four corner
  readouts - now shifts together by a single constant, `ND_SHIFT_X`, set to
  24 pixels. One number to raise if it still reads left, or lower if the
  right-hand readouts crowd the bezel.
- Checked that the shift cannot push anything off the other edge: with it
  applied the compass arc reaches x 570 and the rightmost readout ends at
  579, both inside the display, and the layout contract asserts it.
- Tests run: ND layout contract with the shift applied, three shifted frames
  rendered from the live aircraft, `launch.py --check`.

## 2026-08-27 - The EFIS mode knob did nothing: the live ND path

- **The fault.** The ND's mode, range, switches and radios were being sampled
  and then thrown away. The live display loop reads through the smoothing
  telemetry hub, and that path's ND snapshot asked for three values -
  ground speed, latitude, longitude. Everything added for the modes was
  resolved, subscribed and updated, then dropped before the renderer saw it,
  so turning the EFIS mode knob changed nothing on the screen.
- The earlier work was verified against `_cockpit_secondary_snapshot`, which
  is not the function the live loop calls. The snapshot now supplies every ND
  value, and the route with it.
- **A second fault found in the same place.** The hub's alpha-beta motion
  filter was being applied to states as well as motion. A mode selector read
  1.58 between VOR and MAP, and a released push button read -0.45. Modes,
  ranges, buttons, the tuned navaid, wind and true airspeed are now taken as
  sampled; only position, track and ground speed are smoothed, which is what
  the filter is for.
- **Guarded so it cannot recur.** The ND renderer declares `ND_VALUE_KEYS`,
  and the PFD self-test now fails if the live snapshot does not supply every
  one of them. A value that is sampled but never handed over draws nothing and
  looks exactly like a broken switch, which is precisely how this presented.
- Verified end to end against the running simulator this time: the hub was
  started, allowed to connect, and its ND snapshot read back - map_mode 1.0
  exactly, ctr 0.0, range 80, and 29 route points.
- Tests run: PFD self-test with the new guard, both layout contracts,
  differential checker, `launch.py --check`.

## 2026-08-27 - The ND draws the FMC route

- MAP and PLAN now draw the active route: the magenta line the aeroplane is
  following, with a fix symbol at each waypoint, projected around the
  aeroplane heading up, and north up in PLAN.
- The map scale follows the EFIS range switch: the compass radius stands for
  the selected range, as it does on the aeroplane, so the route redraws to
  scale from 5 NM to 640 NM.
- Read from Zibo's own `fms/legs_lat` and `fms/legs_lon`. Those arrays hold
  256 slots and are not self-describing, so the route was verified rather than
  assumed: every leg's geographic length was checked against the FMC's own
  `legs_dist`, and all agreed to within a tenth of a mile. That is what
  established the array really is one continuous path, including a 209 NM leg
  that looked wrong until it was checked.
- Route legs are clipped to the display and then rasterised as runs along
  their major axis, rather than stepped in fixed blocks. A leg can be
  hundreds of miles long while the display shows ten; stepping the whole leg
  spent about 870 commands drawing off-screen. A complete ND frame with the
  route is now 507 reports at 10 NM, and an unchanged frame is still one.
- The ND's values are now sampled at the rate each actually changes: position
  and track every frame, the switches and radios once a second, and the route
  every five seconds, cached between reads.
- Tests run: the ND layout contract, extended with routes that run off the
  display and with the aeroplane in centred and plan modes; line clipping
  asserted directly; frames rendered from the live aircraft's own route at 10,
  40 and 160 NM; PFD self-test, PFD contract, differential checker and
  `launch.py --check` all still pass.
- Known limits: the whole route is drawn rather than only the leg ahead,
  because the active-leg index is not confirmed; waypoint names are not drawn,
  as the idents are string arrays; and one dataref read over X-Plane's Web API
  costs about 54 ms, which - not the drawing - is what limits how often the ND
  page can update.

## 2026-08-27 - ND modes: APP, VOR, MAP, PLAN, and the EFIS switches

- The ND now draws what the EFIS mode selector asks for instead of one layout
  regardless: APP and VOR add the tuned course line, its deviation scale and
  bar, and a navaid block giving the station, its frequency, the selected
  course and DME distance. MAP keeps the map arc. PLAN swings the display
  north up.
- The CTR switch now closes the arc into a full compass rose with the
  aeroplane at its centre, in every mode that has one, carrying the track line
  and heading bug with it.
- The EFIS overlay switches - WXR, STA, WPT, ARPT, DATA, POS, TERR, TFC - are
  read and annunciated when selected. Their map content needs navigation data
  the bridge does not read, so pressing one says so plainly rather than
  drawing invented returns on a navigation display.
- Values confirmed against the running aircraft first, as before:
  `EFIS_control/capt/push_button/*`, `nav1_course_degm`, `nav1_dme_dist_m`,
  `nav1_freq_hz`, and Zibo's captain-side `laminar/radios/pilot/nav_hdef`.
- Three faults the offline checks caught before the cockpit did: curve squares
  were bounds-checked at their first pixel rather than their far corner, so
  one at the bottom edge ran off the display; the navaid block's course and
  distance were dropped for not fitting their slots; and the overlay
  annunciation row sat on top of the tuned frequency in VOR and APP.
- The ND's periodic recovery frame is spaced to once a minute rather than
  inherited from the PFD, because a full rose is most of a complete frame.
- Costs measured per mode: complete frame 277 (MAP), 326 (APP), 458 (PLAN),
  468 (CTR); an unchanged frame is one report in every mode.
- Tests run: the ND layout contract across all four modes, centred, every
  overlay on, and all values missing; five mode frames rendered; PFD
  self-test, PFD layout contract, differential checker and `launch.py --check`
  all still pass.

## 2026-08-27 - Navigation display rebuilt as a 737-800 ND

- Replaced the placeholder ND page - a titled box with a small arc, latitude
  and longitude - with a real navigation display in
  `muslimsim/devices/nd_renderer.py`.
- Laid out as the aeroplane lays it out in expanded mode: the aeroplane symbol
  low and centred, the compass arc sweeping across the top around it, ticks
  every five degrees, numbers every thirty with N/E/S/W at the cardinals, the
  lubber line above, and the heading readout boxed at the top centre with MAG
  beside it.
- Added the numbers that belong in the corners: ground speed and true airspeed
  at the top left with the wind direction, speed and arrow beneath them, and
  the map mode and range at the top right.
- Added the dashed half-range arc with the distance it stands for at both
  ends, the dashed track line the aeroplane is actually following, and the
  magenta selected-heading bug, which parks at the edge of the arc when the
  selection is off-scale rather than disappearing.
- Every value was confirmed against the running aircraft before use:
  `ground_track_mag_pilot`, `wind_speed_kts`, `wind_heading_deg_mag`,
  `map_range_nm`, `true_airspeed`, and Zibo's own
  `EFIS_control/capt/map_mode_pos`. A value the aircraft does not publish
  only warns, and the renderer draws nothing for it.
- The ND uses the same differential output as the PFD, so its static arc is
  paid for on page entry rather than every frame: a complete frame is 269
  reports and an unchanged frame is 1.
- Tests run: the ND's own layout contract across normal, wrapped-heading,
  extreme-range and all-missing states; a frame rendered from live in-flight
  values; the page driven end to end through the bridge's own ND functions
  with live values, confirming 269 reports then 1; PFD self-test, layout
  contract and `launch.py --check` all still pass.
- Not yet drawn, because the data is not wired: the FMC route and waypoints,
  VOR/ADF pointers, airports and navaids, terrain and weather returns.

## 2026-08-27 - Frozen PFD: three faults found and fixed

- **The freeze.** The reference-bug labels passed an alignment argument to
  `_draw_text`, which does not take one. `flaps_speed` is always published, so
  the flap bug's label was drawn on every frame and raised every frame. A
  bridge started while that code was loaded would render no further frames and
  the panel would hold its last picture. Fixed by moving the alignment onto
  the slot, where it belongs. **A running bridge must be restarted to pick
  this up**, since it holds the code it imported at start.
- **Change detection did not know about the new values.**
  `_pfp_graphical_state` rounds telemetry to decide whether a redraw is worth
  sending, and the speed bands, bugs and trend were not in it. The trend arrow
  would have sat still until some unrelated value moved. All thirteen are now
  part of the state, with the trend stepped to the same half knot the renderer
  rounds its tip to.
- **A pre-existing self-test failure.** `expected_graphical_state` was written
  against coarser rounding steps and was never updated when those steps were
  refined, so `--test-pfp-pfd` had been failing before any of today's work.
  Confirmed by running the check against a backup taken before it. The
  expected state is now generated from the live rounding steps.
- Two budgets were raised deliberately rather than worked around: the
  telemetry budget from 24 to 38 values, and the complete-frame USB budget
  from 250 to 290 reports, both documented at the assertion with what the
  extra buys. The differential frames that follow a complete one are
  unaffected.
- Tests run: `--test-pfp-pfd` now passes (265 full, 183 refine, 1 steady
  reports); `launch.py --check`; layout contract; the differential checker's
  full set including periodic recovery and offline-to-live recovery; and a
  frame rendered from live in-flight values read out of the running simulator,
  which is the case that was crashing.

## 2026-08-27 - Airspeed trend vector

- Added the green airspeed trend vector: a line from the speed pointer to
  where the airspeed will be in ten seconds at the present acceleration, with
  an arrowhead showing which way it is going. It hides below four knots of
  projected change, as the aircraft does.
- Wired to the captain's own `airspeed_acceleration_kts_sec_pilot`, with
  Zibo's `laminar/B738/autopilot/acceleration` as the fallback; both were
  confirmed reading the same value on the running aircraft. It is sampled on
  the fast cycle, since an arrow that lags the speed it projects from is
  worse than no arrow.
- The tip is rounded to half a knot so live acceleration noise cannot flicker
  it, and cannot spend display traffic redrawing sub-pixel movement.
- Moved the reference-bug labels outboard of the speed tape to give the trend
  the gutter. The aircraft puts them inboard, but at this cell size both
  cannot have the same 34 pixels, and a label cut to one character stops
  being a label. A label that would fall on the live-speed readout is
  dropped; its mark still shows.
- Fixed an alignment argument passed to the wrong function in the bug labels,
  which would have failed the moment V-speeds were set. The layout contract's
  scenarios now carry bands, bugs, a flap lever and an acceleration, so that
  whole group is exercised by the offline check instead of only in flight.
- Tests run: `assert_layout_contract()` with the extended scenarios; band and
  bug frames rendered; the differential check still matches a full repaint;
  the trend dataref resolved and read on the running simulator; frame sent to
  the PFP.
- Live cockpit confirmation still needed: that the arrow tracks sensibly
  through a real acceleration and deceleration.

## 2026-08-27 - Speed awareness bands, flap and V-speed bugs

- Added the 737 speed-awareness bands to the PFD: red barber poles beyond the
  limit speeds and amber bands from each manoeuvre speed out to them.
- Added the reference bugs: V1, VR, V2, VREF, and the flap manoeuvre speed,
  which is the one that says when to move the flap lever. The flap bug is
  labelled with the lever's own detent, UP through 40.
- Rearranged the speed tape's inner strip to make room: numbers, then ticks,
  then the bands against the inboard edge, as on the aircraft.
- Wired the values to Zibo's own PFD datarefs, confirmed against the running
  aircraft rather than guessed. Added `tools/probe_speed_datarefs.py`, which
  reads X-Plane's dataref catalogue and names the exact refs to use.
- This build publishes no `max_speed_show`. A band whose flag is absent is now
  shown, and only an explicit zero hides one, so the missing flag cannot
  silently drop the VMO barber pole.
- A bug label gives way when it would collide with one already placed; the
  mark itself always shows.
- Tests run: `assert_layout_contract()`; band-flag semantics asserted
  directly; all offline scenarios rendered, including two new ones carrying
  real Zibo band values; the differential check still matches a full repaint;
  every new dataref resolved against the running simulator (13 of 14, the
  fourteenth confirmed absent); `launch.py --check`; frame sent to the PFP.
- Live cockpit confirmation still needed: that the bands track correctly
  through a flap schedule on a real approach.

## 2026-08-26 - PFD fine tuning: bank scale angles, tape ticks, selected heading

- Corrected the bank scale: its marks were a hand-placed list sitting at
  roughly 13, 27, 42 and 56 degrees while claiming to mark 10, 20, 30, 45 and
  60. They are now stepped along their true radius and read correctly.
- Moved the speed tape's tick marks inside the strip, beside the numbers, as
  the aircraft draws them, freeing the gutter for the speed bug and trend.
- Added the magenta selected-heading readout below the heading rose, which
  every reference photograph shows and the panel did not have.
- Removed the heading box from the design sheets: the aircraft reads heading
  from the arc under the lubber line and has no such box.
- Fixed altitudes below sea level, which the readout and the tape both blanked
  as invalid. The readout now puts a minus in the ten-thousands position and
  the tape labels negative values.
- Widened the minimums zone to ten cells so a five-figure setting cannot be
  silently dropped, the same fault the barometric unit had.
- Gave the barometer a gap between its value and its unit.
- Raised the arc's side numbers clear of the new heading readout, which they
  overlapped by four pixels.
- Added `zero`, `extreme` and `below-sea-level` scenarios so these edge
  conditions are checked by name instead of by hand.
- Tests run: `assert_layout_contract()` plus explicit capacity checks that the
  longest minimums and barometer labels fit their zones; all ten offline
  scenarios rendered; `launch.py --check`; display-only frame sent to the PFP.
- Live cockpit confirmation still needed: that the corrected bank scale reads
  properly against a real banked attitude.

## 2026-08-26 - PFD visual pass: design sheets, offline emulator, redrawn readouts

- Added `tools/build_pfd_design_png.py`: the agreed 737 PFD design drawn to
  PNG sheets in `PNG/` on the live renderer's own 640 x 480 contract, plus a
  protected-zone map.
- Added `tools/render_pfp_frame_png.py`: an offline emulator of the PFP's
  native command surface that runs the live renderer, saves the frame as a
  PNG, and reports the real USB cost. It opens no hardware and no simulator.
- Replaced fixed-block drawing with exact scanline rasterisation and a blended
  horizon edge, which removed the staircase from the rounded attitude corners,
  the banked horizon, the pitch rungs, the compass rose, and the V/S needle.
- Redrew the selected-speed bug, the live speed readout, the vertical-speed
  wedge, and the altitude readout from cockpit reference photographs,
  including rolling drums and the green ten-thousands hatch.
- Enlarged the cockpit font's artwork inside its unchanged 17 x 29 cell, so no
  zone, bridge path, or upload behaviour had to move.
- Added `tools/build_pfp_shape_tiles.py`: the heading rose and V/S wedge baked
  into spare glyph codes of the existing font, which cut about 56 ms from every
  frame. The renderer falls back to rectangles when the generated tile module
  is absent.
- Added the approach minimums presentation: `BARO` with a tape pointer,
  `RADIO` as text only, both turning amber at or below the setting.
- Fixed a barometer fault found while drawing the minimums: the unit zone held
  two native cells, so `HPA` was silently dropped and hectopascals showed with
  no unit. The zone is now three cells.
- Tests run: `assert_layout_contract()` after every renderer change; all seven
  offline scenarios rendered; tile output verified pixel-identical to the
  rectangle path; frame cost measured against the bridge's own canvas and timed
  on the panel at about one millisecond per HID report; `launch.py --check`;
  display-only frames sent to the real PFP with `tools/show_pfd_preview.py`.
- Live cockpit confirmation still needed: whether the larger cockpit type is
  too heavy on any label, and that the shape tiles upload correctly on a cold
  start of the panel rather than only after a re-upload in the same session.

## 2026-08-26 — living documentation created

- Added the master project history, system architecture, device reference, and
  this changelog.
- Added a permanent documentation-update rule in `AGENTS.md`.
- Linked the existing detailed PFD history to the project-wide record.
- Verified that all living documentation files and their required update-rule
  markers are present.

## 2026-08-26 — WinCtrl rudder pedals integrated

- Added the WinCtrl Orion Combat Rudder Pedals as an independent device.
- Default mapping: axis 0 left toe brake, axis 1 right toe brake, axis 2
  rudder.
- Added protected no-jump pickup for rudder and both toe brakes.
- Added `--test-pedals`, pedal inversion flags, `--no-pedals`, and launcher
  `--without-pedals`.
- Confirmed syntax, pedal, PU light, starter retract, PFD, and launcher checks.

## 2026-08-26 — MuslimSim modular layout and PFD reliability work

- Moved active work into the managed `MuslimSim` folder and `Backup/` policy.
- Added device boundary modules and one launcher for PU, WinCtrl, AGP, PFP,
  and pedals.
- Reworked PFP output into packed native HID frames and isolated it in its own
  worker.
- Refined native PFD layout, compact type, protected zones, compass geometry,
  standby presentation, and developer stamp.

## Earlier work in this project session

- Established PU Overhead, P7 annunciator, COM5, starter/ignition, and
  no-write startup safety behaviour.
- Added WinCtrl Boeing throttle/reverse mapping with 737 idle at physical 0
  and separate red-REV behaviour.
- Added AGP flight/electrical/navigation display work, gear control/indicator
  work, and smart autobrake gesture handling.

## Required format for the next entry

Add new work at the top, using this pattern:

```markdown
## YYYY-MM-DD — short change title

- What changed.
- Why it changed or what it fixes.
- Tests actually run.
- Any live-cockpit confirmation still needed.
```

## 2026-09-02 — Portable Device Platform V2: shared HID/SDL runtime locators

- Extended the Phase-1 product registry into the shared SDL identity source used by the live bridge.
- The one existing SDL owner now identifies PU, WinCtrl throttle, Orion pedals and TCA Boeing by stable product definition rather than hard-coded index assumptions. The advanced custom pedal-name override remains available and unchanged.
- Added HID locator enumeration/resolution that exposes current HID paths only as runtime locators. Unit serial numbers are not retained by the product manager.
- Added SDL locator resolution where index, instance ID and GUID are explicitly runtime-only. A replacement product can move index/GUID and retains the same MuslimSim key/profile.
- Multiple identical simultaneous SDL units are not guessed by enumeration order. A still-valid prior runtime instance can be reused; otherwise the resolver returns ambiguous.
- Background Studio discovery still does **not** open SDL joystick objects. SDL metadata inventory is opt-in diagnostics with Studio closed.
- No device packet protocol, output authority, aircraft mapping, calibration, HOWALT transport, PU serial protocol, BB35/BB36 display path or Studio UI was changed.
- Offline checks: Portable V1 PASS; Portable V2 PASS; global output authority 67/67 PASS; Hardware Lab PASS; AGP radio 119/119 PASS; PDC/PAP3/FCU-EFIS PASS; TCA Boeing 158/158 PASS; `launch.py --check` PASS.
- Live check still required after install: restart Studio and smoke-test the shared SDL owner (PU, throttle, pedals, TCA), then unplug/replug at least one SDL product and confirm the same logical device key returns.

## 2026-09-02 — Portable Device Platform V3: clean-PC bootstrap

- Added `muslimsim/hardware/windows_bootstrap.py`, a read-only runtime/PnP
  readiness layer and guarded signed-INF installer framework.
- Added `driver_family` deployment metadata to the stable product registry.
  This does not participate in device identity or change any existing owner.
- Added `driver_bundles.json`. It currently contains no unreviewed kernel
  driver package. MuslimSim will only install a future local INF after exact
  SHA-256 and Authenticode/signer validation.
- Added `MuslimSim.exe --readiness`, `--readiness-json`, and
  `--bootstrap-drivers`. Normal Studio startup is unchanged in this phase.
- PyInstaller now bundles the driver manifest and will include only reviewed
  `.inf/.cat/.sys/.dll` assets placed under `drivers/`.
- No `bridge/final.py`, Studio control/layout, device protocol, output path, or
  aircraft-power behavior was changed.
- Offline tests: Portable V1/V2, V3 bootstrap, runtime bundle, Hardware Lab,
  global output authority, AGP, PDC, PAP3, FCU/EFIS, TCA and launcher checks.
- Live Phase-2 probe identified the working Orion pedals HID interface as `4098:BEF0`; V3 now records that stable product identity while leaving the proven single SDL control owner unchanged.

## 2026-09-03 — BB36 recovery V7: progress-aware, no overlapping output owner

- BB36 health now watches accepted native F0 report progress in addition to
  frame-start/frame-complete heartbeat. A slow frame that is still sending
  accepted HID reports is no longer misclassified as a dead panel.
- The BB36 native canvas gained an optional progress callback. It is unset on
  BB35, so BB35 output bytes/timing remain unchanged.
- A verified BB36 recovery stall closes the stale output HID handle before
  waiting on the blocked output worker. Normal handoff/shutdown retains its
  previous ordering and final-shutdown blackout contract.
- The router tracks a retired BB36 output worker. A replacement output owner is
  forbidden until the retired worker is actually quiescent; this prevents
  overlapping daemon writers after a native HID stall.
- Recovery is stateful across reopened paths. One first failure gets a bounded
  same-page soft reopen. Repeated instability before 120 seconds of healthy
  operation escalates to the existing BB36-only USB/PnP recovery path.
- Automatic USB/PnP recovery that fails because Studio is not elevated is
  remembered instead of being retried every few seconds. The recovery circuit
  waits 60 seconds before another bounded soft probe.
- A real physical unplug/replug resets the recovery circuit because it is a
  genuine firmware reset.
- BB36 graphical page selection is preserved across same-mode recovery.
- Path-open failures now use bounded exponential retry up to 30 seconds instead
  of a fixed 1-second reopen loop.
- Offline validation: BB36 recovery V7 26 checks, shared display telemetry V2
  40, shared telemetry V1 47, global output authority 67, Hardware Lab, AGP,
  PDC, PAP3, FCU/EFIS, TCA, Studio `--check`, and launcher `--check` all pass.
- Live proof still required: reproduce a long-running BB36 session and confirm
  no repeated owner-reopen storm, no overlapping output worker, and successful
  same-page recovery after a transient F0 error.

## 2026-09-03 - Studio live feedback V2: physical state and device mirrors finally share one read-only path

A full bridge-to-Studio audit found that simulator dispatch and Studio feedback
were separate paths. Physical device workers correctly called
`HardwareLab.input(..., source="physical")` and device managers published live
LCD/display mirrors, but Studio's generic faceplate state used only
`state["mirror"]`. Most button/knob animation depended on the last 100
diagnostic events and a 1.1-second flash. The authoritative latest
`lab.inputs`/`lab.outputs` state arriving in every status response was not
composed into `_device_mirror()` or common control colours.

Studio now adds a read-only `live_feedback` composition layer:

- established device-specific mirror values remain highest priority;
- top-level/diagnostic live values fill only missing mirror fields;
- bridge-held `lab.inputs` and `lab.outputs` are exposed as stable latest state;
- every common faceplate button/toggle/selector can reflect the real physical
  state directly instead of depending on a diagnostic event still being in the
  bounded history;
- relative rotaries show a short, truthful direction indication from their
  latest physical pulse;
- maintained FCU/EFIS selector poses are resynchronized from authoritative lab
  state, while momentary push-button logic is unchanged;
- the authored AGP can derive only its already-known mechanical gear/brake-fan/
  anti-skid/autobrake pose from the same physical contacts when its device
  mirror did not publish a `controls` block;
- PDC BB62 and other managers that publish useful diagnostics but no `mirror`
  no longer appear empty in Studio.

No bridge, simulator-write, HID/serial/SDL owner, shared telemetry, BB36
recovery, mapping, output-power authority, or device protocol was changed.

Offline proof: Studio live feedback 39 checks, actual loopback status round
trip, 150-event diagnostic-ring overflow proof, global output authority 67,
Hardware Lab, AGP 80, PDC, PAP3, FCU/EFIS, Portable V1/V2/V3, Studio `--check`,
and launcher `--check` all pass. AGP/TCA/ECAM/FMC authored render tests pass
under Xvfb. The existing FCU layout test has a one-pixel overlap failure on the
unmodified baseline and remains unchanged by this fix.


This is the short, date-ordered record of completed work. The full story is
in [PROJECT_HISTORY.md](PROJECT_HISTORY.md).

## 2026-09-02 - A footer banner that could be raised but never taken down

The owner reported "Hardware is still connected; waiting for its live update"
permanently pinned to the bottom of Studio. **The hardware was fine and the
status poll was working.** The banner simply had no way to come down.

`_control_failures` counts failed status polls, and three of them raise that
line. Three is reached in 0.3 s at ten polls a second, which every bridge
startup does before the control channel is listening. `_receive_status` then
resets the counter on the next success - but the banner is footer *text*, and
nothing ever set it back. So a normal startup left a stale warning on screen
for the rest of the session, describing a failure that had ended seconds in.

- A recovered status poll now retires the banner its own failures raised.
- Only the three transient connection banners are cleared. A message the owner
  still needs - an output test result, a mapping confirmation, a panel fault
  location - survives an unrelated poll recovering, and that is asserted.
- The three strings became `BANNER_WAITING_UPDATE`, `BANNER_STILL_CONNECTED`
  and `BANNER_SERVICE_STOPPED`, used at their call sites. They were literals in
  two places, so editing the wording would have silently stopped the clearing;
  the test now also fails if a hard-coded banner literal reappears.

Measured while looking for a real fault first: the status snapshot builds in
0.08 ms and serialises to 102 KiB in 0.73 ms against a 1.0 s client timeout,
about 0.7% of a core at ten polls a second. Nothing was actually failing.

- Tests: `tools/test_moza_ab6_capture.py` 106 -> 116 checks. All 26 suites pass
  and `python launch.py --check` passes.

## 2026-09-02 - The AB6 had three selectable controls, not 137

"It works for a couple of seconds then stops." Three more pre-capture
assumptions were still in Studio, and together they meant the AB6 could show a
brief flicker of life and then nothing that could be acted on.

- **`_visual_controls()` returned three hard-coded "visual practice pose" axes**
  for the AB6 - `axis_x`, `axis_y`, `axis_z` - written when its catalogue held
  nothing else. Its 128 contacts, hat, slider and dial were not selectable at
  all, so **no function could be assigned to any of them**. It now reads its
  own catalogue exactly as the A210 does: **3 controls -> 137**.
- **`_learned_source()` returned `""`** for the AB6, on the reasoning that "an
  AB6 preset provides settings, not a verified HID identity". True before the
  capture, false after it, and it made every control an invalid mapping source.
- **The capture-proven selection description was A210-only**, so selecting an
  AB6 contact fell through to "Moza visual calibration control" and never said
  it was mappable. The calibration drag pose also still claimed the base had no
  physical HID axis report.

### Why it looked like it "stopped"

The reader emits the full axis set once on its first report, then **only
changes**. A stationary force-feedback base therefore emits nothing, the
selection flash expires after 1.1 s, and the panel goes quiet. That part is
correct behaviour, not a fault - but with only three selectable controls there
was nothing to interact with afterwards, so it read as having stopped.

### Panel faults now name their own location

The tick swallows any exception from a draw and printed only
`Panel update recovered: {type(exc).__name__}`. A KeyError from a faceplate and
one from a status payload looked identical, which is why the previous round was
diagnosed by inference rather than evidence. It now reports the exception type,
its message and the failing `studio.py:line`, and writes the full traceback to
`logs/studio_panel_faults.log` - once per distinct location, because a draw that
fails once fails every 70 ms.

- Tests: `tools/test_moza_ab6_capture.py` 83 -> 106 checks, asserting both bases
  offer the same 137 controls, that AB6 contacts are valid mapping sources, that
  the placeholders are gone, and that a fault report names a file and line.
  All 26 suites pass and `python launch.py --check` passes.

## 2026-09-02 - "Panel update recovered: KeyError" - a three-key seed

The AB6 page was still blank after being pointed at the right device, and the
screenshot carried the answer in its footer: **Panel update recovered:
KeyError**. The draw was raising, the tick was swallowing it, and an empty
faceplate was the visible result.

`_moza_practice_axes` seeds each base's stored pose. The A210's listed all
eight axes. **The AB6's listed three** - `axis_x`, `axis_y`, `axis_z` - left
from when those were the only axes its preset had named. The lookup then did:

```python
fallback[key] = self._axis_fraction(self._number(item, "value", fallback[key]))
```

The reader publishes **all eight axes on its very first report**, so the moment
live data arrived, `fallback["axis_rx"]` raised `KeyError` and took the whole
panel down with it. Nothing about the reader, the catalogue or the device was
wrong; the page simply could not survive its own hardware working.

- The lookup now fills in whatever the stored pose is missing instead of
  trusting its shape, and reads through `.get(key, .5)`.
- `MOZA_AXIS_KEYS` is defined once, so a seed and a reader cannot disagree
  about how many axes a base has again.
- The AB6's seed carries all eight, matching the A210's.

- Tests: `tools/test_moza_ab6_capture.py` 70 -> 83 checks. The new one
  reproduces the exact failing condition - a three-key seed against a reader
  publishing eight - and also covers a device with no stored pose at all.
- Backup: `Backup/moza_ab6_studio_live_v1_20260902-225902/` holds the
  pre-change file for this and the previous entry.

## 2026-09-02 - "nothing" - the AB6 page was reading the A210

The reader was running and the bridge was on the new code, verified by process
start time. The lab accepted AB6 input and the device was enabled. Studio still
showed nothing, and the reason was three floors up in the GUI.

**Studio's AB6 surface was authored when the AB6 had no captured report**, so
it was written to show nothing on purpose - and every one of those decisions
was still in force:

1. `_moza_a210_live_axes()` was hard-wired to `moza_a210` and returned early
   with `seen=False` on any other page. The AB6 page therefore drew the A210's
   fallback dict - a dead centre pose - whatever the physical base did.
2. The status pill read `"LIVE HID" if live_axes and not is_ab6` - the AB6 was
   explicitly excluded from ever showing live, and labelled REFERENCE/PRACTICE.
3. The eight console contacts were drawn `enabled=False`, with a caption
   stating the button protocol was not captured yet.
4. `_moza_pressed` and `_draw_moza_hat` read `"moza_a210"` unconditionally.
5. **The MAX3 grip tab read the A210's contact pool** while being drawn on the
   AB6 page. The grip is mounted on the AB6 on this rig, and the capture
   observed contacts 1 and 10 closing there - this grip's own TRIGGER and TOP -
   so its presses were arriving on a base the page was not reading.

### What changed

- `_moza_live_axes(device)` replaces the hard-wired helper.
  `_moza_a210_live_axes()` is kept as a wrapper returning
  `self._moza_live_axes("moza_a210")`, so the A210 page is untouched.
- `_moza_pressed`, `_draw_moza_push`, `_draw_moza_raw_badge`, `_draw_moza_hat`
  and `_draw_moza_max3_layout` take a `device` argument **defaulting to
  `moza_a210`**, so every existing call site keeps its exact behaviour.
- The AB6 faceplate now draws from live HID: the stick tracks X/Y, the eight
  console contacts light on press, and the MAX3 tab reads the AB6.
- **SLIDER and DIAL are drawn as axes**, with a live position and percentage.
  They were previously six guessed contacts, `B057`-`B062`, invented from the
  reference drawing; the capture proved both sweep the full 0..65535 range.
- Captions rewritten. They asked for a capture that has now happened, and the
  panel says what is true instead: the base prints no button names, so
  functions are assigned to numbered contacts; Z/Rx/Ry/Rz are declared but
  idle; and nothing is ever sent to this base.

- Tests: `tools/test_moza_ab6_capture.py` 62 -> 70 checks, asserting the AB6
  page reads the AB6, the live-HID exclusion is gone, the contacts are no
  longer disabled, and every helper still defaults to the A210. All 26 suites
  pass and `python launch.py --check` passes.
- Backup: `Backup/moza_ab6_studio_live_v1_20260902-225902/`.
- Live acceptance: restart Studio, open the AB6 page. The header should read
  LIVE HID, the stick should follow the base, SLIDER and DIAL should track, and
  pressing a console contact or a MAX3 button should light it.

## 2026-09-02 - The AB6 capture finished: live axes established, and a reader

The owner ran `--watch` and exercised the base. 28669 frames settled the
question the descriptor could not: **which of the eight declared axes the AB6
physically carries.**

| Axis | Observed | |
| --- | --- | --- |
| X, Y | `0 .. 65535` | full sweep |
| Slider, Dial | `0 .. 65535` | full sweep |
| Z | pinned `32767` | idle |
| Rx, Ry, Rz | pinned `0` | idle |

Hat positions `0, 2, 4, 6, 7` plus the `8` null, and 14 contacts seen closing.

The four idle axes are **kept and marked observed-idle, not deleted.** The
report field exists and decodes; one session showing no motion is evidence, not
proof of absence, and a note costs nothing while a deletion cannot be undone by
the next person who fits a different grip.

### The gap this exposed

The owner said the buttons have no printed names and they would assign
functions in Studio - which is right, and is the honest end of the capture.
But nothing was reading the AB6. Its catalogue entry said `implemented` while
no reader existed, so Studio would have had no input to assign. That would have
been a broken promise the moment they tried it.

- `MuslimSimMozaA210` gained optional `vid`/`pid`/`label` parameters, **all
  defaulting to the A210**, so every existing caller opens the same device and
  behaves exactly as before. Only `_open()` and two log strings were touched.
- The bridge now starts an AB6 reader beside the A210's, in its own `try`, with
  its own device registration, diagnostics and power-cycle entry. One Moza base
  being absent never silences the other.
- Verified live against the connected base: status `connected`, report id 1,
  length 34, events flowing, axes/hat/contacts all decoding.

### Studio's AB6 page now has real controls to bind

137 inputs - 8 axes, hat, 128 contacts - streaming from the base, replacing
three preset-derived `unknown` axes that could never be mapped to anything.

- Tests: `tools/test_moza_ab6_capture.py` extended 50 -> 62 checks, asserting
  the live/idle axis split is recorded and that the idle four stay catalogued.
  All 26 suites pass, `python launch.py --check` passes.
- Backup: `Backup/moza_ab6_reader_v1_20260902-225003/`.
- Live acceptance: restart Studio so the bridge reloads, open the AB6 page, and
  confirm the stick, slider and dial move and that pressing a contact registers
  for **Learn physical control**. No force-feedback output exists, so nothing
  on this base should ever light or resist.

## 2026-09-02 - The MOZA AB6 has a real identity now, read off the base

The AB6 was never captured. It entered the catalogue from an owner-supplied
A320/MSFS2024 `.preset`, and a preset carries calibration numbers rather than a
USB identity or a report layout - so the AB6 sat at `status: unimplemented`,
with no VID/PID, three axis names taken from the preset, and nothing Studio
could actually read.

### The tool

`tools/capture_moza_ab6.py`, in three phases: `--report` for identity and
protocol, `--watch` for live decode and which axes really move, `--capture` for
guided one-control-at-a-time naming.

**It is read-only by construction.** This is a force-feedback base, so the tool
opens the HID handle, reads the report descriptor, reads input reports, and
never calls `write`, `send_feature_report`, or any Moza SDK entry point. The
test asserts that against the parsed AST rather than the source text - the
first version of that check failed on the docstring promising it, which is
exactly the kind of false pass worth avoiding.

### What the base actually said

- **Identity**: VID `346E` / PID `1002`, `Gudsen` / `MOZA AB6 FFB Base`,
  interface 2, Generic Desktop / Joystick.
- **Report descriptor**: 1259 bytes, SHA-256 `d6749e44…4edbdd15` - **byte for
  byte the A210's own descriptor.** The AB6 was *not* assumed to match its
  sibling because they share a vendor id; both descriptors were read and
  compared, and the equality is what licenses reusing the A210's decode.
- **Input**: report `01`, 34 bytes at about 975 Hz - eight unsigned 16-bit
  axes, a four-bit hat, 128 generic HID contacts. The existing capture-proven
  `decode_moza_a210_report` accepts a live AB6 frame unchanged.
- **At rest**: stick near centre, `Rx/Ry/Rz/Slider` flat at zero, `Dial` 773,
  hat 8 (the descriptor's null state), contact 3 closed.

### What landed

- The catalogue entry is rewritten from the capture: `USB HID`,
  `VID 346E / PID 1002`, `implemented`, and 137 real inputs in place of three
  preset-derived `unknown` axes.
- Registered where identity matters: product registry (`346E:1002`), the USB
  lifecycle presence monitor, and `usb.py` so `Power cycle` can restart it -
  keyed separately from the A210 so restarting one never restarts the other.
- **Removed a stale duplicate.** A second, preset-derived `moza_ab6`
  `ProductSpec` existed only because the AB6 had no captured USB identity.
  Leaving both made `product_for_runtime_text("MOZA AB6")` ambiguous and it
  started returning `None`; the platform-V2 suite caught it immediately.

### What was deliberately not done

**Which physical control is which contact number is still owner work.** A
generic HID button number does not say what legend is printed above it, and the
A210 carries the same honest limitation. Same for which of the eight declared
axes the AB6 physically has - `Rx/Ry/Rz/Slider` read flat at rest, but flat at
rest is not proof of absent. `--watch` and `--capture` exist for exactly this
and need the owner at the hardware.

**No force-feedback output was invented.** No Moza output protocol was supplied
or inferred, so `force_feedback_profile` stays `unimplemented` and untestable,
Practice drives nothing on this base, and Studio sends no motor command.
`tools/probe_moza_flight_sdk.py` remains the open line of enquiry.

- Tests: new `tools/test_moza_ab6_capture.py`, 50 checks. All 24 other suites
  pass and `python launch.py --check` passes. Two existing suites failed on
  first run and were corrected rather than worked around: `test_hardware_lab.py`
  asserted the AB6 had no VID/PID, which is now false, and the platform-V2
  ambiguity above.
- Backup: `Backup/moza_ab6_capture_v1_20260902-223755/`.
- `test_bridge_control_channel.py` fails while Studio is open - it launches a
  second bridge - and Studio is running again on this machine.

## 2026-09-02 - Practice mode did nothing on twelve of seventeen devices

The owner reported it plainly: "i can enter any controller page and start mess
with it and it never post anything and all the screen don't react at all and
some other don't even wakeup if i touch them."

That was accurate, and worse than it sounded. `tools/probe_practice_coverage.py`
was written to measure it rather than argue about it - it drives the real
`HardwareLab` and the real `ControlServer.apply_practice_snapshot` with
`apply_lab_output` recorded, so it reports the shipping path's own behaviour.

**Before: 5 of 17 devices posted anything at all.** The PU Overhead's 32 lamps,
ECAM32's 19 LEDs, the throttle's 7 backlights and fault lamps, and the two
HOWALT panels' 17 indicators were all dark no matter what you pressed. With the
simulator off, a working panel and a dead one looked identical - which makes
Practice useless for the one job it has.

The cause was not subtle. `VirtualZiboPreview` only ever modelled five devices,
and `apply_practice_snapshot` only knew those same five by name, so
`only_device=` scoping filtered every press on the other twelve down to nothing.

### What changed

- **New `muslimsim/hardware/practice_echo.py`** holds the policy and no state:
  which controls Practice may drive, and when a device goes back to sleep.
- **Every device now responds when practised.** Its capture-proven lamps and
  LEDs light through `apply_lab_output` - the same single safe path Studio's
  existing output test already uses, which refuses any control the catalogue
  has not marked `implemented` **and** `testable`. **No vendor packet is
  invented anywhere in this change.**
- **New `practice_wake` control command.** Opening a device's page in Practice
  is also asking it to prove itself. This is the only way ECAM32 can respond at
  all: it has 19 proven LEDs and still no catalogued input to press. Studio
  sends it on page change and re-asserts it every 6.7 s while the page is open.
- **Rule 0.1 is honoured, and amended.** A practised device goes dark on its
  own 20 s after you stop using it, and leaving Practice darkens everything at
  once. The rule's old "lights only the one output being tested" wording is now
  "lights the device being practised", recorded in `AGENTS.md` as a deliberate
  amendment at the owner's instruction.

**After: every device that has something driveable posts.** The remaining seven
are correct: `pdc_bb62`'s sole output is `unmapped_vendor_output` with an
`unknown` protocol, both Moza units expose only an `unimplemented` force-feedback
profile, and `tca_boeing`, `winctrl_pedals`, `pdc_bb61_left` and
`pdc_bb52_right` have no output controls at all - they post to Studio, not to
themselves.

### What Practice deliberately still will not do

Displays and actuators are excluded on purpose. Every display adapter takes its
own shape, so a sixth practice page has to be authored, not guessed. Gauges and
solenoids are real actuators here - the throttle's two vibration motors and the
PU's timed starter retract - and Practice lights panels rather than shaking
hardware. Both exclusions are asserted by the tests.

### Practice never passes to Live

Stated by the owner and now enforced and tested: "what you practice never pass
to live... in order for my assigned function to be saved it has to be done in
live. practice only for experiment." The practice path touches inputs, outputs
and diagnostics only; it never reaches `profile_store`. A practice wake is
refused outright while the lab is in Live mode.

- Tests: new `tools/test_practice_all_devices.py`, 277 checks. All 24 suites
  pass, `python launch.py --check` passes, and Studio imports cleanly.
  `test_global_output_authority.py` still passes unchanged at 67 checks.
- New diagnostic: `tools/probe_practice_coverage.py`.
- Backup: `Backup/practice_all_devices_v1_20260902-222134/`.
- **Live acceptance still required.** Restart Studio, turn Practice on, and
  walk the device list: each page should light that panel and only that panel,
  and it should go dark about twenty seconds after you move on. Note that a
  device the bridge never opens with X-Plane off still cannot respond - the
  throttle, TCA, both HOWALT panels and the AB6 have no simulator-down reader
  yet, which is a separate piece of work and is not addressed here.

## 2026-09-02 - The MCDU32 froze, and nothing was watching the PFP3N at all

The owner reported two things: the MCDU32 freezes after a while, and after
closing and reopening Studio neither the PFP3N nor the MCDU32 comes back -
both just stay frozen. `logs/bb36_live_owner_takeover_v3.log` had been
recording the answer for three days: **3556 health failures, 2211 firmware
recovery attempts, and every single one of them failed the same way.**

### What the log actually says

The recorded staleness separates into two clean populations, and that is the
whole diagnosis:

- **5561 stalls read 8.0 or 8.1 s.** The startup grace is 8.0 s, so these
  paths published no heartbeat at all after starting. That is a panel whose
  firmware has stopped acknowledging, and reopening HID cannot reach it.
- **~104 stalls read 3.0 to 3.6 s**, clustered just above the old 3.0 s
  threshold. Those are live panels having one slow frame.

The second population precedes the first. On 2026-09-02 a lone 3.1 s stall at
18:14 tore down a working panel; another at 19:19; at 19:24:59 the write
returned `-1`, and from 19:25 the 8.1 s cascade ran continuously. Overnight on
2026-09-01 the same cascade ran from 00:00 to 09:30 - one teardown and reopen,
font upload included, every twelve seconds, for nine and a half hours.

### Five separate defects, each fixed in the smallest place

1. **The BB36 stall threshold was inside the slow-frame population.** 3.0 s ->
   6.0 s. It clears the worst recorded slow frame with margin and still sits
   below the 8.0 s grace, so a real wedge is still caught on the first check
   after the grace - the wedges report 8.0/8.1 s, which fails either value.
   This is the change that stops working hardware being torn down.
2. **BB35 had no output watchdog at all.** `_active_is_healthy` was thread
   liveness alone, and a worker parked inside a native F0 write to a stalled
   panel stays alive forever - so a frozen PFP3N was reported live and never
   reopened. It now reads the same frame-start heartbeat BB36 reads, seeded in
   `start()` so a worker that blocks on its very first write is still seen. A
   build that publishes no heartbeat keeps its old is_alive()-only contract.
3. **BB35's teardown wrote on a handle its worker might still own.** The three
   darkening reports were sent after a bounded 6.0 s join with no liveness
   guard, so they could interleave with an in-flight native F0 burst and leave
   the panel holding a torn transaction - which outlives the handle close, and
   is still there after a Studio restart. **This is the best candidate for why
   a restart did not help.** BB36 already guarded its teardown exactly this
   way; BB35 now does too. When the worker exits normally, which is the
   established case, the writes are unchanged and still sent.
4. **BB36 retried an impossible recovery forever.** Every attempt failed with
   `LabError: Restart screen/device requires Administrator rights`, because
   `pnputil /restart-device` refuses a non-elevated session - so the one
   recovery this panel responds to was never available. Retries now back off
   1.5 -> 3 -> 6 -> 12 -> 24 -> 30 s and stop there, the first three attempts
   are logged verbatim and then one in twenty, and the first failure prints
   the thing the owner actually needed to know: **a Studio restart cannot clear
   a wedged BB36; run Studio as Administrator, or replug the panel.** A path
   that recovers clears the backoff, so a later unrelated wedge still gets its
   fast first retry.
5. **Studio's status polls were writing the supervisor's health verdict.**
   `live_snapshot` runs the same predicate from HTTP request threads - the log
   carries `PFD HEALTH FAILURE` lines attributed to `process_request_thread` -
   racing the supervisor into reporting the wrong recovery reason. The check
   takes `record=False` now; the supervisor's own call is unchanged.

### What was deliberately not changed

The trigger for the very first wedge is still unproven. The leading remaining
suspect is the ENG PRI / MFD / HYD REST fallback, which issues up to 24
sequential dataref reads at `PFP_PFD_HTTP_TIMEOUT` = 0.25 s inside one frame -
enough to produce exactly the 3.0-3.6 s slow frames above. Raising the
threshold removes the harm without touching that working telemetry path, per
rule 0.2; bounding the fallback itself is a separate decision and is not made
here.

Rule 0.1 note: on a stalled teardown the blackout write is now skipped rather
than raced. A write that interleaves with an in-flight transaction darkens
nothing anyway, and the handle close still happens - this is the same trade
BB36 and PAP3 already made.

- Tests: new `tools/test_display_stall_recovery.py`, 29 checks. All other
  suites re-run unchanged - global output authority 67/67, hardware lab, FMC
  authored faceplates 45/45, portable device platform 11/11, input chains
  28/28, AGP radio 80/80, TCA Boeing 158/158, plus both module self-tests and
  `python launch.py --check`. `tools/test_bridge_control_channel.py` cannot
  pass while Studio is open - it launches a second bridge - and was failing
  for that reason before this change.
- Backup: `Backup/bb35_bb36_freeze_recovery_v1_20260902-214339/`.
- **Live acceptance still required, and it needs a full Studio restart so the
  bridge reloads.** If the MCDU32 is wedged right now, replug it first - no
  amount of restarting will clear it. Then confirm: the MCDU32 no longer
  restarts itself every twelve seconds; a frozen PFP3N is reopened instead of
  reported live; and closing Studio still leaves both panels dark.

## 2026-09-02 - Portable Device Platform V1: product identity replaces COM/index identity

MuslimSim now has one stable physical-product registry and one runtime locator
service. Supported products are identified by VID/PID, product strings and,
where necessary, a read-only protocol identity. Unit serial numbers, COM
numbers, HID paths, SDL indices and install paths are explicitly runtime-only
and are not valid product identity. A replacement D201/D203/BB35/BB36/PAP3/etc.
of the same supported model therefore inherits the same MuslimSim device key
and profile.

The first active owner migrated is the PU Overhead serial side. `--port` now
defaults to `auto`: MuslimSim resolves the present PU serial endpoint from its
`3561:8561` product identity/product strings and resolves again on reconnect.
The historical COM5 text is retained only as an internal interception token for
the established Serial() call; automatic mode never opens COM5 by guess when
the product resolver has not identified the PU. If Windows re-enumerates the same supported PU as COM27/COM44 on
another PC or after replug, the existing reconnectable PU owner opens the new
locator without changing the device profile. An explicit `--port COMx` remains
a diagnostic override only. No PU packet, timing, starter, lamp, input, or
aircraft-control behavior was changed.

Read-only Studio discovery now sources its established WinCtrl/generic USB map
from the shared product registry and adds an additive platform snapshot for
serial endpoints/runtime readiness; existing callers that read only `devices`
retain the same contract. HOWALT remains safer than a raw USB match: D201 and
D203 share the WCH bridge and are still separated by their existing read-only
MobiFlight firmware name, never by the captured serial number.

The PyInstaller recipe was also tightened for an end-user, no-pip build. It
now explicitly bundles `pu_physical_authority.py`, websocket-client, all
MuslimSim hardware/device/control submodules, X-Plane/MSFS command catalogues
and the PFP bank plan. `build_exe.py` runs the new portable product/locator and
runtime-bundle tests before packaging.

Tests: `tools/test_portable_device_platform.py` 11/11, portable runtime recipe
19 checks, global output authority 67/67, Hardware Lab self-test pass, AGP radio
119/119, TCA Boeing catalogue 158/158, PDC BB62 pass, PAP3 MCP pass, FCU/EFIS
BA01 pass, and `python launch.py --check` pass. The changed source plus existing
Python source parses cleanly. No hardware or simulator was opened. Live
acceptance still required on Windows: start with the PU on its current COM,
unplug/replug if Windows changes the COM number, then prove the same PU owner
recovers without `--port`; separately confirm all existing HID/HOWALT panels
retain their current behavior.

## 2026-09-02 - The AGP radio page now operates the aeroplane

The radio page is wired: the window follows the aircraft, the knobs tune it,
and SET swaps the standby in. This is the change that reverses the AGP's
display-only contract, so it was done on its own with its own tests.

### What the windows show

- **CHR** names the selected radio. Seven segments have no diagonals, so a true
  "V" cannot be drawn - `U` is the only form the hardware can render, and the
  window reads **U1 / U2 / U3**. A "V" mask was deliberately not invented; the
  test asserts one never appears.
- **UTC** is the frequency of that radio, read from the aeroplane: 120.900 MHz
  reads as `120900` across the six digits.
- **ET** is the transponder code, replaced by the mode - ALoF / ALon / tA /
  tArA - for 1.5 s whenever it moves, because a spring switch returns to centre
  and would otherwise leave no confirmation it was seen.

### The switches

- **GPS / INT / SET** picks the radio: V1, V2, V3. On every other page that
  switch still selects the display page exactly as before.
- **CHR** is the outer knob, whole megahertz. **RST** is the inner one, 25 kHz
  channels. The two descriptions given for this were opposite, so both live in
  `AGP_RADIO_OUTER_KNOB`/`AGP_RADIO_INNER_KNOB` and swapping them is one edit.
- Turning either knob **enters standby**, because tuning the live frequency is
  not something a radio lets you do. CHR then reads **Sb1 / Sb2 / Sb3** so the
  window says which frequency is on it.
- **The SET knob** commits: it writes the tuned standby and fires the
  aeroplane's own swap command, so the aircraft performs the exchange rather
  than MuslimSim writing an active frequency directly. Pressing it again steps
  back into standby to tune the next one. That is the whole of "SET makes this
  active, tap again to edit".
- **RUN** turns the transponder on; the spring **RST** steps ALT OFF -> ALT ON
  -> TA -> TA/RA, driven through Zibo's own `transponder_mode_up`/`_dn` to the
  target position rather than by writing a mode value.

### The sluggishness

Every radio branch sets `next_agp_display_read = 0.0`, so a knob refreshes the
window on the same pass instead of waiting out `AGP_DISPLAY_INTERVAL`. That
0.25 s wait was the entire reason the numbers felt like they lagged the knob.

### Safety and limits

- **V3 is not tunable and does not pretend to be.** Every Zibo com3 DataRef is
  read-only, proven by `tools/probe_howalt_live_targets.py`, so V3 displays the
  aeroplane and the knobs and SET decline to act on it.
- A standby being tuned is the owner's, not the aeroplane's: the refresh never
  overwrites it mid-edit.
- The radio commands resolve exactly like the gear commands - optional, warned
  about once, and an unavailable one leaves that action inert rather than
  stopping the panel.
- The page is reached by the CHR knob like every other page, and the existing
  CHR press still means "back to flight", so there is always a way out.
- Studio's faceplate now follows the bridge's published page, so the drawn
  panel cannot drift out of step with the physical windows.

### Tests

`tools/test_agp_radio_page.py` extended to **119 checks**. It does not check
that a legend exists - it encodes each one into a real packet and asserts every
character lights at least one segment, the only thing separating a legend from
a blank window. Stepping is checked at the band edges and from junk input, and
a full turn of the outer knob must leave the channel part alone. The wiring is
checked at the source: the switch picks the radio, the knobs step the standby,
SET writes and swaps, V3 is excluded, the refresh is forced, and the display
pass does not overwrite a standby being edited.

15 of 16 suites pass; `test_bridge_control_channel.py` fails only because
Studio is running and owns the loopback port. `python launch.py --check`
passed. Backup: `Backup/agp_radio_page_wiring_20260902-135305/`.

**Live check needed, after a full Studio restart:** turn the CHR knob past
NAVIGATION to reach RADIO, confirm U1/U2/U3 follow GPS/INT/SET, tune with CHR
and RST, press SET and confirm the standby becomes active, then RUN and the
spring RST for the transponder modes.

## 2026-09-02 - Why the AGP radio legend showed nothing, and the font that fixes it

- **The window showed a blank, not an error.** The AGP is a real seven-segment
  display driven by packed bitplanes, and `AGP_SEGMENT_MASKS` defined only the
  ten digits, `-` and space. `_agp_encode_segments` falls back to `0x00` for
  anything else, so every letter of a radio legend lit **zero segments** and
  the digit simply went dark. Nothing failed and nothing was logged.
- Added the letters seven segments can actually form - A b C d E F H L n o P r
  S t U y - each derived from the masks already in the table in the same bit
  order, not guessed. The ten digits, `-` and space are byte-identical, and a
  regression check pins them.
- **There is no V on seven segments.** `U` is the long-established stand-in, so
  the selected radio reads **UHF1 / UHF2 / UHF3** with a rounded V. A "V" mask
  was deliberately *not* invented, and the test asserts it stays absent.
- The standby legend does double duty as the edit indicator, which answers the
  third request without spending a window on it: **UHF2** means the frequency
  below is the live one, **Stb2** means it is a standby being tuned. Tapping
  SET moves between them, so "SET makes this the active frequency" and "tap
  again to edit standby" are the same control.
- ET carries the transponder code, which is what is wanted at a glance, and is
  replaced by the mode - **ALoF / ALon / tA / tArA** - for 1.5 s whenever the
  mode moves. A spring switch returns to centre, so without that flash there
  would be no confirmation the switch was seen.
- New suite `tools/test_agp_radio_page.py`, 108 checks. It does not check that
  a legend exists; it encodes each one into a real packet and asserts **every
  character lights at least one segment**, which is the only thing that
  distinguishes a legend from a blank window. It immediately earned that: it
  caught `Stb1` using an `S` that had no mask, before any of it reached the
  panel. `S` now reuses the digit `5` mask, which is the same shape.
- Tests: 15 of 16 suites pass. `test_bridge_control_channel.py` fails only
  because Studio is running and owns the loopback port - confirmed in the
  process list - and `python launch.py --check` passed.
- Backup: `Backup/agp_segment_letters_20260902-134100/`.
- **Still to wire, and deliberately not rushed:** `_agp_radio_page_text` is the
  content model and is proven, but nothing calls it yet. The remaining work is
  the display hook, an immediate refresh on a knob event rather than waiting
  out `AGP_DISPLAY_INTERVAL` (0.25 s, which is the sluggishness reported), and
  routing GPS/INT/SET to the radio selection, the CHR and RST encoders to the
  frequency, SET to the active/standby swap, and RUN/STP/RST to the
  transponder. That last part reverses the AGP's display-only contract and
  writes to a live aircraft, so it is being done as its own change with its own
  tests rather than folded in behind a font fix.

## 2026-09-02 - An authored AGP faceplate, drawn the HOWALT way

- The AGP faceplate was generated inline in `muslimsim/gui/studio.py` from
  proportional boxes. It is now authored the same way MUSLIMRTP and MUSLIMATC
  are: `muslimsim/devices/agp_faceplate.py`, one fixed 900x660 reference space
  taken from the owner's photograph, reserved label and control regions checked
  against each other **at import**, and a single uniform scale so nothing
  reflows into anything else.
- That validator earned its place immediately: it caught the CHR encoder and
  the GPS/INT/SET paddle authored on top of each other before anything was
  rendered. The right column was respaced and both fit.
- Drawn from the photograph: the LDG GEAR green window with its three
  gear-down arrows, BRK FAN, the LO/MED/MAX autobrake blocks, the A/SKID &
  N/W STRG bat toggle with its ON/OFF legends, TERR ON ND, the amber
  separators, the recessed CHR/UTC/ET windows with their MIN/SEC and
  HR/MO-MIN/DY-SEC/Y sub-legends, the three white press-encoders with a
  travelling ball in a channel, both three-position paddles, and the UP/DOWN
  gear lever panel alongside.
- All 24 catalogue controls the panel offers keep a clickable tag, checked
  across both switch positions because some are only drawn in one.
- **Window modes.** The three windows now have two pages, chosen by a button on
  the faceplate itself: `clock` is the panel exactly as it has always been, and
  `radio` re-labels the windows RADIO / FREQ / SQUAWK for the radio and
  transponder head described below. The mode is Studio view state and never
  changes what the hardware reports.
- Three additive edits to `studio.py`: the mode's initial value, the dispatch
  to the new module, and an intercept so the mode button does not fall through
  to select-or-activate - it is not a catalogue control, and in Practice that
  fallthrough would try to operate something that does not exist. **The
  original `_draw_agp` is kept as the fallback**, so a drawing error can never
  leave the panel unusable. One line removed, 31 added.
- New suite `tools/test_agp_faceplate_layout.py`, 50 checks: both modes render,
  every catalogue control is clickable, the printed legends are present, the
  window legends actually change with the mode, and every authored region stays
  inside the reference space. **All 15 suites pass** and `launch.py --check`
  passed.
- Backup: `Backup/agp_faceplate_v1_20260902-132345/`.
- **Not yet done, and deliberately not half-done:** radio mode currently
  *draws* but does not yet *operate*. Wiring GPS/INT/SET to the VHF selection,
  the CHR and RST encoders to the frequency with SET to accept, and RUN/STP/RST
  to the transponder mode is bridge work, and it changes the AGP's standing
  contract - `bridge/final.py` says in as many words that CHR/UTC/ET are
  "intentionally display-only: they read the selected Zibo values and never
  write anything back". Making them write is a deliberate reversal of that,
  and it is the next task rather than something to slip in unannounced.

## 2026-09-02 - ATC source lamps back in Live, and a two-speed pitch trim

- **The ATC 1/2 lamps stopped showing.** They are the "1" and "2" lamps beside
  the XPNDR legend, and they were only ever driven by
  `_handle_howalt_practice_input` - practice/Test mode. In Live nothing wrote
  them, so they simply sat wherever they had last been left. That went
  unnoticed until the new aircraft-power blackout started clearing them on the
  way to dark, after which nothing ever lit them again. **This one is mine.**
  - Fixed at the cause rather than by not clearing them: in Live they are now
    driven from `laminar/B738/switch/xpndr_atc_pos`, the aircraft's own source
    position, which is the thing the lamps report. Dirty-only, and a manual
    Studio output on either lamp still wins.
  - They also come back after a blackout, because the power restore clears the
    live value cache.
  - The practice handler had the same polarity error the faceplate selector
    had: it lit "2" for a closed contact. The contact closes in position 1, so
    both now agree.
  - Proof: aircraft position 0 -> `1-LED=255, 2-LED=0`; position 1 ->
    `1-LED=0, 2-LED=255`; and unpowered -> ALL_OFF -> power restored ->
    lamps re-asserted.
- **Pitch trim was too slow.** One cadence cannot be both fast and accurate on
  a spring rocker, so there are now two, and holding the rocker chooses.
  - A short press keeps the proven fine cadence exactly as it was - 0.10 s
    interval, 0.10 s command duration - so a single nudge is still one small
    step. That is the accuracy half, and it is unchanged.
  - Holding past `WINCTRL_PITCH_TRIM_ACCEL_AFTER` (0.45 s) switches to the fast
    pair: a 0.04 s repeat interval with a 0.18 s command duration. The duration
    deliberately outlasts the interval so activations overlap and the trim
    wheel runs **continuously** instead of stepping, which is where the old
    "slow" feel came from - each activation ended before the next arrived.
  - All four values are named constants next to `WINCTRL_PITCH_TRIM_COMMANDS`
    so the feel can be tuned without touching the loop.
  - `winctrl_trim_hold_since` tracks the current hold and is cleared when the
    rocker returns home. It never influences direction.
- Rule 0.2: both are additive. The trim block's held-state latches, direction
  choice, error backoff and Studio-binding precedence are untouched, and the
  readout re-arm added earlier still fires.
- Tests: **all 14 suites pass**, including `test_bridge_control_channel.py`,
  which passes again now that Studio is closed. `python launch.py --check`
  passed.
- Backup: `Backup/atc_source_leds_and_trim_rate_20260902-131639/`.
- Live check: confirm the ATC 1/2 lamps follow the source switch, and that a
  tap on the trim rocker still gives one small step while a hold runs the wheel
  smoothly. If the hold is now too fast, lower `WINCTRL_PITCH_TRIM_FAST_DURATION`
  or raise `WINCTRL_PITCH_TRIM_FAST_INTERVAL`.

## 2026-09-02 - The blackout is back, and this time the trim LCD survives it

The owner asked for the working blackout returned, every device cold and dark
with an unpowered aeroplane, every device asleep after Studio closes - and the
pitch trim back when the aircraft is loaded. That last clause is the whole
reason this was reverted once, so it is the part that got the attention.

### Why it broke the trim LCD last time

The RUD TRIM number is **event-driven, not polled**. It is written only while
the rocker is moving, and the readout disarms itself on the settled reading
after release - `winctrl_stab_trim_readout_pending` is set when the rocker
moves and cleared when it stops. The bridge comment says it plainly: nothing
is read from the simulator unless the owner is actually trimming.

So a blackout takes `trim_display_backlight` to 0 and blanks the window, and
**nothing ever writes the number again** until the owner physically moves the
trim rocker. Restoring the backlight brings back a window that is lit and
empty. The AGP authority block had always got this right for its own display -
it clears `last_agp_display_text` and forces `next_agp_display_read = 0.0` on
restore - and the throttle block simply never had the equivalent.

**The fix is three lines in the restore branch:** re-arm
`winctrl_stab_trim_readout_pending = True` and make it due immediately with
`next_winctrl_stab_readout = 0.0`, so the stabilizer units come back with the
power. Guarded now by two new checks, with the reason written into the test, so
this cannot quietly return.

### What was restored

All of it byte-identical to the proven 2026-09-01 code, not rewritten:

- `_winctrl_throttle_blackout` / `_winctrl_throttle_restore_defaults`, which
  write the captured channel report at 0 and at the captured defaults. **How it
  goes dark:** `_winctrl_throttle_output_packet(key, 0)` - the protocol's own
  off, no invented packet.
- The aircraft-power authority block, beside the AGP one and behaving
  identically: only while the simulator is up, only outside Test mode, rate
  limited to 0.5 s, written only on a change of state.
- The simulator-offline blackout, which also resets the remembered state to
  unknown so recovery re-applies rather than trusting a stale belief.
- The Studio-shutdown blackout inside `_close_winctrl_trim_display`, under the
  existing lock while it is still the sole owner.

Insertion-only into `bridge/final.py`: 111 lines added, and the single removed
line is that function's docstring, reworded to say it now releases the handle
dark.

### D201 and D203 now inherit rule 0.1

They had no power path at all - no avionics or battery DataRef anywhere in the
stack, `all_off()` reachable only through a display command string, and
`stop()` closing the port with the panel lit.

- `_all_panels_dark` calls each router's own `all_off`: `set_output(name, 0)`
  for every declared output and a blank through the same masked display writer
  normal output uses. **No vendor packet was invented to force this dark.**
- Aircraft power is read from the same candidates `bridge/final.py` uses for
  the PU and the throttle - `dc_stdbus_status`, then `battery_on`, then
  `avionics_on` - because rule 0.1 is one rule about the aeroplane, not a
  per-device opinion.
- The two kinds of "no reading" are told apart, matching
  `_agp_aircraft_output_powered`: no ref resolved at all means the aircraft
  publishes none, so preserve what was working; a ref that resolved and cannot
  be read is live data lost, which goes dark.
- Both shutdown paths darken before the ports close - `stop()` and the
  monitor's own exit when the bridge's shutdown event fires.
- Proof: unpowered -> both panels ALL_OFF with nothing lit; powered -> normal
  display; ref unreadable -> ALL_OFF; no ref published -> preserved; and
  `stop()` -> ALL_OFF on both before either port closes.

### The PU is still the exemption, and that is not a gap

The owner asked for every device, and the PU cannot comply with the shutdown
half: it has no off state, returning to its physical knob brightness about a
second after anything stops sending it frames. Five attempts were made and
removed on 2026-09-01. `AGENTS.md` records the exemption and
`DEVICE_REFERENCE.md` records the measurements. **It does go dark when the
aircraft is unpowered, which is the half that works and the half that matters.**
The two stale test checks guarding the removed exit blackout were dropped, with
the reason written where they stood.

### Tests

`tools/test_global_output_authority.py` was still the pre-revert version,
asserting PU dim code the owner had deleted. Trimmed exactly as the 2026-09-01
entry describes - the PU shutdown-dimmer checks and the dim-holder/COM5
handover checks, both of which only guarded removed code - then extended with
the HOWALT coverage entries and the three new trim-recovery checks.

**It passes at 67 checks. It was failing when this session started.** 13 of 14
suites pass; `test_bridge_control_channel.py` fails only because Studio is
running and owns the loopback port, the documented cause, confirmed by finding
`MuslimSim Studio.pyw` and its bridge live in the process list.
`python launch.py --check` passed.

Backup: `Backup/winctrl_blackout_restored_with_trim_recovery_20260902-122416/`.

**Live check needed, and it needs a full Studio restart:** with the aircraft
cold and dark confirm the throttle backlight, the flaps/airbrake backlight, the
RUD TRIM window and both HOWALT panels are all off; switch the battery on and
confirm they come back **and that the RUD TRIM window shows the stabilizer
units again without touching the rocker**; then close Studio and confirm
everything stays dark except the PU, which returns to its knob brightness.

## 2026-09-02 - ATC source and ALT source reach the aircraft

The last two unmapped D203 controls now have measured targets. The earlier
searches missed them because the names use `xpndr_`, not `transponder_` or
`atc_`, and because the switch is moved by a **command** while its position is
published as a separate read-only DataRef.

- Measured in `B737-800X/b738_4k.acf`:
  - position, read-only: `laminar/B738/switch/xpndr_atc_pos` and
    `laminar/B738/switch/xpndr_alt_pos`
  - movement, commands: `laminar/B738/toggle_switch/xpndr_atc` and
    `laminar/B738/toggle_switch/xpndr_alt`
- The mismatch that needed solving: the D203 switch is **absolute** - it is
  either in position 1 or position 2 - while the aircraft offers only "flip
  it". Firing the toggle on every event would make the aircraft switch follow
  the *number of events* rather than the physical position, and the two would
  drift apart the first time either side moved alone.
- `_set_atc_source` reads the aircraft's position, compares it with the
  physical one, and fires the toggle **only when they disagree**. Repeated
  events are absorbed, and moving the switch re-asserts its position after the
  aircraft was changed from the cockpit.
- Both edges are dispatched. `_dispatch_atc_live` discards `release` for
  everything else, so the source branch is decided ahead of that guard -
  moving a two-position switch to position 2 is a release, not nothing.
- Proof: from sim position 1, "switch to 1" is handled with no toggle, again
  with no toggle; "switch to 2" toggles once and the position follows; again
  with no toggle. ALT behaves the same. On an aircraft publishing neither
  DataRef, both return False and stay remappable.
- **One live check needed, and it is a coin flip that the hardware settles.**
  The physical contact closes in position 1 and Zibo counts its position from
  0, so pressed maps to position 0. If the switches turn out reversed, it is
  one edit: `ATC_SOURCE_PRESSED_POSITION`, kept as a single named constant for
  exactly this reason.
- Tests: 13 of 14 suites pass, unchanged, with the same deliberate
  `_winctrl_throttle_blackout` failure. `python launch.py --check` passed.
- Backup: `Backup/howalt_v4_atc_alt_source_20260902-115632/`.

## 2026-09-02 - VHF3 follows Zibo's third COM, DATA and all

The aircraft answered the VHF3 question directly, so it is now wired from
measured names rather than guessed ones.

- `tools/probe_howalt_live_targets.py` against `B737-800X/b738_4k.acf`
  (13534 DataRefs) found Zibo's third COM published in parts:
  `laminar/B738/comm/com3/act_freq_MHz` and `_kHz` with an `act_freq_data`
  flag, and the matching `stdby_freq_*` trio.
- The `_data` flag is the interesting one. It is what puts **DATA** in the
  window instead of a number, which is exactly what the owner reported seeing
  in the sim - DATA in the active window, 118.800 in the standby.
- Added `_zibo_com3_window`, which returns "DATA" when the flag is set, else
  `MHz.kHz` zero-padded to three places, else "" when the aircraft publishes
  no third COM at all.
- All six DataRefs are **read-only**, so VHF3 stays display-only. There is no
  writable third-COM target, so the panel does not pretend to tune it.
- Proof: vhf1 -> 120.900/129.875, vhf2 -> 121.500/118.250,
  **vhf3 -> DATA/118.800**, hf1 -> blank; and on an aircraft with no third
  COM, vhf3 falls back to blank rather than showing COM1.
- The letters go to the firmware's own MAX7219 font, so how cleanly D-A-T-A
  renders on the physical 7-segment window still needs a look on the hardware.
- Backup: `Backup/howalt_v4_vhf3_zibo_com3_20260902-115338/`.
- Still open: ATC source 1/2 and ALT source 1/2. Neither `transponder_source`,
  `xpdr_source`, `atc_source` nor `alt_source` exists anywhere in those 13534
  DataRefs, and the `laminar/B738/toggle_switch/` sweep was truncated at 40
  entries. The probe now prints up to 250 per group and also sweeps every Zibo
  knob/selector and anything mentioning ATC or XPDR.

## 2026-09-02 - D201 selector windows, and the inverted D203 source switches

Two defects reported from the hardware after the Live routing fix.

- **VHF3/HF1/HF2/AM showed VHF1's frequency.** `_sync_live_displays` chose its
  DataRef pair with `if self._rtp_live_radio == "vhf2": ... else: COM1`, so
  every selector position that was not VHF2 - including VHF3, HF1, HF2, AM and
  OFF - fell into the COM1 branch. The panel confidently displayed COM1 under
  a selector that was not COM1.
  - Replaced the two-way branch with `LIVE_RTP_RADIO_SOURCES`, which maps only
    the positions that have a verified aircraft source: VHF1 to COM1, VHF2 to
    COM2. A position absent from that table now **blanks** SMG-1/SMG-2 rather
    than showing another radio's frequency. Wrong data is worse than none, and
    this matches the panel's existing rule that unverified controls are not
    redirected to a guessed target.
  - Proof: vhf1 -> 120.900/129.875, vhf2 -> 121.500/118.250, and vhf3, hf1
    and am -> blank. NAV and squawk paths untouched.
  - VHF3 does not yet *follow* the aircraft. Doing that needs the aircraft's
    own VHF3 source, which is not guessed here; see the open question below.
- **XPNDR source and ALT source read backwards in practice mode.** Both
  selectors were drawn with `1 if _pressed(...) else 0` against labels
  `("1","2")`, so a pressed contact rendered as position 2. On the hardware
  the closed contact is position 1, so both read inverted. Flipped both to
  `0 if _pressed(...) else 1` - one expression each, two lines total, no other
  behaviour changed.
- Neither source switch is dispatched in Live: `_dispatch_atc_live` returns
  False for `xpn_1_2` and `alt_1_2` by design, because no verified aircraft
  source-selection target has been established. They remain remappable. This
  is unchanged here and is the second open question below.
- Tests: 13 of 14 suites pass, unchanged. `tools/test_global_output_authority.py`
  fails identically before and after on `_winctrl_throttle_blackout`, which is
  absent by the owner's deliberate revert to the working trim LCD.
  `python launch.py --check` passed.
- Backup: `Backup/howalt_v4_radio_select_and_source_switch_20260902-114248/`.
- Added `tools/probe_howalt_live_targets.py` so those two questions are
  answered by the aircraft rather than guessed. It searches the loaded
  aircraft's DataRefs and command inventory for VHF3/third-COM, transponder
  source and altitude source, prints each match with its current value and
  whether it is writable, and re-checks the five NAV commands the D201 lower
  encoders and transfer key already use - because "the NAV knobs do nothing"
  and "these command names are not in this aircraft" look identical from the
  cockpit. Read-only: it writes nothing, opens no serial port and is safe to
  run beside a live bridge.
- First run of that probe found nothing at all, and the reason is worth
  writing down: `filter[name]` on the `datarefs` endpoint is an **exact-match**
  filter that answers HTTP 404 for a partial name. It cannot discover anything.
  That is why `resolve_dataref_id` works - it only ever passes full names - and
  why every substring search in the first version returned 404 while the
  command inventory, which is paged rather than filtered, worked fine. The
  probe now pages the whole DataRef inventory and filters locally, the same
  shape as `_muslimsim_list_live_commands`.
- The same run confirmed the NAV command names are correct: all five of
  `sim/radios/nav1_standy_flip` and `stby_nav1_coarse_up`/`_down`/`fine_up`/
  `_fine_down` are present in `B737-800X/b738_4k.acf`. So the NAV knobs doing
  nothing was the dead write path, not a wrong name. Zibo also publishes its
  own `laminar/B738/push_button/switch_freq_nav1_press`, which is the better
  transfer target if the stock command turns out to be ignored - not changed
  yet, pending a live retest with the write path restored.
- Open, pending the owner's capture or confirmation:
  1. the aircraft's VHF3 active/standby source, so VHF3 can follow the sim;
  2. a verified target for ATC source 1/2 and ALT source 1/2 - the aircraft
     labels these ATC 1/2 and ALT 1/2, so they are expected to appear in the
     `laminar/B738/toggle_switch/` sweep the probe now prints.

## 2026-09-02 - D201 and D203 reach the aircraft in Live mode

- **Symptom:** MUSLIMRTP (D201) and MUSLIMATC (D203) behaved correctly in
  practice mode but controlled nothing in Live. Panels lit, displays tracked,
  and the radio selector moved, but no COM/NAV transfer, no tuning, no
  ATC/TCAS mode change, no IDENT/TEST and no squawk edit ever reached the
  simulator.
- **Cause:** `install_howalt_v4` accepts five simulator helpers. The bridge
  call site passed only the two read helpers, `resolve_dataref_id` and
  `read_dataref`. `HowaltV4Bundle.__init__` tried to recover the three write
  helpers with `getattr(__main__, ...)`, which cannot work in this process:
  `muslimsim/core/engine.py` loads `bridge/final.py` under the module name
  `_muslimsim_bridge_engine`, so `__main__` is `launch.py` and all three
  lookups returned `None`. `_command_once` and `_write_ref` both open with a
  `callable(...)` guard, so every live control returned False without ever
  attempting a write. Reads worked, which is why the displays looked healthy.
- **Fix:** pass the three helpers `bridge/final.py` already defines, at the
  existing HOWALT call site, exactly as the PDC BB61/BB52 dispatchers and
  three other installers in the same file already do - `set_dataref`,
  `resolve_command_id` and `activate_command`. Insertion-only: 3 lines added,
  0 removed, confirmed by diff against the backup. No existing caller changed
  and no working code was restructured.
- Signatures were checked against the call sites before wiring:
  `set_dataref(api_version, dataref_id, value)` against
  `self.set_dataref(version, ref, float(value))`;
  `resolve_command_id(api_version, name)` and
  `activate_command(api_version, command_id, duration)` likewise.
- **Proof, offline with fake helpers, before vs after.** Before, only `vhf1`
  was handled, and that is a local selector state change that sends nothing.
  Every simulator-touching control returned False with zero calls: `tfr1`,
  `tfr2`, `bmq2_1`, `bmq2_2`, `bmq3_1`, `stby`, `ta_ra`, `ident`, `atc_test`
  and `bmq1_1`. After, all of them dispatch - the ten above issue their
  command, and `bmq1_1` issues the squawk DataRef write.
- Tests: 13 of 14 suites pass, unchanged from before this fix.
  `tools/test_global_output_authority.py` fails identically before and after,
  on `_winctrl_throttle_blackout`, which is absent by the owner's deliberate
  revert to the state where the trim LCD works. Not touched here.
  `python launch.py --check` passed.
- Backup: `Backup/howalt_v4_live_write_helpers_20260902-112239/`.
- **Known gap, not addressed here:** the HOWALT V4 stack has no rule 0.1
  power path. There is no reference to any avionics or battery DataRef in it.
  `all_off()` exists at `howalt_v4_protocol.py:791` but its only reachable
  caller is a display command string of "all off"/"blackout", and `stop()`
  closes the port without darkening. D201/D203 are also absent from the
  device-coverage table in `tools/test_global_output_authority.py`. This
  change adds no output path; it only restores the input path.
- Live check still needed: with the aircraft powered, confirm VHF1/VHF2
  select COM1/COM2, the transfer keys flip active/standby, the four encoders
  tune, the five ATC detents drive the Zibo transponder mode, and each of the
  four encoder sections edits its own squawk digit.

## 2026-09-01 - Every PU overhead shutdown attempt removed

- None of them worked, and the owner asked for them out. Removed from
  `bridge/final.py`, restoring the original code exactly:
  - the extended pre-stop wait, back to `max(0.15, interval * 3.0)`
  - the COM5 owner's exit blackout
  - the `P2=1,P3=1` shutdown dim frame, with the optional `p2`/`p3` parameters
    and `PU_DIMMER_*` constants added for it. `build_packet` is byte-identical
    to before and `_pu_safe_dark_packet` is back to `OVHD,0,4,4,0,...`
  - `_pu_release_dim_holder` / `_pu_start_dim_holder` and both call sites
- Deleted four dead-end tools: `pu_dim_holder.py`,
  `probe_pu_shutdown_relight.py`, `probe_pu_dark_frame.py`,
  `probe_pu_vendor_minimum.py`.
- **What is kept is the part that works: when the aircraft is unpowered, every
  device goes dark.** `_pu_output_mode` still returns `aircraft-unpowered` and
  drives the PU dark; the throttle blackout still fires on aircraft power loss,
  simulator loss and handle release; AGP, ECAM, FCU/EFIS, BB35, BB36 and PAP3
  are untouched.
- The PU is now exempt from the shutdown half of rule 0.1, recorded in
  `AGENTS.md` and `DEVICE_REFERENCE.md` so it is not attempted a sixth time. It
  has no off state: it returns to its physical knob brightness about a second
  after anything stops sending it frames. Established by driving the panel
  directly three ways - closing the port, varying the frame, and sending PU
  CONNECT's own minimum - and in every case the dim lasted exactly as long as
  the stream.
- Tests: `tools/test_global_output_authority.py` trimmed 72 -> 52 checks,
  dropping everything that only guarded the removed code. The device-coverage
  table, the throttle blackout checks and the AGP power checks all remain. All
  14 suites passed and `python launch.py --check` passed.
- Backup of everything removed:
  `Backup/pu_shutdown_attempts_removed_20260901-221822/`.

## 2026-09-01 - A holder keeps the PU dim after Studio closes

- The PU has no off, and no shutdown frame can leave it dark: it returns to its
  physical knob brightness about a second after anything stops sending it
  frames. Tested against the port closing, the frame contents, PU Korea's own
  minimum, and the stream length; the dim always tracked the stream.
- The owner asked for a helper anyway, and asked the right question of it -
  if we are paying for a helper, make it hold. One correction went with that:
  a helper can hold the **dim floor**, not darkness. `P2=1,P3=1,P8=0` is as far
  as this protocol goes; only the knob reaches true off.
- Added `tools/pu_dim_holder.py`. It streams the captured vendor minimum at the
  bridge's own cadence and does nothing else. Confirmed on the hardware: the
  panel holds dim, and releases the moment PU CONNECT MSFS starts.
- **It holds COM5, which is its entire cost**, so it yields to anything with a
  better claim: PU CONNECT starting, a stop file, or Ctrl-C. It refuses to
  start while Studio or the bridge is running.
- The handover is a race, and the rate is a straight trade rather than a free
  win. Each scan enumerates every process at about 10 ms, so the 1 s default
  costs roughly 1% of one core and leaves a 1 s window; `--scan 0.2` closes the
  window at 5%. Measured, not estimated.
- Wired into the bridge, two calls and nothing else touched:
  - `_pu_release_dim_holder()` before the COM5 open at line 18997, ahead of the
    open at 19006. It asks rather than kills, and the wait is bounded: a stuck
    holder cannot hang every Studio start.
  - `_pu_start_dim_holder()` after `ser.close()`, at 24755 against the close at
    24746, so the two never hold the port at once. Launched detached so
    Studio's exit is not blocked, and told `--wait-for-exit 20` because
    MuslimSim is necessarily still alive at the moment it is launched.
- The holder gained `--wait-for-exit` for that reason: launched from a running
  Studio, it must wait for MuslimSim to disappear rather than refuse, and it
  never opens COM5 while MuslimSim still holds it.
- Tests: `tools/test_global_output_authority.py` extended 65 -> 72 checks - the
  release must precede the open, the start must follow the close, the release
  must be bounded, and the holder must be launched detached and told to wait.
  Two of those checks were wrong on the first attempt, matching the function
  definitions rather than the call sites; they now locate the call lines. All
  14 suites passed and `python launch.py --check` passed.
- Backup: `Backup/pu_dim_holder_wiring_v1_20260901-221103/`.
- Live check still needed: restart Studio so the bridge reloads, close it, and
  confirm the PU drops to dim and stays there - then start Studio again and
  confirm it takes COM5 back without complaint.

## 2026-09-01 - PU dims to the vendor's own minimum when Studio closes

- The owner captured PU CONNECT MSFS deliberately, moving its LCD and backlight
  dimmer sliders, and supplied `PU_Brightness.pcapng` so the real minimums would
  be known rather than guessed.
- The capture settles what the PU protocol is. PU CONNECT speaks the same
  `OVHD,` frames MuslimSim does, on device 49 endpoint 0x02, and its brightness
  UI moves **three** fields:
  - `P2` over 1..14
  - `P3` over 1..14
  - `P8` over 0..250
  Its all-the-way-down frame is `OVHD,0,1,1,0,12345,12345,0,0`.
- **MuslimSim has always sent a fixed `4` for P2 and P3.** They are hard-coded
  constants that the bridge header does not document - it explains P4 through
  P8 and skips straight past them - so every "dark" frame we have ever sent had
  two dimmer channels sitting at 4 while only P8 went to zero. That is why the
  panel dimmed but never went as far down as the vendor's software could take
  it.
- `build_packet` gained optional `p2`/`p3` parameters defaulting to `None`,
  which keeps the module constants. Every existing caller therefore emits
  byte-identical output; verified, a normal frame is still
  `OVHD,0,4,4,...`. Only `_pu_safe_dark_packet` passes the minimum, and the
  shutdown frame is now `OVHD,0,1,1,0,<blank>,<blank>,0,0`.
- Values are clamped to the captured 1..14 range, so a future caller cannot
  drive these fields somewhere the vendor never went.
- **The PU has no off, and that is now recorded rather than chased.** Measured
  across three probes: the panel dims but never extinguishes, and PU CONNECT's
  own minimum leaves it dim too. Rule 0.1 is satisfied for this device as far
  as the protocol allows and no further. The three probes written while
  establishing that are kept - `probe_pu_shutdown_relight.py`,
  `probe_pu_dark_frame.py`, `probe_pu_vendor_minimum.py` - because the next
  person to doubt it can re-run them instead of re-deriving it.
- Also recorded: the PU is made by **PU Korea**, not WinCtrl. The vendor was
  written down nowhere, and `PFD_PROJECT_HISTORY.md` grouped it as "or other
  WinCtrl". The catalogue now names it and carries the no-off finding.
- Noted, not changed: `P8_MAX = 125` while the vendor drives P8 to 250, so
  MuslimSim's brightness range is half the hardware's. `build_packet` already
  clamps P8 to 255, so the cap is only in `brightness_to_p8`. Raising it would
  make every panel brighter than the owner is used to, so it waits for an
  explicit decision.
- Tests: `tools/test_global_output_authority.py` extended 62 -> 65 checks. It
  asserts the shutdown frame carries the captured vendor minimum on both
  dimmers, and that a normal frame still carries the established constants so
  the shutdown values cannot leak into live output. All 14 suites passed and
  `python launch.py --check` passed.
- Backup: `Backup/pu_shutdown_dim_v1_20260901-214158/`.
- Live check still needed: close Studio and confirm the PU drops to the dim
  state rather than staying at knob brightness.

## 2026-09-01 - The throttle stayed lit because MuslimSim never darkened it on the way out

- The owner reported the PU, the throttle and the PAP3 all lighting up when
  Studio closes, and reasoned correctly that nothing else could be doing it:
  those panels reach X-Plane only through Studio, and X-Plane does not drive
  them directly.
- Three devices with separately verified blackouts lighting at the same instant
  is not three bugs. It is one cause acting after all three, and the obvious
  candidate was panel firmware returning to a lit power-on state when the last
  HID handle closes - which no amount of "write dark, then close" could fix.
- Added `tools/probe_shutdown_relight.py` to separate the two possibilities
  rather than guess between them: wake the panel, black it out with the handle
  still open, pause to look, close the handle, pause to look again.
- **Measured on the hardware: it lit, went dark, and did not relight.** The
  firmware holds the dark state after release. So the panels really were ours
  to darken and something in our shutdown simply was not doing it.
- **Found it.** `_close_winctrl_trim_display()` releases the sole B930 output
  handle and closed it without darkening anything. The throttle blackout had
  been wired to two of the three cases that need it - aircraft power lost, and
  simulator gone - but not to the third, MuslimSim itself exiting. That third
  case is the one the owner was reporting.
- Fixed inside that function, under the existing lock while it is still the
  sole owner, using the same captured `_winctrl_throttle_blackout`. All four
  callers are process-exit paths, each followed by `control_server.stop()`, so
  unlike the BB36 handoff there is no transient release here to flash.
- The other two were already handled and need only a Studio restart to take
  effect: the PU COM5 owner blacks out as it exits (fixed earlier today), and
  PAP3 blacks out when its manager-level stop event is set. Both were verified
  present again while chasing this.
- Tests: `tools/test_global_output_authority.py` extended 60 -> 62 checks. It
  now asserts that releasing the B930 handle darkens it first, and that the PU
  COM5 owner blacks out on exit. All 14 suites passed and
  `python launch.py --check` passed.
- Backup: `Backup/winctrl_close_blackout_v1_20260901-211113/`.
- Live check still needed, and it needs a full Studio restart so the bridge
  reloads: close Studio and confirm the throttle backlight, the PU overhead and
  the PAP3 all stay dark.

## 2026-09-01 - BB36 blackout gated to the final teardown; it was flashing

- The BB36 shutdown blackout added an hour earlier made the MCDU flash. The
  owner reported it immediately: "it keep flashing if we stop that flashing it
  will work".
- The blackout was put in `BB36PFDPath.stop()`, on the assumption that stopping
  a path means shutting down. It does not. That path is torn down on every
  FMC/PFD handoff and on every recovery - `_stop_active_path` alone has six
  call sites, five of which are not shutdown - so the screen was darkened and
  relit constantly.
- This is exactly the lesson `pap3_mcp.py` already carries, and it had been
  quoted in the previous entry while writing the bug: "Preserve the last valid
  frame through a short reconnect. Repeated blackouts were perceived as PAP3
  flashing." PAP3 blacks out only when its manager-level stop event is set,
  never on a transient teardown. BB36 now does the same.
- `BB36PFDPath.stop()` and `BB36FMCPath.stop()` take `final: bool = False`, and
  `_stop_active_path` forwards it. The default is off, so all five handoff and
  recovery callers keep their existing behaviour byte for byte. Only the
  supervisor loop's own exit - which happens once, when `stop_evt` is set -
  passes `final=True`.
- `BB36FMCPath` behaviour is deliberately unchanged. It already blanks its page
  on every teardown, and that blank is a handoff blank the incoming native-F0
  PFD session depends on, as its own comment says. It accepts `final` only so
  the router can stop either path the same way.
- Tests: `tools/test_global_output_authority.py` extended 57 -> 60 checks. It
  now asserts the blackout is gated - `if final and output_device is not None`
  must appear in the teardown - and that exactly one of the several
  `_stop_active_path` call sites is final. More than one means a handoff
  darkens the screen and it flashes again. All 14 suites passed and
  `python launch.py --check` passed.
- Backup: `Backup/bb36_shutdown_blackout_v1_20260901-205527/` still holds the
  pre-blackout file.
- Live check still needed: confirm the MCDU no longer flashes during FMC/PFD
  handoffs, and still goes black when Studio closes.

## 2026-09-01 - Rule 0.1 audited across every device, and made enforceable

- The owner asked for the guarantee in full: every single device dark when the
  aircraft has no power or the software is off. That deserved an audit rather
  than an assurance, so every catalogue device with implemented, testable
  outputs was checked for both a power gate and a shutdown blackout.
- Eight devices can light something: `pu_overhead` (37 outputs), `ecam32` (19),
  `winctrl_throttle` (11), `agp_bb80` (5), `fcu_32_efis` (4), `pap3_mag` (4),
  `pfp3n_bb35` (1) and `mcdu32_bb36` (1). Three more declare outputs that are
  not implemented - `pdc_bb62` and both Moza bases - and rule 0.1 leaves those
  alone rather than forcing them dark with a guessed packet.
- **`pap3_mag` was already covered, and nearly got "fixed" anyway.** Its
  `stop()` looked bare - set the event, join, set status - but `_blackout` is
  called from the session teardown when `stop_event` is set, deliberately not
  on a transient reconnect because repeated blackouts were perceived as the
  panel flashing. Its power gate is already there too:
  `display_enabled = transport_connected and avionics and ...`, and
  `lcd_backlight = 180 if avionics else 0`. Rule 0.2 is what stopped a
  pointless edit to working code.
- **`mcdu32_bb36` was the real gap.** Its router closed the output handle
  without darkening it, while the BB35 sibling immediately above it in the same
  codebase zeroes both brightness channels and the EXEC light before releasing.
  So the MCDU screen stayed lit after Studio exited.
- **How it goes dark:** the darken sequence this module already uses elsewhere
  - black background packet, `BB36_EXEC_DASH_LIGHT_CHANNEL` to `EXEC_LIGHT_OFF`,
  then brightness channels 1 and 0 to zero. Not a new sequence. It runs only
  when the worker has actually stopped; a stalled worker may still be mid-write
  on that handle, and the handle is closed underneath it exactly as before.
- **Made enforceable for devices that do not exist yet.**
  `tools/test_global_output_authority.py` now carries a blackout coverage
  table, and fails in both directions: a catalogue device with implemented
  outputs and no declared blackout fails, and a declared blackout for a device
  that no longer has outputs fails as stale. Adding a new output device now
  forces someone to say how it goes dark, which is exactly what rule 0.1 asks
  for. "It probably inherits it" is how the throttle and the BB36 were each
  missed once.
- The test additionally pins the two that were missed: the throttle blackout
  must use the captured channel report, and the BB36 router must darken between
  `def stop(` and `output_device.close()`.
- Tests: `tools/test_global_output_authority.py` extended 39 -> 57 checks. All
  other suites passed and `python launch.py --check` passed.
  `test_bridge_control_channel.py` fails only because Studio is running and
  owns COM5/HID/SDL; confirmed three times today that it passes with Studio
  closed.
- Backup: `Backup/bb36_shutdown_blackout_v1_20260901-205527/`.
- Live check still needed: close Studio and confirm the MCDU BB36 screen goes
  black rather than staying on the last page.

## 2026-09-01 - PU stayed lit at Studio shutdown: the dark frame was never sent

- The owner reported the PU Overhead lighting up when Studio is closed, lamps
  and LCD both, when rule 0.1 says a normal shutdown leaves every panel dark.
- The shutdown design was right and the packet was right. `force_dark` is
  checked first in `_pu_output_mode`, ahead of Test mode, and
  `_pu_safe_dark_packet` really is dark - verified as
  `OVHD,0,4,4,0,<blank>,<blank>,0,0`: P1 off, EGT zero, both altitude windows
  blanked, all-dark P7 mask, zero P8 brightness.
- **The dark frame was simply never written.** Switching to forced-dark also
  switches the altitude windows to their native ----- control-line state. That
  transition sets the line, then parks the writer in
  `stop_evt.wait(PU_SERIAL_DASH_LATCH_SECONDS)` - 1.50 s - and reaches
  `ser.write(packet)` only afterwards. The shutdown gave it
  `max(0.15, interval * 3.0)` first, which is **0.15 s** at the default 0.05 s
  interval, then set `stop_evt`. The wait returned early, the writer broke out
  of its loop before writing anything, and the panel kept its last lit mask.
  Ten times too short, and only on the one transition that shutdown always
  triggers.
- The caller's own backstop could not cover it either: the final
  `_pu_write_safe_dark_frame` is deliberately skipped while the writer thread
  is still alive, because two writers on COM5 is the one thing that must never
  happen.
- Two fixes, both additive, nothing existing restructured, per rule 0.2:
  - The pre-stop wait now outlasts the latch:
    `max(0.15, interval * 3.0) + PU_SERIAL_DASH_LATCH_SECONDS +
    PU_SERIAL_VALUE_SETTLE_SECONDS`, so 1.70 s instead of 0.15 s. The latch
    itself is capture-proven and untouched; only the wait around it changed.
  - `_serial_output_worker` now writes the safe dark frame as it exits.
    However the loop ended, that thread is the sole COM5 owner right up to the
    moment it returns, so it is the one place a final blackout needs no
    two-writer guard at all. It closes the gap the caller cannot reach.
- **How it goes dark**, as rule 0.1 now requires every output path to state:
  the existing captured `_pu_safe_dark_packet`, written three times at cadence
  by `_pu_write_safe_dark_frame`, with the serial line forced to the dash
  state first. No new packet and no new value.
- Tests: `tools/test_global_output_authority.py` extended to 39 checks. It
  asserts the dark packet really is dark field by field, that the pre-stop wait
  outlasts the dash latch - the exact arithmetic that was wrong - and that the
  COM5 owner blacks out as it exits. All 14 suites passed and
  `python launch.py --check` passed.
- Backup: `Backup/pu_shutdown_dark_latch_v1_20260901-204821/`.
- Live check still needed: close Studio with the PU lit and confirm the lamps,
  the backlight and both altitude windows all go dark before the port closes.
  Shutdown now takes about 1.6 s longer, which is the latch being allowed to
  finish.

## 2026-09-01 - Rule 0 added, and the throttle now goes dark with the aircraft

- The owner made two standing rules, and asked for them to outrank everything
  else in `AGENTS.md`. Both are now `Rule 0`, at the top of that file, to be
  checked before starting a task and again before calling one finished.
- **Rule 0.1 - no output lights while the aircraft is unpowered.** Screens
  black, lamps dark, backlights off, windows blank. It covers the WinCtrl
  throttle backlight, every panel currently connected through Studio, and every
  device added in future - a new device inherits the rule the day it is added,
  without being named. Test mode still lights only the output under test. A
  device with no capture-proven safe OFF is left alone and flagged, never forced
  dark with a guessed packet. Unknown counts as unpowered. Any new output path
  must state in its changelog entry how it goes dark.
- **Rule 0.2 - never disturb something that already works.** Fix the smallest
  broken part; do not restructure working code around a defect. Prefer a new
  parameter whose default preserves current behaviour over editing an existing
  path, so every existing caller behaves exactly as before. Prove it where the
  proof is cheap. If a fix appears to require changing a working part, stop and
  ask first.
- **The throttle was the gap in rule 0.1.** Its wake sequence lights the
  backlight when the HID handle opens, regardless of whether the aeroplane has
  any electrical power, and the existing authority work covered the AGP, ECAM,
  FCU/EFIS and BB36 but never the B930.
- Added `_winctrl_throttle_blackout` and `_winctrl_throttle_restore_defaults`.
  **How it goes dark:** both write the captured channel report built by
  `_winctrl_throttle_output_packet`; only the value differs, and 0 is that
  protocol's own off. Verified every blackout report is byte-identical to
  `_winctrl_throttle_output_packet(key, 0)` and keeps the captured 14-byte
  length. No packet was invented. The numeric window needed no blank glyph mode
  either: `trim_display_backlight` is itself a captured channel, so taking it to
  0 darkens the window.
- The power source is the PU aircraft-power dataref, not anything
  throttle-specific, because rule 0.1 is one rule about the aeroplane rather
  than a per-device opinion. Any future device should read the same value.
- The authority block follows the existing AGP one deliberately, so both
  devices behave identically: only while the simulator is up, only outside Test
  mode, rate limited to 0.5 s, and written only on an actual change of state.
  A lost simulator also blacks the throttle and resets the remembered state to
  unknown, so recovery re-applies rather than trusting a stale belief.
- Rule 0.2 was followed here: nothing existing was edited. Two new helpers, one
  new authority block beside the AGP one, and one blackout call added to the
  offline path. The wake sequence, the display writer, the trim paths and every
  other output are untouched.
- Tests: `tools/test_global_output_authority.py` extended to 30 checks - the
  blackout must cover every declared channel, each report must equal the
  captured builder at 0, reports must keep the captured length, and both the
  throttle backlight and the window backlight must be covered. All other suites
  passed and `python launch.py --check` passed.
  `test_bridge_control_channel.py` fails only because Studio is running and
  owns COM5/HID/SDL; it passes with Studio closed, as confirmed twice today.
- Backup: `Backup/winctrl_throttle_output_authority_v1_20260901-203704/` and
  `Backup/AGENTS_before_output_power_rule_20260901-203505.md`.
- Live check still needed: with the aircraft cold and dark, confirm the throttle
  backlight, the flaps/airbrake backlight and the RUD TRIM window are all off,
  and that they come back when the battery is switched on.

## 2026-09-01 - The stabilizer readout was refused silently, and Practice was gated on the wrong thing

- The owner reported the RUD TRIM window blank, having worked in Practice
  before. Reading found nothing: the practice handler was byte-identical to the
  version that worked, the catalogue control, profile switch, device
  registration and startup init were all intact, the output authority never
  touched that region, `device_lifecycle` wraps only the AGP opener, and the
  display packets were proven byte-identical before and after the recent work.
- So the display was driven directly instead, through the bridge's own opener
  and writer (`tools/probe_winctrl_trim_display.py`, new). The window showed
  every value: `L 2.5`, `R 1.0`, `0.0`, then `4.9` and `15.8` in the new units
  mode. The driver accepted all writes, returning 64 bytes each, and the packet
  header matched the capture. The display path was healthy; the fault was in
  what reached it.
- **Bug found, introduced earlier the same day.** `stab_trim_display` was
  written through `control_server.apply_lab_output`, which validates every
  control against the catalogue - and it had deliberately been given no
  catalogue entry, on the reasoning that a bridge-owned readout does not need a
  Studio-mappable control. That reasoning was wrong for the routing path
  chosen: `lab.output` raises `Unknown control`, the Practice sink swallows the
  error into a diagnostic, and the live loop catches it, so **both** stabilizer
  readout paths failed completely silently.
- Added the `stab_trim_display` output to the catalogue. It is the same
  physical window and the same two captured reports, declared as the unsigned
  units mode. Keeping it in the catalogue also keeps the device-enabled and
  profile checks that bypassing the lab would have skipped.
- **Practice no longer gates the rocker on the MODE trim role.** The rocker is
  hard-wired to the stabilizer in Live, so Practice now moves a simulated
  stabilizer value and writes it to the window in units, 0.1 per press. The old
  path read `if role not in winctrl_trim_values: return`, which returns
  silently whenever MODE sits in IGN/START - indistinguishable from a dead
  display. Only the reset contact stays role-owned, because centring is what
  MODE actually selects.
- `winctrl_trim_values` gained a `STAB` entry starting at 4.9, a normal
  on-ground setting rather than 0.0, which is not a trim position a 737 is
  found in. The existing `RUDDER` and `AILERON` entries and the status mirror
  are unchanged.
- Extended `_run_winctrl_trim_display_self_test` to close the hole for good: it
  now asserts that every window mode the bridge writes exists as a catalogue
  control and is implemented and testable. Verified it catches the exact bug -
  removing the entry fails with "written by the bridge but is not a catalogue
  control, so every write to it is refused silently".
- Tests: all 14 suites passed and `python launch.py --check` passed.
- Backups: `Backup/winctrl_practice_stab_trim_v1_20260901-202617/`.
- Live check still needed: in Practice, hold the rocker and confirm the window
  now counts in trim units regardless of where MODE is sitting.

## 2026-09-01 - RUD TRIM window reads out the stabilizer trim it is setting

- Follow-up to the rocker hard-wire. The rocker moved pitch while the numeric
  window beside it still read rudder trim, which was recorded at the time as an
  inconsistency rather than smoothed over. The owner asked for the window to
  work while trimming, so it now shows live stabilizer units.
- Source: `laminar/B738/flight_model/stab_trim_units`, the same units the real
  737 trim indicator shows, read from the running aircraft (4.899 at the time).
  Zibo publishes its own travel limits beside it - `def_elevator_trim_dn` 4.8
  and `def_elevator_trim_up` 15.8 - which is what proved the signed rudder
  scale could not carry it.
- The window is four cells: a direction glyph, tens, ones and tenths. The
  captured glyph table holds only digits, `L`, `R` and blank. A trim setting is
  not a left or a right, and no honest U/D glyph can be built from that table
  without inventing segment patterns the capture never proved, so the units
  readout leaves the leading cell **blank**: `4.9` renders as `"  49"` and
  `15.8` as `" 158"`.
- The signed rudder path is untouched. `_winctrl_trim_segment_planes`,
  `_winctrl_trim_display_packets` and `_winctrl_write_trim_display` gained a
  `signed=True` keyword, so every existing call behaves exactly as before:
  `-2.5` still renders `"L 25"` and `1.0` still renders `"R 10"`.
- Bounds are separate rather than widened. `WINCTRL_TRIM_DISPLAY_MIN/MAX` stay
  at +/-10.0 for rudder and aileron; the units readout uses
  `WINCTRL_STAB_TRIM_DISPLAY_MIN/MAX` of 0.0 to 19.9, which is what three digit
  cells can physically render. Above that it saturates rather than wrapping to
  a smaller, believable, wrong number.
- `stab_trim_display` is accepted by the existing single writer as a second way
  to address the same window. **Correction, same day:** it was first left out of
  the catalogue on the reasoning that a bridge-owned readout needs no
  Studio-mappable control. That reasoning was wrong and is recorded here
  because it caused a silent failure - see the entry above.
- The readout is tied to the trim repeat, not polled. Nothing is read from the
  simulator unless the rocker is actually being held, and one final reading is
  taken after release so the settled trim stays on the window instead of
  stopping at whatever was mid-movement. A read error backs off to 0.5 s and
  gives up once the rocker is home.
- Extended `_run_winctrl_trim_display_self_test` again: no stabilizer value may
  light the direction cell, the units mode must not reuse the clamped signed
  scale, and the readout must saturate at the window maximum. Verified it
  catches a regression - pointing both rocker directions at one command fails
  with "directions must be opposite".
- Tests: all 14 suites passed, `python launch.py --check` passed.
  `test_bridge_control_channel.py` passes again now that Studio is closed,
  confirming its earlier failure was environmental - it starts a second bridge
  that cannot take COM5/HID/SDL while Studio holds them.
- Backup: `Backup/winctrl_trim_lcd_stab_units_v1_20260901-200602/`.
- Live check still needed: hold the rocker and watch the window count in trim
  units alongside the stab trim wheel, then confirm the settled value stays
  after release.

## 2026-09-01 - RUD TRIM rocker hard-wired to the Zibo stabilizer trim wheel

- The owner asked for the physical RUD TRIM knob on the WinCtrl URSA MINOR to
  drive the Zibo pitch/stabilizer trim wheel, hard-coded, independent of the
  MODE rudder/aileron trim-role selector.
- Confirmed the hardware first rather than assuming it: the rocker is a
  three-contact spring switch on B930 buttons 26 (LEFT), 27 (spring centre)
  and 28 (RIGHT), already mapped in both bit tables. Only 26 and 28 latch a
  held state; 27 needs no action because releasing 26/28 already stops the
  repeat.
- Confirmed the commands against the running aircraft rather than guessing
  names: `laminar/B738/flight_controls/pitch_trim_up` and `pitch_trim_down`
  exist in the loaded Zibo's inventory and resolve to command ids 4475 and
  4476. These are Zibo's own captain-side electric trim commands - the pair
  the yoke trim switches use, which is what turns the stab trim wheel. The
  `fo_pitch_trim_*` pair is deliberately not used: this is the captain's
  quadrant.
- The repeat loop previously built its command as
  `f"{role.lower()}_{direction}"` from the MODE selector, and did nothing at
  all when MODE sat in IGN/START. It now reads
  `WINCTRL_PITCH_TRIM_COMMANDS[direction]`, so the rocker trims pitch in every
  MODE detent including IGN/START.
- The repeat cadence (0.10 s held, 0.25 s backoff), the held-state latches and
  the mutual-exclusion between left and right are the proven rudder/aileron
  ones and are unchanged. Only the command chosen differs.
- Direction follows the convention already used everywhere else on this
  quadrant - left decreases, right increases - so LEFT is nose down and RIGHT
  is nose up. `WINCTRL_PITCH_TRIM_COMMANDS` is the single place that decides
  it; swapping its two values is the whole change if it feels backwards on the
  physical unit.
- A Studio binding on these contacts still wins. `_muslimsim_observe_lab_event`
  consumes the event and the live loop does `continue`, so the native
  hard-wired path never sees a contact the owner has remapped. No double
  command is possible.
- Deliberately left alone, and worth knowing: the MODE selector, the RUD TRIM
  numeric window, and the reset contact (button 25) keep their existing
  rudder/aileron behaviour. Only the rocker moved. That means the numeric
  window still reads the selected role's trim, not stabilizer units.
- Extended `_run_winctrl_trim_display_self_test` so this cannot drift silently:
  it now asserts both pitch command names, that the rocker maps exactly `left`
  and `right`, that the two directions are not the same command (which would
  trim one way only and look like a stuck switch), and that both resolve to
  real keys in `WINCTRL_COMMANDS`.
- Updated the catalogue's `default_role` text for the two contacts to say
  plainly what they now do. The printed face label still reads RUD TRIM.
- Tests: `python launch.py --check` passed, which runs the extended self-test.
  Full suite re-run - 13 of 14 passed. The single failure,
  `test_bridge_control_channel.py`, is environmental and pre-existing: it
  starts a second bridge, which cannot take COM5/HID/SDL while Studio is
  running, so it never reports a loopback port. It passes with Studio closed
  and is unrelated to this change.
- Backup: `Backup/winctrl_rud_trim_to_pitch_trim_v1_20260901-194945/`.
- Live check still needed: hold the rocker each way and confirm the stab trim
  wheel turns and `sim/cockpit2/controls/elevator_trim` moves in the expected
  direction. It read `-0.390` before this change.

## 2026-09-01 - False green altitude-tape hatch removed

- Traced the bright green horizontal bands on BB35/BB36 to the renderer's
  destination-field-elevation hatch, not to the diagonal-line/font trials.
- Zibo's `laminar/B738/fms/dest_runway_alt` supplies an FMC elevation value,
  but no matching PFD visibility state. The renderer no longer treats that
  value alone as permission to cover the altitude tape with a green/black
  pattern.
- Preserved the altitude drum, target-altitude bug, trend vector, tape labels,
  V/S geometry and differential report counts unchanged.
- Saved the prior renderer as
  `Backup/pfp_renderer_before_field_elevation_gate_20260901-203000.py`.
- PFD, simulator-offline and all 15 output-authority checks pass.

## 2026-09-01 - Automatic LevelUp, ToLiss and C172 NG Digital workspaces

- Added read-only `.acf` path classification for the installed LevelUp
  `737NG_Series_V2`, all ToLiss family folders, and the AirfoilLabs
  `C172 NG DIGITAL`; the default Laminar C172 remains generic and cannot be
  mistaken for the AirfoilLabs aircraft.
- Published the confirmed aircraft identity through the private Studio status
  channel. Studio now moves to the matching isolated mapping/profile file
  automatically after X-Plane loads an aircraft, including when Studio was
  started first.
- Added the `C172 NG DIGITAL` Studio workspace and its independent
  `hardware_profiles_c172ng.json` profile.
- Imported `2,380` applicable standard X-Plane commands from the owner's
  installed `Resources/plugins/Commands.txt`, including `237` G1000 commands.
  When the C172 is live, its Web-API command inventory replaces this offline
  list so newly registered aircraft-plugin commands can also be assigned.
- Kept Zibo-only commands and axes out of the C172 catalogue. C172 saved
  mappings may use its generic hardware readers only after both the selected
  workspace and loaded AirfoilLabs aircraft match; Boeing defaults remain off.
- Added C172 catalogue, aircraft status and isolation coverage to the hardware
  self-test and added real/fallback C172 path cases to the aircraft-profile
  self-test.
- Preserved the prior state at
  `Backup/aircraft_autodetect_c172_catalog_before_20260901-202500/`.
- Passed aircraft-profile, Studio handoff, hardware-lab, startup-safety,
  simulator-offline, PFD, launcher and all 15 output-authority checks.

## 2026-09-01 - Live zoom, compact text and two-circle ND PLAN page

- Added Zibo captain range-detent input and normalized all eight EFIS ranges;
  the generic X-Plane NM value remains the fallback.
- Put the range detent on the immediate ND snapshot, so MAP and PLAN react as
  soon as the hardware zoom selector moves.
- Corrected PLAN route projection to use the same centred north-up geometry as
  its visible rings instead of expanded MAP's low aircraft origin.
- Replaced BB35/BB36 ND text with the PFD's tightly packed slot-3 micro glyphs.
  Joined GS/TAS and range/NM, guarded every character inside the bezel-safe
  area, and used true compact widths for waypoint labels.
- Replaced PLAN's crowded compass rose with exactly two clean distance circles
  for half/full selected range, plus `N`, route legs and waypoint names.
- Added hidden three-band construction for page entry, MAP/PLAN changes and
  scheduled recovery.
  Only the complete page receives the LCD refresh; the largest burst is `272`
  reports and no partial band is shown.
- Added `tools/check_nd_zoom_compact.py`. MAP zoom costs at most `225` reports,
  PLAN zoom at most `173`, and a steady page sends zero.
- Preserved the prior state at
  `Backup/nd_before_zoom_compact_plan_20260901-191500/`.
- Passed compact-ND, PFD, startup, simulator-offline, launcher and all 15
  output-authority checks.

## 2026-09-01 - Complete MAG arc no longer alternates between halves

- Removed the timed left/right PFD healing swaps after the physical BB35/BB36
  showed that an untouched half is not retained reliably.
- Kept full, atomic recovery on PFD page entry, simulator reconnect and return
  from standby. Normal live movement remains differential and immediate.
- Kept compact text phase stable; elapsed time alone can no longer widen text
  or replace half of the visible MAG arc.
- Added a 122-frame long-hold regression. It remains pixel-identical to a full
  repaint with a median of one report.
- Preserved the prior state at
  `Backup/pfd_before_full_compass_healing_20260901-185200/`.
- Passed the PFP self-test (`287` page entry, `266` maximum refinement, `1`
  steady and `1` elapsed-hold report), pixel-identical differential suite,
  hybrid-transparency verification, startup safety, simulator-offline reset,
  launcher validation and all 15 output-authority checks.

## 2026-09-01 - Clean banked lines with software-transparent text cells

- Kept the proven clean native 10/20-degree rung glyph when its complete cell
  is safely over one sky/earth colour.
- Replaced only a boundary-crossing cell with foreground-only rectangles from
  that exact glyph mask. The live sky/earth field is therefore untouched even
  though WinCtrl firmware ignores native text alpha.
- Applied the same conditional foreground-only fallback to slot-3 pitch
  numbers and letters. Normal cells retain the fast native path.
- Extended the generated plan with exact masks for all 183 line glyphs and all
  95 printable slot-3 characters; the uploaded font binary is unchanged.
- Added `tools/check_pfp_hybrid_transparency.py`. It validates every mask
  pixel, rejects any opaque cell that crosses the moving background, and
  exercised 336 masked rung cases across the pitch/bank grid.
- Preserved the prior state at
  `Backup/pfd_before_hybrid_transparency_20260901-183400/`.
- Passed the PFP self-test (`287` page entry, `266` maximum refinement, `1`
  steady and `267` healing reports), hybrid transparency check, pixel-identical
  differential suite, startup safety, simulator-offline reset, launcher
  validation and all 15 output-authority checks. No banking QA image was kept.

## 2026-09-01 - Settled PFD numbers no longer widen during healing refreshes

- Fixed the reported size pulse after several seconds. The 120-frame healing
  refresh was resetting compact typography to phase zero for one visible LCD
  swap, then rebuilding it over the next refinements.
- Kept phase zero only for genuine page entry. Once the compact text has
  settled, every later healing pass retains phase three, so values never
  change width or spacing.
- Split settled healing into alternating exact left/right half-screen passes.
  Dirty live regions in the other half are included immediately, so speed,
  altitude and attitude changes never wait for the next healing pass.
- Added a regression that forces both healing halves, requires the compact
  phase to remain settled and enforces the 290-report BB36 ceiling. The
  worst half is `267` reports.
- Preserved the prior state at
  `Backup/pfd_before_stable_compact_recovery_20260901-174849/`.
- Passed the PFP self-test (`283` page entry, `265` maximum refinement, `1`
  steady and `267` maximum healing reports), the pixel-identical differential
  suite, startup safety, simulator-offline reset, launcher validation and all
  15 output-authority checks.

## 2026-09-01 - Bottom PFD values aligned beneath their tapes

- Moved the complete BARO/HPA value from y=435 to y=404, directly beneath
  the altitude tape at x=480..552.
- Moved the RADIO/BARO minimums annunciation to the next line at y=435 and
  right-aligned it to the same altitude-tape edge. RADIO therefore appears
  below `1013HPA` instead of taking its position above it.
- Moved both left-side rows from x=14 to the speed tape's x=90 edge. The Mach
  readout now keeps its leading `M` visible (`M.62` rather than a detached
  `.62`), and `LS113.3` starts on the same vertical line immediately below.
- Preserved the prior state at
  `Backup/pfd_before_bottom_strip_alignment_20260901-174040/`.
- Passed the PFP self-test (`283` full, `265` maximum refinement and `1`
  steady report), the pixel-identical differential suite, startup safety,
  simulator-offline reset, launcher validation and all 15 output-authority
  checks. The retained four-value QA is level-wing only.

## 2026-09-01 - Altitude box right wall moved another two millimetres inward

- Kept the altitude box nipple, left edge, compact digits and overall anchor
  fixed. Moved only its right wall another 12 LCD pixels left, from x=578 to
  x=566, which is approximately two physical millimetres on the panel.
- Kept the V/S silhouette and its needle fixed. The centre notch remains at
  x=586, so the clean black separation from the altitude box is now 20 pixels.
- Left the rolling altitude cells at their proven positions ending at x=551;
  altitude movement therefore remains isolated from the V/S redraw region.
- Preserved the complete previous state at
  `Backup/pfd_before_altitude_wall_2mm_inward_20260901-172940/`; Point A,
  Point B and all earlier restores remain untouched.
- Passed the PFP self-test (`283` full, `265` maximum refinement and `1`
  steady report), the pixel-identical differential suite, startup safety,
  simulator-offline reset, launcher validation and all 15 output-authority
  checks. The retained QA is level-wing only.

## 2026-09-01 - White aircraft contour and compact PFD value typography

- Added a thick white contour around the complete black aircraft reference:
  both wings, inner hooks and the centre square. The contour is installed on
  the precision frame so the BB36 page-entry frame keeps its protected budget.
- Moved the BARO value/unit zone to exactly the altitude tape's 72-pixel span
  at x=480..552. Values such as `1013HPA` and `29.92IN` now sit directly below
  the grey altitude tape rather than extending toward the V/S display.
- Rebuilt slot 3 with every micro value glyph left-aligned inside the proven
  17x29 opaque cell. Digits, decimal points and value letters are advanced only
  after their visible ink ends, applying compact spacing across PFD value
  fields without clipped characters or a new font header.
- Staged the compact value groups over three refinement frames. The final
  appearance is unchanged, while no individual refinement exceeds the full
  frame traffic guard. Tests pass at `283` full, `265` maximum refinement and
  `1` steady report.
- Preserved the complete previous state at
  `Backup/pfd_before_white_reference_and_packed_type_20260901-171924/`.
  Differential output remains pixel-identical; startup, simulator-offline,
  launcher and all 15 output-authority checks pass without hardware.

## 2026-09-01 - Altitude box shortened only from its right end

- Kept the established nipple, left edge and entire box position fixed.
  Shortened only the outboard end by moving the right wall six pixels left,
  from x=584 to x=578.
- Kept the V/S silhouette at x=586. The corrected geometry now has eight
  black pixels between the white altitude-box wall and the grey V/S shape,
  comfortably exceeding one physical millimetre on the PFP LCD.
- Left every compact altitude digit and rolling-cell position unchanged, so
  altitude motion remains isolated from the V/S redraw region.
- Preserved the prior state at
  `Backup/pfd_before_shorter_altitude_right_wall_20260901-171210/`; Point B
  and all earlier restores remain untouched.
- Passed the PFP self-test (`281` full, `220` refinement, `1` steady), the
  pixel-identical 12-frame differential suite, startup and offline-reset
  tests, launcher validation and all 15 output-authority checks. The QA frame
  is level-wing only; bank-angle previews are no longer used for this work.

## 2026-09-01 - Altitude-box outboard wall refined without V/S coupling

- Extended the live-altitude box two pixels outboard, moving its right wall
  closer to the simulator proportion.
- Rebuilt the native slot-3 V/S silhouette around the new edge. The V/S grey
  shape still begins after a two-pixel black gap, so it never touches the
  white altitude-box outline.
- Kept the compact rolling altitude cells unchanged: their final cell still
  ends at x=551 inside the altitude-tape dirty column, so altitude changes do
  not drag the V/S tile into the same redraw region.
- Preserved the exact post-banking, pre-refinement state at
  `Backup/pfd_before_altitude_box_outboard_20260901-170044/`; Point B and every
  earlier restore remain available.
- Passed the PFP self-test (`281` full, `220` refinement, `1` steady), the
  pixel-identical 12-frame differential suite, startup safety,
  simulator-offline reset, launcher validation and all 15 output-authority
  checks without opening X-Plane or hardware.

## 2026-09-01 - Black aircraft reference now banks with the aeroplane

- Changed the complete black aircraft reference from level-fixed to one rigid
  roll-following assembly. In a left bank its left wing moves down and its
  right wing moves up; a right bank mirrors that motion.
- The two thick wings, inner hooks and hollow centre square all rotate around
  the centre together. The white natural-horizon separator keeps its existing
  opposite movement.
- Added a layout regression for the left-bank direction. A low-command
  recovery silhouette protects the BB36 USB budget, followed immediately by
  the exact continuous scanline geometry.
- Preserved the previous state at
  `Backup/pfd_before_banking_aircraft_reference_20260901-165125/`. Point A,
  Point B and all earlier restores remain untouched.
- Verification passed: PFP PFD self-test (`281` full, `220` refinement and
  `1` steady report) plus the 12-frame differential repaint suite.

## 2026-09-01 - Black fixed aircraft reference matched to the simulator PFD

- Corrected the initial interpretation of the simulator photograph. The black
  reference is not the moving blue/brown separator; it is the fixed aircraft
  symbol made from two opposed thick wings and the small hollow centre square.
- Restored the moving natural-horizon separator to white. Changed only the
  fixed aircraft wings, inner hooks and centre square from white to black.
  Their position remains fixed while the horizon and pitch indications move.
- Added a layout regression that keeps the natural-horizon separator white.
  The pre-change state is in
  `Backup/pfd_before_black_horizon_and_full_clean_ladder_20260901-174100/`;
  Point A and Point B remain untouched.
- Verification passed: renderer syntax, the PFP PFD protocol self-test
  (`280` full, `191` refinement and `1` steady report), and the 12-frame
  differential repaint suite. The generated normal and high-bank QA frames
  also keep the moving separator white and only the fixed aircraft reference
  black.
- Confirmed from the emitted command stream that labelled 10/20-degree lines
  are using native slot 8. Added an offline full-ladder sizing tool; the
  unfinished appearance is from the still-coded 2.5/5-degree marks, not a
  silent fallback of the labelled lines.

## 2026-09-01 - Continuous background-matched pitch rungs for BB35/BB36

- Preserved the complete pre-integration state in
  `Backup/pfd_before_masked_continuous_rungs_20260901-161500/`; Point A,
  Point B and every earlier restore remain untouched.
- Completed the physical background investigation on BB35. Alpha, shortened
  background commands and alternate font-header fields all remained opaque.
  The successful card drew two clean white continuous diagonals: one wholly
  over blue and one wholly over brown, with each opaque native text cell set
  to the exact local field colour. Both cell rectangles disappeared while
  both lines remained clean. This is now the production method.
- Replaced the rejected individual 24 x 20 segment glyphs with complete paired
  10/20-degree rungs rasterised once and cut into 40 x 40 native cells. The
  generated table covers an exact level line, two-degree steps, and exact
  -45/+45 endpoints. Its 183 unique tiles fit in proven slots 7 and 8 (95 and
  90 glyphs including each blank), and the 64,689-byte slot-3/4/5/6 resource
  remains the exact prefix of the live resource.
- Added `pfp_bank_line_plan.json`, which groups adjacent tiles into at most
  three native text runs per complete rung. The renderer tests all four
  corners of every opaque 40 x 40 cell against the moving natural horizon and
  rounded attitude shell, then uses the exact production sky or earth colour.
  The existing exact coded path remains only as a geometry safety fallback
  when an entire native cell cannot be admitted.
- Updated the resource self-test and offline frame emulator for both variable
  native slots. Generated normal and 45-degree QA frames contain no black
  cells, color crossings or broken tile joins. No PNG is used at runtime.
- Passed syntax parsing, resource round-trip and prefix validation, the PFD
  packet/layout self-test (280 full, 190 refinement, one steady report),
  normal and extreme offline rendering, pixel-identical differential motion
  through all suites, launcher integrity, startup safety, simulator-offline
  recovery and all 15 global output-authority checks. Current differential
  medians are 70 reports in cruise, 218 while turning, 64 under jitter, 247
  through mode/extreme changes and one when steady. Remaining check: restart
  Studio so the new resource uploads, then inspect live banking on BB35 and
  BB36.

## 2026-09-01 - Clean native pitch-line glyphs with opaque-cell safety

- Preserved the complete pre-integration state in
  `Backup/pfd_before_bank_line_font8_20260901-143357/`; Point A, Point B and
  every earlier restore remain unchanged.
- Completed the physical fallback experiment after the undocumented line
  commands failed. A tiled text-glyph diagonal appeared clean on both BB35
  and BB36, and a corrected 128 x 128 single-glyph diagonal also appeared on
  both. An alpha-zero background test produced a white line inside a black
  box, proving that the controller always paints the complete text cell and
  does not support transparent glyph backgrounds.
- Added `tools/build_pfp_bank_line_font.py` and generated
  `winctrl-pfp-b737-cockpit-font3-4-5-6-8.xpwwf`. Its first 64,689 bytes are
  the current slot-3/4/5/6 resource byte-for-byte. Slot 8 adds 5,952 bytes of
  glyph memory (7,605 resource bytes including command/report framing): blank
  space plus 92 clean 24 x 20 pitch-segment glyphs covering -45 through +45
  degrees in two-degree steps and two background-side anchors.
- The live renderer uses slot 8 only for the separated left/right segments of
  labelled 10/20-degree pitch rungs. Before every draw it checks all four
  corners of the opaque cell against the rounded attitude window and the
  moving natural horizon. A cell wholly above receives the exact sky colour,
  a cell wholly below receives earth, and a cell that could touch or cross the
  boundary falls back to the existing exact rectangle raster.
- Clean glyph cells draw first; exact 2.5/5-degree rungs and numerical labels
  draw afterward, so an opaque background cannot erase a nearby minor line.
  The horizon, bank ticks, pointer and every other PFD element keep their
  proven code-drawn paths. No PNG is loaded at runtime and no rejected
  `0x115`-`0x117` function entered production.
- Updated the offline frame emulator for variable native cell sizes and added
  `assets/pfp-bank-line-font8-preview.png` plus
  `PNG/pfp-slot8-check-extreme.png`. The extreme preview contains no black
  cell, sky-over-earth cell or earth-over-sky cell.
- Passed the resource/prefix guard and PFD self-test at 280 full, 190
  refinement and one steady report. Differential output was pixel-identical
  to a forced repaint through cruise, turning, jitter, mode/extreme, periodic
  recovery and live/offline/live sequences; traffic medians were 70, 203, 64,
  246 and one report. Launcher integrity, startup safety, simulator-offline
  reset and all 15 global output-authority checks also passed without opening
  X-Plane or hardware. Remaining check: restart Studio and inspect the live
  PFD on BB35 and BB36.

## 2026-09-01 - BB35/BB36 native-line experiment completed (no primitive found)

- Preserved the exact current renderer and documentation in
  `Backup/pfd_before_undocumented_line_experiment_20260901-133542/`. The
  owner's Point A and Point B restores remain untouched.
- Confirmed why the temporary 45-degree recovery frame looks blocky: its
  exact scanline spans are compressed into a few bounding rectangles. The
  settled refinement is exact, but the moving/recovery approximation is not
  visually acceptable and has not been declared finished.
- Added read-only inspectors for SimAppPro's Electron archive, native WinCtrl
  modules and cached firmware. SimAppPro exposes rectangle, font, colour,
  text and refresh commands (`0x110` through `0x114`) but leaves `0x115`
  through `0x117` unused in JavaScript; its next exposed command is the text
  grid at `0x118`.
- Found the downloaded `MCDU-32` and `PFP-3N` firmware containers. Their
  235,230-byte bodies are identical and only the clear one-byte panel
  identifier differs. The common body is block-encrypted; an exhaustive
  2,961,270-key-window AES check found no key in `WWTHID_JSAPI.node` or
  `WWTHID.dll`, so no command meaning was guessed from encrypted bytes.
- Added `tools/probe_pfp_native_line.py`, an isolated display-only test for one
  candidate function and payload at a time. It never contacts X-Plane or other
  controls, draws four known witness blocks, and refuses to open BB35/BB36
  while MuslimSim Studio or `launch.py` is running. It is not wired into the
  production renderer.
- Physically tested the same 15 combinations on both BB36 and BB35 (30 cards
  total): candidate IDs `0x115`-`0x117` with endpoint16, endpoint16 plus
  16/32-bit thickness, endpoint32 and origin/size payloads. Every card received
  F0 acknowledgements and displayed its four cyan witness blocks, but none
  produced a white diagonal. These IDs/layouts are therefore rejected on both
  panels and will not be added to production.
- The probe now performs Studio's proven F2 blank + F0 clear + HID reopen
  reinitialization before each card, then wakes only the selected screen. This
  removed the need for a manual unplug between later tests. A real Windows USB
  restart remains Administrator-only and is never falsely reported as done.
- Restored BB36 and BB35 to clean dark pages after their final tests. Python
  compilation passed for the updated probe. The safe rectangle/text renderer,
  Point A, Point B and the pre-experiment backup remain unchanged.

## 2026-09-01 - Replace block-built angled marks with solid rotated strokes

- Preserved the preceding radially aligned version in
  `Backup/pfd_before_solid_angled_ladder_20260901-132715/`. Point A, Point B
  and every earlier rollback point remain untouched.
- Split the two bank slopes that had incorrectly been tied together. The
  moving triangle and every small numbered pitch-ladder rung now bank together
  by the aeroplane's angle, while the thick sky/earth horizon banks in the
  opposite direction.
- Rotated the numbered ladder as one rigid assembly instead of merely tilting
  every rung around a fixed x-coordinate. Every rung centre now lies on the
  radial centreline of the small upward-pointing triangle that moves along the
  bank arc. The downward-pointing triangle that remains at the top centre is
  only the fixed zero-bank index and no longer appears to control the ladder.
- Replaced the pitch ladder's major-axis square-run raster with a true rotated
  rectangle. Its thickness is measured perpendicular to the requested angle,
  its ends are extended to their pixel centres, and each LCD row receives one
  unbroken scanline span. Shallow, steep and exact 45-degree strokes are now
  edge-connected rather than corner-connected diamond chains.
- Kept the labelled 10/20 rungs split around the reference centre, but made
  every unlabelled 2.5/5-degree mark one continuous centred two-pixel stroke.
  The controller has no proven native line command, so this uses only the
  established safe colour/fill protocol and no PNG.
- In a right bank the triangle moves right and the 10/20 ladder has its left
  side up and right side down; the bold horizon has its left side down and
  right side up. A left bank is the exact mirror. The layout regression now
  locks all three relationships independently.
- Kept the moving pointer as a filled radial triangle aimed at the fixed bank
  scale. The slip/skid marker rotates beneath that pointer, aligns with it in
  coordinated flight and moves tangentially for slip or skid.
- Retained the clean code-drawn attitude geometry: paired continuous ladder
  lines with a centre gap, solid radial bank ticks, no lower hooks and a white
  sky/earth separator. No PNG is loaded by the live display.
- Kept the V/S needle's fixed pivot at `(626,226)`, the centre of the V/S
  strip's far-right edge. Its inboard end follows climb/descent while the
  outboard pivot stays centred.
- Passed at 286 full, 204 refinement and one steady report. Differential
  output remained pixel-identical to full repaints; traffic medians were 70
  reports in cruise, 205 while turning, 64 under jitter, 249 in
  modes/extremes and one at steady state. Startup, simulator-offline reset,
  launcher and all 15 output-authority/blackout checks passed offline. Live
  BB35/BB36 inspection remains required after restarting Studio.

## 2026-09-01 - Aircraft-shaped PFD altitude and V/S right strip

- Preserved the complete post-Point-B starting state in
  `Backup/pfd_right_strip_before_20260901-115333/`; the owner's named Point A
  and Point B restores were not modified.
- Corrected the selected-altitude bracket so its top, bottom and right sides
  stay straight while the left notch folds inward into the magenta box. The
  live-altitude box moved right to `480,200`, became ten pixels narrower, and
  now has a tape-contained left nipple. Its black interior follows that
  outline instead of spilling over the white edge.
- Tightened the five live-altitude positions to a safe ten-pixel visual pitch
  inside their unchanged 17 x 29 native cells. The final rolling cell remains
  inside the altitude-tape dirty region, so altitude changes do not force the
  V/S background to redraw.
- Rebuilt the V/S strip with its straight outer body, 34-pixel outer chamfers,
  true 45-degree transitions and a vertical void around the altitude box. Its
  needle now emerges from the box edge. Eleven unused slot-3 glyphs carry this
  static silhouette, preserving the full slot-4/5/6 resource byte-for-byte.
- Passed the PFD/resource contract at 287 full, 196 refinement and one steady
  report. Differential frames stayed pixel-identical to forced repaints;
  medians were 70 reports in cruise, 165 while turning, 64 under jitter, 250
  in modes/extremes and one at steady state. Launcher, startup-safety,
  simulator-offline reset and all 15 global output-authority/blackout checks
  passed without opening X-Plane or hardware. The remaining check is visual
  inspection on BB35 and BB36 after a normal Studio restart.

## 2026-09-01 - Point B PFD proportions, tighter joins and cleaner Boeing geometry

- Preserved the physically approved compact slot-3 PFD as the owner's named
  `Point B` in `Backup/point_b_pfd_slot3_20260901-110843/`. The snapshot holds
  the exact bridge, both display renderers, all three compatible font
  resources, builders/tests, histories, SHA-256 restore note and baseline PNG.
  Point A remains untouched.
- Kept the controller's proven 17 x 29 native cell and the measured slot-3
  upload, then used 12 otherwise-unused slot-3 characters as safe visual
  boundary aliases. Their ink moves four pixels inside its own cell, so
  `LS113.3`, `1013HPA`, `29.92IN` and `335H` close the number/letter boundary
  without overlapping opaque cells, changing a font header or adding a draw
  command.
- Widened the attitude sphere from 252 to 272 pixels into the protected black
  gutters while keeping its proven height and tape coordinates. The right edge
  now continues ten pixels behind the opaque altitude readout, matching the
  simulator's layered construction without crossing either tape body.
- Reworked the selected-altitude bracket to the simulator's left-facing notch
  and moved both MCP target outlines after tape text, so their complete
  magenta edges remain visible. The fixed-aircraft symbol is now the thinner
  Boeing wing/hook shape with a hollow centre reference; the bank index is a
  compact stepped triangle.
- Kept the fast two-pixel native stair steps where a mathematically continuous
  line would have exceeded the protected USB budget. The official PFD test
  passes at 288 full, 209 refinement and one steady report. Differential frames
  are pixel-identical to full repaints; medians are 60 reports in cruise, 169
  while turning, 56 under jitter, 250 in modes/extremes and one at steady state.
- Passed launcher check, startup-safety and simulator-offline reset tests, plus
  all 15 global output-authority/blackout checks. No physical panel or
  simulator was opened. Remaining live check: restart Studio and inspect this
  geometry on BB35 and BB36.

## 2026-09-01 - PFD values reduced again with native slot 3

- Added `tools/build_pfp_quad_font.py`, an offline builder that preserves the
  entire approved slot-4/5/6 font resource byte-for-byte and appends a new
  slot-3 transaction cloned from the same measured WinCtrl font upload.
- Generated `winctrl-pfp-b737-cockpit-font3-4-5-6.xpwwf`. Slots 4, 5 and 6
  are byte-identical to the previous live resource; only 95 newly rasterised
  printable glyphs were added in slot 3. Point A remains the unchanged prefix
  beneath both generations.
- Reduced PFD value runs from slot 4 to slot 3. The new 14-point centred
  artwork produces digits roughly 4..8 pixels wide by 10 high, compared with
  slot 4's roughly 5..9 by 13. BB35 ND stays on slot 4, PFD operational words
  stay on slot 5, and BB36 ND/systems stay on slot 6.
- Updated the exact offline emulator to decode slot 3 from the four-slot
  resource. Before/after frames remain 436 fills, 53 text runs and 31 colour
  changes; the smaller result changes glyph pixels only, not cell positions or
  instrument geometry.
- Passed: four-slot prefix/resource guard; PFD layout and launcher self-test
  (285 full, 198 refinement, one steady report); complete differential suite
  with pixel-identical forced repaints; safe launcher check; and all 15 global
  output-authority checks. Traffic is unchanged from the approved slot-4
  version: cruise median 62, turning 171, jitter 56 and steady state one.
- Backup and exact slot-4/slot-3 comparison renders:
  `Backup/pfd_even_smaller_numbers_before_20260901-105133/`.

## 2026-09-01 - Smaller PFD numbers on BB35 and BB36

- Added a separate PFD value-font path: numerical/value runs now select the
  already-proven native slot 4 (10 x 15 ink), while FMA words, `CMD`, marker
  beacons and other PFD labels retain slot 5 (13 x 19 ink).
- Applied the smaller value glyphs to selected speed/altitude, both live
  rolling readouts, tape and pitch numbers, vertical-speed and compass values,
  selected heading, Mach/radio altitude/minimums, the joined ILS frequency,
  speed-bug labels and the joined barometer value/unit. Their existing 17 x 29
  controller cells, positions and opaque backgrounds did not move.
- BB35 and BB36 now receive the same established slot-4/5/6 resource. It is
  Point A's exact slot-5/6 byte stream with the already-measured slot-4 upload
  appended; the immutable Point A file and rollback remain untouched. BB35 ND
  already used slot 4, while BB36 ND and all systems pages remain on slot 6.
- Before/after emulation kept exactly 436 fills, 53 text runs and 31 colour
  changes. Differential frames stayed pixel-identical to forced full repaints:
  cruise median 62 reports, turning 171, jitter 56 and steady state one. The
  small extra font selection costs at most one or two reports in the measured
  moving suites, not another drawing pass.
- Passed: PFD layout/font-resource contract; launcher PFD self-test (285 full,
  198 refinement and one steady report); full differential suite including
  live/offline/live recovery. Remaining live check: restart Studio normally
  and review the smaller values on BB35 and BB36.
- Backup and exact before/after renders:
  `Backup/pfd_smaller_numbers_before_20260901-104221/`.

## 2026-09-01 - Zibo PFD armed-mode arrays use their published names

- Fixed the startup warning for the nonexistent
  `laminar/B738/autopilot/pfd_alt_mode_armed[0]`. The running Zibo catalogue
  publishes `pfd_alt_mode_arm` (singular `arm`), and Studio now resolves that
  exact captain-side array.
- Corrected the companion roll-mode source at the same time. There is no
  `pfd_spd_mode_armed` array in the loaded aircraft; the published armed roll
  source is `pfd_hdg_mode_arm`. The internal value is now named
  `fma_lateral_armed` and decoded with lateral FMA labels instead of
  autothrottle labels.
- Preserved the existing PFD text-cell geometry, dirty regions, polling rates,
  hardware ownership and global output authority. This repair changes only
  which read-only simulator values feed the two existing armed-mode fields.
- Added an offline guard that fails if either published singular `_arm` name
  is replaced or an incorrect armed-FMA key is added again.
- Proved both corrected names against the running X-Plane v3 catalogue and
  resolved captain index 0 successfully. Passed the PFP PFD self-test (283
  full, 197 refinement, one steady report), pixel-identical differential
  suite, safe launcher check, and all 15 global output-authority checks. No
  simulator value or hardware output was written. Restart Studio once to load
  the corrected bridge.
- Backup: `Backup/zibo_pfd_fma_arm_ref_before_20260901-102715/`.

## 2026-09-01 - PFD values and units read as one group

- Removed the artificial native-cell gap between PFD values and their units
  on both BB35 and BB36. Barometric settings are now one text run, such as
  `1013HPA` or `29.92IN`, instead of separate number and unit runs.
- Removed the explicit space and redundant trailing frequency zero from the
  lower-left navigation readout, so the user's example is rendered exactly as
  `LS113.3` rather than `LS 113.30`.
- Tightened selected heading to `335H` and moved `MAG` to the right side of the
  live heading box. The two labels now flank the box with equal eight-pixel
  clearances instead of placing MAG underneath it.
- Added layout guards for all four exact strings and for the left/right heading
  relationship. Exact native-font before/after rendering changed 1,951 pixels,
  all confined to the protected ILS, heading and barometer zones; the rest of
  the PFD stayed pixel-identical. The grouped barometer also removes one native
  text transmission.
- Passed: modified-file syntax; PFD layout contract; exact pixel-isolation
  check; PFP display self-test (283 full, 197 refinement and one steady report);
  global output authority (15 checks); and safe launcher check. No hardware or
  simulator was opened. Live check remaining: confirm joined unit spacing and
  the balanced `335H`/`MAG` row on both physical displays.
- Backup: `Backup/pfd_unit_spacing_before_20260901-101055/`. The earlier named
  Point A rollback remains unchanged.

## 2026-09-01 - BB35-only tiny ND font experiment, with named Point A

- Preserved the complete working Boeing-organized ND as the owner's named
  `Point A` in `Backup/point_a_bb35_boeing_nd_20260901-011500/`, including the
  renderer, bridge, font builder, exact font resource, offline renderer and
  documentation. `POINT_A_README.txt` records what that rollback means.
- Added a dedicated native font slot 4 for BB35 ND text. Its printable ink is
  10 x 15 inside the controller's required opaque 17 x 29 cell, compared with
  Point A slot 5's 13 x 19 artwork. PFD text remains on slot 5 and BB36 ND/
  systems remain on slot 6.
- Built BB35's separate
  `winctrl-pfp-b737-cockpit-bb35-font4-5-6.xpwwf` resource by preserving all
  37,779 Point A bytes as an exact prefix and appending the measured `0x106`,
  `0x107`, `0x105` font-definition/chunk/commit sequence for slot 4. No new
  vendor command was invented.
- Kept BB36 on the exact Point A
  `winctrl-pfp-b737-cockpit-dual-font5-6.xpwwf`; it does not receive the
  experimental font slot. Its 37,779 font bytes and representative 630-command
  ND frame both compare exactly with Point A.
- Passed: modified-file syntax; contiguous 10,556-byte font memory for each of
  BB35 slots 4/5/6; exact Point A prefix and BB36 resource checks; exact native
  font-4 offline render; BB35/BB36 layout and live-identifier contracts; PFP
  display self-test (284 full, 197 refinement and one steady report); global
  output authority (15 checks); and safe launcher check. No hardware or
  simulator was opened. Live check remaining: fully restart Studio so BB35
  receives slot 4, then confirm the smaller ND type is readable. If firmware
  rejects or mishandles slot 4, restore Point A.

## 2026-09-01 - BB35 gets its own Boeing-organized Navigation Display

- Split ND presentation by the physical WinCtrl display identifier. BB35
  (`0x31`) now receives a Boeing-organized page, while BB36 (`0x32`) retains
  its established Airbus-panel presentation and larger native font.
- Reused the dual-font resource already uploaded to the panels: BB35 ND text
  now uses compact native slot 5. No PNG, scaled bitmap, new font upload or
  framebuffer was added to the live path.
- Reorganized BB35's live information to match the simulator's priorities:
  combined GS/TAS and wind at left; green TRK with the live track boxed at
  centre; active waypoint, ETA, distance, mode and range at right; vertical
  EFIS overlay labels; a bracketed right-side RNP/ANP block; and `FMC L` when
  real route data is present. The selected heading remains the magenta compass
  bug instead of competing for the top band.
- Changed only BB35's range guides to the solid white Boeing arcs and reserved
  the new side zones from route/database labels, preserving all existing route,
  traffic, bearing-pointer, failure and live-data drawing functions.
- Passed: syntax; BB35 and BB36 layout contracts including live hardware-ID
  routing and shift bounds; BB36 renderer comparison against the backup (four
  representative modes byte-for-byte, plus a 630-operation live-style frame);
  exact native-font offline renders of both panels; direct and launcher PFP
  display self-tests (284 full, 197 refinement and one steady report); global
  output authority (15 checks); and safe launcher check. No hardware or
  simulator was opened. Live check remaining: open ND on BB35 and confirm the
  compact Boeing organization is readable through its physical bezel at the
  user's usual 20/40 NM ranges.
- Backup: `Backup/bb35_boeing_nd_before_20260901-004004/`.

## 2026-09-01 - Live CDU EXEC reminders on BB35 and BB36

- Added the captain-side Zibo EXEC annunciator as a read-only display signal.
  The preferred source is `fms_exec_light_pilot`, with Zibo's shared
  `fmc_exec_lights` indication retained as a compatibility fallback.
- BB35 now drives its Boeing-labelled EXEC top window on the established
  WinCtrl light channel 16. BB36 uses channel 15, the second top window from
  the right requested by the owner. The supplied SimAppPro update capture
  proves the existing `0x49` light command and the five-window channel bank
  `12..16`; no new vendor packet was invented.
- Wired the reminder into both native-FMC and graphical PFD/ND/system/FMC
  owners, so it follows the pending EXEC state whichever page is displayed.
  It is kept outside the LCD draw stream and therefore adds no PFD redraws or
  refresh traffic.
- Preserved global output authority: the reminder can illuminate only with a
  connected simulator and powered Live display. It is explicitly cleared on
  startup ownership transfer, simulator loss, aircraft power loss, path
  handoff and normal Studio shutdown before the HID handle is released.
- Passed: modified-file syntax; BB35 and BB36 separate-path self-tests; full
  PFP/BB36 coded-display self-test (284 full, 197 refinement and one steady
  report); startup safety; simulator-offline reset; hardware laboratory; and
  safe launcher check. No simulator or physical hardware was opened. Live
  check remaining: create a CDU modification, confirm BB35 EXEC and BB36's
  second dash from the right light together, then press EXEC and confirm both
  extinguish immediately.
- Backup: `Backup/cdu_exec_alert_before_20260901-002521/`.

## 2026-08-31 - Studio detects an aircraft loaded after Studio starts

- Split X-Plane Web-API readiness from aircraft readiness. Studio no longer
  commits permanently to the generic/read-only path just because X-Plane's
  capability endpoint appeared before the aircraft path and plugin DataRefs.
- Kept global Live output authority offline, and retained the existing
  simulator-down hardware owners, until the loaded aircraft supplies its path
  and the established required Boeing feedback set. The wait remains
  interruptible by a normal Studio shutdown.
- Added a slow read-only aircraft-profile watcher for automatic mode. If
  X-Plane first exposes a default/generic aircraft and Zibo, LevelUp or ToLiss
  becomes ready later, the bridge performs its normal black/off teardown and
  Studio starts one clean child generation with the correct profile. No input
  or output owner is duplicated.
- Fixed Studio's child supervisor so an exited bridge's old loopback port is
  never returned as a live client. This lets the existing exited-child restart
  path actually run after the profile watcher requests the clean recycle.
- Made the generic PFP loop observe authenticated Studio shutdown and send its
  established black/off display state before releasing the HID handle.
- Passed: modified-file syntax; late-aircraft/profile isolation and same-path
  compatibility-upgrade checks; watcher stop/recycle check; stale child-port
  recovery check; startup safety; simulator-offline reset; PFP PFD output
  handoff (284 full, 197 refinement and one steady report); safe launcher
  check; panel check; hardware laboratory; and global output authority (15
  checks). No simulator, serial port or cockpit hardware was opened. Live
  check remaining: start Studio with X-Plane closed, then start X-Plane and
  load Zibo/LevelUp/ToLiss; Studio should connect automatically without being
  closed and reopened.
- Backup: `Backup/xplane_late_aircraft_detection_before_20260831_233452/`.

## 2026-08-31 - Pixel-identical PFD command reduction and smoother IAS drum

- Confirmed that the live BB35/BB36 PFD is already entirely code-drawn. PNG
  files are offline previews only and are never loaded or transmitted by the
  live display path.
- Coalesced only consecutive, same-colour native fill rectangles whose exact
  edge-touching union is another rectangle. Draw order, geometry, colours,
  fonts and final pixels are unchanged; gaps, non-rectangular overlaps, text
  boundaries and colour changes remain separate commands.
- Reduced measured differential traffic without lowering visual quality:
  ordinary speed/altitude motion fell from a 75-report median to 62 reports,
  and combined turning/climbing motion fell from 201 to 170 reports. Jitter
  motion fell from 65 to 56 reports.
- Tightened BB36's outer airspeed duplicate threshold from 0.20 knot to 0.05
  knot. The native units drum now keeps about 1.5-pixel intermediate positions
  instead of skipping roughly six pixels, while its normal dirty-region path
  still prevents unchanged physical frames.
- Passed: modified-file syntax; direct and launcher PFP PFD self-tests (284
  full, 197 refinement and one steady report); full pixel-for-pixel
  differential equivalence across cruise, turns, jitter, extremes and recovery;
  PFD/ND/systems layout contracts; safe launch check; hardware-lab; and global
  output authority (15 checks). No hardware or simulator was opened. Live check
  remaining: observe BB36 bank, IAS drum and altitude drum motion in flight.
- Backups: `Backup/bb36_command_stream_before_20260831_232222/` and
  `Backup/bb36_speed_drum_before_20260831_232500/`.

## 2026-08-31 - BB36 capture-proven LCD-refresh completion guard

- Analysed the supplied 310 MB `mcdu_update.pcapng` by the enumerated BB36
  identity (`4098:BB36`, USB address 49), rather than assuming which busy USB
  endpoint belonged to the display.
- The recorded PFD update contained 368 consecutive F0 output reports and 368
  consecutive device acknowledgements: zero USB status errors, zero invalid
  payload lengths, and zero sequence gaps. The visible missing/pixelated lines
  were therefore not missing host packets.
- Reassembled all 20,566 payload bytes into 829 complete native commands: 771
  fills, 15 foreground changes, 22 background changes, 20 text runs and one
  LCD refresh. The refresh header began at the end of report 367 and completed
  in report 368, while the last drawing report was still outstanding.
- Ordinary drawing acknowledgements measured 1.606-11.957 ms for 95 percent
  of reports; the final drawing acknowledgement took 2.951 ms. The refresh
  itself took 29.911 ms to acknowledge, proving a separate LCD-swap phase.
- Retained the earlier BB36-only four-millisecond quiet period before the now
  isolated refresh, and added a 35-millisecond completion guard afterwards.
  A large page-entry frame can no longer start its next update while firmware
  0x0104 is still swapping the previous frame onto the glass. BB35 and the
  established every-eight-report BB36 burst pacing are unchanged.
- Passed: in-memory syntax; direct and launcher PFP PFD self-tests (285 full,
  200 refinement and one steady report); full differential equivalence; PFD,
  ND and systems layout contracts; safe launch check; hardware-lab; and global
  output authority (15 checks). No captured packet was replayed and no physical
  device or simulator was opened. Live check remaining: restart Studio, cycle
  BB36 between PFD/ND/MFD repeatedly, and watch fine attitude/tape lines during
  both a full page entry and subsequent motion.
- Backup: `Backup/bb36_pcap_refresh_completion_before_20260831_230053/`.

## 2026-08-31 - BB36 PFD marker flash and page-entry refresh repair

- Fixed the exact BB35/BB36 difference seen in the cockpit. BB36 suppresses
  duplicate graphical frames to protect its slower MCDU endpoint, but that
  comparison predated the completed PFD and did not contain marker beacons or
  the other later approach/flight-path indications. `IM` changing by itself
  was therefore discarded on BB36 while BB35 continued to flash correctly.
- Extended BB36's visual-state comparison with every added PFD indication,
  including OM/MM/IM, minimums, raw ILS, armed FMA, FPV, pitch limit, rising
  runway and the navigation identifier. The existing dirty-region renderer
  still sends only the pixels that changed; a settled IM flash measured 15
  reports on and 14 reports off rather than a complete PFD.
- Protected BB36 page entry from command-boundary sensitivity. Its proven
  native `0x103` LCD refresh is now emitted in a separate F0 burst after a
  four-millisecond controller settle, so the optional IM text command cannot
  shift the refresh into a still-processing full-frame burst. BB35 retains its
  established combined batching. No vendor command or packet was invented.
- Added offline guards for marker-only state changes, small IM on/off dirty
  frames, and BB36-only refresh isolation while confirming BB35 batching is
  unchanged.
- Passed: in-memory syntax; direct and launcher PFP PFD self-tests (285 full,
  200 refinement, one steady report; IM 15 on/14 off); full differential
  equivalence; PFD, ND and systems layout contracts; safe launch check;
  hardware-lab; and global output authority (15 checks). No test opened a
  simulator or physical device. Live check remaining: fully restart Studio,
  cycle BB36 through ND/MFD/PFD while over the inner marker, and confirm IM
  flashes without a torn or pixelated PFD entry.
- Backup: `Backup/bb36_pfd_marker_refresh_before_20260831_224643/`.

## 2026-08-31 - Smaller PFD-only native font

- Added a dual-size native font resource. Slot 5 now contains moderately
  smaller 17 x 29 artwork for the PFD text and numbers; slot 6 remains
  byte-for-byte identical to the proven compact resource, including its
  embedded static shape tiles.
- PFD selected values, FMA, tape numbers, live speed/altitude, heading,
  minimums, barometer, radio altitude and ILS text use the smaller slot 5.
  Cell geometry and every protected PFD zone are unchanged.
- ND, ENG PRI, MFD and HYD explicitly retain the previous larger slot-6 font.
  The graphical FMC continues to use its separate established font resource.
- Added `tools/build_pfp_dual_font.py` and taught the offline PFP emulator to
  decode the font ID selected by each native text command.
- Passed: dual-font isolation; 95 printable slot-5 glyphs; syntax; PFD, ND,
  systems and HYD marker-motion layout contracts; installed-runtime PFP PFD
  self-test; launcher PFD self-test; full differential equivalence; safe
  launch check; hardware-lab; global output authority (15 checks); and offline
  rendering of all coded pages. No hardware or simulator output was opened.
  Live check remaining: completely restart Studio so it uploads the new font,
  then inspect PFD readability on BB35 and BB36.
- Backup: `Backup/pfd_smaller_font_before_20260831_223012/`.

## 2026-08-31 - HYD control motion and physical-bezel safe text

- The HYD/FLT CTRL page now reads the already-established X-Plane pilot
  control positions for roll, pitch, yaw, and independent left/right toe
  brakes. Aileron, elevator, rudder, and brake markers therefore remain
  visible during a control test even if unpowered hydraulics keep the actual
  aircraft surfaces still. Existing surface outputs remain the fallback.
- Added a moving green brake marker inside each left/right wheel symbol while
  retaining all four aircraft brake-temperature values.
- Reflowed each crowded `FLT SPLR` caption into separate `FLT` and `SPLR`
  lines. The verified 17 x 29 controller font remains unchanged; no guessed
  font packet or bitmap image was added.
- Moved ENG PRI/HYD left titles and the right `MUSLIMSIM` mark into a 34..606
  bezel-safe band. Moved the PFD top-right selected-altitude and vertical-FMA
  text into the same safe right edge.
- Added an offline marker-motion contract for roll, pitch, yaw and both toe
  brakes, plus neutral and deflected HYD review renders.
- Corrected a stale installed-runtime assertion that expected a failed display
  refresh to re-light the panel. The test now enforces the current blackout
  rule: a failed restart leaves both brightness channels at zero until
  Live/Test authority explicitly permits output. Runtime behavior was already
  dark and was not weakened.
- Passed: in-memory syntax compilation; systems layout/marker-motion and PFD
  layout contracts; `bridge/final.py --test-pfp-pfd`; `launch.py
  --test-pfp-pfd`; `launch.py --check`; differential-frame equivalence;
  pedal mapping; hardware-lab; global output authority (15 checks); and coded
  page rendering. The simulator-down control-channel test was correctly
  refused because the user's already-running Studio owned the bridge
  singleton; it was not stopped. Live check remaining: restart Studio, move
  roll/pitch/yaw and each toe brake on HYD, then confirm both physical display
  edges are visible.
- Backup: `Backup/display_motion_safe_area_before_20260831_215756/`.

## 2026-08-31 - BB35/BB36 coded PFD, ND, engine and hydraulic suite

- Expanded the shared BB35/BB36 graphical worker into an explicit coded page
  suite: PFD, ND, futuristic `ENG PRI`, secondary engine `MFD`, and `HYD`.
  BB36 retains its separate graphical FMC handoff. Existing captured HID
  input, controller, motor, solenoid and selector paths were not replaced.
- Completed the PFD with Mach, radio/barometric minimums, ILS identifier and
  frequency, localizer/glideslope scales, marker beacons, armed FMA modes,
  field-elevation hatch, slip/skid, exact Zibo FPV, stall/pitch-limit cue,
  rising runway, and a six-second altitude trend. The new FPV/stall/runway
  positions come from datarefs explicitly present in the installed Zibo
  aircraft rather than guessed calculations.
- Rebuilt the ND as code-native APP, VOR, MAP, PLAN and VSD pages with all EFIS
  ranges, centred/expanded geometry, active/modified/missed/alternate/offset
  routes, waypoint constraints/ETA, RF legs, holds, track trend, altitude
  intercept, RNP/ANP, terrain/weather inputs, TCAS classes, VOR/ADF pointers,
  fuel-range ring, marker/glideslope presentation and failure annunciations.
  Opaque waypoint labels now collision-test against protected map zones.
- Route strings and arrays use exact installed Zibo FMS datarefs. They refresh
  through a bounded daemon cache so an unavailable or slow X-Plane Web API
  cannot stall the physical display loop. No fictitious route, navigation or
  failure value is drawn when the aircraft does not publish one.
- STA, WPT and ARPT now draw real nearby entries from the installed X-Plane
  `earth_nav.dat`, `earth_fix.dat` and Global Airports `apt.dat`. Each database
  loads only after its EFIS switch is selected, on a daemon thread, into a
  one-degree spatial index. Repeated display queries use a movement/range cache
  (3,000 cached queries measured about 0.003 seconds), so no frame scans the
  full database. Minor WPT entries suppress automatically at 80 NM and above.
- Added aircraft-style secondary engine and hydraulic pages plus a new
  futuristic ENG PRI, all drawn from native fills/text. No PNG is loaded by a
  live display path. `tools/render_coded_display_pages.py` creates offline PNG
  snapshots only for visual QA.
- Preserved global output authority: unavailable/unpowered Live output goes
  black, Test permits only its selected output, and normal shutdown blackens
  before releasing the panel. The renderer never keeps ownership afterward.
- Passed: syntax and all three layout contracts; `bridge/final.py
  --test-pfp-pfd`; differential-frame equivalence (cruise, turning, jitter,
  modes/extremes, recovery); `launch.py --check`; global output authority (15
  checks); bridge simulator-down control channel; input-chain self-test (28
  checks); and offline rendering of all nine coded scenarios. No simulator or
  hardware was opened. Installed database parsing also passed for 7,523
  stations, 240,642 fixes and 38,359 airports, including KDFW. Live check
  remaining: run X-Plane/Zibo, cycle every
  page on BB35 and BB36, and compare live route, TCAS, FPV, approach, engine
  and hydraulic indications against the aircraft.
- Backup: `Backup/coded_complete_displays_before_20260831_204903/`.

## 2026-08-31 - FCU/EFIS typography enlarged and separated

- Preserved the existing captain EFIS / four-column FCU / first-officer EFIS
  design and every existing control tag.
- Enlarged the main headings, FCU/EFIS titles, digital values, toggle labels,
  selector labels, knob captions, PULL controls, and lower FCU action buttons.
- Gave the central knob captions, PULL row, and two action rows independent
  vertical bands. On both EFIS wings, STD/QNH, BARO, unit, MAP MODE, RANGE,
  NAV 1, and NAV 2 now have explicit spacing between text and guide lines.
- Added `tools/test_fcu_faceplate_layout.py`, which renders the actual Tk
  faceplate, verifies each typography band is separated, enforces the larger
  selector/button font sizes, and confirms every FCU/EFIS control remains
  clickable. The test caught and removed a final one-pixel STD/BARO collision.
- Offline rendered-layout, BA01 semantic/Zibo routing, syntax, and global
  output-authority checks passed. No hardware or simulator was opened. Live
  check remaining: reopen Studio at the normal window size and visually review
  the larger labels.
- Backup: `Backup/fcu_text_spacing_before_20260831-194213/`.

## 2026-08-31 - ECAM measured-name box moved below the faceplate

- Moved the two-line `MEASURED BUTTON NAMES` guidance box out of the ECAM
  button bay and into the unused dark-blue area below the physical panel. It
  no longer covers the bottom CLR control or its click target.
- Moved the colour/state legend into the unused lower trim of the physical
  panel so both pieces remain fully visible on the fixed 980 x 680 Studio
  design surface.
- Added an offline rendered-layout check that verifies the complete guidance
  box is below the panel, remains inside the canvas, and does not overlap any
  of the 18 physical button tags.
- Offline ECAM layout and syntax checks passed; no hardware or simulator was
  opened. Live check remaining: reopen Studio and confirm the placement at the
  user's normal window size.
- Backup: `Backup/ecam32_status_box_layout_before_20260831-192751/`.

## 2026-08-31 - ECAM32 button names changed from guessed order to guided capture

- Fixed the cause of physical ECAM buttons selecting the wrong Studio name
  (for example BLEED appearing as ELEC). Studio had zipped the 18 raw BB70
  contacts from a packet recording onto the 18 Airbus labels by recording
  order. That order did not prove which legend was pressed, so it was removed.
- Studio now uses only a user-measured `visual name -> raw contact` relation
  for ECAM32. Unmeasured buttons show `CAPTURE` and cannot masquerade as a
  different button or be routed under a semantic key that the hardware never
  reported.
- Added `CAPTURE_ECAM32_BUTTON_NAMES.cmd`. With Studio closed it asks for ENG,
  BLEED, PRESS, ELEC, HYD, FUEL, APU, COND, DOOR, WHEEL, F/CTL, ALL, left CLR,
  STS, RCL, right CLR, T.O CONFIG, and EMER CANC one at a time. It accepts only
  one clean press plus its release, rejects duplicate/ambiguous contacts, and
  requires `SAVE` after showing all 18 results.
- The wizard is a temporary sole HID owner and refuses to run while Studio or
  the bridge is active. It keeps the panel dark, never connects to a simulator,
  sends capture-proven OFF on exit, releases the HID handle, rechecks that
  Studio is still closed, and only then writes profiles.
- The physical name map is copied to every named profile in every existing
  `hardware_profiles*.json` file because PCB contact identity does not change
  with aircraft or simulator. Simulator-function bindings are preserved.
  Each profile file receives a timestamped backup and the complete measured
  map is retained as `ecam32_button_names_*.json`.
- Added `tools/test_ecam32_button_capture.py`. Offline checks passed for syntax,
  18-name completeness, clean press/release, missing/duplicate/ambiguous
  rejection, two profile files, multiple named profiles, binding preservation,
  backup/audit creation, and the Studio-owner process guard. Hardware Lab,
  global output authority (15 checks), the TCA rendered faceplate (89 checks),
  `muslimsim_panel.py --check`, and `launch.py --check` also passed. No test
  opened the ECAM or a simulator. Live check still required: run the new CMD,
  capture all 18 real buttons, restart Studio, and verify each physical label.
- Backup: `Backup/ecam32_guided_button_mapping_before_20260831-173901/`.

## 2026-08-31 - TCA Practice levers rebuilt from the proven live axis path

- Before editing, the already-running bridge was observed read-only. The real
  TCA reported continuous values roughly every 15-32 ms, not button edges;
  rest is raw `+1.0`, full travel is `-1.0`, and the existing faceplate uses
  `(1.0 - raw) / 2.0`. That physical polling, deadband, pickup baseline, and
  sole SDL ownership remain unchanged.
- Practice no longer treats a TCA axis click as `value=1` / `phase=press`.
  Pressing a handle or any point in its slot starts a continuous drag. Every
  pointer sample moves only the tagged handle group with `Canvas.move`; the
  whole Studio canvas is not deleted and rebuilt during the drag.
- Loopback posting uses one coalescing background drain. It keeps only the
  newest raw value, preserves the live reader's `0.0015` meaningful-change
  threshold and 15 ms cadence, and always sends the final release position.
  A server-side `practice_only` gate holds the Lab mode lock across the Test
  check and input, so a delayed drag packet cannot cross into Live routing.
- Practice draws both physical-style quadrants together as six independent
  slides: AIRBRAKE, THRUST 1, THRUST 2, THRUST 3, THRUST 4, FLAPS. Both units
  include all three axes, five side buttons, six handle contacts, the
  three-position select knob, both encoder directions, and its pushbutton.
- The same one-quadrant physical interface is now selectable and remappable
  after it enumerates as bank 1&2 or bank 3&4. Bank 1&2 keeps its existing Zibo
  defaults. Bank 3&4 gets no invented aircraft defaults; the owner chooses its
  assignments in Studio.
- The sole physical SDL reader still opens one TCA quadrant, exactly as it did
  before this work. Simultaneously opening a second physical unit was not mixed
  into this smoothness repair because that reader also owns PU, WinCtrl
  throttle, and pedals; it needs a separately approved live-hardware change.
- The complete `_pu_controller_reader` block is byte-identical to the backup:
  both hash to `40F63B8D...F8E81`. This is the direct check that the working
  physical polling and pickup code was not rewritten during the retry.
- Offline tests passed: Practice mechanics 20 checks, catalogue 158, knob 39,
  real hidden-Tk faceplate rendering 89, Hardware Lab, global output authority
  15, syntax compilation for all changed Python files, and `launch.py --check`.
  No test opened SDL hardware or a simulator.
- Backup: `Backup/tca_verified_smooth_baseline_20260831-165409/`.

## 2026-08-31 - TCA faceplate: a real 2D quadrant that is live and clickable

- The owner reported that moving the slides in Studio "don't post on the
  software". The cause was not the mapping layer, which was already correct:
  `_draw_tca_boeing_combined` contained **zero `_tag()` calls**, and
  `_faceplate_click` only reacts to a `control:<key>` tag. With no tags nothing
  on the panel could ever be selected, so "Choose simulator function" could
  never leave its disabled state and the footer stayed on "Choose a visual
  control first".
- The same function also read no live values. Every lever handle was drawn at
  `(lane_top + lane_bottom) / 2` - a hardcoded mid-lane - which is why all six
  sliders in the owner's screenshots sat dead centre regardless of the
  hardware. Its "AXIS 0/1/2" captions were `enumerate()` ordinals that matched
  no hardware at all; the three levers are SDL axes 3, 4 and 5.
- Replaced it with `MUSLIMSIM_TCA_BOEING_2D_FACEPLATE_V3`: one quadrant drawn
  as the single physical unit it is, rather than two side-by-side bank cards.
  Every control from the 2026-08-31 capture is in its physical place - three
  levers labelled LEFT/MIDDLE/RIGHT with their AIRBRAKE/THRUST/FLAPS roles,
  reverse levers on the middle and right handles, a button on each of those two
  handles, five side buttons down the captain edge, the continuous top knob
  with its two direction contacts, the PUSH/SELECT button, and the
  three-position select knob captioned IAS/MACH, HDG/TRK and ALTITUDE.
- Handles now track the live bridge mirror through `_device_mirror`. Travel is
  drawn as `(1.0 - raw) / 2.0`, which is deliberately the same expression the
  binding uses, so rest sits at the bottom stop and means idle thrust,
  speedbrake in, flaps up. The panel and the aircraft cannot disagree about
  which way a lever is pointing.
- Every control is tagged with its catalogue key, so clicking one selects it
  and enables the mapper. Pressed contacts light, the selected control takes
  the standard highlight ring, and a control the catalogue has not verified is
  drawn muted rather than offered as mappable.
- Added `tools/test_tca_boeing_faceplate.py`, 43 checks. It draws the panel
  onto a real off-screen Tk canvas and then interrogates the result: every
  captured control carries a `control:` tag, no tag names anything that is not
  a catalogue control, the middle lever actually moves between rest and full
  travel and moves *upward* for full travel, moving one lever does not move
  another, selecting adds geometry, and a press changes fill colours. A syntax
  check cannot catch a bad colour literal or a static handle; drawing it can.
  On a machine with no display the test reports that and exits 0.
- Also fixed a collision found by rendering it: the handle button sat below the
  handle, which overlapped the axis caption once a lever reached its bottom
  stop - which is exactly where a throttle rests. It now sits beside the handle.
- Tests: `tools/test_tca_boeing_faceplate.py` passed (43 checks). Full suite
  re-run and passed unchanged - `test_global_output_authority.py` (15),
  `test_tca_boeing_knob.py` (39), `test_tca_boeing_catalog.py` (127),
  `test_chains.py` (28), `test_hardware_lab.py`,
  `test_bridge_control_channel.py`, `test_fcu_efis_lab.py`, plus
  `python launch.py --check`.
- Backup: `Backup/tca_faceplate_2d_v1_20260831-145535/`.
- Preview of the rendered panel: `PNG/tca_faceplate_2d.png`.
- Live check still needed: open Studio, select the quadrant, and confirm the
  handles follow the physical levers and that clicking one enables "Choose
  simulator function".

## 2026-08-31 - Global output authority, rebased onto the TCA work instead of over it

- The owner supplied an externally generated package,
  `MUSLIMSIM_GLOBAL_OUTPUT_AUTHORITY_V1.zip`, and asked for it to be checked
  before use. **It must not be applied as shipped.** It is locked to
  `final.py` SHA `e1a6a65d...`, which is the revision from *before* the TCA
  knob dispatcher, and it ships whole-file payload replacements rather than
  diffs. Its payload contains zero occurrences of
  `MUSLIMSIM TCA BOEING KNOB DISPATCH V1`, `_tca_boeing_knob_observe`, or
  `pap3_next_speed_value`, and its `lab.py` contains no `DEFAULT_BINDINGS`.
  Applying it would have deleted both the knob dispatcher and the
  out-of-the-box lever rules. Its installer refuses on hash mismatch, which is
  correct behaviour and the only reason the risk was contained.
- Its actual changes were extracted by diffing the payload against its own
  declared base, then rebased onto current. All 20 `final.py` hunks and all 3
  `lab.py` hunks applied cleanly with offsets; nothing it changes overlaps the
  TCA work. The other four files were untouched by MuslimSim work and were
  installed from the payload directly.
- The design is sound and matches the owner's clarified rules: Live enforces
  aircraft power, Test is active-test-only, a normal shutdown sends proven
  OFF/BLACK before releasing hardware, and no vendor packet is invented -
  ECAM32, FCU/EFIS and BB36 all reuse already-captured writes.
- **Correction 1 - a scoped mirror instead of a severed one.** The package
  removed all three call sites of `_emit_practice_snapshot`, which satisfied
  "entering Test mode must not wake everything" by also losing "the thing you
  are testing lights up". Pressing a control *is* asking to test it. The
  mirror is kept and restricted: `_advance_practice` now emits with
  `only_device=<the device pressed>`, and `ControlServer.apply_practice_snapshot`
  takes an `only_device` filter. `only_device` is part of the cached
  signature, because the same snapshot scoped to a different device is a
  different physical write and must not be suppressed as a duplicate.
- This also removed the dead code the package would have left behind:
  `_emit_practice_snapshot`, `_practice_output_sink` and
  `apply_practice_snapshot` would all have had zero callers while
  `bridge/final.py` still registered a sink that could never fire.
- Scoping additionally fixes a violation the package only hid. Every mirror
  wrote `("fcu_32_efis", "backlight", 180)` and `("pap3_mag", "backlight", 1)`
  unconditionally - one of the "woken with non-zero brightness before power is
  known" cases this work exists to stop. Those writes are still needed to see
  the device under test, so they are kept and the update list is filtered.
- **Correction 2 - the AGP power judgement no longer fails open.**
  `_agp_aircraft_output_powered` returned True whenever it collected no
  values, conflating two opposite situations. It now separates them: no
  electrical ref configured means the aircraft does not publish one, so
  established behaviour is preserved; refs configured but unreadable means
  live data was lost while Studio is in Live mode, which must go dark rather
  than hold a stale indication. This was the one place the package's code
  disagreed with its own stated rule.
- Added `tools/test_global_output_authority.py`, 15 checks: registering a sink
  writes nothing, entering Test mode writes nothing, a press emits scoped to
  exactly the pressed device, a release emits nothing, the mirror never runs
  in Live mode, the server honours the scope it is given, and the four AGP
  power cases resolve the way the rule requires.
- Tests: all seven suites passed - `test_global_output_authority.py` (15),
  `test_tca_boeing_knob.py` (39), `test_tca_boeing_catalog.py` (127),
  `test_chains.py` (28), `test_hardware_lab.py`,
  `test_bridge_control_channel.py`, `test_fcu_efis_lab.py`, plus
  `python launch.py --check`. Both feature sets verified present afterwards.
- Backup: `Backup/global_output_authority_v1_rebased_20260831-144232/` holds
  all six files as they were.
- Live check still needed, and none of this has been flown: cold and dark
  should give dark screens and no lit lamps in Live mode; losing the simulator
  in Live mode should go black rather than showing a standby card; Test mode
  should light only the output being tested; and a normal Studio shutdown
  should leave the panels dark.

## 2026-08-31 - TCA Boeing knob: select picks a function, the top encoder adjusts it

- The owner corrected the earlier guess: the select knob has three positions,
  not four, and they name what the top encoder controls - left IAS/MACH, middle
  HDG/TRK, right ALTITUDE. The knob pushbutton engages whatever that window is
  showing.
- This could not be a `MappingBinding`. A binding is static per control, and
  here encoder-clockwise means a different thing at each select position. It is
  therefore real code: `MUSLIMSIM TCA BOEING KNOB DISPATCH V1` in
  `bridge/final.py`, added directly after the existing V5 block, plus one hook
  in `_muslimsim_observe_lab_event`.
- HDG and ALT step through commands. Heading uses the generic
  `sim/autopilot/heading_up` / `_down` for the same reason PAP3 does - one
  degree per detent instead of Zibo's accelerated knob behaviour. Altitude uses
  `laminar/B738/autopilot/altitude_up` / `_dn`.
- IAS/MACH deliberately is not a command. PAP3 already established that Zibo
  owns its MCP speed dial and immediately overwrites X-Plane's generic airspeed
  dial, so the dispatcher does a read-modify-write on
  `mcp_speed_dial_kts` / `mcp_speed_dial_kts_mach`, choosing the dial that
  matches `sim/cockpit/autopilot/airspeed_is_mach`. The step arithmetic is
  `pap3_next_speed_value` imported and reused, not reimplemented, so the two
  MCP speed paths cannot drift apart. An unreadable Mach flag falls back to
  IAS: a knot step on a Mach dial is visible and harmless, the reverse is not.
- Precedence is unchanged and explicit. The dispatcher checks
  `profile_store.has_binding()` first and yields to any saved binding, so a
  rebound encoder behaves the way the owner set it. When the dispatcher does
  act, the same contact is still recorded for the Studio but `route=False` is
  passed, so one detent never acts twice.
- Nothing is assumed before the select knob has been seen in a detent: with no
  position known, the encoder does nothing rather than guess which function to
  move. The detent is tracked in the baseline phase sampled at connect, so the
  first step after a reconnect already knows where the knob is.
- Added `tools/test_tca_boeing_knob.py`, 39 checks, which loads `bridge/final.py`
  through `importlib` (its entry point is `__main__`-guarded and it executes
  nothing at module level) and replaces the five simulator helpers with
  recorders. It proves the direction of every step, that Mach mode writes the
  Mach dial, that a release does not repeat a press, that a baseline sample
  does not write, that a saved binding wins, and that non-knob contacts are
  left alone.
- Tests: `test_tca_boeing_knob.py` (39) and `test_tca_boeing_catalog.py` (127)
  passed. Existing suite re-run and passed unchanged - `test_chains.py` (28),
  `test_hardware_lab.py`, `test_bridge_control_channel.py`,
  `test_fcu_efis_lab.py`. `python launch.py --check` passed with no simulator,
  serial port, WinCtrl, or PU hardware opened.
- Backup: `Backup/tca_boeing_knob_dispatch_v1_20260831-142925/` (bridge/final.py
  at 22265 lines before the change).
- Live check still needed, and not yet flown: turn the select knob to each
  position and confirm the top encoder moves the matching MCP window, then
  press the knob button and confirm it engages.

## 2026-08-31 - TCA Boeing quadrant: the owner's lever rules as out-of-the-box defaults

- The owner asked for the quadrant to follow their rules straight out of the
  box, while still letting any lever be reassigned. Precedence is now:

  ```text
  saved user binding  >  declared device default  >  bridge dispatcher / nothing
  ```

- `DEFAULT_ROLES` in `muslimsim/hardware/catalog.py` could not carry this. It
  is descriptive only: a control with no saved binding falls through to the
  bridge dispatcher that already owns that hardware. The TCA has no
  dispatcher - the bridge tracks it for display and routes nothing on purpose -
  so "no saved binding" meant "does nothing at all".
- Added `DEFAULT_BINDINGS` beside it: executable defaults, consulted by
  `HardwareLab._binding()` only when `profile_store.has_binding()` is False.
  That method already existed for exactly this question, so the meaning of an
  absent entry is unchanged for every other device. The table names
  `tca_boeing` and nothing else, and a test fails if that ever stops being true.
- The rules, for one quadrant: left slide is the airbrake, right slide is the
  flaps, and the middle slide drives every engine through
  `sim/cockpit2/engine/actuators/throttle_ratio_all`. That target is
  engine-count agnostic, so the middle slide is correct on a twin and on a four
  with no branching - the owner's rule 1 layout generalises. The middle and
  right reverse levers drive `reverse_lever1` and `reverse_lever2`.
- Axis scaling needed no bridge change. The binding sink computes
  `(1 - raw) * scale`, and the levers report -1.000..+1.000 resting at +1.000,
  so `invert` with a 0.5 scale maps rest to 0.0 and full travel to 1.0. Rest
  meaning 0.0 is deliberate: idle thrust, speedbrake retracted, flaps up - the
  safe end whichever way round the levers are physically oriented.
- Added two entries to `SAFE_AXIS_FUNCTIONS` in
  `muslimsim/hardware/zibo_library.py`: the Zibo flap lever and the all-engine
  throttle. Both were confirmed writable against the running aircraft before
  being offered. Without them the owner could rebind a lever away from its
  default and have no way to pick the default back.
- Note the deliberate change of posture: `bridge/final.py` carries the comment
  "Once live, only a user-saved HardwareLab mapping may route this raw source."
  Shipping defaults means the quadrant now routes without a saved mapping. That
  is what was asked for, and it is recorded here rather than left implicit.
  `bridge/final.py` itself was not modified.
- Tests: `tools/test_tca_boeing_catalog.py` extended to 127 checks - every
  default is a valid binding on an implemented control, every default axis
  target is offerable in `SAFE_AXIS_FUNCTIONS`, a saved binding beats a
  default, an explicit `disabled` is honoured rather than resurrecting the
  default, restoring a profile brings the rules back, and no other device gains
  a default. Existing suite re-run and passed unchanged: `test_chains.py` (28),
  `test_hardware_lab.py`, `test_bridge_control_channel.py`,
  `test_fcu_efis_lab.py`.
- Backup: `Backup/tca_boeing_default_rules_v1_20260831-141729/`.
- Live check still needed, and nothing here has been flown: start Studio,
  confirm the three slides drive speedbrake, thrust and flaps, and confirm the
  direction. If a lever works backwards, the fix is one `invert` flag in the
  default, not a code change.
- Not built, and still needed for the rest of the owner's rules: the two-knob
  mechanism (select knob picks, encoder adjusts - the four target functions are
  not yet decided), and rules B and C, which both need two physical quadrants
  connected at once. The current `_TCA_BOEING_STATE` tracks one unit at a time.

## 2026-08-31 - TCA Boeing quadrant: captured, catalogued, and its keys made routable

- The Studio drew the Thrustmaster TCA Boeing quadrant and the quadrant sent
  nothing to X-Plane. Three faults were stacked in
  `muslimsim/hardware/catalog.py`, and every one of them was silent:
  - The catalogue described axes 0..2. Capture proved the three levers are on
    axes 3, 4 and 5, and that axes 0, 1 and 2 never leave their rest value. The
    real levers therefore had no catalogue entry at all.
  - The catalogue spelled button keys zero-padded (`bank12_button_00`), while
    `_tca_boeing_control_aliases()` in `bridge/final.py` looks up
    `bank12_button_4` and twelve other unpadded spellings. Every button lookup
    missed. `_tca_boeing_lab_input()` caches a miss and returns None so that a
    static catalogue is not re-walked at joystick poll rate, so nothing was
    ever logged.
  - Every control was `status="unknown"`, and `_input()` sets
    `remappable = (status == "implemented")`. So even a correctly spelled key
    could not have been bound from the Studio.
- Added `tools/capture_tca_boeing_one_unit_both_banks.py`: a read-only SDL
  capture that refuses to start while Studio or the bridge is running, per the
  no-second-SDL-reader rule. It runs a discovery sweep, then names each control
  by prompting for it and recording whichever axis or contact actually moves.
- Captured the owner unit on bank 1&2 - axis pass twice, button pass once.
  Three levers on axes 3/4/5 left to right, full -1.000..+1.000 travel resting
  at +1.000. Buttons 1/2 on the middle and right slides, reverse levers 4/5 on
  the same two slides (owner-confirmed), five side buttons 6-10, a
  three-position select knob on 11/12/13, a direction-coded continuous encoder
  (CW 15, CCW 14), and a knob pushbutton on 16.
- No slide has a detent switch: nothing closed during a full sweep of any
  lever. Reverse is the separate lever contact, not a below-idle band, so this
  quadrant does not need the WinCtrl URSA MINOR idle-gate treatment.
- Rewrote the catalogue block as `MUSLIMSIM_TCA_BOEING_SINGLE_UNIT_CATALOG_V3`
  with the captured labels, the correct axis indices, and unpadded keys. Bank
  1&2 now has 18 controls at `status="implemented"`, so they are remappable and
  every alias the bridge asks for resolves. Buttons 0 and 3 complete the
  slide-button and reverse-lever runs but were not isolated by a prompt, so
  they stay `unknown`. Bank 3&4 is the same unit but was not captured, so it
  stays `unknown` until the selector is moved and the capture re-run.
- Added `tools/test_tca_boeing_catalog.py`, which fails if a key is padded, if
  a captured control is not `implemented`, if a phantom axis is promoted, or if
  bank 3&4 claims to be verified. The original bug produced no error anywhere;
  this turns it into a failing test.
- Tests: `tools/test_tca_boeing_catalog.py` passed (97 checks). The existing
  suite was re-run and passed unchanged - `test_chains.py` (28 checks),
  `test_hardware_lab.py`, `test_bridge_control_channel.py`,
  `test_fcu_efis_lab.py`. `bridge/final.py` was not modified.
- Backup: `Backup/tca_boeing_catalog_capture_v3_20260831-140645/`.
- Live check still needed: bind a slide in Studio and confirm it moves the
  aircraft. Not yet done.
- Still to do, and not started: the Studio faceplate is a static picture -
  `_draw_tca_boeing_combined()` reads no live value and draws every lever at
  mid-lane, and its "AXIS 0/1/2" labels are loop ordinals that match no
  hardware. The owner engine-count rules also need
  `sim/aircraft/engine/acf_num_engines`, which nothing reads yet.

## 2026-08-31 - Project root settled: `D:\MuslimSim` is canonical, the Howalt folder is a working copy

- The user confirmed they work in `D:\MuslimSim` and keep
  `D:\Howalt d203 requre signature\MuslimSim` only as a working copy. The two
  had drifted apart: the code was newer in `D:\MuslimSim` (`bridge/final.py`
  about 12 KB larger, plus `muslimsim/devices/pdc_bb61_bb52.py` and
  `muslimsim/hardware/device_lifecycle.py`, which existed nowhere else), while
  every specialist document still lived only in the working copy.
- This mattered for the rules, not just for tidiness. `AGENTS.md` rule 4
  requires updating `PROJECT_HISTORY.md` and the relevant specialist document
  on every material change, and rule 1 named the Howalt folder as the only
  place to work. Working in `D:\MuslimSim` meant rule 4 could not be followed,
  because those documents were not present there.
- Copied the missing documentation and diagnostics into `D:\MuslimSim`:
  `PROJECT_HISTORY.md`, `PFD_PROJECT_HISTORY.md`, `DEVICE_REFERENCE.md`,
  `SYSTEM_ARCHITECTURE.md`, `CONTROL_PANEL.md`, `HARDWARE_LAB.md`,
  `MCDU_BB36_INVESTIGATION.md`, `README.txt`, `diagnose_bb36_lifecycle.py`,
  `diagnose_bb36_live_freeze.py`, and `PU_SOURCE_EVIDENCE_DASHES_V9_1.zip`.
  Nothing was overwritten - none of these existed in `D:\MuslimSim` before the
  copy - and each was verified byte-identical to its source afterwards.
- Updated `AGENTS.md` rules 1 and 2 to name `D:\MuslimSim` as the only place
  to work and to back up, and to state that the Howalt folder is a working
  copy that must not be edited or trusted as the source of truth. The previous
  file is kept at `Backup/AGENTS_before_root_relocation_20260831-123137.md`.
- Verified afterwards with a full-tree comparison (ignoring `__pycache__`,
  `build`, `dist`, `Backup`, `backups`, `logs`) that nothing remains in the
  working copy which is missing from `D:\MuslimSim`.
- No renderer, bridge, or hardware-mapping behaviour changed, and nothing was
  run against the rig. Tests: none applicable - this was a file relocation and
  documentation change only.

## 2026-08-29 - MOZA Flight SDK probe: first live run, both bases confirmed visible with real parameter/command IDs

- The user ran `tools/probe_moza_flight_sdk.py` on the real hardware (via
  `& "C:\Users\noureddine aidoudi\AppData\Local\Programs\Python\Python311\python.exe" probe_moza_flight_sdk.py`,
  since plain `python` was not on PATH in their PowerShell - documented for
  next time). No code change in this entry; recording what the probe proved.
- `Moza_Initialize` returned `NO_ERROR(0)`. The forwarded SDK log shows the
  device service process was NOT already running (`设备服务进程未启动，第1次尝试启动`)
  and the SDK started it itself by a registry lookup, resolving to
  `C:/Program Files (x86)/MOZA Cockpit/bin/MOZADeviceService.exe`. That is
  `MOZADeviceService.exe`, a background service binary that lives inside the
  Moza Cockpit install folder - not the Cockpit GUI process itself. This is
  the strongest evidence yet for the user's requirement ("even if mozasoftware
  is closed"): the SDK can locate and launch the device service on its own
  via the registry, independent of whether Cockpit's window is open. Still
  need the user to confirm explicitly whether Cockpit's GUI was open or
  closed for this particular run, and ideally get a second run in the other
  state for a clean before/after (see Live check below).
- 4 devices discovered, all `MOZA_DC_AS`: `AY210 Yoke Base` (id=1, COM4,
  PID 0x1001) with child `MFY Yoke Handle` (id=4, a detachable stick device
  on the yoke base's own port); `AB6 Base` (id=2, COM6, PID 0x1002) with
  child `Stick` (id=3, on the AB6's own port). This confirms the AB6 is the
  base with a plain stick attached and the AY210 is the yoke base with its
  own detachable handle - useful context for the Studio UI grouping.
- Full parameter and command lists were dumped for every device (387
  parameters / 735 commands for AB6, 361 parameters / 681 commands for
  AY210, 29/47 and 12/16 for the two stick devices). Confirmed concrete IDs
  for the SAVED CALIBRATION fields, present on both AY210 and AB6:
  - `overall_strength` -> parameter `Main_Steer_AllStrengthCoefficient` (id 86),
    commands `MainSet_Steer_AllStrengthCoefficient`/`MainGet_...` (212/213)
  - `max_torque` -> parameter `Main_Steer_TorqueMax` (id 79), commands 198/199
  - `damper` -> parameter `Main_Steer_DampCoefficient` (id 88), commands 216/217
  - `friction` -> parameter `Main_Steer_FricCoefficient` (id 90), commands 220/221
  - `inertia` -> parameter `Main_Steer_InertiaCoefficient` (id 89), commands 218/219
  - `spring` -> parameter `Main_Steer_SpringCoefficient` (id 87), commands 214/215
  - `game_force_feedback` -> parameter `Main_Steer_GameForceFeedbackCoefficient`
    (id 63), commands 166/167
  - the FFB master switch `Main_CtrlFfbEnable` (id 312) is present on both
    bases, matching the id already documented in
    `docs/Flight_Base_Force_Feedback_Command_Guide.md`.
  - The `MainCtrl_Ffb*` command family (603-610: NewEffect/Constant/Ramp/
    Periodic/Condition/Envelope/EffectOperation/Control) is present as real
    commands on both AY210 and AB6, confirming the FFB Command Guide's
    documented protocol matches what these specific units actually expose.
  - `background_led_brightness`/`gear_led_brightness` and related LED
    parameters exist only on the AY210 (ids 22-28), not the AB6 - matches
    `moza_presets.py`'s existing preset structure exactly (those fields are
    only in the `a210_*` presets, never `ab6_*`).
  - No device-side parameter corresponds by name to the FLIGHT EFFECTS
    toggles (g-force, stall buffet, runway rumble, gear/flaps motion, jet
    rumble, turbulence, speedbrake buffet). The closest relatives are
    `Main_DynamicConditionForceBind_Aileron/Elevator`,
    `Main_DynamicConditionForceEnable_Aileron/Elevator`, and the
    `Main_VariablePointCurve_*` curve parameters. This means those effects
    will most likely have to be synthesized bridge-side as FFB periodic/
    envelope commands driven by X-Plane telemetry, not simply toggled as a
    device parameter - important for scoping the next implementation step.
  - The single read-only value read succeeded on 3 of 4 devices (`Main_YawConnected`
    on AB6, `Main_PanelRawData` on AY210, `Stick_Data` on the yoke handle) and
    timed out on the fourth (`Stick_Data` on the AB6's stick) - the script
    reported the timeout cleanly (`TIMEOUT(11)`) instead of crashing, and no
    `SetValue`/`CommandSend`/FFB call was made anywhere in the run.
  - The script completed cleanly end to end with no crash: `Moza_ValueDestroy`,
    `Moza_DeviceClose` x4, and `Moza_Shutdown` all ran, confirmed by the
    trailing SDK log lines (`已关闭ZMQ消息处理线程池`, `设备服务SDK资源已关闭`).
- **Live check still needed** - confirm whether Moza Cockpit's GUI was open
  or closed for this run, and get one run in the other state to close out
  the dependency question cleanly. After that, the next step is deciding
  scope for the actual write path: wiring the six confirmed calibration
  parameters to real `Moza_DeviceParameterSetValue(Sync)` calls, and
  separately scoping the FFB command work for the flight-effects toggles -
  not started yet, pending user direction given this next step will be
  capable of driving real hardware torque.

## 2026-08-29 - Added a read-only MOZA Flight SDK discovery probe (`tools/probe_moza_flight_sdk.py`)

- New file, not an edit of an existing one, so no backup entry applies (AGENTS.md
  rule 2 covers changes to existing material files).
- Purpose: the user wants Studio's SAVED CALIBRATION values (OVERALL/MAX
  TORQUE/DAMPER/FRICTION/INERTIA/SPRING/flight-effects) to actually drive the
  physical MOZA AY210 yoke base and AB6 base, with force feedback and
  vibration working even when Moza Cockpit's own window is closed. Today
  those values are only ever written to a local JSON profile
  (`muslimsim/hardware/moza_presets.py`) - no Moza output protocol exists in
  this project yet, by design (see that file's own docstring).
- Confirmed which vendor SDK is the right one: MOZA's Racing SDK
  (`RS21_sdk`, previously downloaded) has zero flight-base awareness and its
  own readme requires "MOZA Pit House (SDK version)". The Flight SDK
  (`MOZA_SDK` 1.0.0.4) covers `MOZA_DC_AS` aircraft devices - wheelbase,
  stick, throttle, control panel, screen - and its docs only ever mention a
  generic background "device service", never Cockpit/Pit House. Confirmed
  via `include/moza/moza.h`, `include/moza/private/macros.h` (plain
  `__declspec(dllexport/dllimport)`, no `__stdcall` - so Python `ctypes.CDLL`
  is the correct binding, not `WinDLL`), `docs/MOZA_SDK_Developer_Guide.md`,
  `docs/MOZA_SDK_API_Reference.md`, `docs/Flight_Base_Force_Feedback_Command_Guide.md`,
  and `examples/c_api_example.c` (the discover -> open -> list-parameters ->
  list-commands -> close -> shutdown flow this probe follows).
  The SDK download itself now lives at
  `C:\Users\noureddine aidoudi\Downloads\MOZA_Flight_SDK_1.0.0.4 - enUS\MOZA_SDK\`,
  with `x64-release\bin\MOZA_SDK.dll` (14 MB) as the runtime library and an
  included `tools\SdkDebugTool\ApiDebugTool.exe` GUI for manually
  cross-checking the same parameter/command lists.
- The probe: initializes the SDK, registers the SDK's own internal log
  callback (useful when init fails, since MOZA_ERR_SERVICE_NOT_FOUND is
  exactly the "is the device service even running" signal this is meant to
  test), waits (default 5s, matching the vendor's own example's `Sleep(5000)`)
  for the device service to enumerate, lists every device, and for each
  `MOZA_DC_AS` device opens it and prints its full parameter list and
  command list with real IDs and names from
  `Moza_DeviceParameterGetList`/`Moza_DeviceCommandGetList` - not guessed.
  It cross-references each parameter name against Studio's own calibration
  field names from `moza_presets.MOZA_EDITABLE_KEYS` and flags a likely
  match inline, to locate the concrete parameter IDs behind OVERALL/MAX
  TORQUE/DAMPER/FRICTION/INERTIA/SPRING.
- Strictly read-only: only `Moza_Initialize`, the `*_GetList` functions, and
  (unless `--skip-value-read`) one `Moza_DeviceParameterGetValueSync` read of
  a single already-readable parameter are called. No `Moza_DeviceParameterSetValue(Sync)`,
  no `Moza_DeviceCommandSend(Sync)`, and no `MainCtrl_Ffb*` command exists
  anywhere in this file - no torque, effect, vibration, or motor motion is
  possible from running it.
- ctypes struct layouts were built directly from `moza.h`: `MOZA_LOG_CONTEXT`
  is declared before the header's `#pragma pack(push, 1)` so it uses natural
  alignment (no `_pack_`); `MOZA_VALUE`, `MOZA_DEVICE_INFO`,
  `MOZA_PARAMETER_INFO`, and `MOZA_COMMAND_INFO` are declared inside that
  packed region, so each ctypes `Structure`/`Union` sets `_pack_ = 1` to
  match.
- Also gives the user the concrete two-run test for the open question of
  whether device discovery needs Moza Cockpit's GUI open or just a
  background service: run once with Cockpit fully closed, once with it
  open, and compare.
- Tests run: `python -m py_compile` and `python -m pyflakes` on the new
  file, both clean. No live run - this session has file access to
  `D:\MuslimSim` but no shell on the machine that owns the hardware, and the
  DLL is a Windows PE binary that cannot be loaded from this session's Linux
  workspace either.
- **Live check still needed** - the user needs to actually run
  `python tools/probe_moza_flight_sdk.py` on their PC (once with Moza
  Cockpit closed, once with it open) and share the output. Nothing further
  is implemented until that confirms the AY210/AB6 are visible to this SDK
  and clarifies the service-vs-Cockpit dependency; this is deliberately only
  the discovery step, not yet the parameter-set or FFB-command wiring.

## 2026-08-29 - Moza Studio: fixed FLIGHT EFFECTS/disclaimer overlap, moved MAX3 GRIP to the AB6 tab set

- Fixed a layout bug in `muslimsim/gui/studio.py`'s `_draw_moza_calibration`
  (the shared MOZA A210/AB6 SAVED CALIBRATION panel): the FLIGHT EFFECTS
  section's third row used the same 52px row step as the first two sections,
  which put its bottom edge past the disclaimer text below it. Reduced the
  FLIGHT EFFECTS row step to 44px, which reclaims enough room that the last
  row (TURBULENCE/SPEEDBRAKE) no longer runs into the "Preset values are
  saved..." disclaimer text underneath it. Confirmed the box math by hand:
  the third row's bottom edge now sits well clear of the disclaimer's text
  block instead of a few pixels inside it.
- Moved the MAX3 GRIP tab from the A210 tab set to the AB6 tab set, per the
  user: the MAX3 grip mounts on the AB6 base on this rig, not the A210 yoke
  base. `_draw_moza_max3_layout` itself is untouched - same faceplate, same
  live TRIGGER/TOP button state, still read from the A210 HID contact pool
  per the existing capture (that part of the comment on the function is
  still accurate; the grip's electrical contacts are proven to enumerate
  through the A210's HID pool regardless of which tab surfaces the
  faceplate). Only the tab bar and the click handler's page whitelist moved:
  A210 keeps A210 BASE / DETACHABLE YOKE, AB6 gets AB6 BASE / MAX3 GRIP.
- Updated `_activate_moza_visual`'s tab-click guard, which previously only
  accepted page clicks when `device == "moza_a210"` - AB6's single tab was
  effectively decorative. It now looks up a per-device set of valid pages,
  so AB6's two tabs are both clickable.
- Nothing else in `studio.py` was touched - no other device's panel, no
  other Moza layout function, no calibration values or presets.
- Tests run: `python -m py_compile` on the changed file, and a full diff
  against the pre-change backup confirming the change is confined to the
  three edited spots above.
- **Live check still needed** - this was verified by reading and compiling,
  not by opening the Studio window (no shell/GUI access from this session).
  Please open Displays/Calibration for both Moza devices and confirm: no
  text/button overlap at the bottom of either panel, and the AB6 screen now
  shows AB6 BASE and MAX3 GRIP tabs, both clickable, with MAX3 GRIP no
  longer appearing under A210.

## 2026-08-29 - BB35/BB36 path routers: restored auto-restart on a dead display worker

- Today's undocumented BB35/BB36 separate-paths edit (made ~26 minutes after
  the `bb35_bb36_restart_mode_fix_20260829` backup, with no backup of its own
  and no changelog entry) changed the router's dead-worker handling from a
  same-mode restart to `self.stop_evt.set()`. That does not just skip one
  restart: it ends the router's `_run()` loop permanently. Nothing calls
  `.start()` again afterward, so the panel stops receiving frames and is left
  showing whatever was already on the glass - explaining the frozen BB35
  ENG PRI and BB36 "PRACTICE COCKPIT" pages reported after the last fix.
- Restored the pre-edit behaviour on both panels: a dead display-worker
  thread sets `restart_dead_path = True` and the router loops back to
  recreate and restart the same-mode path, instead of shutting itself down.
  This re-enables logic that was already present but had gone dead
  (`restart_dead_path` was declared and read downstream on both files but
  never set `True` any more).
- Deliberately left everything else from today's edit alone: PERIOD x3 stays
  disabled as a display-mode handoff on both panels (matches
  MCDU_BB36_INVESTIGATION.md's finding that repeated F0/F2 handoffs degrade
  this firmware), `toggle_evt.clear()` in `start()` stays, and the
  `live_plane_refresh_pending` removal stays.
- Backed up the two pre-fix files to
  `Backup/bb35_bb36_worker_restart_regression_fix_20260829_131043/` before
  writing the change.
- Tests run: `python -m py_compile` on both changed files (clean), and a
  line-by-line diff against `Backup/bb35_bb36_restart_mode_fix_20260829/`
  confirming the restored block is byte-identical to the last version that
  was actually exercised on hardware, with only today's other, intentional
  changes remaining as differences.
- **Live-cockpit check still needed** - this fix was written and verified by
  reading, not by running the bridge or touching the panels: no shell/HID
  access from this session. Please restart the bridge, confirm BB35 and BB36
  both come up live (not on a stale frame), and if either was already stuck
  before this fix was installed, do a real "Restart screen" (USB
  re-enumeration, Administrator) first - a soft Redraw will not clear a
  frame the firmware is already holding.

## 2026-08-28 - Throttle below-idle split, forced per-unit calibration

- Added a Throttle tab that draws the WinCtrl quadrant as the two bands a 737
  actually has: IDLE to TOGA, and IDLE through REV IDLE to full reverse. Each
  band is drawn only over its own travel, so both read 0.0% at the idle
  detent and there is no ambiguity about which side of it the lever is on.
- Established that the hard-coded detents are wrong on this hardware. The
  left lever reads 20165 against an assumed 19308, which is 1.85% commanded
  thrust with the lever in its own idle detent. Confirmed through the
  bridge's own `_winctrl_throttle_values`, not a re-derivation.
- Added `--throttle-left-idle`, `--throttle-left-rev-idle`,
  `--throttle-right-idle` and `--throttle-right-rev-idle`. The control panel
  passes measured values on every start. An impossible calibration (REV IDLE
  above IDLE) is refused with exit 2 rather than clamped: a silently
  corrected throttle would command thrust the pilot did not ask for.
- The quadrant is read over raw HID, matching the bridge's Raw Input decode.
  Calibrating through SDL would have produced values the bridge never sees.
  The preview borrows the bridge's mapping function rather than copying it.
- Two safety checks added: thrust is exactly zero at IDLE and anywhere below
  it whatever the reverse handle does, reverse is inert with the handle down,
  and an invalid calibration never reaches the bridge. 16 checks now pass.
- Offline tests passed: `--test-winctrl-throttle`, `--test-pfp-pfd`,
  `--test-aircraft-profiles`, `--test-startup-safety`, `launch.py --check`,
  `muslimsim_panel.py --check`. Live cockpit check still needed: capture both
  detents and confirm idle settles at zero on both engines.

## 2026-08-28 - MuslimSim.exe: a real application, no console and no batch file

- Packaged the control panel as `dist/MuslimSim.exe` (27 MB, one file,
  windowed via pythonw). Built by `build_exe.py` from `MuslimSim.spec`.
- The manifest requests Administrator, because a real screen restart
  re-enumerates the USB device and Windows refuses that silently otherwise.
- Rebuilt the panel as tabs: Devices, Calibration, Throttle, Displays, Output.
- Live axis calibration for pedals, throttle and yoke with a bar per axis,
  range capture, centre capture and invert. Read through SDL because SDL is
  what the bridge reads these devices through. Keyed by controller name, not
  index, because SDL renumbers devices when one is unplugged.
- Live display mirror of the PFP and MCDU at about 12 ms per frame, drawn by
  the same renderer the bridge uses from the values it drew its last frame
  with. The bridge now records those values and serves them over the control
  channel; a second dataref reader was rejected because it would show live
  numbers while the panel showed standby.
- A frozen exe has no interpreter to start the bridge with, so it re-runs
  itself with `--run-bridge`. Settings are written beside the exe, not into
  the unpacked bundle, which Windows deletes on exit.
- Fixed two bugs that only a frozen build exposed: the self-test read .py
  files that do not exist inside a bundle, and asserted the bridge starts via
  `launch.py`. Added a check that the files loaded by path are bundled.

## 2026-08-28 - USB power cycle: stop trusting the exit code

- Measured that `pnputil /restart-device` exits 0 without elevation and does
  nothing at all: after a reset reporting success, the bus was polled at
  50 ms for 3.5 s with 0 absent samples out of 80. The device never left.
- `reset_device` now checks for Administrator up front, targets the USB
  parent PnP node rather than the HID child, and verifies the device really
  left the bus and came back before reporting success.
- Fixed `present()`: `hid.enumerate(0, 0)` treats zero as a wildcard, so a
  presence check for a nonexistent device returned True. It now verifies the
  returned entries rather than trusting the filter.

## 2026-08-28 - Control panel and the in-bridge control channel

- Added a control panel that owns the bridge as a child process and can stop,
  start or reset one device without restarting the others. Previously the
  only granularity was Ctrl+C.
- Added a loopback JSON-line control channel inside the bridge
  (`--control-port`, `--control-token`), bound to 127.0.0.1 and carrying a
  per-run token. Off unless the panel passes it, so terminal launches are
  unchanged.
- The channel opens BEFORE the wait for X-Plane. The first version opened it
  after the managers exist and so never came up with the simulator down,
  which is exactly when the panels may need resetting. Stop went from a
  Ctrl+Break kill (0xC000013A) to a clean unwind in 1.9 s, exit code 0.
- Added `muslimsim/hardware/catalog.py`: every device declaratively, so
  adding a panel is one entry rather than changes spread across the launcher,
  the GUI and the bridge. The ECAM (BB70) is listed with `implemented=False`.
- Corrected the PFP catalogue entry to use launcher vocabulary: `launch.py`
  strips a bare `--pfp-pfd` unless its own `--with-pfd` was given, so the
  engine flag would have been silently deleted. A self-test check pins this.

## 2026-08-28 - MCDU speckles investigated; no fix applied

- The reported black specks on the MCDU PFD are NOT in the rendering.
  Counting gaps pixel by pixel over three attitudes: the PFP, which has no
  speckle complaint, has 108; the squeezed MCDU has 69. Drawing 300
  successive frames onto one canvas gave zero wrongly-black pixels and two
  stale white pixels, fixed and non-growing.
- Two changes made on the false hypothesis were reverted: the vertical
  compression back to the known-good 0.10, and an erase-rounding change whose
  stated rationale had been disproved. A note at the constant says not to
  re-tune it chasing these specks.
- Added `tools/probe_mcdu_speckle.py`, which paints flat fields to settle
  whether the panel speckles with no PFD on screen at all. Not yet run.

## 2026-08-27 - PAP3 MCP speed dial and annunciator-power correction

- Replaced the PAP3 SPEED rotary's generic X-Plane commands with writes to
  Zibo's verified writable MCP selector through the PAP3 manager's existing
  Web API socket. IAS writes the underlying `mcp_speed_dial_kts` control,
  rather than its combined display mirror, which Zibo restores to 100 each
  frame; Mach retains the combined dial representation.
- Removed the false `electric/main_bus` output gate. The current Zibo reports
  that value as zero while avionics are powered and MCP statuses are active;
  it had held the PAP3's global LED brightness at zero, making every MCP and
  A/T annunciator appear dark. Avionics state is now the power gate.
- Added `tools/test_pap3_mcp.py`, which verifies speed bounds, the WebSocket
  write packet, active annunciators with a zero main-bus reading, and the
  magnetic A/T solenoid output.

## 2026-08-27 - BB62 MINS and BARO rotary controls bound from raw trace

- The focused physical trace proved that the apparent shared HID axis was
  background movement, not a common rotary source. MINS clockwise and
  counter-clockwise pulses are bits 41 and 39; BARO clockwise and
  counter-clockwise pulses are bits 44 and 42.
- Bound MINS direction pulses to Zibo CAPT minimums up/down and BARO direction
  pulses to the Zibo pilot barometer up/down commands. The existing no-write
  baseline still prevents a stationary panel from changing the aircraft at
  startup or after reconnect.
- Offline mapping/dispatch tests, syntax compilation, and launcher checks
  passed. Live confirmation remains limited to one parked rotary detent at a
  time after a bridge restart.

## 2026-08-27 - BB62 VOR/ADF reliability fix and focused knob trace

- Replaced the VOR/ADF selector's inferred numeric-state logic with absolute,
  saturating Zibo command sequences. Each physical VOR, OFF, or ADF position
  now first reaches the appropriate endpoint and, for OFF, takes one step
  back to centre. This avoids the previous failure where only the OFF position
  could be applied reliably.
- Added the read-only `tools/probe_pdc_bb62.py --knob-trace` mode. It records
  four labelled raw HID traces: MINS clockwise/counter-clockwise, then BARO
  clockwise/counter-clockwise. The two rotaries remain deliberately unbound
  until that source/direction evidence separates them safely.
- Offline PDC mapping and command-sequence tests, syntax compilation, and
  launcher checks passed.

## 2026-08-27 - BB62 CAPT EFIS controls bound from physical capture

- Applied the captured 64-button/axis map from the connected `4098:BB62`
  panel. CAPT MINS mode, BARO unit selector, VOR/ADF selectors, MODE, RANGE,
  RST/STD, TFC/WXR/STA/WPT/ARPT/DATA/POS/TERR/FPV/MTRS now dispatch only after
  a no-write startup baseline.
- Verified the active Zibo/X-Plane v3 API exposes the required CAPT datarefs
  and command names; the manager uses the bridge's existing REST helpers,
  resolves IDs lazily, and refreshes one stale ID after an aircraft reload.
- MINS and BARO knobs both captured as HID axis 0. They are deliberately
  ignored rather than being allowed to move both settings together. Run
  `--diagnose-pdc` and capture each knob's raw direction/source separately.
- Offline tests passed: expanded `tools/test_pdc_bb62.py`, syntax compilation,
  and launcher checks. Live confirmation is still required one EFIS control at
  a time, parked, with `--diagnose-pdc`.

## 2026-08-27 - WINCTRL 3N PDC / EFIS BB62 capture-first integration

- Added an independent PDC BB62 (`4098:BB62`) manager to the same standalone
  MuslimSim process. It owns only its own non-blocking HID reader; absent,
  unplugged, or malformed PDC reports cannot stop the PU, throttle, PAP3,
  AGP, pedals, PFD/BB35, or MCDU/BB36 paths.
- The current device is deliberately capture-only: its first valid 64-button,
  two-axis report is a no-write baseline, later raw report deltas are available
  with `--diagnose-pdc`, and it sends no aircraft command or dataref change.
  No PDC display/LED selector is guessed or written.
- Added generic, PID-parameterised (`62 BB`) 0x02 and 0xF0 packet builders as
  offline-only protocol support. A future mapped action is designed to use the
  bridge's existing `set_dataref` / `activate_command` helpers rather than a
  separate PDC WebSocket stack.
- Registered the PDC in `ALL_DEVICES` and `DeviceSelection`; `--without-pdc`
  maps to `--no-pdc`, and `--without-winctrl` also disables the PDC like PAP3.
- Corrected the read-only probe's selector flow: every held position is now
  compared with a different position on the same selector, so an initial
  resting position can be captured accurately.
- Offline tests passed: `tools/test_pdc_bb62.py`, syntax compilation of the
  touched modules/bridge, and `launch.py --check`. Live cockpit confirmation
  still required: run the supplied physical-control capture sequence before
  adding any semantic PDC mapping.

## 2026-08-26 - PFD differential output completed and live recovery fixed

- Replaced unconditional whole-screen PFD transmission with a persistent
  24-pixel dirty-region grid. Only cells whose final pixels changed are sent
  to the PFP, while a periodic complete recovery frame protects against a lost
  USB update.
- Fixed the opaque-font overlap case found by the differential checker: a text
  run is expanded to its complete native cell bounds before dirty output, so a
  partial repaint cannot erase an unchanged neighbouring symbol.
- Added quantised attitude/heading inputs and motion-adaptive geometry. A
  moving or recovery horizon uses economical two-row bands; a stationary
  follow-up restores the one-pixel detail.
- Fixed live -> offline -> live recovery. Boot and offline pages now invalidate
  the renderer's persistent state, so reconnecting with unchanged aircraft
  values still sends a complete live PFD instead of leaving the standby page.
- Split live telemetry into a 0.25-second fast flight sample and a 1.0-second
  complete sample for slower FMA/barometer values. This improves motion updates
  without multiplying every X-Plane read.
- Added `tools/check_pfd_differential.py`, which proves the differential canvas
  pixel-identical to a forced full repaint through cruise, turns, sensor jitter,
  display modes/extremes, periodic recovery, and live/offline/live sequences.
- Measured results over the 120-frame suite: cruise median 75 reports, turning
  median 201, jitter median 66. The banked recovery self-test is 248 reports,
  its stationary refinement is 183, and an unchanged frame is one refresh
  report.
- Tests passed: syntax compilation; the expanded differential suite;
  `--test-pfp-pfd`; `--check`; `--test-pu-lights`;
  `--test-starter-retract`; `--test-pedals`; and
  `--test-winctrl-throttle`.
- Live cockpit confirmation still needed: PFP motion smoothness and X-Plane
  frame pacing during a real turn, with PU CONNECT's PFP output closed.

## 2026-08-27 - The PFP page fix was lost and restored

- The PFP lost its page cycling again. The BB35 file had reverted to the
  repair package's `lambda: "pfd"`, undoing the fix made earlier the same
  session. It was lost while proving the guard bites: the file was copied to
  a temporary path, deliberately broken, and the copy-back did not take.
- The guard worked exactly as intended and named the fault immediately:
  "The BB35 worker's page getter does not follow the router: it still reports
  'pfd' after a cycle". Writing it was worth more than the fix itself.
- Restored from `pfp_bb35_separate_paths_KNOWN_GOOD_20260827_184552.py`, which
  differed from the live file in nothing but that fix. Verified the getter
  follows the router again: reports pfd, then nd after one cycle.
- Lesson recorded: never verify a guard by breaking the live file. Break a
  copy and run the test against the copy.

## 2026-08-27 - The PFP's page fix does not apply to the MCDU

- Checked whether the MCDU carries the same fault the PFP had, and it does
  not. The PFP's pages were pinned because the PAP3 repair replaced its path
  methods and handed the worker `lambda: "pfd"`. The MCDU router:
  - has no repair block and nothing replaces its methods;
  - already passes its own `get_display_page` in the nine-argument call;
  - stores `display_page` on the same instance the slash detector cycles,
    behind the same lock, exactly as the PFP does;
  - cycles page names the worker accepts -- both lists are
    ("pfd", "nd", "eng_pri", "mfd").
- So there is no equivalent fix to apply. Every static check says the wiring
  is right, which points at the slash not being detected at all rather than
  the page not being picked up. The worker prints GRAPHICAL PAGE -> on every
  change, and in the logs so far it has only ever printed PFD.
- Added live key diagnostics instead of guessing again: with
  `--diagnose-mcdu`, the MCDU's PFD path names every button it sees and marks
  which one is bound to the page trigger and which to the path toggle. A
  trigger bound to a wrong index fails silently, and this is what makes it
  visible without stopping the bridge.

## 2026-08-27 - MCDU display behaviour restored to its pre-session state

- Walked every backup and built a timeline. The MCDU ran on offset 10,
  compression 0.10, starting on FMC for the whole project. All three of the
  display behaviours that differ today were changed during this session, and
  the panel was reported working before any of them.
- Restored all three:
  - the viewport maps every fill again, instead of passing a full-screen fill
    through unmapped and banded;
  - compression back to 0.10 from 0.0512;
  - the startup refresh sends the MCDU no character-plane configuration. That
    was added so its startup blank would land, and it puts the panel into
    character mode before the PFD path ever opens.
- The shutdown restore still sends that configuration, which is correct: it
  hands the panel back to WinCtrl equipped as WinCtrl expects.
- Removed two self-test guards that enforced the reverted behaviour: the
  full-plane clear coverage check, and a cap on the compression. That cap
  encoded a measured preference for keeping more of the picture, and the panel
  contradicts it -- 0.10 is what it ran on. The guard that ordinary fills are
  still fitted stays.
- Kept from this session: the MCDU starting on the PFD (asked for), the
  standby pages, the page-getter fix, and the geometry guards.

## 2026-08-27 - The PAP3 package pinned the PFP to its PFD page

- Page cycling stopped working on the PFP after the PAP3 repair was installed.
  The cause is in that package's BB35 handoff patch:

      if needs_page_getter:
          path._repair_page_getter = lambda: "pfd"
          args.append(path._repair_page_getter)

  It hands the display worker a constant getter. SLASH x2 still advances the
  router's page, the worker just never asks it, so the display stays on the
  PFD for the life of the session. ND, ENG PRI and MFD become unreachable with
  nothing in the log to say why. Their README documents this as intended
  ("additionally receives a callback returning \"pfd\"") -- which is wrong for
  any build that has page cycling, and this one has had it for a while.
- Fixed to pass the router's own `get_display_page`, keeping the constant only
  as a fallback for a router that genuinely lacks the method. Verified the
  getter now follows the router: reports `pfd`, then `nd` after one cycle.
- Guarded it in `--test-pfp-pfd`: the worker must receive a page getter, and
  that getter must change after a cycle. Proved it bites by restoring the
  package's version -- "does not follow the router: it still reports 'pfd'".
- Note for future installs: re-running the PAP3 repair will overwrite this,
  because the marker block is replaced wholesale. The self-test will catch it.

## 2026-08-27 - The MCDU page cycle is correct; verified rather than changed

- Checked the ND / ENG PRI / MFD cycle end to end against the PFP 3N and found
  nothing to fix. Reporting that rather than changing something that works.
  - The trigger listens on button 70, and the panel's own key map calls that
    index `('/', laminar/B738/button/fmc1_slash)`.
  - Two presses within 0.55 s, the same as the PFP.
  - The cycle produces pfd -> nd -> eng_pri -> mfd -> pfd, the same order.
  - The PFD path hands `get_display_page` to the worker in the nine-argument
    call.
  - The detector and the cycle function differ from the PFP's only in their
    docstrings.
  - All four pages render through the MCDU's viewport with essentially the
    same ink as the PFP: pfd 75150 vs 78704, nd 4008 vs 4099, eng_pri 9072 vs
    9051, mfd 8945 vs 9023. The ND draws its compass, range, ground speed,
    wind and mode correctly.
- So the pages do not appear on the panel for the same reason the PFD does not
  after a handoff: the graphics plane stops displaying. It is the known fault
  in MCDU_BB36_INVESTIGATION.md, not a second problem.
- Added a parity guard to `--test-pfp-pfd`: the MCDU's trigger index must be a
  key the panel actually calls "/", both panels must cycle the same pages in
  the same order with the same press count, and the real detector is driven
  against the real cycle callback so an order that looks right but does not
  advance is still caught. Proved it bites by setting the index to 69, which
  the panel calls Z.

## 2026-08-27 - PAP3 repair package v2 applied

- Installed `MuslimSim_PAP3_BB35_PFD_PFP_Repair_2026-08-27_v2`. Its 26-test
  suite passed, both patch targets validated, and every installed file
  compiles.
- Caught a real hazard in its default behaviour first. The installer picks the
  newest `final*.py` carrying the PAP3 marker, and the backup taken minutes
  earlier was newer -- its first dry run selected
  `Backup/pre_pap3_.../final.py` as the active bridge. Run unpinned it would
  have patched a backup and left the real bridge untouched. Both the dry run
  and the install pinned `--bridge` and `--bb35-module` explicitly.
- Verified the change by applying it to a throwaway copy and diffing before
  touching the installation. It is 14 lines, all PAP3: the LCD refresh floor
  moves 0.04 -> 0.12 s, a new `--pap3-start-delay` (default 3.0 s) lets the
  displays finish initialising before PAP3's first output burst, and that
  delay is passed to the manager.
- The BB35 router came out byte-identical; its handoff patch reported "already
  current" because an earlier version of this package was installed before.
  `pap3_mcp.py` and `winctrl_output_bus.py` were already present and identical.
- Confirmed none of this session's work was disturbed: MCDU viewport still
  10 / 0.0512, cell pitch 23x29, MCDU still starts on the PFD, standby pages
  intact, both handoff traces intact, and the dead functions removed earlier
  stayed removed. `launch.py --check` and `--test-pfp-pfd` both pass.

## 2026-08-27 - Tuned after the move to D:\MuslimSim

- Verified the move: launcher check, PFD self-test and the differential
  checker all pass at the new path, all five fonts sit beside final.py, and
  the 49 restore points came across. Nothing used absolute paths.
- Removed the two dead functions this investigation left behind,
  `_blank_mcdu_between_paths` and `_hard_reset_mcdu_display` (71 lines). The
  second is the one that painted the panel dark on every trigger; leaving it
  in the file was a trap for whoever read it next.
- Removed `DISPLAY_HANDOFF_BLACKOUT_SECONDS` and the `blackout_seconds`
  parameter, which existed only for that reset.
- `_winctrl_background_packet` now uses `WINCTRL_BACKGROUND_FUNCTION` instead
  of repeating 0x104 as two loose bytes. Verified the packet is still
  byte-identical to the proven one.
- Rewrote `MCDU_BB36_INVESTIGATION.md`. Several of its conclusions had been
  disproven by later testing and it would have sent the next reader down the
  same dead ends. It now separates what is established from what was claimed
  and later broken, and marks as *untested* the recovery commands that were
  only ever tried on an already-dead panel.
- Audited every top-level function: 10 unreferenced ones remain, all
  pre-existing (1226 lines, mostly superseded PFD and cockpit page drawing).
  Left alone rather than removed unasked; reported for a decision.

## 2026-08-27 - MCDU investigation handed over

- Wrote `MCDU_BB36_INVESTIGATION.md`: what is established by measurement, the
  panel's real geometry, the seven approaches ruled out and why, the two
  questions still open, and the one mechanism not yet tried. Written so a
  fresh attempt does not repeat any of today's dead ends.
- The tree is verified clean: nothing added during the investigation still
  paints the MCDU between paths.

## 2026-08-27 - The black screen was the hard reset painting it

- Found what was actually darkening the MCDU on every trigger, and it was the
  hard reset added earlier today. It fills the whole graphics plane with the
  background colour (6, 7, 13), which on this panel reads as black, and the
  incoming PFD then cannot draw over it.
- Unwired it. The toggle is a plain handoff again, with nothing painting the
  plane between paths. Confirmed nothing else remains: no blackout on stop,
  no clear on FMC entry, no hard reset from the router.
- The startup refresh keeps its own clear, which is correct there and is what
  the BB35 panel visibly restarts from.
- This also explains the report that BB35 restarts at startup while BB36 does
  not: the visible part of that refresh is its brightness blackout, and this
  panel does not appear to respond to it. Both panels run the same code and
  both report success, which is why it looked identical in the log.

## 2026-08-27 - Reverted the handoff blackout; what the attempt did establish

- Reverted the whole handoff blackout. It made the PFD unreachable: after the
  flash the panel stayed dark and the returning PFD never appeared, which is
  worse than the border it was meant to replace. The router is back to its
  2026-08-27 13:50:56 state; the regression is kept beside it as
  `mcdu_bb36_BLACKOUT_regression_*`.
- What the attempt did establish, and it is the most useful fact of the day:
  a long-running PFD session's writes reach the glass -- the black fill was
  plainly visible, the first whole-screen change anything produced on this
  panel all session. A freshly opened PFD session's writes, after the FMC
  path has run, do not: its own background restore lands, but nothing the PFD
  draws afterwards appears.
- So the split is not between planes or coordinates. It is between a session
  that has been drawing and a session that has just opened. Every clear that
  "succeeded" and did nothing was issued from a freshly opened session; every
  write that visibly worked came from one already running.
- That also explains the power cycle: it is the only thing that returns the
  panel to a state where a fresh session can draw.

## 2026-08-27 - The blackout was a state, not a flash

- The handoff blackout worked -- the screen visibly goes black, which is the
  first time anything in this session has produced a visible reset on this
  panel. But it was left there: the graphics plane stayed black, so when the
  PFD came back its own page was hidden underneath.
- The plane is now returned to its normal background after the hold, so the
  blackout is a flash rather than a state. Verified the colours are used in
  order (0,0,0) then (6,7,13), both covering all 480 rows.
- Also confirmed, by comparing the two panels, that the character-plane blank
  is byte-identical between them: spaces at COLOR_WHITE, same encoder. That
  had been a suspect for the black sitting on top and it is not one.

Needs a look in the cockpit: whether the trigger now flashes black and then
shows the incoming page, in both directions.

## 2026-08-27 - Brightness cannot blank this panel; its own PFD session can

- Measured against the panel: setting the MCDU's screen brightness channel to
  zero and holding it for two seconds did not blank the screen. The packet is
  byte-identical to the one the FMC path uses successfully to set 128 and 220,
  so the command is right and this panel simply does not black that way.
- That rules out the blackout the handoff reset was built on, and explains why
  lengthening it from 60 ms to 0.45 s would not have helped either.
- The handoff blackout now comes from the outgoing PFD session instead, which
  is the one place on this panel proven to write the graphics plane -- it has
  been drawing the PFD there all along. It fills the framebuffer black, holds
  it 0.45 s, then hands over. Verified the fill covers all 480 rows.

Needs a look in the cockpit: whether the MCDU now visibly goes black on each
trigger.

## 2026-08-27 - The hard reset was running invisibly

- The handoff reset blacked the panel out for 60 ms, which is below what the
  eye registers. It has run correctly on every trigger and looked like a page
  flip, which is exactly what was reported.
- The flicker the PFP 3N shows on a handoff is not a blackout either: it is
  its 0.89 s font upload, during which the character grid is configured but
  not yet written, so a bare grid is on the glass. That is what reads as a
  reset there.
- The handoff now holds its blackout for 0.45 s, separate from the 0.06 s the
  startup refresh uses, so a reset is visible as one.

Needs a look in the cockpit: whether the MCDU visibly goes dark on each
trigger, and separately whether a brightness of zero blanks this panel at all.

## 2026-08-27 - The border was geometry: the PFD drew where the page cannot reach

- With both PFD paths finally visible, the traces are equivalent. BB35's PFD
  entry is 2 reports, BB36's is 5 -- the same clear, banded. FMC entry and
  closing match phase for phase. Nothing about what is sent differs.
- The fault was where the PFD draws. It drew into rows 10..449 while the FMC
  page covers only 37..443, so 27 rows at the top and 6 at the bottom held PFD
  content the incoming page could never paint over: the selected speed and
  altitude along the top, a strip along the bottom. Exactly the photographs.
- The PFD's viewport is now confined to the page's own area. Nothing is drawn
  where the FMC page cannot cover it, so no clear is needed and none of the
  clearing this session attempted was ever going to work.
- Offset 10 -> 37, compression 0.10 -> 0.20. Not the 0.1805 the arithmetic
  gives: fills round outward and that still spilled four rows past the page.
  Measured through the offline emulator across level, banked and descending
  frames -- all three paint rows 46..440, inside the page's 37..443.
- The PFD loses 33 rows of height. That is the cost, and it buys a border that
  cannot come back rather than one being chased with clears.
- `--test-pfp-pfd` fails if the viewport ever starts above the page or reaches
  below it. Proved by restoring the old values: it names row 10 against the
  page at 37.
- This is also why the PFP 3N never had the problem: its FMC page covers
  everything its PFD draws.

Needs a look in the cockpit: whether the border is finally gone, and whether
the slightly shorter PFD reads acceptably.

## 2026-08-27 - Traced both panels: the FMC paths match, the PFD paths do not

- Added `--trace-pfp-handoff`, a pass-through wrapper on both panels' HID
  handles that reports what each path sends at entry and at close. Verified
  byte-identical pass-through and off by default.
- The FMC paths are the same, measured rather than read:
    BB35 entry: 597 F0 | ch1=255 | 42 F0 | 16 F2 | ch0=128 | ch1=220 | 1 F2
    BB36 entry: 541 F0 | ch1=255 | 42 F0 | 16 F2 | ch0=128 | ch1=220 | 1 F2
  Same phases in the same order; the 597 against 541 is only BB35's font
  rebuild sending more packets. Both closings are F2 page traffic followed by
  a single F0 packet. So the FMC side needs nothing further.
- The PFD paths are not the same, and the trace showed it by capturing
  nothing at all: BB35 reported 3396 reports while leaving its PFD, and BB36
  reported none, despite its PFD visibly running at 12.6 fps.
- The cause is structural. BB35's PFD draws through a `_PfpNativeCanvas`
  directly. BB36's draws through `_McduPfdFittedCanvas`, a vertical viewport
  wrapping a native canvas, so the handle the writes actually go through sits
  one level further in. The trace now walks the canvas chain to find it.
- That viewport is also mis-set against this panel. It maps 0..480 onto rows
  10..449, while the test card measured the visible glass as rows 10..469 --
  so twenty rows of visible screen are never drawn on. A compression of
  0.0512 rather than 0.10 would use the full height.

Needs one more run with the trace to see what the MCDU's PFD path actually
sends, now that its writes are visible.

## 2026-08-27 - Triple-PERIOD hard resets the MCDU screen

- Every triple-PERIOD now hard resets the panel before the incoming path is
  created: blackout, both plane configurations rewritten, character plane
  blanked, graphics plane cleared, brightness restored, handle closed. The
  next path then opens a completely fresh session.
- It runs with no path holding the panel, and settles on both sides so
  Windows has released the handle before another session claims it.
- Brightness is restored even when a step fails, so a reset that does not
  complete cannot leave the panel dark. That failure is what made an earlier
  attempt at this black the screen.
- Measured live against the panel: 0.18 s per reset.

## 2026-08-27 - The MCDU now comes up on the PFD, like the PFP 3N

- The MCDU came up on its FMC menu while the PFP beside it came up on the
  PFD. The PFP 3N router hardcodes `self.mode = 'pfd'`; the MCDU router took a
  `start_mode` that defaulted to `"fmc"`, and start_muslimsim.cmd passes no
  override. Both defaults are now `pfd`.
- Comparing the paths step for step never showed this, because the difference
  was never in the paths -- they were already identical. It was one line in
  the router, and it took being told to look there.
- Compared the two routers behaviour by behaviour rather than one difference
  at a time: retry on start failure, toggle wait, toggle clear, full teardown,
  handoff settle, mode flip, handoff print, active-path stop and supervisor
  join all matched already. The starting mode was the only difference in the
  whole class.
- `--test-pfp-pfd` now reads the router's own signature and fails if its
  default view ever stops matching the PFP's.
- The option itself is kept, unlike the PFP which has none, because starting
  the MCDU on its FMC page is a reasonable thing to want. Only the default
  changed.

Also recorded, from reading the PFP 3N's font code: the .xpwwf resource is
authored at 23x29, which is the MCDU's own pitch. The PFP rebuilds it to
23x32 so its six line-select rows meet its physical LSK keys. So on geometry
the MCDU is the native case and the PFP is the adaptation -- copying the
PFP's rebuild would misalign the MCDU's rows against its own keys. Its
measured screen characteristics are now named constants in its module, with a
self-test guard against exactly that change.

## 2026-08-27 - BB36 runs the PFP 3N lifecycle, and nothing else

- Removed everything this session added to the BB36 paths, on the grounds that
  the PFP 3N works and the MCDU should do what it does. Gone: the PFD path's
  clear on stop, the FMC path's clear on entry, the handoff restart session,
  the injected native canvas and the banded clear helper. BB35 has none of
  them and never needed them.
- Each of those was added to remove the stale border, and each was reasoned
  from evidence that turned out not to mean what it appeared to: the wear test
  showed the panel accepts every write whether or not it acts on it, so no
  clear could ever be confirmed from this side. The additions could not be
  shown to help, and the panel degraded across handoffs while they were in.
- Verified step for step against BB35 rather than asserted: PFD start, PFD
  stop, FMC start and FMC stop are now all IDENTICAL in sequence, and BB36
  carries zero of the extras.
- The stale border is expected to return. It is the known cost of the MCDU's
  page covering less glass than the PFP's, and it is a better state than a
  panel that stops drawing after two handoffs.
- The self-test guards for the deleted feature were removed with it; the
  standby-page and viewport guards remain.

Needs a look in the cockpit: whether the handoff is stable again over several
triggers, which is what this trades the border for.

## 2026-08-27 - The panel fails silently, and that invalidates the evidence

- Repeated the handoff's HID work eight times against the real MCDU, counting
  every write and timing every phase: 589 writes per cycle, zero short, zero
  failed, font upload 0.582-0.584 s and clear 0.005 s on every single cycle.
  Nothing at the USB level changes as the panel degrades.
- So the panel keeps acknowledging writes it no longer acts on. Every
  "success" this bridge printed about a clear was evidence of nothing, and so
  was all the packet-level verification -- it only ever proved the packets
  were well formed, which was never in question. Added
  `tools/probe_mcdu_handoff_wear.py`, which is what established this.
- Combined with the photographs, the shape of the fault is now clear and it is
  not a clearing problem: the first handoff after startup is clean, the second
  leaves a frame of the previous page, and by the third the PFD will not draw
  at all. A power cycle restores it completely. Something in the handoff is
  progressively disabling the display.
- The startup refresh therefore looks reliable only because it runs on a panel
  that has just been connected, not because of anything it does differently.
- Withdrew the font-precondition conclusion entirely. The test that produced
  it ran immediately after a power cycle, so the power cycle explains it just
  as well; it was a confound, and building on it corrupted the glyph table.
- The MCDU is addressable to Windows as
  `USB\VID_4098&PID_BB36®5D1217760606282261023`, so a software power
  cycle through Disable-PnpDevice/Enable-PnpDevice is possible in principle,
  but the bridge does not run elevated and cannot do it as things stand.

## 2026-08-27 - Reverted: uploading a second font corrupts the glyph table

- Reverted the whole font-precondition change. It corrupted the FMC page's
  text and left the PFD black -- both far worse than the border it was meant
  to remove. Both files are back to their 2026-08-27 12:07:05 state and the
  broken pair is kept beside them as `*_BROKEN_font_upload_*` for reference.
- What it got wrong: the panel's font is not a value that a later upload
  replaces. Uploading the native font and then re-uploading the FMC font left
  the glyph table mixed, so the page rendered with characters missing and
  wrong. Re-uploading afterwards does not undo it.
- This was a known risk in this project -- handing an FMC path the PFD font
  has corrupted its text before -- and it was flagged before the change went
  in. It should have been tested on one path before being applied to three.
- What survives the revert, and is still true: the panel answered that fills
  do reach the whole visible glass (rows 10-469; rows 0-9 and 470-479 are
  outside the viewable area), and that a session which has uploaded a native
  font can clear it while one that has not cannot. The conclusion was sound;
  acting on it by uploading a font into a session that already had one was
  not.
- Back to the known behaviour: the handoff restart, the PFD path's clear and
  the FMC path's entry clear all run, and the border remnants remain. That is
  the state to work from, with the panels otherwise correct.

## 2026-08-27 - Font before config, or the panel draws a bare grid

- Fixed a regression from the font-precondition change: adding the native
  font upload had pushed it after the config packets, so the grid was being
  configured while no font was loaded. The PFP showed exactly that -- a bare
  grid where its page should be.
- BB35's own FMC path has always done font, settle, then background and grid.
  Both the shutdown restore and the startup refresh now follow that order
  again. Verified by capturing what each routine actually writes:
  - restore: blackout, native font, F0 clear, WinCtrl font, config, F2 blank,
    brightness
  - refresh: blackout, native font, config, F2 blank, F0 clear, brightness
- The graphics clear stays with the native font, which is what makes it
  reach the glass at all, and a fill needs no grid configured -- so in the
  restore it can happen before any character-plane setup and leave the
  panel's final font and grid exactly as WinCtrl expects them.
- The restore now takes 2.98 s for both panels, up from well under a second:
  it uploads two fonts to each. That is shutdown, so the time costs nothing.

Needs a look in the cockpit: whether the PFP now comes back to a proper
WinCtrl page rather than a bare grid, and whether the MCDU does too.

## 2026-08-27 - The graphics plane needs a font loaded before it draws

- The panel answered it. A test card painted in labelled bands showed green at
  rows 10-36, blue through the middle and yellow at rows 443-469 -- the whole
  visible glass, including both bands where the remnants appear. Fills do
  reach those rows, so the coordinate model was never the problem.
- The difference between that working and every failure is one step: the
  session must have uploaded a native font before the graphics plane accepts
  drawing. An identical session without one painted nothing at all, not even
  a flicker; the same fills after an upload covered the screen.
- That is why every clear so far "succeeded" and did nothing. The startup
  refresh, the handoff restart and the FMC path's clear all skip the font
  upload, so their fills were accepted over USB and drew nothing. The first
  clean load was a freshly powered panel, not a working clear.
- Also learned: rows 0-9 and 470-479 are outside the viewable area. The MCDU
  shows roughly rows 10-469 of the 640x480 framebuffer, which is why the red
  and magenta edge bands never appeared.
- The handoff restart, the FMC path's entry clear and the shutdown restore now
  each load the native font before clearing. The FMC path and the restore then
  put their own font back, so the page still renders in its own glyphs --
  handing an FMC path the PFD font has corrupted its text before in this
  project.
- Cost: a font upload is 582 packets, about 0.58 s. The handoff restart went
  from roughly 0.1 s to 0.76 s measured, which is a visible blink, and the
  trigger was meant to visibly restart the screen.

Needs a look in the cockpit: whether PERIOD x3 both ways now leaves nothing
behind.

## 2026-08-27 - Correction: the cell-size difference is a font resize, not hardware

- Withdrew the 512x480 framebuffer hypothesis and the claim that the two
  panels differ in hardware cell size. Both are 640x480, and the config
  packets carry no screen-size or cell-size field: they differ only in device
  address and grid origin (bytes 4, 21, 23, 29).
- The cell size comes from the font, and both FMC paths load the *same*
  resource. BB35 resizes it -- "Critical PFP3N calibration: 23x29 authored
  font -> 23x32 cells" -- and BB36 loads it as authored. That, not the
  hardware, is why the two pages cover different amounts of glass.
- So the authored cell is 23x29, not the 17x29 quoted in the previous two
  entries, and the MCDU's page is 552x406 at (52, 37), not 408x406. Its
  exposed margins are top 37, bottom 37, left 52, right 36 -- wide top and
  bottom bands with thin sides, which is exactly where the remnants appear in
  the photographs. The geometry explains where they show; it still does not
  explain why three clears do not remove them.
- BB35's own margins are not zero either (top 24, bottom 8), so covering the
  glass is not the whole of why it stays clean.

## 2026-08-27 - Three clears run and the remnants survive all of them

- A run log now proves all three clears execute on a PFD -> FMC handoff: the
  PFD session's own, a full soft reboot reporting "F2 blank + F0 clear + HID
  reopen state reset", and the FMC session's on entry. The frame of the
  previous page survives all three.
- That rules out the explanation every fix so far has been built on. The
  remnants are not being addressed by a graphics-plane fill or a
  character-plane blank, so the model of this panel is wrong somewhere and a
  fourth clear would be the same mistake a fourth time. Stopped adding them.
- Standing hypothesis, from arithmetic rather than assumption: the MCDU's
  framebuffer may not be 640x480. Its character grid is 408x406 at (52, 37),
  which on a 512x480 screen gives margins of 52 left, 52 right, 37 top and 37
  bottom -- symmetric on both axes. The PFP's grid on its known 640x480 screen
  is not symmetric on either (50/38 and 30/2), so this is not a house style;
  it is what a centred grid on a 512-wide screen looks like. A 640-wide fill
  on a 512-wide framebuffer would not cover what the PFD drew.
- Rewrote `tools/probe_mcdu_graphics_plane.py` to settle it. It paints in
  colours that cannot be mistaken for flight information and waits for an
  answer at each step: the whole plane in one fill, the whole plane in bands,
  the four margins alone, and an oversized 1024x768 fill. Between them they
  say whether the graphics plane reaches those edges at all, and whether the
  framebuffer is wider than the fills being sent.

Needs a run in the cockpit: `python tools/probe_mcdu_graphics_plane.py` with
the bridge stopped. Its answers decide where the remnants actually live.

## 2026-08-27 - The triple-PERIOD trigger restarts the display

- The trigger is a display restart, not a page change. Every handoff now
  rebuilds both planes from nothing in a session of their own -- the same
  sequence the bridge runs at startup, which is the only one proven to clear
  this panel.
- Found why the earlier attempt at exactly this took the MCDU black, and it
  was a real defect in the restart routine, not in the idea. It blacks the
  panel out as its first act, and every failure path jumped straight to
  closing the handle without ever restoring brightness. At startup the device
  is free and it succeeds; at a handoff the device was just released by the
  outgoing session, so an open or a write can fail -- and the blackout stayed.
- Brightness is now restored on the failure path too. Proved it both ways
  against a device that accepts the blackout and then fails every other
  write: the version that shipped leaves brightness at 0 (dark), this one
  restores 220 (lit).
- `--test-pfp-pfd` now fails if a failed restart leaves the panel dark.
- The handoff also settles on both sides of the restart rather than opening a
  new session the instant the old one closes. Opening too early is what made
  those writes fail in the first place.

Needs a look in the cockpit: whether PERIOD x3 now visibly restarts the panel
and leaves no trace of the previous path.

## 2026-08-27 - The clear has to run where F0 is known to work

- A run log settled what three rounds of reasoning could not. Between
  `BB36 HANDOFF: PFD -> FMC` and `BB36 PATH -> FMC` no warning appears, and
  the FMC path prints one if its graphics clear throws or cannot run. So that
  clear executed, inside the FMC session, without error -- and the border
  survived it. An F0 clear issued from the FMC session does not reach the
  glass.
- So the clear now runs in the PFD path's own `stop()`, the one session that
  can prove it writes the graphics plane: it has been drawing the PFD on it
  all along. It settles 0.06 s before the handle closes, the same way the FMC
  path settles after blanking its page.
- This is a deliberate deviation from BB35, which closes its PFD path without
  clearing. BB35 does not need it: its 23x32 cells give an FMC page covering
  x 50..602, y 30..478, which hides whatever is underneath. The MCDU's 17x29
  cells cover only x 52..460, y 37..443.
- An earlier attempt put a clear in the same place and it did not work, for a
  different reason: it went through the PFD's vertical viewport as bands, and
  reached only rows 10..448. With the `native_canvas` unwrap it now covers
  0..479, verified against a mock device -- 5 reports, every row, ending in an
  LCD refresh.
- Both clears now name themselves in the log ("graphics plane cleared before
  handoff" / "on entry"), so the next run shows which ran instead of leaving
  it to be inferred from silence.

Needs a look in the cockpit: whether PERIOD x3 back to the menu is finally
clean, and which of the two clear lines the log prints.

## 2026-08-27 - BB36 given the same lifecycle as BB35

- Reverted the handoff blank added earlier the same day. It opened its own HID
  session between path teardown and startup and took the MCDU black; a second
  session in that window is not something the panel tolerates. The bridge no
  longer does it.
- Found why BB35 never had this problem, and it is not a missing step. Its
  character cells are 23x32, so its FMC page covers x 50..602, y 30..478 of
  the glass and hides whatever the PFD left underneath. The MCDU's cells are
  17x29, so its page covers only x 52..460, y 37..443 and leaves a frame of
  bare graphics plane on all four sides. BB35 never needed to clear that
  plane; the MCDU cannot avoid it.
- BB36's path lifecycle now matches BB35 step for step, and the alignment is
  checked rather than asserted:
  - PFD start: open, repaint the complete surface, start threads. It never
    sends F2 -- the outgoing FMC path blanks its own character plane.
  - PFD stop: close. A path clears what it owns when it starts; it does not
    tidy up for the path that follows.
  - FMC start: open, font, settle, background, grid, blank page, brightness,
    threads -- plus the graphics clear the MCDU's geometry requires, placed
    with the other background work, before any text is written.
  - FMC stop: blank the page, send the background packet, close. BB36 was
    missing that background packet, which BB35 has always sent.
- Both routers are now armed first and released together through a barrier
  rather than started sixty lines apart, so the two panels come up beside
  each other instead of in build order. Measured spread between the two
  starts: 0.078 ms. Each panel's first page still takes as long as its own
  font upload, which differs between them.

Needs a look in the cockpit: whether PERIOD x3 now resets cleanly in both
directions, and whether both panels come up together.

## 2026-08-27 - The PFD/FMC handoff, where the border actually came from

- Narrowed the stale border to the handoff itself: the MCDU comes up clean,
  the PFD is clean, and the border appears only on PERIOD x3 back to the FMC
  menu. So the fault is in the transition, not in either page.
- Reproduced it offline through the emulator rather than guessing. A PFD frame
  paints physical rows 19..451; the clear the handoff performed reached only
  rows 10..448, leaving 449, 450 and 451 -- the strip along the bottom of the
  photograph.
- Cause: the handoff clear issues eight bands, and it was issuing them through
  the PFD's vertical viewport. No single band is a full-screen fill, so none
  was recognised as a clear, and every one was fitted into the viewport
  individually. The two fixes were cancelling each other out.
- The viewport now exposes the unfitted canvas as `native_canvas`, and the
  clear unwraps it, so its bands reach the glass. Verified in the emulator:
  the same sequence now leaves nothing painted.
- `--test-pfp-pfd` fails if a clear issued through the viewport leaves any
  physical row untouched. Proved the guard bites by removing the unwrap: it
  named rows 0..9 and 449..479.
- Also added a blank between path handoffs from a fresh HID session, the same
  sequence that clears the panel at startup. An in-session clear depends on
  the plane still accepting drawing from a handle that is about to close;
  owning a session does not. It covers both directions, and it explains why
  the first load looked clean while a handoff did not -- the startup refresh
  was doing that work, not the FMC path's own clear.

Needs a look in the cockpit: whether PERIOD x3 in both directions now leaves
a clean panel.

## 2026-08-27 - Both panels are handed back to WinCtrl on exit

- Closing the bridge now returns both displays to their original WinCtrl
  state instead of leaving MuslimSim's last page on the glass. MuslimSim
  uploads its own glyph artwork and draws on both display planes, so simply
  exiting handed the WinCtrl software a panel carrying MuslimSim's font in
  its slot and a MuslimSim page on the screen.
- The restore puts back the manufacturer's font
  (`winctrl-pfp-b737-clean-font6.xpwwf`), the original plane configuration, a
  blank character page, a cleared graphics plane and normal brightness. It
  runs last in shutdown, after the routers and the PFP worker have released
  their HID handles, because it opens its own sessions. Verified against both
  panels: `{'bb35_restored': 1, 'bb36_restored': 1}`.
- Not yet restored: the factory WinCtrl logo. MuslimSim replaces it by
  sending native function 0x104 with selector byte 0x0E, but the value the
  panel starts with is recorded nowhere in this project, and guessing at
  firmware is how displays end up in modes nobody can explain. Added
  `tools/probe_winctrl_logo.py`, which steps the selector through its
  candidates so the panel itself can answer; setting
  `WINCTRL_FACTORY_BACKGROUND` then completes the restore.
- The MCDU no longer just goes black when it has nothing to show. It sat dark
  beside a PFP that explained itself, and a dark panel is indistinguishable
  from a broken one. The FMC path now draws a MuslimSim standby page in its
  own 24x14 character grid -- the proven page path, not graphics.
- It tells the two cases apart honestly: an FMC state that never arrived is a
  stopped simulator, while a populated but blank page is a CDU with nothing
  to show. A real CDU page is never replaced.
- `--test-pfp-pfd` covers the MCDU standby page's text, checks it survives the
  real packet encoder, and fails if a populated CDU page could ever be
  mistaken for a blank one.

Needs a look in the cockpit: whether both panels come back the way WinCtrl
expects after closing the script, and which selector value the logo probe
shows.

## 2026-08-27 - The MCDU starts in FMC mode, and nothing cleared its graphics plane

- Found the real cause of the stale frame around the MCDU's picture, from the
  observation that the two panels start differently: the PFP comes up showing
  the PFD, the MCDU comes up showing the FMC menu (`--mcdu-start-mode`
  defaults to `fmc`).
- The FMC path writes only the character plane. That plane covers just the
  middle of the glass -- 24x14 cells from (52, 37), so x 52..460 and y
  37..443 of 640x480 -- so anything a previous PFD session left on the
  graphics plane outside it stays visible as a frame around the page. The
  PFP never showed this because its PFD paints the whole screen.
- Neither BB36 path was clearing the graphics plane: the FMC path never
  touched it, and the PFD path closed its session without blanking it.
- Both now hand the glass over blank. The PFD path clears in `stop()`, with
  its worker stopped but the session still open -- the one moment the clear
  is certain to land, since that session has been drawing successfully all
  along. The FMC path clears on open, because its page owns the whole screen
  and anything underneath is stale by definition.
- The router does not carry a second copy of the native graphics encoding;
  `final.py` installs its canvas class into `NATIVE_CANVAS_FACTORY`, the same
  reasoning behind the router importing the FMC packet builders rather than
  reimplementing them. If it is ever missing, the FMC path says so rather
  than silently skipping the clear.
- `--test-pfp-pfd` now fails if the router loses that canvas, if the clear
  stops covering all 480 rows at full width, or if it never refreshes.
- Added `tools/probe_mcdu_graphics_plane.py`: fills the plane red without a
  native font upload and green after one, so the panel itself answers whether
  the font upload is a precondition for drawing. Diagnostic only -- it writes
  to the display, never to the simulator, and leaves the glass dark navy.

Needs a look in the cockpit: whether the border is finally clean, and which
colours the probe shows.

## 2026-08-27 - No page keeps flying after the aeroplane stops

- Every page now stands by when the information stops being real. Only the PFD
  noticed a stopped simulator before; ND, ENG PRI and MFD kept redrawing
  whatever they last held, so closing X-Plane left a plausible-looking
  navigation display on the glass indefinitely.
- Two triggers, both debounced over two samples so a dropped HTTP read or a
  switch caught mid-throw cannot flash the card:
  - the simulator going away -> "SIM STOPPED" / "START X-PLANE";
  - the aeroplane's own displays losing power -> "AIRCRAFT UNPOWERED" /
    "BATTERY SWITCH ON".
- Display power comes from `laminar/B738/electric/dc_stdbus_status`, the bus
  that feeds the captain's instruments. Confirmed by probing the running
  aircraft: X-Plane's generic electrical datarefs do not follow Zibo's
  switches -- with the battery off they still report 23.5 V on three buses,
  while every Zibo bus reads 0 and `hot_batbus_status` reads 1. That last
  value is what proves the 1 = powered convention rather than assuming it.
- The power check fails towards showing the flight display: a missing or
  unreadable bus value counts as powered. A wrong "off" would blank a working
  PFD in flight; a wrong "on" only leaves the previous behaviour in place.
  `--no-power-standby` switches the trigger off entirely.
- The card is drawn once and held, not repainted per frame: 13 reports on the
  PFP, 16 on the MCDU, then nothing until the state changes.
- Recovering from standby invalidates the renderer's dirty history and redraws
  the page's background. The card replaced the whole screen, so every
  dirty-region record described pixels that were no longer there.
- Entering a page and recovering from standby now share one
  `_cockpit_draw_page_static`, so they cannot drift apart.
- The standby card names the panel it is on -- WINCTRL PFP or WINCTRL MCDU.
- Fixed the centring on the standby and boot pages: both advanced 23 pixels
  per character while native font 6 draws 17-pixel cells, so every line sat
  left of centre. Only visible once the card carried longer lines.
- Telemetry budget raised 38 -> 39 for the bus, which rides the slow sample
  cycle; the self-test now fails if it is ever moved to the fast group.
- `--test-pfp-pfd` covers all four pages, both reasons, both panels, and all
  four power-gate cases. Differential checker still passes, including
  live-offline-live recovery. PFD budget unchanged: 265 full, 183 refine, 1
  steady.
- Previews: `PNG/nd_standby_sim_stopped.png`, `PNG/pfd_standby_unpowered.png`.

Needs a look in the cockpit: whether the bus reads 1 with the battery on. The
0 state was sampled directly from the cold aircraft; the powered state is
inferred from `hot_batbus_status` following the same convention. If a page
ever stands by while you are flying, `--no-power-standby` is the escape hatch.

## 2026-08-27 - The stale frame around the MCDU's picture

- Fixed the border of old PFD pixels that survived every restart on the MCDU.
  The character plane cleared (the previous fix), which is why only the middle
  of the glass went black; the frame around it is outside the 24x14 grid, so
  only a graphics-plane clear can reach it.
- Root cause: the BB36 viewport compresses Y, and it mapped a full-screen clear
  like any other fill. Mapped, `fill(0, 0, 640, 480)` covers physical rows
  10..448 and no further. Every renderer draw is mapped into that same
  viewport, so nothing ever repainted rows 0..9 or 449..479 -- whatever an
  older build left in those margins outlived every clear for as long as the
  panel stayed powered.
- A full-screen fill now means "scrub the glass" and is passed to the native
  plane unmapped, at full physical extent. Ordinary fills are still fitted.
- Whole-plane clears are now issued as eight horizontal bands rather than one
  640x480 rectangle, in the startup refresh and the MCDU's own open path. That
  single giant rectangle is the one shape nothing else in the protocol
  exercises; eight fills cost about 200 bytes, well under a millisecond, so the
  certain form is cheaper than proving the elegant one.
- `--test-pfp-pfd` now fails if a full-screen clear through the viewport leaves
  any physical row untouched, or if ordinary fills stop being fitted. Verified
  both ways: the guard names rows 0..9 and 449..479 when the fix is removed.
- The PFD's own budget is unchanged: 265 full, 183 refine, 1 steady.

Needs a look in the cockpit: whether the border around the MCDU's picture is
now clean after a restart.

## 2026-08-27 - Why only the MCDU did not refresh at startup

- The startup soft reboot cleared the PFP but appeared to do nothing on the
  MCDU, while reporting success on both.
- Ruled out first, by measurement rather than assumption: the MCDU enumerates
  normally (VID 0x4098 / PID 0xBB36, one interface); the call site does ask
  for it; the F2 blank packets are byte-for-byte identical between the two
  devices; both character grids are 24 x 14; and the routine's brightness and
  graphics-clear commands already carried the right device identifier.
- The cause is the character plane's configuration, which the routine never
  sent. That configuration is per display and differs in more than the
  address: the PFP and the MCDU use different text-grid origins, bytes 21 and
  23 of the grid packet - 0x32/0x18 against 0x34/0x25 - as well as different
  addresses at bytes 4 and 29. Without it the MCDU's F2 blank landed outside
  the visible grid and its old FMC page stayed on the glass, which is exactly
  what a display that "does not refresh" looks like.
- Each display's spec now carries its own proven background and grid packets,
  taken from that device's own module rather than patched copies of the PFP's,
  and the refresh sends them before blanking the character plane. The MCDU
  keeps graphics-only clearing if its packets cannot be imported, with a
  warning rather than silence.
- Tests run: the refresh executed against the real MCDU and reported 1 found,
  1 refreshed; PFD self-test; `launch.py --check`.
- Needs a look in the cockpit: whether the MCDU's page now actually clears.
  The mechanism explains the symptom, but only the panel can confirm it.

## 2026-08-27 - Display wiring rebuilt after an older final.py was restored

- An older copy of `bridge/final.py` was pasted in, which silently removed
  every piece of display wiring while all the renderers stayed in place. The
  symptom is quiet rather than loud: the ND falls back to its placeholder page
  and the speed tape loses its bands, because a renderer with no values simply
  draws nothing.
- Rebuilt on top of the restored file rather than over it, so the newer work
  in that copy - the startup display refresh, the BB36 path router and the
  MCDU vertical fitting - is untouched. Nine pieces were restored: the
  speed-awareness datarefs, the trend on the fast sample, change detection for
  all thirteen new values, the telemetry and frame budgets, the ND renderer
  import, the ND datarefs, the ND live snapshot, the ND page block replacing
  the placeholder, the ND states marked as states rather than motion, the
  per-display bezel shift, and the separate FMC font.
- The self-test now refuses to pass if the ND renderer is not wired, if the
  live ND snapshot does not supply every value the renderer declares, or if
  the FMC and PFD paths share one font. Losing this wiring again will fail
  `--test-pfp-pfd` loudly instead of showing a placeholder quietly.
- `Backup/final_KNOWN_GOOD_display_wiring_20260827_033409.py` is a complete
  working copy. If final.py is ever replaced again, copying that file back
  over `bridge/final.py` restores everything in one step.
- Verified: PFD self-test, both layout contracts, differential checker,
  `launch.py --check`, all 38 PFD datarefs and all 22 ND values resolved
  against the running simulator, and the other session's work confirmed still
  present.
- Noted, not changed: `_cockpit_draw_nd` is now dead code - the old full-page
  placeholder drawer, defined but called from nowhere.

## 2026-08-27 - FMC and PFD paths load separate fonts

- **A regression of mine, found while looking at the MCDU.** The navigation
  display's static shapes are stored in spare glyph codes of the PFD font.
  Both path routers were handing that same font to their FMC page, and an FMC
  page prints those codes as text: Zibo's CDU output contains lower case, and
  `_normalize_24` turns a degree sign into a lower-case "o". So compass tiles
  appeared in the middle of FMC lines. That is what the two paths were
  conflicting over - they each opened their own HID handle, but shared one
  font resource.
- The FMC/PFP text pages now load `PFP_FMC_FONT_FILENAME`, the factory
  resource, which keeps its own glyphs and its own 24-column grid geometry -
  what those pages were authored for. The PFD path keeps the cockpit font with
  the display shapes. Separate handle, separate font, separate state, on both
  BB35 and BB36.
- The PFD self-test now refuses to run if the two paths are ever pointed at
  one font, naming the reason.
- Verified rather than assumed: all 28 tile glyph codes were compared between
  the two font resources and differ in every one, so the FMC font keeps its
  real letters, including the lower-case "o" a degree sign becomes.
- Tests run: PFD self-test with the new font guard, both layout contracts,
  `launch.py --check`, and a direct glyph-by-glyph comparison of the two fonts.
- Not verified here: how the FMC page looks on the panel with the factory
  font's wider cells. Its grid is what that font was authored for, but it
  wants a look in the cockpit.

## 2026-08-27 - The ND on the MCDU 32

- Checked before building: the BB36 MCDU runs the same shared graphical
  worker as the BB35 PFP, with the same page order, so the new navigation
  display, its four modes, the EFIS switches and the route already reach it.
  Nothing needed porting.
- What does not transfer is the bezel. The horizontal shift is now a property
  of each display rather than of the renderer: every canvas can carry
  `_muslimsim_nd_shift_x`, and the two units are set separately as
  `PFP_ND_SHIFT_X` and `MCDU_ND_SHIFT_X`. Both start at 24; the PFP's was
  measured against the panel, the MCDU's is a starting value until it is seen
  in the cockpit.
- The MCDU's existing vertical fitting is inherited automatically: the BB36
  canvas compresses Y below the FMA region to keep content off its bottom
  bezel, so the ND is fitted the same way the PFD already is. The compass arc
  is slightly elliptical there as a result, which is the trade that fitting
  already makes.
- **A real fault the new guard caught.** Shifting the frame moved the
  full-screen background clear with it, leaving a strip of the previous page
  standing down the left edge. A fill spanning the whole width is now
  recognised as background and stays put; content shifts and clips. The
  layout contract additionally rejects any shift that would drop an item off
  the display - it accepts up to 72 px and refuses 96.
- Verified the MCDU path end to end offline, through its own fitted canvas
  rather than the renderer alone: a complete frame is 312 reports and an
  unchanged one is 1.
- Tests run: PFD self-test, both layout contracts, differential checker,
  `launch.py --check`, and an MCDU-fitted ND frame rendered from the live
  aircraft's own position and route.

## 2026-08-27 - ND shifted clear of the bezel

- The ND sat left of centre on the panel: the page was centred on the frame's
  own middle, but the PFP bezel masks a strip at the physical left edge, so
  the middle the pilot sees is further right.
- The whole page - compass, aeroplane symbol, route, and all four corner
  readouts - now shifts together by a single constant, `ND_SHIFT_X`, set to
  24 pixels. One number to raise if it still reads left, or lower if the
  right-hand readouts crowd the bezel.
- Checked that the shift cannot push anything off the other edge: with it
  applied the compass arc reaches x 570 and the rightmost readout ends at
  579, both inside the display, and the layout contract asserts it.
- Tests run: ND layout contract with the shift applied, three shifted frames
  rendered from the live aircraft, `launch.py --check`.

## 2026-08-27 - The EFIS mode knob did nothing: the live ND path

- **The fault.** The ND's mode, range, switches and radios were being sampled
  and then thrown away. The live display loop reads through the smoothing
  telemetry hub, and that path's ND snapshot asked for three values -
  ground speed, latitude, longitude. Everything added for the modes was
  resolved, subscribed and updated, then dropped before the renderer saw it,
  so turning the EFIS mode knob changed nothing on the screen.
- The earlier work was verified against `_cockpit_secondary_snapshot`, which
  is not the function the live loop calls. The snapshot now supplies every ND
  value, and the route with it.
- **A second fault found in the same place.** The hub's alpha-beta motion
  filter was being applied to states as well as motion. A mode selector read
  1.58 between VOR and MAP, and a released push button read -0.45. Modes,
  ranges, buttons, the tuned navaid, wind and true airspeed are now taken as
  sampled; only position, track and ground speed are smoothed, which is what
  the filter is for.
- **Guarded so it cannot recur.** The ND renderer declares `ND_VALUE_KEYS`,
  and the PFD self-test now fails if the live snapshot does not supply every
  one of them. A value that is sampled but never handed over draws nothing and
  looks exactly like a broken switch, which is precisely how this presented.
- Verified end to end against the running simulator this time: the hub was
  started, allowed to connect, and its ND snapshot read back - map_mode 1.0
  exactly, ctr 0.0, range 80, and 29 route points.
- Tests run: PFD self-test with the new guard, both layout contracts,
  differential checker, `launch.py --check`.

## 2026-08-27 - The ND draws the FMC route

- MAP and PLAN now draw the active route: the magenta line the aeroplane is
  following, with a fix symbol at each waypoint, projected around the
  aeroplane heading up, and north up in PLAN.
- The map scale follows the EFIS range switch: the compass radius stands for
  the selected range, as it does on the aeroplane, so the route redraws to
  scale from 5 NM to 640 NM.
- Read from Zibo's own `fms/legs_lat` and `fms/legs_lon`. Those arrays hold
  256 slots and are not self-describing, so the route was verified rather than
  assumed: every leg's geographic length was checked against the FMC's own
  `legs_dist`, and all agreed to within a tenth of a mile. That is what
  established the array really is one continuous path, including a 209 NM leg
  that looked wrong until it was checked.
- Route legs are clipped to the display and then rasterised as runs along
  their major axis, rather than stepped in fixed blocks. A leg can be
  hundreds of miles long while the display shows ten; stepping the whole leg
  spent about 870 commands drawing off-screen. A complete ND frame with the
  route is now 507 reports at 10 NM, and an unchanged frame is still one.
- The ND's values are now sampled at the rate each actually changes: position
  and track every frame, the switches and radios once a second, and the route
  every five seconds, cached between reads.
- Tests run: the ND layout contract, extended with routes that run off the
  display and with the aeroplane in centred and plan modes; line clipping
  asserted directly; frames rendered from the live aircraft's own route at 10,
  40 and 160 NM; PFD self-test, PFD contract, differential checker and
  `launch.py --check` all still pass.
- Known limits: the whole route is drawn rather than only the leg ahead,
  because the active-leg index is not confirmed; waypoint names are not drawn,
  as the idents are string arrays; and one dataref read over X-Plane's Web API
  costs about 54 ms, which - not the drawing - is what limits how often the ND
  page can update.

## 2026-08-27 - ND modes: APP, VOR, MAP, PLAN, and the EFIS switches

- The ND now draws what the EFIS mode selector asks for instead of one layout
  regardless: APP and VOR add the tuned course line, its deviation scale and
  bar, and a navaid block giving the station, its frequency, the selected
  course and DME distance. MAP keeps the map arc. PLAN swings the display
  north up.
- The CTR switch now closes the arc into a full compass rose with the
  aeroplane at its centre, in every mode that has one, carrying the track line
  and heading bug with it.
- The EFIS overlay switches - WXR, STA, WPT, ARPT, DATA, POS, TERR, TFC - are
  read and annunciated when selected. Their map content needs navigation data
  the bridge does not read, so pressing one says so plainly rather than
  drawing invented returns on a navigation display.
- Values confirmed against the running aircraft first, as before:
  `EFIS_control/capt/push_button/*`, `nav1_course_degm`, `nav1_dme_dist_m`,
  `nav1_freq_hz`, and Zibo's captain-side `laminar/radios/pilot/nav_hdef`.
- Three faults the offline checks caught before the cockpit did: curve squares
  were bounds-checked at their first pixel rather than their far corner, so
  one at the bottom edge ran off the display; the navaid block's course and
  distance were dropped for not fitting their slots; and the overlay
  annunciation row sat on top of the tuned frequency in VOR and APP.
- The ND's periodic recovery frame is spaced to once a minute rather than
  inherited from the PFD, because a full rose is most of a complete frame.
- Costs measured per mode: complete frame 277 (MAP), 326 (APP), 458 (PLAN),
  468 (CTR); an unchanged frame is one report in every mode.
- Tests run: the ND layout contract across all four modes, centred, every
  overlay on, and all values missing; five mode frames rendered; PFD
  self-test, PFD layout contract, differential checker and `launch.py --check`
  all still pass.

## 2026-08-27 - Navigation display rebuilt as a 737-800 ND

- Replaced the placeholder ND page - a titled box with a small arc, latitude
  and longitude - with a real navigation display in
  `muslimsim/devices/nd_renderer.py`.
- Laid out as the aeroplane lays it out in expanded mode: the aeroplane symbol
  low and centred, the compass arc sweeping across the top around it, ticks
  every five degrees, numbers every thirty with N/E/S/W at the cardinals, the
  lubber line above, and the heading readout boxed at the top centre with MAG
  beside it.
- Added the numbers that belong in the corners: ground speed and true airspeed
  at the top left with the wind direction, speed and arrow beneath them, and
  the map mode and range at the top right.
- Added the dashed half-range arc with the distance it stands for at both
  ends, the dashed track line the aeroplane is actually following, and the
  magenta selected-heading bug, which parks at the edge of the arc when the
  selection is off-scale rather than disappearing.
- Every value was confirmed against the running aircraft before use:
  `ground_track_mag_pilot`, `wind_speed_kts`, `wind_heading_deg_mag`,
  `map_range_nm`, `true_airspeed`, and Zibo's own
  `EFIS_control/capt/map_mode_pos`. A value the aircraft does not publish
  only warns, and the renderer draws nothing for it.
- The ND uses the same differential output as the PFD, so its static arc is
  paid for on page entry rather than every frame: a complete frame is 269
  reports and an unchanged frame is 1.
- Tests run: the ND's own layout contract across normal, wrapped-heading,
  extreme-range and all-missing states; a frame rendered from live in-flight
  values; the page driven end to end through the bridge's own ND functions
  with live values, confirming 269 reports then 1; PFD self-test, layout
  contract and `launch.py --check` all still pass.
- Not yet drawn, because the data is not wired: the FMC route and waypoints,
  VOR/ADF pointers, airports and navaids, terrain and weather returns.

## 2026-08-27 - Frozen PFD: three faults found and fixed

- **The freeze.** The reference-bug labels passed an alignment argument to
  `_draw_text`, which does not take one. `flaps_speed` is always published, so
  the flap bug's label was drawn on every frame and raised every frame. A
  bridge started while that code was loaded would render no further frames and
  the panel would hold its last picture. Fixed by moving the alignment onto
  the slot, where it belongs. **A running bridge must be restarted to pick
  this up**, since it holds the code it imported at start.
- **Change detection did not know about the new values.**
  `_pfp_graphical_state` rounds telemetry to decide whether a redraw is worth
  sending, and the speed bands, bugs and trend were not in it. The trend arrow
  would have sat still until some unrelated value moved. All thirteen are now
  part of the state, with the trend stepped to the same half knot the renderer
  rounds its tip to.
- **A pre-existing self-test failure.** `expected_graphical_state` was written
  against coarser rounding steps and was never updated when those steps were
  refined, so `--test-pfp-pfd` had been failing before any of today's work.
  Confirmed by running the check against a backup taken before it. The
  expected state is now generated from the live rounding steps.
- Two budgets were raised deliberately rather than worked around: the
  telemetry budget from 24 to 38 values, and the complete-frame USB budget
  from 250 to 290 reports, both documented at the assertion with what the
  extra buys. The differential frames that follow a complete one are
  unaffected.
- Tests run: `--test-pfp-pfd` now passes (265 full, 183 refine, 1 steady
  reports); `launch.py --check`; layout contract; the differential checker's
  full set including periodic recovery and offline-to-live recovery; and a
  frame rendered from live in-flight values read out of the running simulator,
  which is the case that was crashing.

## 2026-08-27 - Airspeed trend vector

- Added the green airspeed trend vector: a line from the speed pointer to
  where the airspeed will be in ten seconds at the present acceleration, with
  an arrowhead showing which way it is going. It hides below four knots of
  projected change, as the aircraft does.
- Wired to the captain's own `airspeed_acceleration_kts_sec_pilot`, with
  Zibo's `laminar/B738/autopilot/acceleration` as the fallback; both were
  confirmed reading the same value on the running aircraft. It is sampled on
  the fast cycle, since an arrow that lags the speed it projects from is
  worse than no arrow.
- The tip is rounded to half a knot so live acceleration noise cannot flicker
  it, and cannot spend display traffic redrawing sub-pixel movement.
- Moved the reference-bug labels outboard of the speed tape to give the trend
  the gutter. The aircraft puts them inboard, but at this cell size both
  cannot have the same 34 pixels, and a label cut to one character stops
  being a label. A label that would fall on the live-speed readout is
  dropped; its mark still shows.
- Fixed an alignment argument passed to the wrong function in the bug labels,
  which would have failed the moment V-speeds were set. The layout contract's
  scenarios now carry bands, bugs, a flap lever and an acceleration, so that
  whole group is exercised by the offline check instead of only in flight.
- Tests run: `assert_layout_contract()` with the extended scenarios; band and
  bug frames rendered; the differential check still matches a full repaint;
  the trend dataref resolved and read on the running simulator; frame sent to
  the PFP.
- Live cockpit confirmation still needed: that the arrow tracks sensibly
  through a real acceleration and deceleration.

## 2026-08-27 - Speed awareness bands, flap and V-speed bugs

- Added the 737 speed-awareness bands to the PFD: red barber poles beyond the
  limit speeds and amber bands from each manoeuvre speed out to them.
- Added the reference bugs: V1, VR, V2, VREF, and the flap manoeuvre speed,
  which is the one that says when to move the flap lever. The flap bug is
  labelled with the lever's own detent, UP through 40.
- Rearranged the speed tape's inner strip to make room: numbers, then ticks,
  then the bands against the inboard edge, as on the aircraft.
- Wired the values to Zibo's own PFD datarefs, confirmed against the running
  aircraft rather than guessed. Added `tools/probe_speed_datarefs.py`, which
  reads X-Plane's dataref catalogue and names the exact refs to use.
- This build publishes no `max_speed_show`. A band whose flag is absent is now
  shown, and only an explicit zero hides one, so the missing flag cannot
  silently drop the VMO barber pole.
- A bug label gives way when it would collide with one already placed; the
  mark itself always shows.
- Tests run: `assert_layout_contract()`; band-flag semantics asserted
  directly; all offline scenarios rendered, including two new ones carrying
  real Zibo band values; the differential check still matches a full repaint;
  every new dataref resolved against the running simulator (13 of 14, the
  fourteenth confirmed absent); `launch.py --check`; frame sent to the PFP.
- Live cockpit confirmation still needed: that the bands track correctly
  through a flap schedule on a real approach.

## 2026-08-26 - PFD fine tuning: bank scale angles, tape ticks, selected heading

- Corrected the bank scale: its marks were a hand-placed list sitting at
  roughly 13, 27, 42 and 56 degrees while claiming to mark 10, 20, 30, 45 and
  60. They are now stepped along their true radius and read correctly.
- Moved the speed tape's tick marks inside the strip, beside the numbers, as
  the aircraft draws them, freeing the gutter for the speed bug and trend.
- Added the magenta selected-heading readout below the heading rose, which
  every reference photograph shows and the panel did not have.
- Removed the heading box from the design sheets: the aircraft reads heading
  from the arc under the lubber line and has no such box.
- Fixed altitudes below sea level, which the readout and the tape both blanked
  as invalid. The readout now puts a minus in the ten-thousands position and
  the tape labels negative values.
- Widened the minimums zone to ten cells so a five-figure setting cannot be
  silently dropped, the same fault the barometric unit had.
- Gave the barometer a gap between its value and its unit.
- Raised the arc's side numbers clear of the new heading readout, which they
  overlapped by four pixels.
- Added `zero`, `extreme` and `below-sea-level` scenarios so these edge
  conditions are checked by name instead of by hand.
- Tests run: `assert_layout_contract()` plus explicit capacity checks that the
  longest minimums and barometer labels fit their zones; all ten offline
  scenarios rendered; `launch.py --check`; display-only frame sent to the PFP.
- Live cockpit confirmation still needed: that the corrected bank scale reads
  properly against a real banked attitude.

## 2026-08-26 - PFD visual pass: design sheets, offline emulator, redrawn readouts

- Added `tools/build_pfd_design_png.py`: the agreed 737 PFD design drawn to
  PNG sheets in `PNG/` on the live renderer's own 640 x 480 contract, plus a
  protected-zone map.
- Added `tools/render_pfp_frame_png.py`: an offline emulator of the PFP's
  native command surface that runs the live renderer, saves the frame as a
  PNG, and reports the real USB cost. It opens no hardware and no simulator.
- Replaced fixed-block drawing with exact scanline rasterisation and a blended
  horizon edge, which removed the staircase from the rounded attitude corners,
  the banked horizon, the pitch rungs, the compass rose, and the V/S needle.
- Redrew the selected-speed bug, the live speed readout, the vertical-speed
  wedge, and the altitude readout from cockpit reference photographs,
  including rolling drums and the green ten-thousands hatch.
- Enlarged the cockpit font's artwork inside its unchanged 17 x 29 cell, so no
  zone, bridge path, or upload behaviour had to move.
- Added `tools/build_pfp_shape_tiles.py`: the heading rose and V/S wedge baked
  into spare glyph codes of the existing font, which cut about 56 ms from every
  frame. The renderer falls back to rectangles when the generated tile module
  is absent.
- Added the approach minimums presentation: `BARO` with a tape pointer,
  `RADIO` as text only, both turning amber at or below the setting.
- Fixed a barometer fault found while drawing the minimums: the unit zone held
  two native cells, so `HPA` was silently dropped and hectopascals showed with
  no unit. The zone is now three cells.
- Tests run: `assert_layout_contract()` after every renderer change; all seven
  offline scenarios rendered; tile output verified pixel-identical to the
  rectangle path; frame cost measured against the bridge's own canvas and timed
  on the panel at about one millisecond per HID report; `launch.py --check`;
  display-only frames sent to the real PFP with `tools/show_pfd_preview.py`.
- Live cockpit confirmation still needed: whether the larger cockpit type is
  too heavy on any label, and that the shape tiles upload correctly on a cold
  start of the panel rather than only after a re-upload in the same session.

## 2026-08-26 — living documentation created

- Added the master project history, system architecture, device reference, and
  this changelog.
- Added a permanent documentation-update rule in `AGENTS.md`.
- Linked the existing detailed PFD history to the project-wide record.
- Verified that all living documentation files and their required update-rule
  markers are present.

## 2026-08-26 — WinCtrl rudder pedals integrated

- Added the WinCtrl Orion Combat Rudder Pedals as an independent device.
- Default mapping: axis 0 left toe brake, axis 1 right toe brake, axis 2
  rudder.
- Added protected no-jump pickup for rudder and both toe brakes.
- Added `--test-pedals`, pedal inversion flags, `--no-pedals`, and launcher
  `--without-pedals`.
- Confirmed syntax, pedal, PU light, starter retract, PFD, and launcher checks.

## 2026-08-26 — MuslimSim modular layout and PFD reliability work

- Moved active work into the managed `MuslimSim` folder and `Backup/` policy.
- Added device boundary modules and one launcher for PU, WinCtrl, AGP, PFP,
  and pedals.
- Reworked PFP output into packed native HID frames and isolated it in its own
  worker.
- Refined native PFD layout, compact type, protected zones, compass geometry,
  standby presentation, and developer stamp.

## Earlier work in this project session

- Established PU Overhead, P7 annunciator, COM5, starter/ignition, and
  no-write startup safety behaviour.
- Added WinCtrl Boeing throttle/reverse mapping with 737 idle at physical 0
  and separate red-REV behaviour.
- Added AGP flight/electrical/navigation display work, gear control/indicator
  work, and smart autobrake gesture handling.

## Required format for the next entry

Add new work at the top, using this pattern:

```markdown
## YYYY-MM-DD — short change title

- What changed.
- Why it changed or what it fixes.
- Tests actually run.
- Any live-cockpit confirmation still needed.
```

## 2026-09-02 — Portable Device Platform V2: shared HID/SDL runtime locators

- Extended the Phase-1 product registry into the shared SDL identity source used by the live bridge.
- The one existing SDL owner now identifies PU, WinCtrl throttle, Orion pedals and TCA Boeing by stable product definition rather than hard-coded index assumptions. The advanced custom pedal-name override remains available and unchanged.
- Added HID locator enumeration/resolution that exposes current HID paths only as runtime locators. Unit serial numbers are not retained by the product manager.
- Added SDL locator resolution where index, instance ID and GUID are explicitly runtime-only. A replacement product can move index/GUID and retains the same MuslimSim key/profile.
- Multiple identical simultaneous SDL units are not guessed by enumeration order. A still-valid prior runtime instance can be reused; otherwise the resolver returns ambiguous.
- Background Studio discovery still does **not** open SDL joystick objects. SDL metadata inventory is opt-in diagnostics with Studio closed.
- No device packet protocol, output authority, aircraft mapping, calibration, HOWALT transport, PU serial protocol, BB35/BB36 display path or Studio UI was changed.
- Offline checks: Portable V1 PASS; Portable V2 PASS; global output authority 67/67 PASS; Hardware Lab PASS; AGP radio 119/119 PASS; PDC/PAP3/FCU-EFIS PASS; TCA Boeing 158/158 PASS; `launch.py --check` PASS.
- Live check still required after install: restart Studio and smoke-test the shared SDL owner (PU, throttle, pedals, TCA), then unplug/replug at least one SDL product and confirm the same logical device key returns.

## 2026-09-02 — Portable Device Platform V3: clean-PC bootstrap

- Added `muslimsim/hardware/windows_bootstrap.py`, a read-only runtime/PnP
  readiness layer and guarded signed-INF installer framework.
- Added `driver_family` deployment metadata to the stable product registry.
  This does not participate in device identity or change any existing owner.
- Added `driver_bundles.json`. It currently contains no unreviewed kernel
  driver package. MuslimSim will only install a future local INF after exact
  SHA-256 and Authenticode/signer validation.
- Added `MuslimSim.exe --readiness`, `--readiness-json`, and
  `--bootstrap-drivers`. Normal Studio startup is unchanged in this phase.
- PyInstaller now bundles the driver manifest and will include only reviewed
  `.inf/.cat/.sys/.dll` assets placed under `drivers/`.
- No `bridge/final.py`, Studio control/layout, device protocol, output path, or
  aircraft-power behavior was changed.
- Offline tests: Portable V1/V2, V3 bootstrap, runtime bundle, Hardware Lab,
  global output authority, AGP, PDC, PAP3, FCU/EFIS, TCA and launcher checks.
- Live Phase-2 probe identified the working Orion pedals HID interface as `4098:BEF0`; V3 now records that stable product identity while leaving the proven single SDL control owner unchanged.


V2 also publishes the already-open private control-channel port with flushed stdout after in-memory lab wiring and before simulator-down physical output initialization. This is startup discovery only; the server, token, hardware owners, mappings, simulator dispatch and display paths are unchanged.
