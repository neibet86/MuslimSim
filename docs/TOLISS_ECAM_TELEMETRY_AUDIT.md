# ToLiss ECAM telemetry audit — 2026-09-10 (BUG-41/42/43/44/45/53)

Deployment update: the native SD probe was installed with operator approval
after X-Plane closed on September 10, 2026. Its checksum matches the tested
build. The research report's earlier not-deployed status is historical;
native page-1 testing is now complete; see the acceptance result below.

Research follow-up: `TOLISS_BLEED_SOURCE_RESEARCH.md` traces the historical
temperature columns to XHSI and records the prepared, not-yet-deployed native
SDK probe (subsequently installed/tested). The installation changelog identifies V1.9.1 Build 1696 despite
the V1p8 folder name; old version assumptions must not establish compatibility.

Status: **BLEED temperature telemetry remains unresolved in the live session;
BUG-53 topology/conversions are implemented, not complete live-data acceptance.**
BUG-54 follow-up: live SDline2g/5g/13g returned 36 NUL bytes each with SDPage=1.
Pressure and ambient pressure were numeric. The fixed-column decoder now
preserves embedded empty cells, but cannot recover wholly absent readings.
Do not assume native page selection alone makes these sources available.
After the operator explicitly confirmed selecting native BLEED, repeat GETs
still returned all-NUL green rows 2/5/13 and amber row 2. SDPage remained 1;
LeftBleedPress was 65.344 psia and Pack1Temp was 0.27783 (pointer ratio).
The prior assertion that page selection supplies these six engineering
readings is not supported by this live test. Exact SD-column temperature
mapping remains a synthetic test contract, not a validated live source.
ECAM degree signs now use native hollow rings because LCD text is ASCII-only.
The user's request covers every value, valve, colour, validity flag, startup
phase and aircraft configuration. The existing renderer does not yet meet
that requirement. Unknown is never permission to reproduce a photo's number.
BUG-44 adopts the owner's explicit policy that a plausible live simulator
source should be connected provisionally even when its exact ToLiss index or
encoding is undocumented. “Provisional” never permits a fixed demonstration
number or simulator write.

## Evidence obtained without operating the aircraft

## Expanded review — 2026-09-10 17:09 local

`diagnostics/toliss-ecam/20260910_170956_ecam_all_pages_review.json` contains
573 GET-only source records, zero read errors, all 90 SD text layers empty.
This checks source delivery in one current state, not phase/failure acceptance.

| Page | Current path and remaining acceptance work |
|---|---|
| ENGINE | FADEC masks and live oil/used-fuel inputs; oil ratio-to-QT and N1/N2-based vibration are provisional, not native vibration measurements. Generic engine_vibration absent. |
| BLEED | Pressure and pointer/valve sources readable; six temperature text values unavailable in direct SDK and web tests. |
| CAB PRESS | Cabin pressure/altitude/V/S path exists; landing elevation validity remains unknown; OutFlowValveAft absent in this A321 catalogue. |
| ELEC | Battery/bus/connection sources exist; generic amps, derived load/Hz and oil-temperature proxy for IDG are not exact native engineering readings. |
| HYD | Live pressures/pump codes; pressure-derived fire-valve state remains an approximation requiring native comparison. |
| FUEL | A321 mass/tank mapping, flow and pump enums; engine totalizers, temperature and variant/ACT logic need wider-state native comparison. |
| APU | Master/N/EGT/bleed path; manifold-derived pressure, rundown and generator details require native comparison. |
| COND | Cabin-zone measured temperatures present; trim/selector and cargo indications require native comparison across configurations. |
| DOOR/OXY | Door arrays and slides; generic oxygen value and cockpit indication remain limited; CLGDoor absent. |
| WHEEL | Gear/spoilers/tires available; supply-derived BSCU/steering/brake legends are provisional, not full failure logic. |
| F/CTL | Surface/FCC/hydraulic sources wired; travel, polarity and hydraulic failure behaviour require controlled native tests. |
| STATUS | All 90 SD colour layers empty; cannot certify NORMAL or reconstruct the native status list from master-warning lamps. |

