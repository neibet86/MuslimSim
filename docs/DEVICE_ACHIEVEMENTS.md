# Device-by-device progress

Status updated on **12 September 2026**, from the current MuslimSim source, capture notes, regression checks, and the maintainer's cockpit feedback. This guide describes what has been achieved and where help is still needed. It is not a certification of every device/aircraft combination.

The catalogue contains **25 entries**: 19 built-in entries and six community profiles. MOZA input and force-feedback entries describe different services for the same physical base. The older PDC compatibility entry covers two hardware variants, described separately below. Accessories and recognized display variants are also listed.

## Where the project stands

| Aircraft / simulator | Current position |
| --- | --- |
| X-Plane, Zibo 737 | Most devices work; repeated DFW–KLAS flights reported. Display performance/design and MOZA tuning remain. |
| X-Plane, LevelUp 737 | Existing support needs some tweaks and more testing. |
| X-Plane, ToLiss Airbus | Repeated DFW–KLAS flights reported smooth overall; slow MCDU32/PFP3N updates during climbs and MOZA tuning remain. |
| Microsoft Flight Simulator 2024 | Working integration has not been started. Existing catalogues, presets and launcher scaffolding do not constitute working MSFS24 support. Developer help is wanted. |

**Reading the status:** “captured” means actual hardware reports or protocol traffic were recorded; “implemented” means a path exists in the project; “owner-confirmed” means a particular live check was reported successful. Offline checks protect behavior but do not prove every physical control on every firmware. Community definitions are listed separately because their presence in Studio is not proof of complete runtime support.

### Flight-tested status and where help is needed

The maintainer has flown **DFW–Las Vegas (KLAS) multiple times in both Zibo 737 and ToLiss Airbus** using MuslimSim. He reports smooth operation overall; the main issue observed on these flights is **slow PFP3N and MCDU32 LCD updates during climbs**. This is practical flight experience on his setup, not a claim that every hardware/aircraft combination has been validated.

- **ToLiss displays:** The maintainer tried transferring the simulator's own PFD, MFD and ND imagery over the panels' USB-C connection to reproduce the exact simulator screens. Refresh was too slow in that experiment. The bottleneck has not yet been isolated between extraction/rendering, USB transfer and panel refresh; the connector alone does not establish a native video-input mode. Help measuring and improving this path is welcome. Another option is to extend/refine the existing coded ToLiss displays, following the approach already used for Zibo.
- **Zibo displays:** The coded screens are functional overall, but their visual design still needs refinement, alongside the reported LCD update performance work.
- **MOZA force feedback:** Feedback already works to some extent, but substantial tuning is still needed to get the feel right in **both Zibo and ToLiss**. The maintainer reports having decoded captures available for this work. Help is wanted with aircraft-specific gains, effect response and validation; existing device-specific protocol gates remain in place, including AB6 fields that have not been byte-confirmed in the implemented profile.

## Shared achievements across the integrated devices

- Studio brings device faceplates, input observation, assignments and testing into one application. Reassignment is available without deleting existing assignments; aircraft-specific protected routes still have their documented ownership rules.
- Physical input feedback is independent of simulator connection. The shared controller reader was corrected so WINCTRL throttle, pedals and TCA Boeing inputs do not depend on a PU overhead being attached.
- Presence and identity use the actual device information. Disconnected devices should disappear; unrelated USB equipment must not acquire a WINCTRL identity. The A210/AY210 name mismatch that caused repeated disappearance has been fixed and checked live.
- Practice is an experiment sandbox and does not save simulator-function assignments. Maintained switches and axes retain startup baselines and pickup protections.
- Output support is device-specific. Captured lamps, windows and displays follow the established power and shutdown rules; unknown output packets are not invented. The explicit 3M PDC active-backlight exception and PU shutdown limitation are described below.
- Small explanatory page captions were hidden at the owner's request, while control labels, values and click targets remain. WINCTRL 32 AGP Metal deliberately retains its instructions and quick reference.

