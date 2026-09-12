# MuslimSim project history

## 2026-09-12 — Constant-push warning and three-second preparation interval

Owner confirmed the independent constant-push force now has the intended strong
response. Added a prominent warning: the first push can be strong and hands must
stay on the yoke/control stick throughout the test. Every explicit constant-push
Start receives a bridge-enforced three-second countdown before hardware setup
or force activation. The window shows the remaining countdown. Stop, closing
the window, lost contact or selecting another test cancels the pending push.
The requested test duration starts after activation, not during the countdown.
Movement/vibration/resistance tests retain their existing timing and forces.
Existing gain-off/restoration and protected assignments remain unchanged.


## 2026-09-12 — Constant-push slider is independent

Owner reports weak A210 constant push. Read-only device queries showed overall
intensity and max torque both 100, output gain zero after the test, and all four
builtin resistance fields zero. Studio's manual constant force was multiplied
by the unrelated Movement strength setting. Removed that hidden multiplier:
constant push -100/0/+100 now requests -32000/0/+32000 regardless of movement
strength. Both bases share this manual-test fix; aircraft-driven profile curves
and saved files are unchanged. UI labels the independent strength; diagnostics
show requested_constant_force, including the last test after it stops.

Guard: test_force_test_session covers both bases, both signs, zero, movement
strength 0/15/50/100%, active direction changes and original-setting restoration.
No new output path, registration change or SDK dependency. Existing Stop,
deadlines and captured gain-off remain. The physical cause is not fully proven:
if the prior Movement strength was already 100, this fix alone cannot increase
that run's magnitude. A Studio physical retry is still needed.


## 2026-09-12 — Blue dropdown text and simplified Studio toolbar

