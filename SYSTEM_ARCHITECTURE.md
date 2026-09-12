# MuslimSim system architecture

Last updated: 2026-09-02 - Portable Device Platform V1 adds stable product
identity, runtime locator discovery and automatic PU COM re-resolution.

## Normal launch path

```text
start_muslimsim.cmd
        │
        ▼
launch.py  --with-pfd
        │
        ▼
muslimsim/app.py  (device selections)
        │
        ▼
muslimsim/core/engine.py
        │
        ▼
bridge/final.py  (active hardware and X-Plane bridge)
```

`bridge/final.py` is the managed active bridge. The original
`D:\Howalt d203 requre signature\final.py` is a fallback/recovery copy only.
Never run both at the same time because they would compete for the same
hardware and simulator controls.

Studio and X-Plane may be opened in either order. The bridge first waits for
the X-Plane Web API, then separately waits for a real aircraft path and the
required feedback set for a Boeing profile. `SIMULATOR_OUTPUT_ONLINE` remains
clear through both waits. An older API that never publishes the string path
falls back to safe generic/read-only mode after a bounded 30-second grace and
continues watching. If X-Plane briefly presents a default/generic plane and
the selected supported aircraft becomes ready later, the read-only profile
watch requests a normal bridge stop; every output is blacked/off and released,
then the Studio supervisor launches one fresh child with the new profile. The
supervisor never exposes an exited child's cached loopback port as a client.

## Portable Device Platform V1

MuslimSim now separates a physical product from the temporary Windows locator
used to reach it. `muslimsim/hardware/product_registry.py` is the stable product
identity layer; `device_manager.py` resolves current serial endpoints; the
existing `discovery.py` and `device_lifecycle.py` consume that platform without
opening a second hardware owner.

```text
Product identity                     Runtime locator
----------------                     ---------------
VID/PID                              COM27 / COM44
product/manufacturer string          HID path
read-only protocol model name        SDL instance index
                                      Windows PnP path
```

The right column is never persisted as the identity of a supported device. Unit
serial numbers are not part of `ProductSpec`. A replacement unit of the same
product therefore keeps the same MuslimSim key/profile. HOWALT is the important
shared-ID case: D201 and D203 share WCH USB IDs and remain separated by the
existing read-only firmware model probe. MuslimSim must never guess D201 versus
D203 from COM enumeration order.

PU is the first active owner migrated. Its serial protocol is unchanged, but
its startup locator defaults to `auto` and the reconnectable serial proxy asks
the product resolver again before reopen. A COM renumber after replug no longer
requires configuration. Explicit `--port COMx` is retained as a diagnostic
override while this migration is proven.

The end-user distribution target is `MuslimSim.exe`. The PyInstaller recipe
explicitly bundles dynamically reached hardware/device/control Python modules
and path-loaded runtime data/helpers. End users do not install pyserial, hidapi,
pygame or websocket-client with pip. OS-level signed USB drivers remain a
Windows responsibility when the OS has not installed one; MuslimSim does not
ship or invent an unreviewed vendor driver package.

Migration rule: the registry/manager is added around an existing proven owner
first. Protocol/control ownership is moved only after its current behavior has
been compared and live-tested.

## Device modules and ownership

| Module | What it selects now | Active ownership in the bridge |
| --- | --- | --- |
| `pu_overhead.py` | PU P7 lamps | PU Overhead switches, auto-discovered serial output, P7 lamps, starter/ignition, brightness, APU EGT |
| `winctrl.py` | WinCtrl flight controls | Throttle, reverse, speedbrake, flaps, engine masters, trim, parking brake, A/T disconnect |
| `pdc.py` / `pdc_bb62.py` | WINCTRL 3N PDC / EFIS (`4098:BB62`) | Dedicated HID capture/reconnect plus CAPT EFIS action dispatcher through existing bridge REST helpers; VOR/ADF uses absolute commands and MINS/BARO use confirmed direction pulses |
| `ecam32.py` | WINCTRL 32 ECAM (`4098:BB70`) | One bridge-owned raw-contact reader plus capture-proven wake/lamp output; Airbus names exist only as learned profile relations |
| `pedals.py` | WinCtrl rudder pedals | Rudder yaw and independent left/right toe brakes |
| `agp.py` | AGP panel | AGP displays, landing gear, autobrake, AGP indicators |
| `pfp.py` | PFP page | PFP output-page selection only |
| `pfp_renderer.py` | PFD drawing | Native 640 x 480 PFD layout and protected display zones |
| `pfp_shape_tiles.py` | Static PFD shapes | Generated tile runs; renderer falls back to rectangles without it |
| `nd_renderer.py` | ND drawing | Native APP/VOR/MAP/PLAN/VSD, route, TCAS, bearing, weather/terrain and failure presentation |
| `systems_renderer.py` | Systems drawing | Native ENG PRI, secondary engine MFD and HYD/flight-control pages |

