# MCDU32 and PFP3N page-switching setup

This describes the maintainer's existing physical-key setup. Preserve it when helping with display work; it is separate from ordinary simulator page keys such as PREV/NEXT PAGE.

## Physical gestures

| Gesture | Action |
| --- | --- |
| Press and release `/` twice quickly | Advance through the cockpit display pages on that panel. |
| Press and release `.` three times quickly | Switch from CDU/FMC to PFD, or from a graphical page back to CDU/FMC. |

The detectors count **press edges**, not repeated held reports. The maximum gap between slash taps is **0.55 seconds**; between period taps it is **0.60 seconds**. A longer gap resets the gesture count.

| Device | USB identity | Period index | Slash index |
| --- | --- | --- | --- |
| WINCTRL 32 MCDU CAPTAIN / MCDU32 | `4098:BB36` | `41` | `70` |
| WINCTRL 3N PFP CAPTAIN / PFP3N | `4098:BB35` | `38` | `69` |

These are the existing zero-based hardware key indices. Keep the captured key mapping and simulator bindings intact; do not substitute generic keyboard keys or infer indices from the faceplate artwork.

## Zibo 737 and LevelUp

Double-slash cycles the graphical deck:

`PFD → ND → ENG PRI → MFD → HYD → PFD`

For BB36, triple-period toggles **graphical FMC and PFD within the same persistent F0 display owner**. The current router deliberately disables the older F0/F2 teardown-and-reopen handoff. Some historical module descriptions describe that older arrangement; follow `BB36PFDPath._toggle_graphical_fmc`, `MuslimSimBB36PathRouter.request_toggle`, and `_make_path` in the current source.

BB35 retains its separate FMC/PFD path router. Triple-period switches its FMC and graphical paths; double-slash cycles the deck while in the graphical path. Do not impose BB36's lifecycle on BB35 or change either panel's existing keypad assignments.

## ToLiss Airbus

Both panels start on CDU. Triple-period selects PFD from CDU and returns to CDU from a graphical page. The graphical deck is:

`PFD → ND → ENG → BLEED → PRESS → COND → ELEC → HYD → FUEL → DOOR → WHEEL → APU → FCTL → CRUISE → STATUS`

- **BB36:** double-slash leaves CDU for PFD, then loops through the graphical deck. Use triple-period to return to CDU.
- **BB35:** double-slash cycles `CDU →` the graphical deck `→ CDU`.

Each panel keeps its own selected page and hardware handle. Both keypads use their captured mappings to operate **MCDU1**, including while a graphical page is displayed. Their shared ToLiss telemetry feed does not make them one device. The ToLiss command worker distinguishes multi-tap display gestures from ordinary period/slash input; preserve that buffering and edge handling.

## Source entry points

- [BB36 Zibo/LevelUp routing](../muslimsim/devices/mcdu_bb36_separate_paths.py): gesture detectors, `BB36_DISPLAY_PAGE_ORDER`, graphical FMC toggle, persistent F0 ownership.
- [BB35 Zibo/LevelUp routing](../muslimsim/devices/pfp_bb35_separate_paths.py): separate FMC/PFD router and `DISPLAY_PAGE_ORDER`.
- [ToLiss display paths](../muslimsim/devices/mcdu_bb36_toliss_paths.py): `TolissBB36MirrorPath`, `TolissBB35DisplayPath`, page orders and keypad command worker.
- [Bridge integration](../bridge/final.py): selects the aircraft-specific owners and supplies telemetry/rendering callbacks.

## Help needed

The maintainer reports most devices working with Zibo, LevelUp needing tweaks, and ToLiss almost complete with remaining MCDU32/PFP3N display problems. These are current development assessments, not completed compatibility certification.

For a display report, include the aircraft/version, panel, starting page, exact gesture, resulting page, and whether the problem followed a restart, USB reconnect, or power change. State whether the display froze, became blank, or showed the wrong content only when that symptom was actually observed. Remove credentials and personal/device serial information from logs.

Do not start an additional HID reader, reset the panel during a page switch, or restore BB36's old F0/F2 handoff as a speculative fix. Preserve page independence, existing mappings, aircraft-power handling, and shutdown cleanup.

**MSFS 2024 working integration has not started yet.** The repository's existing MSFS launcher, catalogues and configuration structures are scaffolding. Developers are needed to implement and validate the actual aircraft integration; X-Plane's page/dataref routing must not be presented as MSFS support.