## WINCTRL panels and flight controls

### WINCTRL 3M PDC — BB51

**Purpose:** Boeing EFIS/display controls: map presentation, range, barometric setting, minimums, overlays and navigation selectors. Its current Studio name is **WINCTRL 3M PDC**, without the unwanted trailing “L”. The internal compatibility key remains `pdc_bb61_left` so existing mappings retain their identity.

**Achieved:** A full 38-step guided capture rebuilt the BB51 physical source map, using 1,395 reports and 113 events. Buttons, selector positions, BARO/MINS rotation and fast/slow encoder behavior have dedicated mappings. The panel includes **VSD** and an **endless RANGE encoder**. Reassignment changes the source when requested while preserving simulator-function assignments. Faceplate feedback uses the captured physical controls.

Its backlight now stays on while its owner runs in **Practice and Live**, including with the simulator disconnected or aircraft power unavailable. The owner has confirmed that it stays on in both modes. Normal stop/shutdown still sends the captured zero-brightness state.

**Remaining work:** Broader aircraft/firmware acceptance testing; the backlight confirmation is a specific successful live check, not a claim that all aircraft routes were re-tested in this documentation update.

### WINCTRL 3M PDC — BB52

**Purpose:** The other 3M PDC hardware variant, retained under `pdc_bb52_right`.

**Achieved:** A separate captured control map supports buttons, navigation selectors, BARO/MINS controls, **VSD** and endless RANGE behavior. It uses the shared 3M faceplate design and the same active-backlight policy, with zero on normal shutdown.

**Remaining work:** BB52-specific live confirmation of the latest backlight change and aircraft routes. The owner's current 3M confirmation should not be treated as a separate BB52 hardware test.

### WINCTRL 3N PDC — BB62

**Purpose:** Boeing EFIS controls, catalogue key `pdc_bb62`.

**Achieved:** Captured buttons include FPV, MTRS, WXR, STA, WPT, ARPT, DATA, POS and TERR, plus navigation selectors, minimums, BARO, TFC and mode/range controls. The faceplate shares the requested 3M design language while retaining the **bounded 5–640 range scale**. **VSD belongs on the 3M, not this 3N.** Physical input observation and startup baselines are retained.

**Remaining work:** Some physical source positions, including the displayed 640 range position, still need capture/learning confirmation. A drawn position is not proof that its source was captured. This 3N retains normal requested-brightness behavior rather than the 3M always-on exception.

### WINCTRL 3N PDC — BB61 compatibility variant

**Purpose:** An older 3N variant supported by the compatibility entry `pdc_bb61_left`, alongside the separately identified BB51 3M.

**Achieved:** Its existing capture-based mapping remains separate from BB51. The 3M remap preserves the established BB61 path. It retains 3N bounded-range/no-VSD behavior.

**Remaining work:** More live testing on this exact variant. The legacy key is not an instruction to rename it as 3M or apply BB51 contacts to it.

### WINCTRL 32 FCU with left/right EFIS

**Purpose:** Airbus flight-control and EFIS panel, `fcu_32_efis`, USB `4098:BA01`.

**Achieved:** Integrated FCU and both EFIS sides, including speed, heading, altitude and vertical-speed rotary/push/pull controls, autopilot buttons, BARO, display filters and associated selectors. Zibo and ToLiss routes, numeric windows, backlighting and integral lamps are implemented. The decoder accounts for longer native reports while using only confirmed control bytes.

**Remaining work:** Continue testing both sides and aircraft-specific output behavior. Unnamed raw bits in the catalogue are discovery placeholders, not hundreds of proven physical functions or broken buttons.

### WINCTRL 3N PAP3 MAG / MCP

**Purpose:** Boeing autopilot mode-control panel, `pap3_mag`, USB `4098:BF0F`.

**Achieved:** Course, speed, heading, altitude and vertical-speed controls; flight directors; bank-angle selector; autopilot/autothrottle mode buttons and switches. Implemented outputs include six native numeric windows, annunciators, backlighting and captured binary magnetic A/T ARM arm/release control.