The small device modules deliberately do not duplicate the proven hardware
code yet. They are the safe organisational layer used by the launcher and a
future GUI. The tested input/output logic remains in `bridge/final.py` until
it can be moved one device at a time and retested.

The shared graphical font upload contains two 17 x 29 native matrices. Font 5
has smaller centred ink and is selected only by the PFD text layer. Font 6
retains the previous larger glyphs, is selected by ND and systems pages, and
also carries the PFD's static shape tiles. Switching font IDs is a native draw
command; it does not reload the resource or change screen/output ownership.

## Worker separation

| Worker/path | Responsibility | Why it is separate |
| --- | --- | --- |
| Serial output worker | Fixed-rate PU serial packets on the product-resolved COM locator | Prevents gauges and lamps flickering when web reads are slow |
| P7 annunciator worker | PU lamp feedback polling | Prevents light reads from blocking the serial sender |
| Shared BB35/BB36 display worker | Split-rate X-Plane sample, PFD/ND/ENG/MFD/HYD dispatch, read-only roll/pitch/yaw/toe-brake test positions, persistent differential HID output | One power gate and one renderer owner prevent page changes from flashing black or delaying controls |
| ND route/text refresh | Bounded daemon cache of exact Zibo route arrays and base64 Web-API strings | A slow/stopped Web API never blocks physical display refresh |
| ToLiss full-route source | Read-only, bounds-checked parser of the loaded model's automatic QPS situation; immutable result cached by path/mtime/size and selected with live WPT ID | Recovers expanded FMGS fixes and discontinuities without a simulator write or per-frame 3.8 MB parse |
| ND navigation-database loaders | On-demand read-only X-Plane station/fix/airport parsing into one-degree spatial indexes | Actual STA/WPT/ARPT symbols without full-database work in a display frame |
| Aircraft-profile watcher | One-second read-only aircraft path/readiness check in automatic mode | Detects a plane that finishes loading after Studio without changing mappings under live hardware owners |
| PDC BB62 worker | HID reports, baseline, reconnect, and injected CAPT EFIS actions | Keeps PDC isolated; only post-baseline captured inputs can use the bridge's existing REST helpers |
| ECAM32 BB70 worker | Raw report transitions and capture-proven lamp queue | Keeps anonymous PCB contacts separate from owner-measured Airbus names; normal Studio/bridge remains the sole live HID owner |
| ECAM32 guided capture | Temporary direct HID input while Studio is closed | Captures all 18 physical name relations, keeps output dark, blackouts/releases first, then atomically updates backed-up profile files |
| SDL controller reader | PU Overhead switches, WinCtrl throttle, WinCtrl pedals, one enumerated TCA Boeing quadrant | One owner prevents competing pygame event readers; TCA keeps its original 15 ms continuous-axis cadence and no-write startup baseline |
| TCA Practice drag drain | Newest virtual lever value only | Moves Tk locally, coalesces loopback updates, and never opens SDL or redraws the whole faceplate during pointer motion |
| Main bridge loop | Command/dataref writes and safety pickup | Keeps simulator-control ownership explicit |

## Safety architecture

- **No-write startup baseline:** physical controls are captured and stabilised
  before their simulator values are compared.
- **Read-only reconciliation:** startup warnings describe mismatches; they do
  not change the aircraft.
- **Axis pickup:** a physical continuous input must cross the current
  simulator value before it writes. This applies to throttle, reverse,
  speedbrake, rudder, and toe brakes.
- **Practice-only virtual input:** a TCA drag uses `practice_only=True`. The Lab
  holds its mode lock across the Test check and input dispatch, so concurrent
  loopback requests cannot leak a delayed Practice position into Live.
- **Global output authority remains separate:** TCA is input-only. Live output
  power gating, one-output-at-a-time Test behavior, shutdown black/off, and
  release to other software are unchanged by the faceplate work.
- **Coded pages remain behind the same authority:** page selection never grants
  output permission. Live simulator loss or an unpowered aircraft blackens the
  display; Test can illuminate only the specifically selected display; normal
  shutdown sends black/off and then releases ownership.
