# PFD / graphical display project history

## 2026-09-10 — Altitude readout split into open cradle and outboard drum

The follow-up ALT/SALT comparison showed that one enclosing hammer was still
wrong. The large live hundreds now use slot 6 between two amber horizontal
rails that start and stop inside the 56px grey tape, with no left/right border.
At its right scale wall a separate 30 x 44 amber box contains the smaller
slot-4 rolling pair and projects into black. Mach is right-aligned below the
speed tape; STD/QNH, elevation and DME share the altitude drum's right edge.
Measured traffic remains differential at 319 recovery / 244 moving reports.

## 2026-09-10 — ToLiss altitude drum and PFD proportions rebuilt from references

The A321 PFD now uses the owner's full `PIC/BARO.png` screen and the dedicated
ALT/SALT/SPEED/VS/compass/FMA crops as its authored geometry set. Both side
tapes are 56 pixels wide. The altitude wall is on the right, its ticks point
left, its 500-ft edge labels use the reference chevron, and the centred amber
hammer splits live altitude into fixed hundreds plus the established smaller
slot-4 20-ft rolling drum. The cyan selected-altitude rectangle and inward
nipple move from live target altitude. Speed no longer has the fat generic
white box. The reference palette, short heading strip, bilateral 5-degree pitch
ladder and stepped fixed-aircraft symbol replace the most visible first-pass
approximations. No feed key or display owner changed.

The additional authored marks remain differential: the measured native cost is
333 reports for page recovery and 249 for a simultaneous speed/altitude/bank
change. The complete known-regression suite and dedicated ToLiss display suite
pass; physical-panel comparison still waits for the next safe Studio restart.

## 2026-09-09 — BB36 carries the complete ToLiss graphical deck

BB36 now starts on the full-size ToLiss CDU and can reach the shared PFD/ND
renderers plus ENG, BLEED, PRESS, COND, ELEC, HYD, FUEL, DOOR, WHEEL, APU,
F/CTL, CRUISE and STATUS. BB35 remains a dedicated PFD/ND display and its route
was not broadened.

The most substantial new page is F/CTL: its wing and tail presentation moves
from all ten ToLiss spoiler animations, both actual ailerons, both elevators
and the rudder, with pitch/yaw trim and hydraulic pressure alongside. Every
system page now shares the Airbus lower-SD TAT/SAT/GW/UTC strip. All drawings
remain native commands with dirty-region output; measured traffic is 229 full /
79 moving reports for F/CTL and no ECAM recovery page exceeds 299 reports.

## 2026-09-09 — ToLiss manual geometry and VOR/ADF needles replace placeholders

The ToLiss PFD is no longer a one-row rectangular first pass. Its 640 x 480
layout now follows the installed manual and supplied cockpit references: a
three-row FMA, stepped-rounded attitude aperture, narrow speed/altitude tapes,
split ALT invalid boxes, tapered 1/2/6 V/S scale, shaped current-altitude box
and a heading strip anchored to the lower edge. Red invalid presentation uses
five different Airbus silhouettes instead of five copies of one rectangle.

Nine native `AirbusFBW/FMA*` colour layers now paint the active and armed FMA
text exactly as ToLiss publishes it. The ND gained the missing source path:
absolute ADF/OFF/VOR selectors, native VOR/NDB bearing arrays, validity,
identifiers and VOR DME. NAV1 is drawn as the single needle and NAV2 as the
double needle outside PLAN. Active route geometry is green, range-clipped and
obeys ToLiss's solid/dashed state in ROSE NAV, ARC and PLAN.

The refined code-native pages measure 274 PFD recovery / 180 moving reports
and 427 ND recovery / 356 turning reports. No bitmap is loaded at runtime and
the existing Zibo/LevelUp renderer, font prefix and dispatch paths are unchanged.

## 2026-09-09 — ToLiss PFD gains phase-correct speed and ILS symbology