**Remaining work:** Aircraft-by-aircraft validation. The numeric windows are not arbitrary text screens, and the solenoid protocol does not expose invented strength or travel calibration. Routine Practice lighting must not fire solenoids.

### WINCTRL 32 AGP Metal

**Purpose:** Gear, autobrake, clock and related systems panel, `agp_bb80`, USB `4098:BB80`.

**Achieved:** Gear positions, autobrake selections, brake fan, anti-skid/nosewheel steering, TERR and clock controls are represented. CHR/UTC/ET windows and selector functions have dedicated integration. ToLiss includes the clock and TERR-hold RADIO/CTRL behavior. Its instructions and quick-reference guide are intentionally preserved.

**Remaining work:** More LevelUp and ToLiss cockpit checks, including radio/clock states and power transitions. This panel keeps its own output ownership.

### WINCTRL 32 ECAM

**Purpose:** Airbus ECAM page and alert-control panel, `ecam32`, USB `4098:BB70`.

**Achieved:** Captured 12-byte input handling, a native A320 faceplate and learned physical button names. Existing assignments remain intact with optional source reassignment. The captured wake/keepalive, two yellow backlight zones and verified indicator channels are implemented. A bound ECAM page button can request the corresponding ToLiss systems page on both BB35 and BB36 displays.

**Remaining work:** Any unnamed contact must be physically learned before receiving an Airbus function. Unverified light channels remain unclaimed. Preserve the established ECAM mapping and its shared display-page requests.

### WINCTRL URSA MINOR throttle

**Purpose:** Two-engine throttle and associated systems controls, `winctrl_throttle`, USB `4098:B930`.

**Achieved:** Live thrust-lever, speedbrake and flap feedback; engine masters/mode, disconnect buttons, parking brake, trim and flap-detent handling. Below-idle reverse calibration and aircraft-specific ToLiss A320/A321 calibration have been developed. ToLiss distinguishes engine-mode detents from the trim-role push; Zibo/LevelUp preserve their stabilizer-trim rocker behavior. Captured output support includes lighting, trim-window behavior, engine FAULT/FIRE lamps and bounded vibration test channels.

The controller-reader fix restored feedback without requiring a connected PU overhead. **The owner confirmed that its throttle sliders move**, alongside the TCA sliders, after restarting Studio. Existing assignments and safe axis pickup remain protected.

**Remaining work:** Calibration across other physical units and aircraft, plus further LevelUp tweaks. Captured output/test channels do not imply every aircraft effect is automatically implemented.

### WINCTRL Orion rudder pedals

**Purpose:** Rudder and independent toe brakes, `winctrl_pedals`.

**Achieved:** Separate rudder, left-brake and right-brake axes, live values, calibration/inversion handling and simulator pickup. The shared reader now continues when the PU overhead is absent, covered by offline controller fixtures.

**Remaining work:** Additional live travel, centering and pickup checks on other units. Pedals do not own autobrake, parking brake, throttle or rudder trim.

## CDU and cockpit display panels

### WINCTRL 3N PFP / PFP3N

**Purpose:** Boeing-style keypad and 640 × 480 cockpit display, `pfp3n_bb35`, USB `4098:BB35`.

**Achieved:** Captured 71-key input map, FMC/CDU presentation and authored graphical cockpit pages. Zibo display work includes PFD, ND and engine/systems pages. ToLiss has CDU, PFD, ND and the authored ECAM systems deck, with Boeing key legends translated into Airbus MCDU actions. It can operate with BB36 absent.

Physical shortcuts are part of the design: **triple-tap `.` (index 38) toggles CDU/FMC and PFD; double-tap `/` (index 69) cycles pages**. Its display owner/router remains separate from BB36. Under ToLiss both keypads operate MCDU1, while their selected local display pages are independent.