- **PU-only engine start:** the PU Overhead owns the engine-start rotaries,
  auto-retract timing, and ignition. WinCtrl engine mode cannot take that
  ownership.
- **PFP is display-only:** it reads the simulator and writes its own hardware
  screen. It never controls the aircraft.
- **HYD test markers are read-only:** roll, pitch, yaw and toe-brake values
  feed only the coded display. They do not bypass startup pickup, write the
  aircraft, or replace the established pedal/yoke owners.
- **PDC is capture-first:** the BB62's semantic switch/button map came from
  the read-only probe; every event still follows a no-write baseline. Its
  MINS/BARO direction pulses were separately captured and reviewed; all
  display/LED outputs remain inactive until separately mapped.
  `probe_pdc_bb62.py --knob-trace` remains available for diagnostics.
  VOR/ADF uses saturated Zibo command sequences rather than inferred simulator
  state values.
- **ECAM32 is capture-first:** a BB70 contact becomes ENG/BLEED/ELEC/etc. only
  after `CAPTURE_ECAM32_BUTTON_NAMES.cmd` observes that labelled press. The
  recording-order default was removed. The wizard refuses to coexist with the
  Studio/bridge owner, rejects ambiguous or duplicate contacts, performs the
  proven blackout before release, and never sends a simulator action.
- **One display owner:** when using the bridge PFD, do not let another program
  continuously overwrite the same PFP screen output.

## Folder map

```text
MuslimSim/
├── CAPTURE_ECAM32_BUTTON_NAMES.cmd Guided, dark, sole-owner ECAM name capture
├── launch.py                  One-command entry point
├── start_muslimsim.cmd        Normal PFD-enabled launcher
├── bridge/final.py            Active bridge engine
├── muslimsim/
│   ├── app.py                 Device selections and command forwarding
│   ├── core/engine.py         Managed bridge loader
│   └── devices/               PU, WinCtrl, pedals, AGP, PFP boundaries
├── tools/                     Font, shape-tile, PFD-sheet, emulator, and preview builders
├── PNG/                       PFD design sheets and layout contract
├── assets/                    PFP font/tape previews
├── Backup/                    Timestamped pre-change copies
├── PROJECT_HISTORY.md         Master narrative and milestones
├── DEVICE_REFERENCE.md        Hardware map, test commands, and options
├── CHANGELOG.md               Short chronological change record
└── PFD_PROJECT_HISTORY.md     Detailed PFD-specific history
```

## Performance contract

- PFD output is batched into packed HID chunks rather than one report per
  primitive.
- The renderer owns a persistent 640 x 480 final-pixel canvas and a 24-pixel
  dirty grid. It sends only changed regions, except for periodic/reconnect
  recovery frames.
- Opaque PFP text runs expand to complete native-cell bounds before diffing;
  dirty output must remain pixel-identical to a forced full repaint.
- Fast motion values are sampled every 0.25 seconds by default. The complete
  24-value PFD sample is refreshed every 1.0 second and merged into the fast
  sample, avoiding four complete web-read passes per second.
- Boot and offline pages invalidate the persistent live canvas so reconnecting
  with unchanged aircraft values cannot leave the standby page visible.
- Only the newest PFD frame is retained when rendering/data reads are delayed.
- The serial worker has a fixed cadence and is independent from PFD and lamp
  polling.
- Continuous input events are coalesced so old pedal or throttle positions do
  not build up and replay late.

Any future optimisation must preserve these separations. A speed improvement
is not acceptable if it allows a PFD frame, lamp poll, or new device to delay
engine-start, throttle, or PU COM5 output.

## Control panel layers (2026-08-28)

```text
MuslimSim.exe  (windowed, admin manifest)
        |
        |-- muslimsim/gui/         the window; knows nothing about HID
        |     app.py               tabs, timers, background workers
        |     supervisor.py        owns the bridge as a CHILD PROCESS
        |     settings.py          what is remembered -> the command line
        |     paths.py             source vs frozen
        |     calibration.py / throttleview.py / displayview.py
        |     selftest.py          16 checks, no hardware
        |
        |-- muslimsim/hardware/    talks to devices; knows nothing about the UI
        |     catalog.py           every device, declaratively
        |     usb.py               presence, verified power cycling
        |     axes.py              live SDL axis reading
        |     throttle.py          raw HID quadrant reader + the two bands
        |     displays.py          the display mirror and the real reboot
        |
        |-- muslimsim/control/     the channel into a running bridge
              protocol.py  server.py  client.py
                    |
                    v  loopback TCP, per-run token
              bridge/final.py
```