All shared dropdown styles now use Studio blue (#5aa9ff), including closed
values, opened lists, selections and menu items. Disabled text uses muted blue.
Applied at startup in Studio, the control-panel theme, Hardware Lab and Device
Platform; child dialogs inherit it. Removed the Eye focus and Wake PU panel
controls from Studio's toolbar and the obsolete wake-button state updates.
Device input/output, force tests, saved assignments and protected faceplates
are unchanged. This is a presentation-only change; no new hardware output.
Theme setup runs once at startup, with no per-frame work.


## 2026-09-12 — Studio force-test Windows write-length regression

The first Studio physical retry stopped at the report-length check before
movement. The new integration required returned length == command length.
Windows HIDAPI output writes can return the larger padded report length;
that successful result was incorrectly rejected. Accept counts >= command
length, retain exceptions/negative/zero/short-write rejection, and report the
report ID plus requested/returned counts on a real failure. Commands, force
levels, mappings, timers and gain-off/restoration are unchanged.

Guard: tools/test_force_test_session.py now simulates Windows padded output
counts throughout the real session/lifecycle tests, also tests exact counts,
and rejects failed/short output and feature writes. The previous fake only
returned exact lengths and therefore missed this Windows behavior.
Physical Studio retry remains required. No vendor SDK dependency added.
Reference: https://github.com/libusb/hidapi/blob/master/windows/hid.c (hid_write).


## 2026-09-12 — Bench-confirmed force tests integrated into Studio

Studio's Feedback & Tests now uses MuslimSim's independently authored
capture-tested output session for both A210 and AB6. Separate roll and pitch
buttons and a diagonal button use the full tested 0–65535 position range,
speed 20, temporary centering spring 100 and per-axis travel ratio 100.
Movement strength controls per-axis follow force through its full 0–100% range.
The AB6 pitch ratio previously read 20; its original value is restored afterward.
Targets are percentages of native travel, not measured degrees.

Vibration allocates only the requested capture-derived effect blocks. Spring,
damping, friction and inertia have individual Start buttons in Test resistance.
Damping/friction/inertia combine the bench-tested built-in setting with their
own HID condition on both axes (coefficient up to 32000, zero deadband), and
temporarily use overall intensity 100. AB6's previous overall 70 is restored.
Constant push retains signed 32000 capability as its separate test. New-window
strength defaults are 100%; existing saved test values are preserved and displayed.
The .mslm test settings remain separate from flight effect curves and assignments.

One existing FeedbackService owns each output session. Opening/loading starts
nothing. Explicit Start is bounded to five seconds, with Stop, window-contact
expiry and the captured host lease. Gain-off, position-mode clear/target reset
where applicable, effect reset and readback-verified original-setting restoration
run on completion, cancellation, setup failure and shutdown. Restoration failures
are reported rather than hidden. No joystick input reader, device mappings,
ECAM, WINCTRL throttle or TCA faceplates/banks changed. Aircraft-driven feedback
keeps the existing power/telemetry gate and engine; this task installs manual
Studio tests, not automatic full-strength flight behavior.

No SDK source, library or asset is included. New output code uses MuslimSim's
existing protocol library and owner captures/physical testing. Hardware names
identify compatibility; the test feature and implementation are MuslimSim's.

Validation: full tools/test_known_regressions.py PASS under Studio's Python 3.11;
new tools/test_force_test_session.py covers full-travel signed targets, diagonal
ordering before gain-on, both-axis condition reports, captured vibration patterns,
delta updates, original-setting restoration, setup/cleanup failures, ownership,
Stop, expiry and lost UI contact using simulated transports. Real Tk layout and
routing checks PASS for both device windows. Per-base work is bounded to two
axes/the selected effect; 100 unchanged test ticks emit zero target updates.

Physical evidence comes from the isolated tests: A210 roll/pitch travel, AB6
pitch travel/right roll/one diagonal, AB6 vibration and improved resistance were
owner-confirmed. The stronger AB6 inertia setting was accepted. Studio physical
confirmation and aircraft-specific in-flight feel/latency still need user tests.


## 2026-09-12 - Confirmed A210 turning, test resistance tuning and AB6 mode

Owner now confirms A210 turns using the capture-matched resistance baseline;
smoothness and the requested +/-90-degree travel still need tuning and measured
calibration. Added Test resistance with independent builtin centering spring,
damper, friction and inertia controls. These update an active timed test and
save under tuning.test.physics in .mslm; defaults remain the now-working zero
baseline, with no automatic changes to saved values. Explicit preset resistance
still takes precedence when selected. The existing 32000 force ceiling remains.
A spring-centre percentage is not claimed to be a measured physical angle.

AB6 remains physically unresponsive. Working GearBumps_AB6.pcapng identifies
its device 42 as 346E:1002 and returns param 0x85 = 1 three times, with 0x99=100
during effects. Our older connection-only extraction incorrectly labelled mode
0 as force-feedback-active. Corrected AB6 startup to mode 1 using the verified
single-value encoder/checksum. The older zero was observed in a Cockpit
connection, not a working force-effect capture. Field restrictions, captured
channel 4, shutdown/disarm and shared input ownership remain intact. Physical
AB6 output still requires owner confirmation; this is not declared solved.


## 2026-09-12 - Manual test compared with working pitch/roll captures

The owner reports that raising the limit did not restore useful movement and
asks for a file-level investigation. Compared the working benchmark's complete
replay, Trim.pcapng serial replies and condition reports, and AB6 captures.
Trim.pcapng reads back af/b0/b1/b2 as zero throughout both trim tests (11 replies
per field, AY210 device 51); it requests CP offset 14745 on pitch offset 1 and
roll offset 0. Current tests instead supplied af=100 and b0=10 by default.
The original successful benchmark also explicitly clears all four before its
HID spring ramp. GearBumps_AB6 records its own af=0 write at effect setup.

Manual-test default builtin spring/damper/inertia/friction now match that proven
zero baseline. The HID movement effect still follows the full 0-100% slider
with the owner-selected 32000 ceiling; this does not lower requested force.
The explicit Use fixed preset resistance settings option still overrides those
values when selected. Saved files, flight profiles, bindings, working A210
vibration configuration and device ownership remain intact. Physical resolution
still requires confirmation; no successful packet test is counted as movement.

Validation: full known-regression suite, focused default/override physics tests
and whitespace checks PASS. Latest observed prior-run diagnostics still show
af=100/b0=10; the new baseline has not yet been physically confirmed.


## 2026-09-12 - Owner-selected 32000 force ceiling

The owner explicitly specifies a 32000 limit and requests no hidden reductions.
Spring coefficient ceiling is now 32000 for both bases; profile gain still
scales it. Manual movement sliders span 0-100% on both devices. Removed the
extra 35% multipliers from manual movement, vibration and constant push.
Manual constant-push maximum is explicitly 32000; vibration 100% uses its
base-specific captured reference magnitude. Current slider values and saved
presets are not silently changed to maximum. Timers, reconnect grace, Stop,
lost-window expiry, signed bounds and existing mappings remain intact.

Owner reports extremely gentle A210 movement at the old 35% limit; A210
vibration is confirmed. Useful pitch travel and AB6 physical effects still
need validation. This entry supersedes earlier temporary 35%/28000 limits.

Validation: full known-regression suite, focused packet/lifecycle checks,
real Tk window checks and whitespace checks PASS. No 32000 physical test
was started by the installer.


## 2026-09-12 - A210 manual pitch strength ceiling and test outcome

Owner's isolated pitch test was verified in live diagnostics: pitch CP offset
14745, zero deadband, coefficients 9800, no physical response. The new manual
35% limit was below the existing capture reference 16384 and the previously
owner-tested 28000 ceiling. A210 manual strength now spans 0-100% of that
existing 28000 ceiling, with default 15%, unchanged saturation/trim limits,
timed operation and Stop. AB6's limit and A210's working vibration path remain
unchanged. This makes the previously proven stiffness range reachable; it is
not a claim that pitch movement has been physically fixed.

The test window now distinguishes timed completion, explicit Stop, lost-window
contact and connection failure instead of showing only hardware output inactive.
Physical A210 pitch and AB6 tests remain unresolved pending validation.


## 2026-09-12 - A210 movement test and AB6-specific effect setup

Owner physically confirms A210 vibration works. A210 roll/pitch and all AB6
output were reported nonfunctional despite software writes. Manual spring
strength was scaled a second time and inherited a 5% deadband. Movement tests
now use zero deadband, direct strength capped at the existing 35% maximum, and
the captured trim-offset range. The movement slider is 0-35%; existing files
and simulator assignments are preserved. Both bases receive the captured
1df2 device-gain heartbeat in addition to effect-start heartbeats.

Decoded device descriptors in RunwayRumble_AB6.pcapng and GearBumps_AB6.pcapng
identify device 42 as VID:PID 346E:1002. AB6 uses periodic channel 4, not the
AY210 channel 7. Added its exact 14-message reset/Feature/condition-zero/gain-arm
setup from GearBumps_AB6 (0 through 0.192793 seconds from 1c03); this was absent
from the older serial-only Cockpit connection setup. Runway vibration uses
channel 4, frequency code 80, peak 6881; gear bumps use channel 4, code 35,
peak 3766 and their own captured arming packet. AB6 exposes these two verified
textures; other saved textures are preserved and reported as unverified, not
sent through AY210 channels. More AB6 effects still require capture validation.

Focused packet/lifecycle/reconnect tests, real Tk checks, full known-regression
suite and whitespace checks PASS. Physical A210 movement and AB6 response await owner
confirmation after reload. Stop, disarm, bounded tests and protected mappings
are preserved; merely opening/loading never starts a motor test.


## 2026-09-12 - Measured MOZA reconnect delay

Real connection-only probes measured firmware Host Disconnect after polling
stopped: AB6 2.08 seconds, A210 2.30 seconds. Reopening too soon maintains the
old connection without a fresh Host Connected event. The managed worker now
waits six seconds after closing an output connection before reopening it,
and applies that grace at worker startup. A full zero-effect session measured
4.47 seconds to the disconnect acknowledgment, so the earlier three-second
grace was insufficient in the real repeat test. Connection timeout is fifteen
seconds; once connected the requested motor-test duration remains at most five
seconds, with the same lost-UI lease. The UI displays the reconnect wait;
Stop/lease checks remain active and the timer starts only after connection.
Real zero-vibration checks reached Connected, applied zero effect values and
closed successfully both directly and through Studio's AB6 worker. This proves
connection/output dispatch; physical vibration and roll/pitch feel remain
unconfirmed. Earlier connection ordering alone did not resolve rapid retries.

Validation: full known-regression suite, focused handshake/reconnect tests,
real Tk checks and whitespace checks PASS. Real hardware zero-vibration repeat
checks PASS twice per base: AB6 connected at 7.05/7.03 seconds; A210 at
7.95/8.00 seconds, including the six-second grace. Every check sent Stop and
closed its owner. Nonzero vibration and movement still await owner confirmation.


## 2026-09-12 - MOZA manual-test connection failure

Owner reported no physical response. Live AB6 diagnostics showed test ticks
but no connection, no physics writes and no effect values. This is a failed
connection, not proof of a working motor test. Corrected AB6 startup to replay
its existing captured setup/latch on Host Connecting, before waiting for Host
Connected; AY210 retains its original post-connect ordering. Connection log
fragments now survive short polling calls. A test that never connects reports
a timeout, and the window reports an unavailable bridge instead of silently
dropping the request. Captured packet values, confirmed fields, test limits,
Stop/shutdown and all input mappings remain unchanged. Physical response still
requires owner confirmation after restart.


## 2026-09-12 - File-backed MOZA feedback and simulator-off motor tests

Added Feedback & Tests for both bases: independent roll/pitch centre sliders,
movement strength, captured vibration textures and strength, isolated constant
push, timed tests (up to five seconds), Stop, and a UI lease which stops tests
after lost contact. Tests never auto-replay on preset load. Explicit Save writes
all effect toggles/gains/textures, physics, curves and test settings into the
.mslm file; existing files are backed up before replacement. Preset files win
over bundled titles. New/Add/Remove and full JSON editing preserve custom curves.

One managed worker per base is registered before simulator connection, with
old FFB setup skipped when that owner exists. ToLiss and Zibo use the same
owner lifecycle; server shutdown closes both. Live output requires simulator
and readable aircraft power. Offline output requires an explicit timed test.
AB6 protocol field restrictions remain; tests use only captured report builders.
Disabled/missing effects clear stale conditions/constant force explicitly.

Created named Zibo/ToLiss starters for both bases without changing saved active
selections. Exported Boeing files now use engine N1 rather than on-ground as
the engine-rumble source; 777 gear/spoiler buffet is gated and pitch trim is
represented. These are software-corrected starting points, not physical tuning
certification. Existing device mappings/readers and protected faceplates remain.

Validation: fake-engine lifecycle/control tests and real Tk tab/layout checks
PASS. Required known-regression suite and whitespace checks PASS. Running
Studio registers both managed services; test records exist without reported
errors and both bases were stopped when observed. Physical feel/motion still
awaits owner confirmation. No installer sent motor commands. UI manual tests use reduced output limits and expire automatically.

## 2026-09-12 - Browse and load MOZA .mslm presets

Both A210 and AB6 preset menus now offer Browse… (.mslm), including before
simulator connection. The native file chooser accepts a file from any folder;
the authenticated bridge validates its format and device, retains a separate
copy without overwriting existing files, then Studio selects it through the
existing preset path. Original files are untouched. Name collisions receive
a distinct list name. Cancel does nothing; invalid/wrong-base files report an
error without changing selection. Delayed import callbacks retain their base.
No motor service is enabled and no device protocol or mapping changes.

Validation: focused preset/import tests and required regression suite PASS.
Reopen Studio to load the changed picker and bridge; live visual check pending.

## 2026-09-12 - MOZA presets available before simulator connection

Fixed A210 .mslm discovery/selection while its FFB engine is not registered:
the authenticated control server now lists validated preset files and stores
the chosen name in the existing device-specific sidecar without opening any
hardware. A registered engine keeps its existing live command route.

AB6 now uses the same dropdown, with independent names, selection and delayed
callbacks. Existing AB6 reference-calibration choices remain in that menu.
A210 .mslm files and mappings are preserved; AB6 uses its own preset folder.
The inspected setup has two valid A210 drop-ins and no AB6 .mslm drop-ins.
No A210 motor profile is copied or relabelled for AB6. The new-preset action
is shown only when its FFB service is registered; saved motor selection takes
effect through the existing engine startup path. AB6 motor enablement remains
unchanged. No new output, protocol, supervisor flag or power behavior.

Validation: focused offline picker tests and mandatory regression suite PASS.
Live Studio reload and visual acceptance still needed. Tests use temporary
profiles and fake callbacks/canvas, with no hardware handles or motor writes.

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


## 2026-09-11 - Public collaboration preparation

Documented the present need for development help and the intended one-time
purchase model if a paid release is made later. Added contribution guidance,
component licensing notices, and issue/PR templates. No blanket open-source
license or copyright transfer was added; existing third-party terms remain.
Verified documentation links and scanned existing Git history for credential
patterns with no matches. Documentation only; device code and profiles unchanged.

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

## 2026-09-11 - Matching PDC faces with independent physical feedback

The connected 3N PDC R (BB62) now shares the 3M PDC L flat layout with VSD added.
Controls retain the existing hardware catalog keys and optional learned sources;
no profiles, default assignments, cockpit roles or other device faces changed.
The PDC drawing now shows MINS/BARO rotation and short physical taps without a
simulator. Real owner input reached the existing bridge in simulator-off Practice;
offline and real-Tk checks pass, with updated UI acceptance pending restart.
BB62 VSD has an assignable location; its source is left unguessed until captured.

## 2026-09-11 - Simulator-independent controls preserved

Corrected the connected-only list regression: simulator/service downtime is not a
hardware unplug. Physical controls must remain available in Live and Practice with
no simulator. Generic offline labels and slow discovery no longer hide them. Saved
assignments, device readers, faceplates and TCA banks were not changed.

## 2026-09-11 - Device list follows physical presence

Owner requested removal of unplugged/unpowered hardware from the list and accurate
names for unknown hardware. Studio now uses physical connection evidence and clears
stale entries, without deleting the saved mappings used when the device returns.
Unknown hardware uses its actual reported name; audio-brand matches no longer count
as flight-control discovery. Aircraft power is not mistaken for USB disconnection.

## 2026-09-11 - Optional reassignment across devices

Owner clarified that every device must offer clickable Re-assign while keeping
all existing assignments intact. Studio now supports this through its existing
learned-source persistence and physical event stream. No migration or automatic
remapping is performed. TCA bank identities and existing hardware owners remain.

## 2026-09-10 - Preserve native imagery for a faster output path

Owner asks to keep the design for better display hardware rather than assume
more small changes can make current raster-over-HID fast. Recovery snapshot:
design_archives/native_airbus_20260910_211335. Includes provided teardown photos.
Existing runtime left unchanged. Faster protocol or verified video-output
hardware remains an investigation, not an implemented capability.

## 2026-09-10 - Both PFD tapes receive newest pending updates

Owner confirms jumping altitude and requests the same treatment for speed.
Staged PFD-only latest-delta replacement with committed-pixel shadow and fair
left/right/centre scheduling. Offline correctness and mandatory regressions
pass. Await Studio restart/live comparison; capture remains 2Hz, so this does
not establish smooth tapes or resolve initial-page load latency.

## 2026-09-10 - Physical native flight trial exposes excessive transfer latency

Owner reports 17s PFP3N loading and worse/intermittent MCDU completion. Native
image fidelity alone does not make the existing rectangle transport suitable
for smooth flight. Staged transition-only brightness, successful-write demand
renewal and actual USB timing diagnostics; offline slow-transfer and existing
regressions pass. Plugin is unchanged. Await Studio restart and measured live
results; do not claim physical latency or intermittent blanking resolved.

## 2026-09-10 - Native flight-image candidate deployed

Owner closed both programs. Process check confirmed closure; the tested native
PFD/ND candidate replaced only the isolated trial DLL, with matching SHA256
and rollback copy in Backup/native_flight_install_20260910_202214. Mandatory
regression tests passed again. Awaiting restart and live physical acceptance.

## 2026-09-10 - Aligned native PFD/ND prepared for physical trial

After the owner aligned navigation, the actual atlas showed valid attitude
and ND GPS PRIMARY/route. Added independent demand-driven PFD/ND image channels
to the existing BB35/BB36 owners, using the same proven SD rectangle transport
and full-width fit. Old plugin installations keep vector PFD/ND; new plugin
presence enables the image trial. EWD capture is prepared but not selectable.
No control paths changed. Mandatory regression, display and keypad tests pass.
Candidate compiled; deployment awaits closed Studio/X-Plane. Raw imagery is
accurate to sampled source pixels, but LCD transmission still limits motion.
Do not describe this milestone as smooth physical flight display acceptance.

## 2026-09-10 - Physical BLEED confirmed; extend native SD deck

The owner's sequential photos show both LCDs completing the native BLEED
image. Extended the reader to twelve simulator-command-verified SD page IDs,
full-width layouts, and dark-until-complete first-frame presentation. Pending
jobs no longer wait the ordinary refresh interval between batches. Hardware
acceptance of the new fit and actual loading time awaits Studio restart.
PFD/ND/EWD native-image streaming is still unfinished; a two-Hz system-page
reader is not evidence of adequate moving-flight-display performance.


## 2026-09-10 - Native LCD imagery did not pass physical acceptance

The owner reports old PFP3N output and white square patterns on MCDU32. Fresh
correct source pixels and running status did not establish hardware delivery.
Staged per-batch LCD refresh and explicit first-colour state, replacing the
unverified long uncommitted drawing job. Added image progress counters for
diagnosis. Offline pixel/framing tests pass; physical rendering remains open.


## 2026-09-10 - BLEED live-image handoff race identified

Physical old/new-page alternation coincided with the reader treating an
in-progress producer copy as source loss. Retain the last complete image
only while fresh, without extending the freshness deadline. A live 600-read
check had no unavailable results after the change. Physical acceptance awaits
Studio restart. The independent blank-BB36 startup fault now has observable
error reporting; its underlying cause is not yet established.


## 2026-09-10 - BLEED LCD stream deployed for live acceptance

With both applications confirmed closed, installed the checksum-verified
shared-memory stream DLL into the existing isolated trial plugin. Retained
the measured crop configuration and backed up the prior DLL. Both existing
display workers can consume it on restart; physical delivery and simulator
performance have not yet been verified with this new build.


## 2026-09-10 - First BLEED pixel-to-native-LCD integration staged

Both display owners now have a BLEED-only image adapter behind their original
power/self-test gates. A bounded local shared-memory plugin producer is built;
installation awaits simulator shutdown. Exact resampled captured-image pixels
and incremental USB budgets pass offline tests. No live hardware success or
acceptable simulator-performance claim yet. Other ECAM pages retain numerical
rendering until page identity and image delivery are validated in the cockpit.


## 2026-09-10 - First successful native BLEED image extraction

The local-only trial found the current ToLiss panel and captured real BLEED
digits/valves after startup. Measured EWD and SD regions replace the trial's
full-atlas window. This validates an image-source route around empty SD text
exports, not numeric recovery or physical LCD integration. Performance impact
remains unisolated; the simulator log also shows GPU-memory/texture-scale churn.

## 2026-09-10 - Local ECAM extraction trial deployed

After the owner closed X-Plane, installed the checksum-verified local-only
extractor in a new isolated plugin folder. Existing plugins and production
code were not replaced. Live discovery and performance acceptance are pending;
this does not yet supply BLEED numeric telemetry or BB35/BB36 raster output.

## 2026-09-10 - Complete ECAM button bindings and extraction preparation

T.O CONFIG and EMER CANC were missing from the ToLiss profile despite their
physical contacts already being learned. Both are now saved through the running
bridge, with the other 16 ECAM bindings unchanged. Native command existence
is verified; cockpit button effects still require operator acceptance.
An isolated, local-only XTextureExtractor trial build is prepared, not installed.
It excludes network streaming/continuous readback and fails dark without AC
power. This is a feasibility stage, not a replacement telemetry implementation.

## 2026-09-10 - Native BLEED export limitation reproduced

Three native SDK samples with BLEED selected (SDPage=1) reproduced empty SD
temperature text channels despite visible temperatures on the aircraft display.
This closes the native-versus-web transport question for this state, not the
missing-temperature defect. Production and aircraft controls were unchanged.
Evidence is preserved in `Backup/sd_probe_live_20260910_165858/Log.txt`.

## 2026-09-10 - Read-only SD probe installed for ground acceptance

Following operator approval and verification that X-Plane had closed, installed
the checksum-verified diagnostic into its own new plugin directory. No existing
simulator files were replaced. Native-versus-web BLEED comparison remains pending;
installation is not evidence that missing temperature telemetry is fixed.

## 2026-09-10 - BLEED telemetry source investigation

Traced historical XHSI SD-column extraction and prepared a bounded GET-only
native diagnostic to distinguish provider data from web-API behavior. The
diagnostic is compiled/offline-tested but not deployed. Research also identified
live texture extraction as a fallback requiring current-A321 region validation
and BB35/BB36 transport feasibility, not a ready numeric-telemetry fix.
Evidence and next acceptance gate: `docs/TOLISS_BLEED_SOURCE_RESEARCH.md`.

## 2026-09-10 - ECAM LCD degree glyph and SD decoder follow-up

Replaced unsupported degree characters with native hollow rings and preserved
SD text columns through embedded NUL cells. BLEED telemetry is still partial:
live temperature rows returned only NUL bytes, despite pressure being present.
No simulator controls, hardware ownership, startup or blackout logic changed.

## 2026-09-10 - Native ToLiss APU BLEED reconstruction (BUG-53)

The APU-on photograph exposed two different faults that had been conflated.
First, the page was receiving aircraft data but interpreting absolute manifold
pressure as gauge PSI and substituting cabin/TAT values for three separate
bleed-air temperatures. ToLiss's own SD integration establishes the real model:
subtract live ambient pressure, use `PackTemp` and normalized `PackFlow` only as
arc positions, and decode the engineering values from the colour-layered native
SD rows while BLEED is selected.

Second, pressure alone had been treated as proof that each engine supplied the
manifold. In the captured state the opposite is true: the APU and horizontal
open crossbleed feed both packs while both stopped-engine PRV/HP branches remain
amber and disconnected. The shared renderer now models sources and connections
separately. This also preserves the earlier engines-running recovery, but only
when that engine is actually running above N2 idle, its switch is on, the APU is
not the active supply and gauge pressure exists. Both physical displays continue
to share one read-only feed and one drawing implementation.

## 2026-09-10 - ToLiss GPU lamp and Boeing-style engine start (BUG-52)

The PU's ground-power annunciator had remained hard-dark in the ToLiss output
cache even when the aircraft's own ground-equipment model had a GPU attached.
P7 bit 12 now follows that exact attachment signal. It is the only annunciator
allowed before a DC bus is connected because the offered source powers its own
AVAIL indication; simulator loss and invalid telemetry still fail completely dark.

The two PU engine-start rotaries now own a temporary, explicit lease on the one
Airbus ENG MODE selector. A live GRD edge requests IGN/START while the WinCtrl
engine master remains the separate fuel-introduction step, preserving Boeing
operating semantics. Auto-return is not inferred from a single running flag: it
requires the matching master, FADEC, N1 and native N2 idle signature to remain
valid for a full second. Only then does the existing bounded common P1 actuator
return the physical selector and command NORM. Two simultaneous GRD selections
must both finish, startup contacts remain observation-only, and an OFF edge can
never shut down the newly started engine.

## 2026-09-10 - ToLiss PU overhead and native APU gauge (BUG-51)

The ToLiss runner had already taken sole ownership of the PU joystick but
discarded every event except the WinCtrl quadrant, leaving the overhead inert.
It now translates the physical 737-shaped controls only where the A321 has a
real counterpart. Most importantly, PU IRS 1 owns ADIRU 1 while PU IRS 2 owns
ADIRU 2 and 3 together. Shared Airbus controls use one arbiter rather than
competing writers, and Boeing-only pressurisation/igniter choices remain
Studio-observable instead of being guessed onto unrelated systems.

The physical APU EGT gauge is also an Airbus output for the first time. A
read-only worker converts ToLiss's real N, EGT, changing EGT redline and AVAIL
state into the existing captured P4 calibration: a real rise during start and
an exact mark-4 settled indication at AVAIL. The established COM5 worker stays
the only serial owner, and its writes are now timeout-bounded so shutdown never
writes or closes behind a stuck worker. Energized `DCBusVoltages`, not charged
battery terminals, own the power gate, and the first unreadable sample goes
dark. Landing lights converge to their endpoint while TAXI selects the proper
middle detent. Disabling or losing only AGP no longer disables PU inputs, and
no startup switch pose is sent to the aircraft.

## 2026-09-10 - ToLiss brake controls/lamps and FCU unit truth (BUG-50)

The B930 parking-brake contacts now command absolute ToLiss state after the
protected startup baseline. AGP autobrake ON/DECEL and brake HOT indications
come from ToLiss's own XP12 ATA 32 annunciator array and confirmed physical LED
selectors, so the simulator—not a momentary button animation or guessed
temperature rule—owns latching, disarming and lamp-test behavior. The BA01 FCU
now takes SPD/MACH selection from the actual X-Plane autopilot unit flag rather
than the captain PFD's Mach-caption crossover flag, eliminating the cruise
`.99` false Mach display without changing its speed value or controls.

## 2026-09-10 - Two-part A321 altitude readout (BUG-49)

The current-altitude presentation now models two mechanically distinct areas:
large hundreds inside open horizontal rails on the grey tape, and a smaller
rolling 20-foot pair inside a tall outboard box. The drum begins at the scale
wall and is the only readout geometry extending into black. Lower Mach and
altimeter information now share the right-edge anchors visible in the owner's
reference rather than generic screen margins.

## 2026-09-10 - Reference-calibrated ToLiss A321 PFD (BUG-48)

The first independent ToLiss PFD proved the transport and telemetry contract,
but its 78-pixel generic side tapes and one-piece altitude number were visibly
wrong. The owner's complete PFD and instrument crops are now the geometry
authority. Speed and altitude are narrow; altitude uses a right-side wall,
centred amber hammer, moving cyan target enclosure and a genuinely smaller
20-foot rolling pair. The full attitude field also gains its missing bilateral
5-degree ladder and stepped Airbus fixed-aircraft symbol. These remain native
draw commands driven by the existing live ToLiss values, not photographed
numbers or a runtime screenshot.

## 2026-09-10 - Complete ToLiss FMGS route recovered read-only (BUG-47)

The installed ToLiss A321 keeps its fully expanded FMGS plan in its automatic
situation save even though the public dataref catalogue exposes only the active
waypoint. MuslimSim now discovers that structured route safely, caches it only
when the autosave changes, and draws all available legs on both NDs. The same
source preserves blank discontinuity slots, so fixes after a discontinuity stay
available without a false connecting line. This added no aircraft write or
injected X-Plane plugin.

## 2026-09-10 - ToLiss ND active navigation leg restored (BUG-46)

The authored ND route renderer had been fed nonexistent flight-plan arrays.
The installed A321's actual waypoint course, distance, identifier and aircraft
position now draw the live active FMGS leg on both displays. Full multi-leg
geometry remains available only when a ToLiss version exports coordinates.

## 2026-09-10 - Working-system ECAM state correction (BUG-45)

An engines-running read-only capture exposed wrong enum assumptions rather than
missing aircraft data. BLEED, HYD and the right wing fuel pump now depict their
working state; available ENGINE/ELEC fields are populated with live or clearly
marked provisional derived values. No aircraft controls or processes changed.

## 2026-09-09 - Broad live ECAM telemetry restoration (BUG-44)

At the owner's direction, uncertain-but-plausible ToLiss mappings are now used
provisionally instead of blanking available live signals. This restored common
footer data and connected BLEED, APU, COND, PRESS, FUEL, DOOR/OXY, WHEEL, ELEC
and STATUS fields. The distinction is strict: provisional means a live source
with an undocumented index/convention, never a photographed or fixed number.
No simulator control, HID output or running-process restart was performed.

## 2026-09-09 - ELEC valid-source telemetry restored (BUG-43)

The safety correction that removed page flags and overhead switches masquerading
as electrical measurements had also blanked the valid parts of ELEC. The shared
BB35/BB36 adapter now consumes ToLiss battery voltage, bus voltage presence and
documented source-connection bitfields. Unpublished/unverified engineering
figures stay XX. Native abnormal-state and array-order acceptance remains open;
no running cockpit process or aircraft control was touched.

## 2026-09-09 - WHEEL/BLEED details and observation-only rule discovery (BUG-42)

The owner identified missing gear triangles, centre braking/steering labels,
pack arcs and incorrect closed-valve plumbing. These details now use the
shared native renderer on both BB35/BB36. X BLEED is the provisional source
for the isolated BLEED symbol; it is not a proven rule. A requested four-hour
read-only watchdog and quiet five-minute follow-up collect X/APU valve edges
without operating the aircraft. Only matching native-display observations
can establish a permanent source. No live Studio restart was performed.
Full ToLiss warning logic, every-box telemetry and exact artwork acceptance
remain open in the telemetry audit; the new graphics do not close those gaps.

## 2026-09-09 - Real-source ECAM audit and DU startup (BUG-41)

Read-only inspection of the running ToLiss A321 disproved earlier page-flag
and selector-as-measurement mappings. Audited overrides now supply verified
temperatures/tank quantities/valves/availability, mask unpowered sources and
make unknown fields explicit. Both BB35/BB36 use the simulator DU self-test
timer; no real aircraft control or running process was touched. Layout/power,
keypad/FCU/isolation and known-regression checks pass. Exact artwork and
every-box telemetry in every power/flight phase are still NOT complete.
`docs/TOLISS_ECAM_TELEMETRY_AUDIT.md` records evidence, limitations and the
supervised acceptance sequence. Snapshot work is scoped to the selected page.

## 2026-09-09 - Owner-reference ECAM artwork on both displays

BUG-40 replaces twelve generic ToLiss lower-SD presentations with native
Airbus-style synoptics based on the owner's APU/BLEED/COND/DOOR/ELEC/ENGINE/
F.CTL/FUEL/HYD/PRESS/STS/WHEEL images. Both BB35 and BB36 share the artwork
and existing power gate. F/CTL retains independent live surface positions;
WHEEL also receives spoiler positions. Keypad, FCU, PFD, ND and CDU paths
remain unchanged. Offline layout, motion, display/keypad/power/isolation and
known-regression checks pass. These are reference-based layouts, not a claim
that every ToLiss system value or abnormal page has been mapped. Unverified
fields remain XX; physical-screen and live telemetry acceptance is pending.

> The 2026-09-03 uploaded source snapshot did not contain the older
> `PROJECT_HISTORY.md`. This file is restarted at the current verified
> milestone rather than reconstructing prior history from guesses.

## 2026-09-09 — BB35's own keypad controls the ToLiss CDU

Adding CDU graphics to BB35 exposed a missing input path: the device only
watched its slash gesture, so its screen changed solely when the owner typed
on BB36. The owner explicitly requested working BB35 buttons, extending the
earlier display-only role to the captain CDU keypad.

BB35 now uses its captured 71-key layout with real MCDU1 commands. The two
panels have different digit/letter/gesture indices; a parameterized reuse of
the existing ToLiss command worker preserves BB36 defaults while keeping
BB35's queue, gestures and lifecycle independent. Either keypad operates the
same captain CDU, and the shared text feed reflects those changes on both.
Studio records BB35 edges without redispatching them. Standalone BB35 operation,
no-write startup baselines, held-key deduplication, punctuation, local display
shortcuts and shutdown release are now covered by an end-to-end offline guard.

## 2026-09-09 — BB35 becomes a complete ToLiss coded-display host

BB35's ToLiss route was still deliberately restricted to PFD and ND even after
the full CDU and ECAM deck had been completed on BB36. The owner clarified that
both physical displays must be able to show all of those screens.

BB35 now has the same CDU, PFD, ND and authored system-page inventory. Its
double-SLASH gesture walks the complete deck, while a physical ECAM32 page
selection requests the corresponding page on both screens. The panels keep
independent page state, handles, canvases and differential caches, but consume
the same deduplicated ToLiss subscription.

This is intentionally presentation-only on BB35: MCDU key/command ownership
remains on BB36. The ToLiss BB35 opener loads the combined font only for this
route, leaving the default BB35/Zibo/LevelUp resource untouched. Existing
aircraft-power, lost-telemetry and shutdown blackout behavior remains the final
authority.

## 2026-09-09 — Physical ToLiss altitude follows the FCU selector, not an internal target

During a managed descent, the ToLiss PFD output previously used for the BA01
altitude window stayed at `22000` even though the virtual FCU's selected dial
and both X-Plane selected-altitude datarefs read `8000`. The old value could
look correct in simpler phases, which is why the defect appeared as a frozen
display rather than a consistently wrong conversion.

The ToLiss FCU and WinCtrl CTRL display now share
`sim/cockpit2/autopilot/altitude_dial_ft`, the actual selected dial. The change
replaces one source without adding a subscription or changing output cadence.
The formatter, five-digit zero fill, managed dot, knob writes, absolute EFIS
selectors, aircraft isolation and electrical blackout paths are untouched.

## 2026-09-09 — ToLiss managed FCU state reaches the physical BA01 faithfully

The virtual Airbus FCU was publishing valid managed-state data, but MuslimSim
interpreted ToLiss's `SPDdashed` and `VSdashed` flags as electrical visibility.
That turned the physical SPEED and V/S windows completely off. Heading kept its
last selected number and merely added the managed dot, so the hardware could
show `283` where the aircraft showed `---`. A separate unit error fed the
always-knots-equivalent PFD speed output into the MACH formatter; the live
`257.7408` value consequently saturated at `.99` while ToLiss's unit-aware AP
dial was `0.7781`.

The BA01 renderer now has opt-in Airbus dashed states distinct from true
blanking. Managed SPD/MACH and HDG/TRK render three dashes with their large
dots, V/S/FPA renders the sign stroke plus four digit dashes, and selected
states retain their numeric formatting. The ToLiss worker and AGP CTRL page now
read the unit-aware autopilot speed dial. These additions default off for every
legacy caller, and the original Zibo byte slice remains exact. Power-off still
zeros the entire dynamic region. The VOR/ADF selector dispatcher was left
untouched and its twelve absolute positions remain under the same guard.

## 2026-09-09 — BB36 becomes the complete ToLiss CDU and system-display host

BB36 previously had the beginnings of an Airbus secondary-page cycle, but the
route was not guarded end to end, CRUISE was absent, and F/CTL explicitly
omitted roll control. Its spoiler and trim symbols were representative values
rather than a view of the surfaces actually moving on the aircraft. That made
the most useful controller test page look alive without proving the ailerons,
elevators or rudder.

The BB36 route now contains CDU, the same PFD/ND graphics available on BB35,
and every authored lower-ECAM page through STATUS. The new CRUISE page combines
engine oil/vibration/fuel-flow and cabin data. A shared Airbus-style title and
permanent TAT/SAT/GW/UTC strip make the lower deck visually coherent without
changing the BB35 page owner or Boeing renderers.

F/CTL now consumes the normalized animation outputs that the installed ToLiss
A320 and A321 object files themselves use: ten individual spoilers, left/right
ailerons, left/right elevators and rudder. Those outputs move an Airbus-shaped
wing/tail synoptic together with real trim and hydraulic indications. The
renderer remains differential and bounded at 229 recovery / 79 moving reports;
all ECAM recovery pages stay at or below 299 reports. Power loss, lost telemetry
and shutdown retain the proven black-screen behavior.

## 2026-09-09 — ToLiss becomes the authority for its PFD modes and bearing needles

The remaining display mismatch was architectural as well as visual. The PFD
had been compressed into a generic one-row/rectangular layout, while ToLiss
already published its FMA as exact full-width colour layers. At the same time,
the BA01 VOR/ADF positions were decoded from hardware but intentionally thrown
away, so the ND could neither follow the physical source selectors nor draw the
single/double bearing needles visible in the ToLiss tutorial.

The PFD now uses the manual/reference silhouette: three FMA rows, a rounded
attitude field, narrow Airbus tapes, a nonlinear 1/2/6 vertical-speed scale,
the split invalid-altitude shape and the low heading strip. Native FMA strings
carry ToLiss's own active/armed text and colours instead of a second partial
mode table. The change remains code-native and fits under the existing LCD
report budget.

The installed A320 and A321 both prove the same four writable selector
datarefs and 0/1/2 animation positions. Those absolute writes now drive the
captain and first-officer selectors. The captain ND consumes ToLiss's paired
VOR/NDB bearings, validity, identifiers and DME: NAV1 is a single needle,
NAV2 a double needle. Its active plan is green, becomes dashed only when the
aircraft says so, clips at the selected compass boundary and is present in
ROSE NAV, ARC and PLAN. BUG-34 and the expanded offline guards pin that scope
without modifying any Zibo/LevelUp profile.

## 2026-09-09 — ToLiss speed-envelope and approach symbology closes a silent PFD gap

The initial Airbus PFD already subscribed to several computed speed values,
but subscription was mistaken for presentation: VR was never drawn, V1/V2 were
not wired at all, and both ILS needles were temporary square blocks. That is the
same silent-failure class as the earlier shared-dataref bug—a valid simulator
value could arrive while the physical display showed nothing useful.

The PFD now consumes ToLiss's takeoff visibility flag and independently renders
V1, VR and V2 with their Airbus shapes. F/S, green dot and VFE-next follow the
aircraft's display-ready configuration speeds. The upper red/black strip follows
ToLiss VMax, so ToLiss—not Studio—selects the active flap, gear or structural
limit. LOC and G/S use native magenta diamond glyphs on their real scales.

Three reserved code-native glyphs keep those curves clean without adding PNG
assets or exceeding the BB36 full-frame budget. The display guard now proves
the takeoff phase gate, F/S visibility, both ILS diamonds, dynamic VMax motion,
the exact dataref/translation contract and report ceilings. A new coverage
matrix explicitly records what remains incomplete instead of allowing broad
Airbus feature claims to outrun the code.

## 2026-09-09 — ToLiss gains native Airbus flight displays on BB35 and BB36

The first ToLiss display pass proved that the BB36 could receive native F0
graphics, but it did not yet behave like the Airbus source: text was oversized,
ND scale modes were incomplete, invalid navigation data looked partly alive,
the MCDU used a small inherited grid, and BB35 had no persistent ToLiss owner.
Worse, captain heading and validity are intentionally shared by PFD and ND; a
one-key reverse subscription table delivered each repeated physical dataref to
only its last local consumer. That made one page appear frozen even while the
shared WebSocket was healthy.

The Airbus display path now fans every subscription ID out to all of its local
consumers and lets BB35 and BB36 share that one feed without sharing output
ownership. BB35 owns its own HID/canvas and switches PFD/ND; BB36 retains MCDU,
PFD, ND and the established Airbus system pages. PFD and ND use compact native
typography and Airbus-specific geometry, including EFIS range changes, ARC/
ROSE/PLAN, active route projection and real invalid-source annunciations. The
MCDU uses a separate full-size 24 x 14 native font slot, leaving Boeing's exact
font bytes untouched.

Power authority remains stronger than presentation. Both screens require a
connected feed and positive `AirbusFBW/BatVolts`; loss, shutdown or an
unmonitored mirror-off state goes black. The PFD remains below the BB36's proven
290-report recovery ceiling, and no runtime PNG or second aircraft writer was
introduced. BUG-32 and the new offline display guard pin the subscription,
page-cycle, typography, invalid-state, power and traffic boundaries.

## 2026-09-09 — The Airbus profile is reduced to its real trim and AGP scope

The first complete ToLiss pass deliberately proved every available B930 and
AGP path, but it exposed two modes the owner did not want presented as Airbus
cockpit functions: aileron trim and a separate NAV radio page. ToLiss now
alternates the hidden knob push between PITCH and RUDDER only, while its AGP
hold gesture cycles CLOCK, RADIO and CTRL. These reductions are profile-local;
the working Zibo/LevelUp trim roles and Zibo RADIO/CTRL/NAV pages do not move.

The same live check showed fast RST tuning advancing several visible values at
once. The capture still proves every raw count arrives, so the bridge does not
scale or throw those counts away. It holds them in an ordered ToLiss-only FIFO
and sends one native fine command per short LCD update slice. A fast turn keeps
rolling from the queue, but the physical display can now show the intermediate
steps instead of receiving a burst between readbacks. BUG-31 and the expanded
hardware-free guard pin the new boundary.

## 2026-09-09 — The complete WinCtrl Airbus control surface reaches ToLiss

The ToLiss throttle calibration proved both physical thrust axes, but the rest
of the same B930 quadrant was still stranded in the Boeing-only live loop.
Engine masters, engine mode, speedbrake, flaps, parking brake, trim and the red
lever buttons could appear in Studio without moving the Airbus. The AGP was
likewise limited to its clock behavior, and small FCU targets were space-padded
instead of filling their real three- and five-digit windows.

The ToLiss profile now owns native Airbus mappings for all of those controls.
The owner's MODE capture separated the push hidden in the IGN/START knob from
its three maintained selector contacts: button 24 cycles the one trim rocker
through pitch, rudder and aileron, while buttons 7/8/9 continue to command real
CRANK/NORM/IGN-START. The B930 window follows the selected trim value. The red
lever buttons perform their real Airbus function—A/THR disconnect—without
silently disconnecting AP/FD.

The AGP keeps CLOCK as home and gives a deliberate TERR ON ND hold gesture to
RADIO, NAV and CTRL pages. These operate ToLiss RMP1, captain NAV1 and the FCU
rotary inputs through the existing lossless counters. ToLiss alone opts into
FCU zero filling, so one knot/degree/foot is rendered as `001`, `001`, `00001`;
the established Zibo bytes do not change.

The integration retains one raw-input owner, binding precedence, delta writes,
strict first-report no-write baselines and reach/cross pickup. One Airbus bus
voltage gates every new lamp, backlight and numeric output, including removal
of stale digits from an earlier aircraft. BUG-30 and its dedicated offline
guard preserve those profile and safety boundaries.

## 2026-09-09 — ToLiss throttle calibration becomes a physical guided capture

The first isolated ToLiss throttle table stopped Airbus tuning from changing
the working Boeing aircraft, but its six raw positions were still fixed
numbers and Studio continued drawing the old static ruler. The owner's live
test found the exact consequence: TOGA and IDLE happened to land correctly,
CL and FLEX/MCT did not, and returning from reverse could remain in IDLE REV
until the lever was moved above IDLE and brought back.

Studio now exposes the hardware information the quadrant already had: one
contact at every Airbus thrust gate. A ToLiss-only probe captures the actual
raw count at FULL REV, REV IDLE, IDLE, CL, FLEX/MCT and TOGA for each engine,
in that mechanical order, then stores those twelve values in the active
ToLiss hardware profile. Its ruler immediately redraws from those values.
Zibo and LevelUp keep their own files and converters; no calibration value is
shared across the aircraft boundary.

During capture, simulator thrust remains at its prior value. Completing a
valid sweep swaps the precomputed interpolation table and deliberately
re-arms the existing safe-pickup gate before control returns to the levers.
The IDLE contact is now authoritative over any short reverse-contact overlap,
and every thrust-detent edge carries an axis snapshot, which closes the
reverse-to-IDLE latch without polling or another device owner. BUG-26 and the
two dedicated offline guards preserve this behavior.

## 2026-09-08 — Aircraft-specific calibration reaches the WinCtrl throttles

The WinCtrl quadrant previously crossed an aircraft boundary that the rest of
MuslimSim already treated as strict: ToLiss wrote its own Airbus dataref, but
the values still came from the Zibo/LevelUp 737 converter and its
Zibo-specific reverse-idle threshold. Any attempt to tune the Airbus would
therefore also retune the working Boeings.

The ToLiss A320/A321 family now owns a six-detent profile for each engine.
Physical FULL REV, REV IDLE, IDLE, CL, FLEX/MCT and TOGA contacts land on
precomputed Airbus anchors, while movement between them remains continuous.
ToLiss's own current detent ratios establish the simulator side once per
aircraft generation; the WinCtrl raw values stay in the aircraft profile and
never replace the Boeing values. Reverse is still inaccessible without its
physical lift handle, and the existing readback/cross-target pickup remains in
front of every first write.

This establishes the pattern for the controls that follow: ignition, flaps,
speedbrake, parking brake and rudder trim will each receive a ToLiss mapping in
their own bounded step. They were deliberately not changed as part of the
throttle milestone.

## 2026-09-08 — The native Airbus panel becomes a real ToLiss FCU/EFIS

The WINCTRL BA01 panel already had a ToLiss button profile, but its physical
input report was rejected unless a HID layer padded 41 bytes to 64, all four
central encoders were deliberately discarded, heading and vertical speed were
fed from present-aircraft values, and only one of the six FCU integral lights
was addressable. This made a superficially connected panel behave like a
one-way display: sim-side speed/altitude knob changes appeared, while physical
knobs, selected heading/V/S, and most annunciators did not.

An owner-supplied USB capture established the real input length and FCU light
selectors. The installed ToLiss aircraft's own manipulator configuration and a
reversible live Web API test established its four writable knob-position
inputs. MuslimSim now accepts both native and padded BA01 reports, drives those
inputs one detent at a time, reads selected FCU targets, mirrors both EFIS
sides and all six FCU lamps, and keeps the complete panel dark without aircraft
power. The existing working speed/altitude sources and every Zibo path remain
unchanged. BUG-22 and its dedicated offline guard preserve that boundary.

## 2026-09-05 — LevelUp reuses the proven Boeing paths without owning Zibo

LevelUp detection and an isolated aircraft workspace already existed, but
three display startup gates still excluded the detected profile. BB35 therefore
held an old Zibo frame and BB36 never acquired its graphical path. The fix was
not another display implementation: the installed LevelUp aircraft proves it
publishes every FMC command and dataref the established routers consume, so the
known profile now enters those same guarded paths.

The WinCtrl RUD TRIM rocker exposed the one real command difference. LevelUp's
captain yoke uses X-Plane's generic electric pitch-trim pair, while Zibo uses
Laminar's pair. Two LevelUp-only overrides now express that distinction. The
physical rocker loop and trim-units LCD remain shared, while Zibo's base mapping
remains unchanged.

This milestone deliberately crosses no other ownership boundary: PFD/ND page
drawing, fonts and geometry, shared telemetry, recovery, startup refresh,
PAP3/PDC/FCU gates and Studio were not edited. BUG-18's source-only test pins
that narrow contract.

## 2026-09-04 — Aircraft isolation becomes provable

The owner asked how mappings for one aircraft could be kept from conflicting
with another, and whether the software could avoid talking to an aircraft that
is not loaded. An audit found both already true: mappings are isolated by file,
and the bridge both refuses to dispatch a mapping whose workspace does not match
the loaded aircraft and starts telemetry workers only for the detected one.

What was missing was proof and controlled reuse. Isolation is now a contract
test, and mapping reuse is deliberately two-speed: automatic only between
variants that share an imported function library, explicit and reported
everywhere else. Guessing equivalence between a Zibo DataRef, an Airbus one and
a PMDG LVAR was rejected as a design choice - a control that looks mapped but
fires the wrong command is worse than an unmapped one.

## 2026-09-04 — MSFS 2024 becomes a per-aircraft workspace

The MSFS 2024 side of Studio stopped being one undivided space. It now lists the
owner's add-on aircraft by developer, and each airframe carries its own mapping
profile, matching how the X-Plane aircraft have always been separated.

The imported command workbook is organised by aircraft family rather than by
variant, so variants share a function library while keeping independent
mappings. The function browser filters on that family, which also closed a real
hazard: every MSFS function was previously offered regardless of the aircraft
being mapped.

FlyByWire is listed but has no imported functions. It was added on the owner's
explicit request and reports the gap plainly rather than being quietly omitted
or given guessed commands.

## 2026-09-03 — Live feedback becomes a guarded feature

Studio showing physical movement — a yoke, a throttle, a switch, a knob — is now
treated as a product feature with an enforced contract, not behaviour that
happens to work.

The trigger was a silent failure. Device status callbacks were collected inside
the status request, so a single slow driver pushed the reply past the control
client's timeout. Every poll failed, and because the device list came from the
last reply that had landed, a frozen panel and a working one looked identical.
No error surfaced anywhere.

Device status collection moved off the request path, the client gained
headroom, and `tools/test_live_feedback_contract.py` now fails if either is
undone. The contract reads the device catalogue rather than a fixed list, so
every device adopted from now on must post live physical feedback through
`HardwareLab.input(..., source="physical")` to pass.

## 2026-09-03 — Performance architecture: shared X-Plane telemetry

The first performance architecture milestone separates simulator state
distribution from physical device ownership. Normal bridge DataRef reads now
enter through one shared WebSocket/cache, while all existing panel writers and
command paths remain in their previous owners.

This was driven by a measured source audit showing hundreds of independent REST
value reads per second under a fully populated Zibo cockpit. The new hub is a
compatibility layer first: existing device code can continue using
`read_dataref()` while receiving shared data.

A session resource registry and bounded REST fallback broker are part of the
same milestone so aircraft loading/reconnect cannot substitute lookup/fallback
storms for the old steady-state request storm.

The graphical BB35/BB36 smooth telemetry readers and PU physical-authority
WebSocket are deliberately left as separate streaming owners in Phase A.
Unifying read-only display telemetry is the next performance phase only after
this base layer is live-proven.

## 2026-09-03 — Studio live-feedback distribution milestone

A systemic Studio-only defect was isolated: physical hardware and simulator
outputs were working, but the visual application did not consume the bridge's
authoritative latest physical state consistently. The bridge status response
already contained both device mirror data and `HardwareLab.inputs`; Studio
used the former selectively and treated the bounded diagnostics ring as the
main animation source.

The new read-only composition layer makes the latest bridge state the common
input to all faceplates while preserving every existing device-specific mirror.
No simulator dispatch or hardware owner changed.


V2 also publishes the already-open private control-channel port with flushed stdout after in-memory lab wiring and before simulator-down physical output initialization. This is startup discovery only; the server, token, hardware owners, mappings, simulator dispatch and display paths are unchanged.


GitHub source upload: the modified `tools/XTextureExtractor-trial` source is
included directly, with its existing third-party attribution and license.
Local nested Git metadata, historical archives and compiled temporary products
are excluded. The verified 3M guided capture remains included for offline tests.