**Remaining work:** The maintainer identifies slow LCD updates during climbs as the main PFP3N issue during otherwise smooth repeated flights. The exact-image USB-C experiment was too slow; transport/rendering profiling or refinement of the existing coded screens is needed. Native image extraction/plugin experiments and authored displays should not be confused with fully validated coverage of every simulator screen. Preserve keypad routing and gesture timing while fixing them.

### WINCTRL 32 MCDU Captain / MCDU32

**Purpose:** Airbus-style keypad and 640 × 480 cockpit display, `mcdu32_bb36`, USB `4098:BB36`.

**Achieved:** Captured 74-key map and coded FMC/CDU, PFD, ND and systems displays. Zibo uses a persistent graphics owner to avoid the previous unsafe graphics/character-mode handoff. ToLiss includes the authored ECAM deck and shared aircraft telemetry with independent panel ownership.

**Triple-tap `.` (index 41) toggles CDU/FMC and PFD; double-tap `/` (index 70) cycles pages.** On ToLiss the BB36 graphical loop returns to PFD, whereas BB35's cycle includes CDU. Single punctuation presses retain their keypad meaning after the gesture window.

**Remaining work:** The maintainer identifies slow LCD updates during climbs as the main MCDU32 issue during otherwise smooth repeated flights. Exact simulator imagery and coded screen rendering are the two approaches under consideration; refresh performance needs measurement. Reconnect, display ownership and page-switch regression testing remain important.

Developers should use the [exact page-switching guide](MCDU_PAGE_SWITCHING.md), including timing, page order and single-owner rules, before changing either panel.

### Recognized additional display identities

The product registry also identifies PFP co-pilot **BB3D** and observer **BB39**, and MCDU co-pilot **BB3E** and observer **BB3A** variants. These are family identities, not four additional fully validated captain-panel implementations. Observer input interfaces are read-only. Dedicated routing, ownership and physical acceptance need verification before advertising equivalent support.

## Thrustmaster

### Thrustmaster TCA Boeing Quadrant

**Purpose:** Physical throttle quadrant with selectable engine banks, `tca_boeing`, USB `044F:040A/040B`.

**Achieved:** Captured three lever axes, handle/reverse contacts, side buttons, three-position select knob and continuous directional encoder. Both **1 & 2** and **3 & 4** faceplate/bank views remain intact. The physical switch selects the USB identity at enumeration; this is one quadrant, not two connected devices.

Live sliders use physical travel rather than requiring simulator feedback. **The owner confirmed both this quadrant and the WINCTRL throttle move in Studio** after the shared-reader fix. Established bank 1 & 2 assignments remain; bank 3 & 4 is intentionally available for user mapping.

**Remaining work:** Additional user-defined bank 3 & 4 aircraft mappings and reconnect testing. Do not erase either bank or replace continuous encoder behavior with a bounded selector.

## HOWALT / MUSLIM panels

### MUSLIMRTP / HOWALT D201 RTP

**Purpose:** Radio tuning panel, `muslimrtp_d201`.

**Achieved:** Direct 115200-baud serial ownership without requiring MobiFlight Connector. Implemented radio selections, transfers, tests, panel-off input and tuning encoder controls; LEDs, backlighting, four radio displays and display brightness. Studio exposes mapping/output support.

**Remaining work:** Aircraft-specific radio behavior and replacement-unit checks. D201 and D203 share USB bridge identity `1A86:7523`; firmware model probing distinguishes them instead of treating every such serial adapter as a radio panel.

### MUSLIMATC / HOWALT D203 ATC

**Purpose:** Transponder/TCAS panel, `muslimatc_d203`.

**Achieved:** Direct serial integration, mode positions, transponder/altitude selections, IDENT and four squawk-digit encoders. Squawk display, brightness, backlighting and captured status lamps have implementation paths. Model recognition separates this panel from D201.

**Remaining work:** More aircraft-specific mode/status validation and portable serial discovery checks on other setups.

## PU Korea

### PU overhead

**Purpose:** Overhead systems switches, lamps and instruments, `pu_overhead`, USB `3561:8561`.