The bridge is a child process, never hosted in the panel's interpreter: it
opens serial ports, HID handles and SDL and blocks forever, so a GUI hosting
it would freeze on the first hardware stall and die with it on every crash.

A frozen exe has no interpreter to start the bridge with, so it re-runs itself
with `--run-bridge`.

### Additive blocks inside bridge/final.py

All three are fenced with `>>> MUSLIMSIM ... >>>` and wrapped so a failure is
reported and stepped over rather than raised.

| Block | What it does |
| --- | --- |
| `CONTROL CHANNEL` | Loopback server so one device can be reset while the others keep flying. Started **before** the wait for X-Plane, because that wait is exactly when a panel may need resetting. Devices registered later, as they are created. |
| `DISPLAY TELEMETRY` | Records the values each panel is drawing, at the one point both the WebSocket and REST paths converge, so the mirror shows the glass rather than a second opinion. |
| `THROTTLE CALIBRATION` | `--throttle-*-idle` flags applied before anything reads the quadrant; an impossible calibration exits 2. |

Nothing changes for a terminal launch: `--control-port` is off unless the
panel passes it.

Details: [docs/CONTROL_CHANNEL.md](docs/CONTROL_CHANNEL.md),
[docs/DISPLAY_MIRROR_AND_RESTART.md](docs/DISPLAY_MIRROR_AND_RESTART.md).

## Global output authority (2026-08-31)

MuslimSim never lights hardware as a side effect.  Every physical output is
either commanded by Live mode from real aircraft state, or explicitly asked for
in Test mode.

This is `AGENTS.md` rule 0.1, and it is not optional or per-device: **every**
panel MuslimSim controls obeys it, including any added in future.  A new output
path must say in its changelog entry how it goes dark.

**Live mode.**  Cold and dark means lamps off and screens black.  Losing live
simulator data while Studio is still in Live mode also goes black, rather than
holding stale flight data or falling back to a standby card.  When aircraft
power returns, normal output resumes from current live state.

**Test mode.**  Only the output being tested may operate.  Entering Test mode
wakes nothing; registering an output adapter wakes nothing.  Pressing a control
*is* a request to test it, so the pressed device updates - and only that
device.  `HardwareLab._advance_practice` emits with `only_device`, and
`ControlServer.apply_practice_snapshot` filters its update list to match.
`only_device` is part of the cached signature: the same snapshot scoped to a
different device is a different physical write.

**Normal shutdown.**  Each device is sent its already-proven OFF/BLACK state
while MuslimSim still owns the hardware, then released.  MuslimSim does not run
a watchdog afterwards and does not fight another application for the panel.

**Out of scope, deliberately.**  A force-killed or crashed process, and
anything another application does with a panel after MuslimSim has released it.

**The rule that outranks the others:** never guess a vendor output packet to
make a device dark.  A device without a capture-proven safe OFF is left alone
and flagged for capture.  ECAM32, FCU/EFIS and BB36 all reuse writes that were
already captured.

One judgement is worth knowing about.  `_agp_aircraft_output_powered` separates
two situations that look identical from the outside: no electrical dataref
configured means the loaded aircraft does not publish one, so established
behaviour is preserved; refs configured but unreadable means live data was lost,
which goes dark.  Collapsing those two into "powered" is the natural mistake and
defeats the Live rule.

**Devices covered.**  AGP, ECAM32, FCU/EFIS, BB36, and the WinCtrl throttle.
The throttle was added last and is the useful example: its wake sequence lights
the backlight when the HID handle opens, whether or not the aeroplane has power,
so it needed an explicit blackout.  `_winctrl_throttle_blackout` writes the
captured channel report with a value of 0 - the protocol's own off, not a new
packet - across all nine channels.  The numeric window needs no blank-glyph mode
because `trim_display_backlight` is itself one of those channels.

**One power source.**  Every device reads the PU aircraft-power dataref, not its
own notion of powered.  Rule 0.1 is one statement about the aeroplane; nine
per-device opinions would drift apart.  The AGP additionally consults its own
electrical refs for the finer distinction described above.

**Coverage, and how it stays true.**  Eight catalogue devices have
implemented outputs, and each has a declared blackout:

| Device | How it goes dark |
| --- | --- |
| `pu_overhead` | `_pu_write_safe_dark_frame`, written by the COM5 owner as it exits |
| `winctrl_throttle` | `_winctrl_throttle_blackout`, captured channel reports at 0 |
| `agp_bb80` | `_agp_blackout` |
| `fcu_32_efis` | `fcu_efis_ba01.py` `_write_blackout` |
| `ecam32` | `ecam32.py` `_write_blackout` |
| `pap3_mag` | `pap3_mcp.py` `_blackout`, on stop_event, not on reconnect |
| `pfp3n_bb35` | router `stop()` darkens before releasing the handle |
| `mcdu32_bb36` | router `stop()` darkens before releasing, **final teardown only** |

`pdc_bb62` and both Moza bases declare outputs that are not implemented.  Rule
0.1 leaves those alone rather than forcing them dark with a guessed packet.

The test carries that table and fails **in both directions**: a catalogue
device with implemented outputs and no entry fails, and an entry for a device
that no longer has outputs fails as stale.  So a new panel cannot be added
without someone writing down how it goes dark.  This exists because the
throttle and the BB36 were each missed once, both while the surrounding work
was described as already global.

**A blackout must fire only on the final teardown.**  Display paths are torn
down constantly - FMC/PFD handoffs, recoveries, session restarts - and
darkening on each one makes the panel visibly flash.  PAP3 recorded this first
("repeated blackouts were perceived as PAP3 flashing") and gates on its
manager-level stop event; BB36 gates on a `final` flag that defaults to off, so
only the supervisor's own exit darkens anything.  The test asserts the gating
and that exactly one teardown call site is final, because the earlier test
checked only that a blackout existed - which was true while the screen flashed.

**Three occasions, not one.**  Every output needs a blackout on each of:
aircraft power lost, simulator gone, and **MuslimSim exiting**.  That third one
is where these keep being missed - it is easy to wire the first two and think
the rule is satisfied.  The throttle was lit after Studio closed for exactly
that reason.

Measured, so it does not have to be argued again: the panels do **not** relight
when the last handle closes.  `tools/probe_shutdown_relight.py` blacks a panel
out with the handle open, then closes it, with pauses to look at each step.  It
lit, went dark, and stayed dark.  So a panel found lit after shutdown is always
something we failed to send, never the firmware taking over.

Offline check: `python tools/test_global_output_authority.py` - 62 checks.

## Portable product identity — Phase 2

The Device Manager now models all three current locator classes:

- serial: current COM endpoint;
- HID: current HID interface path(s);
- SDL: current index/instance/GUID.

None is persisted as hardware identity. Stable identity remains the product
definition (VID/PID/product/protocol). HID drivers may still select a specific
usage/interface using their proven device-specific logic; the central manager
returns all matching interfaces rather than guessing. The one bridge SDL owner
uses the shared registry for product recognition and remains the only pygame
input owner.

## Portable Device Platform V3 — bootstrap boundary

The bootstrap layer is not a hardware owner. It may enumerate Windows PnP,
serial and HID interfaces and validate/install a reviewed signed INF, but it
never consumes live cockpit reports or writes panel outputs.

Identity remains ProductSpec product/protocol identity. PnP instance ID, COM,
HID path, SDL locator and serial number are explicitly diagnostic/runtime
locations only.

End-user runtime policy:
- Python-side dependencies ship inside `MuslimSim.exe`;
- Windows-native HID/game class drivers are used directly;
- a non-native driver may be installed only from an embedded reviewed local
  INF whose SHA-256 and Authenticode signer match the release manifest;
- no runtime driver download and no external cockpit application.

## Shared simulator telemetry — Performance Phase A

X-Plane read-only aircraft state is now a shared service rather than a property
of each device worker. `muslimsim/simulator/xplane_telemetry.py` owns one
bridge-wide DataRef WebSocket and a latest-value cache. Existing
`read_dataref()` / `read_dataref_index()` callers transparently consume that
cache, so this capability does not move any simulator write or hardware
ownership.

Named consumer groups make distribution visible (`pu.core`,
`pu.annunciators`, `agp.radio_nav`, `fcu_efis.display`,
`winctrl.throttle.feedback`, `pfd.shared_inputs`, etc.). Whole array DataRefs
are distributed once and indexes are selected by consumers.

REST is compatibility/failure fallback only. It is single-flight, briefly
reusable, and rate-limited per DataRef/index so a broken WebSocket cannot
recreate the former request storm.

Successful DataRef/command name resolutions are cached for the current session;
temporary missing plugin resources use bounded retry backoff. Explicit stale-ID
recovery paths retain a `refresh=True` escape hatch.