All 16 existing ECAM button targets exist in the live catalogue. T.O CONFIG
and EMER CANC were unbound; their learned contacts are now linked to verified
native commands without executing them. Physical acceptance is pending.

The prepared local-only texture trial can provide authoritative selected-page
imagery if its texture scan succeeds. It cannot by itself provide twelve
simultaneous pages, numerical temperatures or an LCD raster transport. First
measure the actual 4096 atlas, power behaviour and frame-time impact. Do not
substitute reference-picture numbers or claim the above provisional paths exact.

## Earlier evidence

- Running aircraft: `Aircraft/Laminar Research/ToLissA321_V1p8/a321.acf`,
  ICAO `A21N`; X-Plane 12.4.3, local read-only API v2.
- `diagnostics/toliss-ecam/20260909_220214_current_observed.json`: 429 values.
- `diagnostics/toliss-ecam/20260909_222101_ground_power_audit.json`: 567 values,
  full catalogue/type metadata and all newly subscribed fields. Operator
  labels describe a snapshot, not independent certification of a flight phase.
- `diagnostics/toliss-ecam/20260909_232907_current-observed-elec-fix.json`:
  568 GET-only values after BUG-43. It proves live BAT/bus/source delivery into
  the adapter in the then-current state; the label is not a certified phase.
- `diagnostics/toliss-ecam/20260909_234552_current_observed_bug44.json`:
  568 GET-only values used for BUG-44. Its rendered sheets prove delivery of
  live 50 PSI bleed supply, 233 PSI tire values, 38 °C fuel temperatures,
  1991 PSI generic oxygen, 75,246 kg loaded mass and empty STATUS layers in
  that observed state. These numbers are evidence, never fallbacks.
- `diagnostics/toliss-ecam/20260910_000816_bug45_engines_working.json`:
  both FADECs active, about 65 psia left/right bleed (approximately 51 PSI
  gauge after BUG-53), 3000 PSI G/B/Y hydraulics,
  live engine oil/speed values and current electrical/fuel-pump enums. This
  disproved the prior “zero bleed indication means failed” assumption.
- Owner's `Screenshot 2026-09-10 133903.png` plus simultaneous GET-only values:
  APU/X bleed and both FCVs open, both engine/HP indications zero, absolute
  manifolds 50.88/50.75 psia and ambient 97,406.6 Pa. The native page shows
  5/210 °C, 37/36 PSI and 190 °C with a horizontal X valve, vertical APU branch
  and stopped-engine branches amber/disconnected. This is BUG-53's state truth.
- Observed: engines/FADECs off, APU master off, external-power display box on,
  AC buses energised, hydraulic pressure zero, ADR indications unavailable.
- No commands, switches, simulator datarefs, HID devices or running Studio
  processes were changed. Captures use GET requests, not subscriptions.

## Sources and their limits

- Installed ToLiss **A321 Tutorial**, page 11: external-power startup picture
  with the 40-second self-test. Installed **A321 Simulation Manual**, page 89,
  section 9.1.3: turning a display brightness control off/on initiates its
  self-test. Files are in the aircraft's `manuals/` folder; PDFs are untouched.