**Achieved:** Serial discovery/output with coordinated physical inputs for electrical, fuel, IRS, hydraulics, heating/anti-ice, signs, packs, wipers and other overhead functions. Aircraft-specific integration includes ToLiss counterparts, APU EGT/N/AVAIL presentation, GPU availability and guarded engine-start return. Startup maintained positions remain observation-only.

**Remaining work / physical limitation:** The panel goes dark on aircraft power loss while MuslimSim owns its output stream, but its firmware returns to physical brightness after writes stop. It cannot be left dark after shutdown using a proven permanent OFF command. Preserve this documented limitation and the guarded starter behavior. It is a **PU Korea device**, not a WINCTRL device.

## MOZA input and force feedback

### MOZA A210 / AY210 base and detachable yoke — inputs

**Purpose:** Yoke/base flight controls, `moza_a210`, USB `346E:1001`.

**Achieved:** Captured 34-byte input decoding for eight axes, a hat and 128 generic HID contacts; remappable inputs, calibration/visual feedback and X-Plane roll/pitch routing. The base remains one USB device when its yoke is removed or refitted. Unknown button legends remain numbered rather than guessed.

The lifecycle checker now accepts both A210 and AY210 names with the verified USB identity. **The owner confirmed the A210 stays visible** after the repeated pop-in/pop-out fix.

**Remaining work:** More labelled-control captures and firmware/aircraft validation. Descriptor contact capacity does not mean 128 separate physical buttons have all been exercised.

### MOZA AY210 — force-feedback output

**Purpose:** Optional motor-output service for the same base, `moza_a210_ffb`.

**Achieved:** Capture-based protocol work without dependence on the MOZA SDK. Spring, trim/centre offset, rumble and constant force are recorded as physically confirmed. Seven physics fields are supported: Spring, Damper, Inertia, Friction, Overall Intensity, Maximum Torque and Friction Compensation. Values may be static or follow live X-Plane dataref curves.

The service uses its own output collection and serial owner alongside the input reader. It is opt-in through `--moza-ffb`, and absent hardware is handled without starting motor output.

**Remaining work:** Substantial aircraft-specific tuning for both Zibo and ToLiss: the owner reports some working feedback, with decoded captures available, but the feel is not finished. This is a separate output service; older input-only notes saying no MOZA output exists predate this achievement.

### MOZA AB6 base — inputs

**Purpose:** Stick-base flight controls, `moza_ab6`, USB `346E:1002`.

**Achieved:** An actual AB6 descriptor capture proved its input layout matches the A210. Full-travel capture confirmed X, Y, Slider and Dial; the other four declared axes were observed idle and retained. The hat and 14 closing contacts were observed. Studio reads this base independently, with live stick, slider/dial and contact feedback.

**Remaining work:** Labelled grip and additional-contact captures. An A320/MSFS2024 calibration preset is reference data, not evidence of working MSFS24 simulator integration.

### MOZA AB6 — force-feedback output

**Purpose:** Optional output service for the same AB6 base, `moza_ab6_ffb`.

**Achieved:** AB6-specific connection capture established its serial path, enable latch, 227-frame setup and 61-frame polling sequence. A separate profile reuses the shared effect-report machinery for spring, trim, rumble and constant force. **Spring, Damper, Inertia and Friction** physics fields are confirmed. The service is opt-in with `--moza-ab6-ffb` and can coexist with input reading.

**Remaining work:** The owner reports some working MOZA feedback and decoded captures available, with substantial Zibo/ToLiss tuning still needed. Overall Intensity, Maximum Torque and Friction Compensation addresses are not byte-confirmed for AB6 and are deliberately refused. AY210's physical effect confirmations are not a substitute for AB6-specific acceptance. The captured disconnect behavior stops polling rather than inventing a HID teardown packet.

### MOZA MFY yoke and MAX3 grip views