This phase intentionally does not merge BB35/BB36 display ownership or the PU
physical-authority monitor. Those are existing streaming readers and are a
separate Phase B optimization after the shared normal bridge path is proven
live.

See `TELEMETRY_ARCHITECTURE.md` for the distribution contract.

## Performance Phase B — one display data source, independent display owners

BB35 and BB36 graphical rendering now share one ref-counted smoothed telemetry
view backed by the Phase-A X-Plane hub. This does **not** merge their hardware
lifecycle: each panel still owns its own HID handle, framebuffer writes,
brightness, reconnect/recovery and page-selection state.

Read-only display data is organized into `pfd.graphical.shared`, `bb36.fmc`,
`pfd.nd.route`, `pfd.nd.traffic`, and `pfd.text` consumer groups. The existing
standalone graphical WebSocket code remains as compatibility fallback only if
the Phase-A shared source is absent.

A simulator generation change clears old smoothed values and advances the
session resource-ID cache. No prior-aircraft value is allowed to become live
simply because a renderer survived the reconnect.

## BB36 recovery ownership boundary

BB36 recovery remains inside its single lifecycle router. No generic device
manager or telemetry layer may open a second BB36 output handle to work around
a stall.

The router distinguishes:
- active output owner;
- dedicated keypad input handle;
- retired output worker (handle already closed, thread still unwinding);
- firmware recovery/circuit state.

A replacement output owner is permitted only when there is no active owner and
no live retired output worker. The shared X-Plane telemetry source survives
this device-only recovery and is not restarted with BB36.

Native F0 progress is presentation/output health evidence only; it never
changes simulator state or hardware mappings.

## Studio live-feedback distribution

The bridge has always owned physical input and device output state. Studio is
only an observer. The observer now has one explicit composition boundary in
`muslimsim/gui/live_feedback.py`:

```text
physical device owner             device display/output worker
        |                                   |
HardwareLab.input()                 status()["mirror"]
        |                                   |
        +----------- control status --------+
                         |
                         v
              compose_live_mirror()
                         |
              MuslimSim Studio faceplate
```

`HardwareLab.inputs` is state, not an event queue. The diagnostics ring remains
for learning/capture and short motion acknowledgement, but a faceplate must not
depend on a diagnostic record surviving long enough to know the current switch
position. Device-specific mirror fields always win; generic lab data only fills
missing read-only fields.

This layer has no simulator or hardware write API. It may not open HID, serial
or SDL, activate commands, write DataRefs, or drive outputs.


V2 also publishes the already-open private control-channel port with flushed stdout after in-memory lab wiring and before simulator-down physical output initialization. This is startup discovery only; the server, token, hardware owners, mappings, simulator dispatch and display paths are unchanged.

### Live-feedback contract (2026-09-03)

Live feedback is a product feature, not an implementation detail of one device,
and it is now enforced by `tools/test_live_feedback_contract.py`.

It failed once in a way nothing reported. Device `status()`/`diagnostics()`
callbacks talk to real hardware, and they were collected inside the status
request. One slow driver pushed the whole reply to 3.05 s while the Studio
control client allowed 3.00 s, so every 0.10 s poll timed out, `self._lab` was
never refreshed, and the faceplates froze while the device list stayed on
screen from the last reply that had landed. No exception was raised and no
error was logged.

Two rules follow from that, and the contract test fails if either is broken:

- **Device status is collected off the request path.** `ControlServer` keeps a
  `DEVICE_STATUS_TTL_SECONDS` cache refreshed by a background sweep, the same
  pattern already used for hardware discovery. The first reply is still
  collected synchronously so Studio's device list is never empty. Any device
  callback over 0.25 s is recorded as a `slow-device-status` diagnostic instead
  of silently delaying every poll.
- **The control client keeps headroom over a status reply.** Studio's client
  timeout must stay at or above `MINIMUM_CLIENT_TIMEOUT_SECONDS`.

The contract also reads the device catalogue rather than a hand-written list:
every catalogued device with an implemented input control must record through
`HardwareLab.input(..., source="physical")` and appear in
`compose_live_mirror()["input_values"]`. **A device adopted in the future
inherits the requirement the day it is added** - if a new driver routes physical
input through a private path instead of the lab, the test names that device and
fails.

## MSFS 2024 add-on aircraft workspaces (2026-09-04)

The MSFS 2024 workspace was previously one undivided space with a single
profile file. It now offers the owner's add-on aircraft, grouped by developer,
from one source of truth in `muslimsim/hardware/msfs24_aircraft.py`.

