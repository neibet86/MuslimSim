# ToLiss display coverage contract

Last audited: 2026-09-09

### BUG-41 telemetry audit supersedes earlier mapping assumptions

See `TOLISS_ECAM_TELEMETRY_AUDIT.md`. SD page flags were not engineering
arrays, temperature selectors were not cabin measurements, and charged
battery voltage did not prove display power. These faults are corrected or
suppressed with explicit unknowns. Native DU self-test is wired on both
display owners. This is a partial implementation, not complete all-state
Airbus parity. Full footer, electrical, pneumatic, oxygen, wheel and STATUS
data remain open; screenshot sample numbers must never fill those gaps.

### BUG-40 reference-layout update

The owner's twelve `PIC/` references now drive the authored ENGINE, BLEED,
CAB PRESS, COND, ELEC, HYD, FUEL, DOOR/OXY, WHEEL, APU, F/CTL and STATUS
synoptics on both panels. Titles use white rules; the footer has three
columns and TAT/SAT/ISA rows. Native fonts are unchanged. This replaces the
generic page bodies; old centered-title/single-row-footer descriptions below
are superseded for these pages. CRUISE retains its prior body and shares the
new footer. Test-only NORMAL and engineering sample values are not live data.

Verified adapter wiring added here: CockpitTemp, generic fuel_flow_kg_sec
converted to KG/MIN, existing CabinDeltaP/LandElev/vent inputs, and all ten
anim/spoiler inputs on WHEEL. Existing F/CTL output/trim/hydraulic paths remain.
Unmapped fields render amber XX; STATUS explicitly reports unavailable data
instead of treating cleared warning/caution lamps as proof of NORMAL.

Still open: ISA deviation, oil quantity in QT, N2 vibration, fuel used/temperature,
oxygen and tire pressure/array ordering, exact generator/TR/IDG readings and
bus connectivity enums, pack outlet/bleed/duct temperatures, pump and crossfeed
state enums, additional aircraft-specific exits, full STATUS text and abnormal
visibility/colour rules. The older translator's SD-array assumptions have not
been validated by a visual redesign. Real-simulator parity and exact physical
pixel appearance are not yet claimed. Screenshot numeric values never enter
the production feed. Offline checks and native preview review passed.

This is the authoritative feature inventory for the ToLiss display path on
BB35 and BB36. A subscribed dataref is not considered implemented until its
symbol is actually rendered, its Airbus visibility rule is applied, and an
offline guard proves that the symbol can both appear and disappear.

Runtime pages remain code-native F0 drawing/text output. PNG files under
`PNG/toliss-display-preview/` are offline QA renders only and are never loaded
by Studio or the bridge.

## Implemented and guarded

| Display | Implemented presentation | Source/authority |
| --- | --- | --- |
| PFD shape, power and source validity | Manual/reference-shaped three-row layout; black when unpowered/disconnected; independent red `SPD`, dark `ATT`, split `ALT`, tapered `V/S`, and low `HDG` failure silhouettes | ToLiss manuals/reference crops, `AirbusFBW/BatVolts` and captain validity outputs |
| PFD takeoff speeds | Cyan V1 `1`, cyan VR ring, magenta V2 triangle; all three obey ToLiss's takeoff-speed visibility flag | ToLiss V1, VR, V2 and `show_to_speeds` outputs |
| PFD flap/configuration cues | Green `F`, green `S`, green-dot clean speed and amber VFE-next double bar | ToLiss display-ready VF, VS, VGreenDot and VFENext outputs |
| PFD speed envelope | Dynamic red/black VMax strip, amber VLS line/cap, alpha-protection and stall/alpha-max regions | ToLiss VMax, VLS, VAProt, VSW and VAlphaMax outputs |
| PFD attitude/guidance | Reference palette, bilateral 5-degree ladder, bank pointer/scale, slip-skid, stepped fixed-aircraft reference, FD cross-pointer and FPV | ToLiss captain attitude, acceleration, FD and flight-path outputs |
| PFD altitude/navigation | 56px tape with one right-side wall, left ticks and 500-ft chevron labels; larger hundreds in open amber rails wholly inside grey; separate smaller live 20-ft drum boxed from the scale wall into black; moving cyan target; nonlinear 1/2/6 V/S, short heading tape; right-aligned Mach and STD/QNH groups | ToLiss captain/general PFD outputs plus documented baro proxy |
| PFD ILS | LS-gated LOC and G/S scales, white reference dots/bars, native magenta deviation diamonds, frequency and DME | `AirbusFBW/ILSonCapt`, raw LOC/G/S, ToLiss ILS/DME outputs |
| PFD FMA text/colour | All three active/armed rows use the aircraft's full-width green/blue/white/magenta/amber colour layers; an older-feed fallback retains the former subset | `AirbusFBW/FMA1*`, `FMA2*`, `FMA3*` |
| ND modes and scale | ARC, ROSE and north-up PLAN; selected range; two ARC/PLAN distance rings | Captain EFIS mode/range outputs |
| ND navigation state | Heading/map invalid presentation, GPS PRIMARY/LOST, GS/TAS/wind, range-clipped expanded green route in ROSE NAV/ARC/PLAN, visible fix IDs, preserved discontinuities, active waypoint and ToLiss solid/dashed state | ToLiss captain/map/GPS, `FlightPlanDashed`, active WPT outputs and its read-only automatic QPS situation |
| ND radio/EFIS | ILS course/deviation; four absolute physical ADF/OFF/VOR selectors; captain NAV1 single and NAV2 double pointers with source ID/validity and VOR DME; ARPT/CSTR/VOR.D/WPT/NDB/WXR/TERR annunciations | ToLiss `ckpt/fcu/adf*` selectors, VOR/NDB bearing arrays and published captain EFIS/ILS outputs |
| MCDU | Full 24 x 14 ToLiss colour-channel text grid; BB35 and BB36 each dispatch their own captured physical keypad to MCDU1 | Published `AirbusFBW/MCDU1*` strings/commands; independent hardware maps and startup baselines |
| BB35/BB36 page ownership | CDU startup; PFD/ND; ENG, BLEED, PRESS, COND, ELEC, HYD, FUEL, DOOR, WHEEL, APU, F/CTL, CRUISE and STATUS on both displays; independent complete-page cycles and BB36's direct CDU/PFD toggle | One HID/canvas owner per display and one shared deduplicated ToLiss feed |
| System display common form | Centered Airbus-style system title plus permanent TAT/SAT/GW/UTC lower-SD line on every page | Generic X-Plane aircraft weather/weight/time telemetry, rendered only while ToLiss power/connection authority is valid |
| System display pages | ENG, BLEED, PRESS, COND, ELEC, HYD, FUEL, DOOR, WHEEL, APU, CRUISE and STATUS coded pages | Published ToLiss/AirbusFBW values with documented generic engine fallbacks |
| F/CTL | Airbus wing/tail synoptic with ten individual spoilers, left/right ailerons, left/right elevators, rudder, pitch/yaw trim and G/B/Y hydraulic indication | Installed A320/A321 `anim/spoiler/1..10`, `anim/aileron*`, `anim/elevator*`, `anim/rudder`, plus published ToLiss trim/hydraulic values |