**Achieved:** Accessory visuals sit under their physical bases rather than appearing as duplicate USB devices. MFY belongs to the A210/yoke presentation. On the maintainer's setup the **MAX3 grip reads the AB6**, with its observed trigger/top contacts, rather than incorrectly using A210 input.

**Remaining work:** More accessory-specific legends and captures across grip variants.

## Community profiles — groundwork awaiting complete integration

These six JSON profiles provide identities, control definitions and initial roles in the catalogue. The generic SDL driver has input-dispatch scaffolding; raw-HID community support is still a stub, and bridge event-dispatch integration is described as future work. **Do not read a profile's `implemented` control labels as proof of working end-to-end simulator control.** No community output is driven by this generic driver.

| Device and catalogue key | What has been added | Help still needed |
| --- | --- | --- |
| **Honeycomb Alpha / Alpha XL yoke** — `honeycomb_alpha` | Shared family profile with roll/pitch axes, hat and button definitions. | Wire and validate runtime dispatch, firmware identity, button numbering and aircraft mappings on physical units. |
| **Honeycomb Bravo throttle quadrant** — `honeycomb_bravo` | Six-axis and button profile with initial control roles. | Live integration, detent/reverser checks and aircraft setup; no claim of working annunciator output. |
| **Logitech / Saitek Pro Flight Multi Panel** — `logitech_saitek_multi_panel` | Autopilot buttons, selector/encoder, flap and autothrottle definitions. | Complete raw-HID reader and routing. LCD rows are explicitly unknown/undriven; output capture and a proven OFF state are still needed. |
| **Logitech X52 Pro / X52 family** — `logitech_x52_pro` | Axes, rotaries, slider, hat and button definitions, with family identity aliases. | Verify Pro/non-Pro differences, firmware layouts and complete live dispatch/mappings. |
| **Thrustmaster TCA Airbus sidestick / quadrant** — `thrustmaster_tca_airbus` | Separate sidestick/quadrant USB identities with roll, pitch, throttle, hat and button definitions. | Complete runtime integration and captures on the actual units. This is separate from the already captured TCA Boeing work. |
| **VIRPIL VPC Alpha / Alpha Prime / WarBRD-D family** — `virpil_vpc_alpha` | Axis, two-hat and button profile with known family identities. | Confirm firmware-specific product IDs, available twist axes, contact layout and end-to-end mappings. |

## What contributors can help finish

The immediate needs are **PFP3N/MCDU32 refresh profiling**, **ToLiss exact-image transport or coded-display refinement**, **Zibo screen design improvements**, **MOZA force-feedback tuning for Zibo and ToLiss**, **LevelUp compatibility tweaks**, **MSFS24 integration from the existing scaffolding**, and physical validation of community profiles. Include the exact hardware variant, simulator and aircraft when reporting a result, and distinguish input feedback, simulator commands and hardware outputs.

Preserve existing assignments, ECAM mappings, TCA faceplates/banks and the single bridge-owned input readers. Read [contribution terms](../CONTRIBUTING.md) before submitting reusable work and [project rules](../AGENTS.md) before changing code. The current aim is development help; any future paid product is intended as a one-time purchase, as stated in the [README](../README.md).

## Evidence and developer references

- [Hardware catalogue](../muslimsim/hardware/catalog.py) and [product registry](../muslimsim/hardware/product_registry.py): current control/service definitions and identities.
- [Device reference and live-test guide](../DEVICE_REFERENCE.md): capture details, aircraft routes and historical limitations. Dated older observations can be superseded by later entries and current code.
- [MCDU/PFP page switching](MCDU_PAGE_SWITCHING.md): exact keypad gestures and display ownership.
- [Community profiles](../community/devices) and [generic driver](../muslimsim/hardware/generic_hid.py): current groundwork and remaining runtime scope.
- [Regression suite](../tools/test_known_regressions.py), [changelog](../CHANGELOG.md) and [project history](../PROJECT_HISTORY.md): guards, recent fixes and validation records.

This documentation update does not change device code, saved profiles or mappings. No new live hardware test is implied by publication.