- **Fenix** - A320, A319, A321
- **FSLabs** - A321, A321neo, A321 Sharklets
- **FlyByWire** - A32NX, A380X
- **PMDG** - 737-600, 737-700, 737-800, 737-900, 777-300ER, 777F
- **iFly** - 737 MAX 8
- **iniBuilds** - A350

Each airframe gets its own isolated mapping profile, exactly as the X-Plane
aircraft do, so an assignment made for a PMDG 737-800 can never appear on a
Fenix A320. The two pre-existing paths are deliberately unchanged:
`hardware_profiles.json` still belongs to Zibo, and
`hardware_profiles_msfs24.json` is still the default MSFS profile, now owned by
the default airframe. Every other airframe uses
`hardware_profiles_msfs24_<key>.json`.

The imported `msfs24_command_catalog.json` is written per *family*, not per
variant, so variants share a function library while keeping separate mappings:

| selector entries | catalogue family | functions |
| --- | --- | --- |
| Fenix A320 / A319 / A321 | `Fenix A320 family` | 192 |
| FSLabs A321 / A321neo / A321 Sharklets | `FSLabs A320 family` | 18 |
| PMDG 737-600/700/800/900 | `PMDG 737 / 777 (737)` | 587 |
| PMDG 777-300ER / 777F | `PMDG 737 / 777 (777)` | 774 |
| iFly 737 MAX 8 | `iFly 737 MAX 8 (MSFS2020/2024)` | 19 |
| FlyByWire A32NX / A380X | none imported | 0 |

The function browser filters on the selected airframe's family string, so a
PMDG command is never offered while a Fenix workspace is open. **FlyByWire has
no functions in the imported workbook.** Both FBW airframes are still offered
and can be practised, and the mapper says the catalogue has none for them rather
than showing an unexplained empty list. Nothing here invents a command: a family
appears only where the import actually contains it.

`tools/test_msfs24_aircraft.py` fails if a family string stops matching the
import, if two airframes share a mapping profile, or if either legacy profile
path moves. MSFS dispatch remains off until its connector is built; this change
selects mapping workspaces only and adds no simulator writer.

### Aircraft isolation contract (2026-09-04)

Three separate properties keep one aircraft out of another's way. They are
enforced by `tools/test_aircraft_isolation.py`.

**Mappings are isolated by file.** Every aircraft in both simulators has its own
profile, 19 in total, and bindings live inside it keyed `device.control`. There
is no shared binding table, so a mapping made for one airframe cannot appear in
another.

**Reuse is allowed only where the function provably exists.** Variants sharing a
catalogue family draw from the identical imported library, so a brand-new
workspace inherits its family siblings' mappings once, when its profile file is
first created, and is fully independent afterwards - editing the A321 never
changes the A320. Across unrelated aircraft nothing is guessed:
`copy_msfs24_bindings()` transfers a binding only when its exact target is
present in the destination's own library and reports everything else as skipped
with a reason. `laminar/B738/...`, `AirbusFBW/...` and a PMDG LVAR have no
reliable equivalence, and a control that looks mapped but fires the wrong
command is worse than one that is not mapped.

**Only the loaded aircraft is talked to.** Outbound, the bridge computes
`selection_matches_loaded_aircraft` and refuses to dispatch a mapping whose
workspace does not match the loaded `.acf`; a second guard stops an MSFS binding
reaching the X-Plane API even if a profile file is copied into the wrong folder.
Inbound, telemetry workers are started per detected aircraft - roughly nineteen
`aircraft_profile` gates - so a worker for an aircraft that is not loaded never
starts and never resolves its DataRefs. Nothing Live starts until
`_await_initial_aircraft_profile` positively identifies the aircraft, and
`_aircraft_profile_watchdog` handles a mid-session change.

### Imported MSFS 2024 command sources (2026-09-04)

`tools/import_msfs24_functions.py` folds owner-supplied command sources into
`msfs24_command_catalog.json`. It is a dry run by default and takes `--apply`;
it backs the catalogue up first and records the originating file on every entry.
Nothing is invented - an entry exists only where a source documents it.

| source | what it gives |
| --- | --- |
| Rowsfire MobiFlight `.mcc` (20 files) | 1,170 labelled controls, 1,330 executable MSFS RPN actions |
| SPAD.neXt Honeycomb profile XML | 88 `SIMCONNECT:` events and `LVAR:` targets for the A32NX |
| Stream Deck A320 `.lua` | 22 `A32NX_*` LVARs |