- [Official ToLiss A321 change log](https://toliss.com/pages/a321-change-log),
  v1.6: improved MCDU, FWC and FMGS startup behaviour. MCDU startup is not
  necessarily the same sequence as an ECAM DU; never invent an application
  startup delay for either.
- [XHSI Airbus dataref source](https://github.com/sum1els/XHSI_plugin/blob/master/datarefs_qpac.cpp)
  and [packet decoder](https://github.com/sum1els/XHSI_plugin/blob/master/packets.cpp)
  corroborate historical AirbusFBW FCC/pump status arrays. They predate the
  installed aircraft and are NOT proof of every current array index/enum.
- The installed A321 `.acf` tank geometry identifies centre tank index 0,
  left wing 1, right wing 2. The live quantities confirm `[0,5400,5400,...]`.
  This mapping is deliberately gated to A321, not imposed on A330/A340.
- [FlyByWire WHEEL reference](https://docs.flybywiresim.com/pilots-corner/a32nx/a32nx-briefing/ecam/sd/wheel/)
  and [BLEED reference](https://docs.flybywiresim.com/pilots-corner/a32nx/a32nx-briefing/ecam/sd/bleed/)
  corroborate the symbol purposes and conditional presentations. They are
  primary documentation for a different simulation, NOT ToLiss dataref proof.
  The owner's photographs remain the requested geometry reference.

## Corrections implemented

| Indication | Corrected source/behaviour | Limit |
|---|---|---|
| Cockpit/FWD/AFT cabin temperature | `CockpitTemperature_degC`, `CabinZone1Temperature_degC`, `CabinZone2Temperature_degC` | Old `CockpitTemp`/`FwdCabinTemp`/`AftCabinTemp` were selector settings |
| Fuel L/CTR/R | `sim/flightmodel/weight/m_fuel[1/0/2]`, A321 only | ACT/additional tanks and other variants still need artwork/mapping |
| Fuel used and flow | Explicit generic X-Plane engine totalizer kg; flow kg/s × 60 | Ground snapshot verified; ToLiss burn/in-flight agreement NOT verified |
| Fuel valve/pump symbols | Explicit documented LP/crossfeed status enums; OHP pump status array with SD auto-pump centre entries | LP code 1 means amber CLOSED, not boolean OPEN. Historical source is cross-checked with the current ground snapshot; transfer/variant cases remain open |
| Engine oil/vibration visibility | Masked while FADEC unavailable; oil ratio provisionally ×16.5 QT; vibration provisionally follows live N1/70 and N2/115 | Curves require native idle/takeoff/flight comparison |
| APU N/EGT/bleed | Existing ToLiss values, masked when APU master is off/unknown; APU PSI averages the two ambient-corrected gauge manifolds only while APU bleed indicates open | Rundown and generator box/load need further validation |
| BLEED engineering values | Proposed green SDline2/5/13 column mapping remains unverified; these rows are wholly NUL in the operator-confirmed native BLEED state | No working live source yet. Native BLEED selection did not recover temperatures; no cabin/TAT/formula substitute |
| BLEED pressure/pointers | Absolute manifold psia minus live ambient Pa/6894.757293; `PackTemp` clamps directly to the C-H arc and `PackFlow` uses `clamp((raw-.8)*2.5)` | Exact normal APU state confirmed; altitude/abnormal sweeps remain |
| Pack/engine valves | FCV indications plus per-engine guarded stale-zero recovery requiring switch, running, N2, APU-off and positive gauge pressure | `ENG*BleedInd` remains stale zero at 65 psia; native fault codes 2/3 override recovery |
| BLEED pack/branch artwork | Four arcs, supplied cross-manifold, static GND marker, independent vertical APU branch, horizontal open X valve and independently gated IP/HP branches | Ground-air connected and abnormal/transit cases still require native comparison |
| WHEEL gear/steering/brakes | Three hatched down-lock triangles from gear indications; NWSAvail steering legend; centre braking labels derived from measured hydraulic supply plus existing brake/anti-skid controls | Limited supply-derived warning logic, NOT verified full BSCU fault telemetry |
| COND temperatures/hot air | Measured cabin and cargo temperatures; live CKPT/FWD/AFT selector values drive the three pointer arcs; `HotAirValve`, cargo hot air and isolation valves drive topology | Selector and cargo conventions remain provisional pending state sweeps |
| F/CTL surfaces | Existing actual `anim/*` positions remain independent and live | Not joystick commands |
| F/CTL availability | L/R aileron/elevator and rudder availability arrays; `FCCAvailArray`, `PitchTrimPowered`, `SDSpoilerArray` | Low/unavailable markers amber, not falsely healthy green; exhaustive failure enums still open |
| HYD | System pressure/quantity and pump array; pressurised Green/Yellow provisionally means fire valve open | Dedicated fire-valve export remains absent |
| A321 doors/OXY | Pax indices 4/5 exits, 6/7 aft; actual windows/slides; generic live bottle pressure duplicated into both displayed OXY positions | Door indices and one-bottle duplication are provisional; ToLiss exports no separate bottle pressures |
| Footer | Live X-Plane TAT/SAT and loaded aircraft mass retained instead of erased | FMGC validity and ISA source/visibility still open |
| DU startup | `DUSelfTestTimeLeft` and `DUBrightness`, captain PFD 0/ND 1/SD 5/MCDU 6 | Timer is simulator-owned; physical six-state acceptance and MCDU-specific startup still required |
| Display electrical gate | Read ToLiss `ACBusVoltages`; batteries alone do not establish display power | Individual DU/bus transfer routing and battery-only emergency configurations still require verification |
| ELEC batteries/buses/sources | Live battery/generator/bus amps and volts; connection codes; 300 A load scale, energized 400 Hz and engine-oil IDG proxy are provisional | Calibrated load/frequency/IDG sources and exhaustive abnormal topology remain unresolved |
| WHEEL pressure | `TirePressureArray[0..5]` provisionally maps nose pair then four main wheels | Installed A321 order must be confirmed by an unequal-pressure/native-display comparison |
| STATUS | All 18×5 `SDlineN{g,a,r,w,b}` native text layers are subscribed and rendered; a wholly empty set means NORMAL | Abnormal/deferred-message capture still required to validate spacing and colours |

`SDFUEL`, `SDELEC`, `SDELECDC` are scalar page-selection flags, NOT arrays
of kg/volts. Those subscriptions were removed. The adapter strictly rejects
scalars where an array is required. It also suppresses the legacy OHP-switch
interpretation of generator output. Old unused drawing code/comments are
not evidence that those mappings are valid.

## Required remaining work — do not hide this with demonstration values

| Page | Unresolved indication/acceptance work |
|---|---|
| ENGINE | Oil quantity in quarts, N2 vibration, exact FADEC rundown/temperature visibility, powered generic-source comparison |
| BLEED | BUG-53 confirms normal APU-on values/topology. Ground-air connected, valve transit and complete fault/anti-ice cases still need native comparison; SD engineering rows require native BLEED selection |
| CAB PRESS | SYS encoding is provisional (`CabPressModeLights` observed 1 with SYS2); FMGC-valid landing elevation and complete fault indications remain open |
| COND | Selector and cargo readings now update; native comparison of the selector/trim conventions and all valve/fault states remains open |
| ELEC | Battery/TR currents, generator load/frequency, IDG temperature, complete APU/EXT PWR boxes and exhaustive failure topology. TR/GEN voltage is provisionally taken from the downstream live DC/AC bus; generic GPU/current values known to disagree remain unused |
| HYD | Exact PTU/RAT/electric-pump/fault enum artwork, reservoir/fire-valve indications |
| FUEL | Wing fuel temperatures now use generic tank telemetry; full transfer/variant/extra-tank cases and burn-phase verification remain open |
| DOOR/OXY | One generic live oxygen bottle feeds both displayed positions provisionally; independent ToLiss bottle sources, exits/slides and cockpit hatch remain open |
| WHEEL | First six TirePressureArray slots are provisionally nose 1/2 then main 1..4; unequal-pressure confirmation, gear transit and full BSCU fault discretes remain open |
| APU | Bleed PSI now uses ambient-corrected gauge manifolds; generator box/values, rundown and full start/availability phases remain open |
| F/CTL | Full failure enums, hydraulic-system assignment, exact scales/positions and controller sweep compared with native SD |
| STATUS | `SDline1..18[a,b,g,r,w]` are published, but blank in the captured state. Full coloured list positioning/selection and NORMAL validity remain unimplemented; absence of master alerts does not establish NORMAL |
| All | Exact fonts/geometry, per-DU power routing, ADR redundancy and FMGC footer validity; no claim of pixel-identical Airbus artwork |

Several unavailable fields have been made more visibly unknown by this audit.
That is intentional: fewer plausible but incorrect numbers is not proof that
the remaining implementation is complete. The blue-grey SD field follows the
new `PIC/cut` references; the photographed bezel/perspective is not drawn.

## Safe acceptance procedure (not executed automatically)

Once the owner is safely parked, compare native and physical displays under
battery-only, external power, APU running, engines running on ground, then in
a separate normal flight. Record snapshots while the owner establishes each
state; do not issue aircraft commands or initialise controls from stationary
hardware. Test both page selectors independently and move each control while
watching the native F/CTL. Capture native self-test entry/exit, brightness OFF,
loss/restoration of supply and disconnect/reconnect.

Remaining numeric boxes require a verified current ToLiss field map or official
display-data integration, plus simultaneous native-display comparison. Asking
the owner for that documentation/integration is preferable to guessing units,
array slots, pressures or generator loads. Do not restart Studio in flight.

## Reproducible checks and performance

- `tools/test_toliss_ecam_telemetry.py`: typed fields, exact SD-column BLEED
  temperatures, ambient-to-gauge pressure, pointer scaling, APU/external/
  engine/failure matrices, non-photographic fuel changes, unavailable masks,
  amber open-door labels and both workers' OFF → SELF TEST → READY → OFF.
- `test_toliss_ecam_reference.py`: all 12 layouts/bounds, moving controls,
  exact full/delta pixel agreement and idle suppression.
- `test_toliss_displays.py`: PFD 319 full/244 moving and ND 434/364 reports
  unchanged by BUG-53. Same offline fixture: F/CTL remains 260/114;
  BUG-41 maximum SD BLEED was 266; BUG-42 made it 310; BUG-53's complete APU
  manifold is 343, still below the existing 400-report ceiling. These are HID-report counts, NOT the PNG
  emulator's raw primitive counts.
- `test_toliss_wheel_bleed_details.py`: requested symbols/colours, horizontal
  open X valve, vertical APU valve, supplied manifold/GND marker, APU-only and
  independent engine/failure branches, exact full/delta pixels and 780-
  primitive guard. Included in the mandatory known-regression suite.
- Previously each LCD copied/sorted all 247 secondary fields every tick.
  It now requests only its precomputed page dependencies: CDU 3, ENGINE 24,
  FUEL 21, F/CTL 34. Adding 10,000 unrelated fields leaves these unchanged.
  Total subscriptions still share one owner; dataref IDs resolve once per
  distinct name per connection, not once per alias. Disconnect/reconnect
  clears retained readings; empty WebSocket closure is not treated as live.
- Native-glyph preview tool now requires explicit `--snapshot FILE` or
  `--samples`. Recorded telemetry and demonstration images are kept separate.
- `test_toliss_bb35_keys.py` (71 keys/142 phases), `test_fcu_efis_toliss.py`
  (110 checks), aircraft isolation, BB36 recovery (26 checks), known
  regressions and `launch.py --check` passed without opening hardware.

Latest backup: `Backup/toliss_bleed_apu_telemetry_20260910_143913/`.

## 2026-09-10 native BLEED page-1 acceptance result

The initial startup samples were pages 0/0/2, so were not accepted as BLEED
evidence. A Plugin Admin disable/re-enable produced three fresh samples, all
page 1, while BLEED was visibly selected. For SDline2g/5g/13g, 2a/5a/13a and
2w, all 63 reads returned one NUL byte: declared size 37, requests 36/40/256,
changed bytes 1 and guards intact. The native display visibly showed top
32/32, compressor 30/30 and duct 32/32 degrees Celsius. These observed values
are evidence only and must not become defaults or simulated telemetry.

Numeric Left/RightBleedPress remained readable (approximately 14.346 absolute
PSI); Pack1Temp and Pack2Temp were 0.5, not Celsius. Direct SDK access therefore
does not recover the missing text in this tested ToLiss state. A web-only
decoder repair cannot supply those six temperatures. This does not establish
that every possible dataref or every aircraft state lacks the values.

The probe automatically ceased reads after sample 3. No aircraft controls,
production files or hardware mappings were changed. Preserved full log:
`Backup/sd_probe_live_20260910_165858/Log.txt`. Next candidate is a separately
approved, measured live display/texture extraction trial; that is not yet an
implemented numeric telemetry source or a validated BB35/BB36 display path.