V1, VR and V2 now reach the physical display as three distinct Airbus symbols
and disappear when ToLiss clears its takeoff-speed visibility output. Green F/S
and green-dot cues plus amber VFE-next follow ToLiss's computed configuration
speeds. VLS/alpha-protection remain the low-speed presentation, while the upper
limit is now a moving red/black VMax strip driven by ToLiss's active lowest
aircraft/configuration limit.

LOC and G/S retain independent raw deviation scales and now use clean native
magenta diamonds rather than square placeholders. Dedicated slot-3 diamond,
ring and triangle glyphs reduce the complete PFD from the first 299-report pass
to 286 reports; a moving frame measures 195. Runtime remains code-native and
the generated previews are QA-only.

`docs/TOLISS_DISPLAY_COVERAGE.md` is now the boundary between implemented
features and the remaining Airbus display backlog. It prevents subscribed-only
or aspirational features from being reported as finished.

## 2026-09-09 — Native ToLiss PFD/ND on both colour panels

ToLiss now owns a separate Airbus graphical route instead of inheriting Boeing
layout decisions. Its PFD keeps the existing code-native foundation but uses
packed small typography, cleaner bank marks, a thin right-pivoting vertical-
speed needle and five independent invalid-data zones. Its ND supplies compact
Airbus headers, range-scaled ARC/ROSE/PLAN geometry, two PLAN/ARC range rings,
route projection, active waypoint information and native map/GPS failure states.

BB35 has its own persistent PFD/ND owner and double-SLASH page switch. BB36
retains the MCDU plus the complete Airbus secondary-page sequence. They consume
one shared, deduplicated WebSocket subscription while keeping separate HID
writers and differential caches. Repeated captain datarefs fan out to every
local PFD/ND key; this closes the silent freeze caused by the earlier one-to-one
reverse map.

All pages remain native F0 primitives and font cells. The isolated ToLiss MCDU
font adds one full-size 23 x 29 slot after the existing resource without
changing the Zibo/LevelUp prefix. Recovery costs measure 288 PFD reports and
424 ND reports; changing motion costs 202 PFD reports and a half-degree turn
costs 353 ND reports. Both devices fail closed to black without connected,
powered ToLiss telemetry, and the offline guard covers invalid-to-valid redraw,
page cycle, duplicate-ID fan-out and font isolation.

## 2026-09-05 — Existing BB35/BB36 routes admitted for LevelUp

The LevelUp 737NG now enters the same BB35 coded-page router and BB36
coded-page/FMC router as Zibo. This is startup routing only: no renderer,
font, coordinate, page sequence, differential update, healing or recovery code
changed.

Compatibility was checked against the installed aircraft before opening the
gates. All 69 FMC1 commands and all five FMC1 datarefs used by MuslimSim's
display modules exist in LevelUp's published command/dataref lists. The shared
telemetry contract still passes all 40 checks, BB36 recovery V7 all 26 checks,
and the full differential exercise remains pixel-identical on every frame.

## 2026-09-03 — Shared BB35/BB36 telemetry

BB35 and BB36 graphical pages now share one ref-counted smoothing hub backed by
the bridge-wide X-Plane telemetry cache. Their HID handles, display writers,
page routing and recovery supervisors remain separate.

The shared source covers PFD, ND, ENG PRI, MFD and HYD numeric data. BB36 FMC
text and ND route/TCAS/NAV-ID raw values are also sourced from the Phase-A
cache. A simulator generation change clears the smoothed signal state before
fresh data is rendered.

## BB36 output recovery V7

BB36 graphical output health is now progress-aware at the native F0 report
layer. Frame completion remains useful telemetry, but it is no longer the sole
proof that the panel is alive.

Recovery sequencing:
1. supervisor confirms stale output progress / stopped worker;
2. remember current graphical page;
3. retire the sole F0 owner and close its stale HID handle;
4. prove the old output worker has left;
5. first instability gets one soft same-page reopen;
6. repeated instability may use the existing BB36-only USB/PnP recovery;
7. if elevation is unavailable, open a 60-second circuit rather than thrash;
8. a replacement F0 owner cannot open while a retired output daemon survives.

Normal shutdown is unchanged: the final teardown still sends the proven BB36
black/off state before closing the output handle.