The upper red/black speed strip is driven by ToLiss `VMax_value`, not by a
second hard-coded flap table in MuslimSim. ToLiss therefore remains responsible
for choosing the active lower limit from VMO/MMO/VFE/gear limits as aircraft
configuration changes. Amber on the Airbus speed tape is low-speed/VLS or the
next-flap cue; it is not a separate yellow overspeed band.

BB35 and BB36 both expose CDU and the full graphical route. Double-SLASH cycles
each display independently, captured ECAM32 page buttons select the matching
system page on both, and triple-PERIOD toggles CDU/PFD on either device.
Both keypads operate the captain MCDU; its mirrored text changes on both
screens. Only the owning keypad worker dispatches each physical edge, while
Studio records it without a second mapping dispatch. F/CTL uses aircraft-output
surface animation values—not joystick
inputs—so its symbols show what ToLiss actually commanded. ELAC/SEC names are
fixed labels only because no reliable status array has been proven; the display
does not fabricate a green availability state.

## Not yet claimed complete

The following families must not be described as implemented until their exact
ToLiss source, enum/visibility semantics and live behavior are proven:

- FMA capture boxes, mode-change boxing timers and pulsing/reversion behavior
  beyond the native ToLiss text/colour layers;
- radio-altitude/minimums and decision-height callouts, landing-reference and
  rising-runway symbols, pitch-limit indication, speed trend and metric-altitude
  presentations;
- approach capability/category, marker-beacon, flight-director configuration,
  stick-position, TCAS/RA, windshear and terrain-warning indications;
- ND traffic targets/RA geometry and actual weather-radar or terrain imagery;
  the currently published feed supplies selector state, not those pixel/target
  data;
- the full ND route feature set beyond expanded waypoint coordinates, fix IDs
  and discontinuities: constraints/ETA, geometrically exact holds/RF legs,
  RNP/ANP and fuel-range prediction;
- every Airbus abnormal/failure variant on the PFD, ND and system display.

This list is a coverage backlog, not permission to invent unavailable data.
When ToLiss exposes no reliable public value for a feature, MuslimSim must say
so and leave it absent rather than display a convincing but false indication.

## Completion rule for each new item

An item moves into **Implemented and guarded** only after all six checks exist:

1. exact ToLiss/AirbusFBW source identified;
2. units, array shape or enum meaning established;
3. real Airbus/ToLiss show/hide rule encoded;
4. code-native rendering reaches both applicable BB35/BB36 page routes;
5. offline test proves visible, hidden, bounds and report-budget behavior;
6. live ToLiss cockpit comparison is recorded.

`tools/test_toliss_displays.py` is the current automated contract for the PFD,
ND, MCDU font isolation, page ownership, blackout and report ceilings.
`tools/test_toliss_bb35_keys.py` separately verifies raw BB35 reports through
the real command loop, all 71 keys, single punctuation/gestures, baseline and
held-key behavior, BB36 defaults, and BB35 startup/shutdown without BB36.