The catalogue grew 1,590 -> 2,254 functions:

| family | before | after |
| --- | --- | --- |
| FlyByWire A32NX | 0 | **274** |
| Fenix A320 family | 192 | 400 |
| FSLabs A320 family | 18 | 82 |
| PMDG 737 / 777 (737) | 587 | 614 |
| PMDG 737 / 777 (777) | 774 | 804 |
| iFly 737 MAX 8 | 19 | 19 |
| iniBuilds A350 | 0 | **61** |

One deliberate exclusion remains. The **FBW A380X** keeps no library: every
imported FBW source documents the A32NX, and lending it the A32NX's LVARs would
map an airframe it does not fit.

**iniBuilds A350** was added on 2026-09-04 and its 61 functions imported. The
Rowsfire panels document the A350 as one airframe; -900 and -1000 variants would
share this family, exactly as the Fenix variants do.

The importer no longer keeps its own copy of the family names - it imports them
from `msfs24_aircraft.py`, so the selector and the import cannot disagree about
how a family is spelled.

The iFly YourControls YAML is a separate case and is not handled by this
importer: its command half is CDU-only, expressed as numbered writes to
`VC_Navigation_trigger_VAL`, and needs its own trigger-number model.

## MSFS 2024 connector - scoping (2026-09-04)

MSFS dispatch is still off, but the ground was surveyed and every prerequisite
is present. The blocking question was never SimConnect; it is that **plain
SimConnect cannot write an LVAR or run calculator code**, and almost the whole
2,355-function catalogue is exactly that:

    20 (>L:VC_OVHD_ADIRS_1_KNOB, number)

Only a WASM module inside the simulator can execute those. Two are already
installed under `D:\MSFS24\Community`, which `UserCfg.opt` confirms is the
active package path (`InstalledPackagesPath "D:\MSFS24"`).

### Transport A - MobiFlight event module (primary)

`mobiflight-event-module` v1.0.1. This is the transport the owner's Rowsfire
`.mcc` configs were authored against, so the imported RPN targets are known to
run on it. Preferred for that reason.

### Transport B - PU Air Korea `WASM_PU.wasm` (proven fallback)

Read out of the binary rather than guessed: the module carries its own log
format strings, which name every channel and verb.

| channel | evidence in the binary |
| --- | --- |
| `PU_WASM.Command` | `SIMCONNECT_RECV_ID_CLIENT_DATA - CMD "%s"` |
| `PU_WASM.Acknowledge` | `RegisterLVar -> Sent Acknowledge ID: %u Offset: %u Value: %d` |
| `PU_WASM.LVars` | `LVar %s with ID %u and Offset %u changed` / `New value is %f` |
| `PU_WASM.Result` | `Error on Setting Client Data RESULT` |

| verb | meaning |
| --- | --- |
| `HW.Reg.<lvar>` | register an LVar; the module answers with the id/offset it will stream changes to |
| `HW.Exe.<code>` | `execute_calculator_code("%s")` |
| `HW.Set.` | set value |

It is simpler than MobiFlight's interface and is what the owner's own PU CONNECT
software uses, so it is a working fallback and a second reference for the
architecture.

### Remaining work, in order

1. **Prove the transport.** `tools/probe_msfs_wasm_channel.py` asks one module
   whether it answers, and changes nothing. It follows
   `probe_mobiflight_boards.py`: confirm the protocol from the simulator before
   writing a driver on it. It needs MSFS running and in a flight.
2. **Dispatcher.** Replace the deliberate refusal in
   `bridge/final_msfs24.py::_binding_sink` with a real route per protocol:
   `rpn`/`lvar` through the WASM channel, `simconnect` through
   `TRANSMIT_CLIENT_EVENT`, PMDG `hevent` through calculator code.
3. **Safety parity with X-Plane.** The loaded-aircraft gate, the unpowered
   blackout rule and the Practice write barrier must all hold before any MSFS
   write is enabled.
4. **Telemetry in.** LVar registration and streaming for live displays.

### Dependency

The connector needs a SimConnect client in the pinned Python 3.11 runtime. The
`SimConnect` package (0.4.26) exposes the client-data API the WASM channel needs
- `MapClientDataNameToID`, `CreateClientData`, `AddToClientDataDefinition`,
`SetClientData`, `RequestClientData` - and ships its own `SimConnect.dll`, so the
MSFS SDK is not required. Installing it is a change to the runtime that owns the
hardware, so it is the owner's call rather than a silent step.

