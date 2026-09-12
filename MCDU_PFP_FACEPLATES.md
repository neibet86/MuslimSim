# MuslimSim authored MCDU32 / PFP3N faceplates

Added from the owner's 2026-09-02 front-face photographs.

## WINCTRL 32 MCDU CAPTAIN — BB36

Studio now draws the physical Airbus-style face:
- large live LCD and 6 left + 6 right line-select keys;
- DIR / PROG / PERF / INIT / DATA and blank top-right key;
- F-PLN / RAD NAV / FUEL PRED / SEC F-PLN / ATC COMM / MCDU MENU;
- BRT and DIM;
- AIR PORT, blank lower key and four arrow keys;
- round numeric keypad;
- A-Z matrix, slash, SP, physical OVEY/triangle legend and CLR;
- white compass-style outlines on E/N/S/W.

Every control remains the already-captured BB36 `key_N`. The physical OVEY
legend therefore still uses key_72's existing proven simulator role; the
faceplate does not rewrite the hardware mapping.

## WINCTRL 3N PFP CAPTAIN — BB35

Studio now draws the physical Boeing-style face:
- large live display and 12 side LSKs;
- INIT REF / RTE / CLB / CRZ / DES;
- split BRT -/+ rocker;
- MENU / LEGS / DEP ARR / HOLD / PROG / EXEC;
- N1 LIMIT / FIX / PREV PAGE / NEXT PAGE;
- round numeric keypad;
- A-Z matrix, SP / DEL / slash / CLR;
- white compass-style outlines on E/N/S/W.

Every control remains the existing BB35 `key_N`.

## Ownership / safety

This capability changes Studio presentation only. It does not change:
- BB35 or BB36 HID opening;
- display ownership;
- FMC/PFD routing;
- Zibo commands;
- HardwareLab binding precedence;
- power/shutdown authority.

If an authored renderer raises an exception, Studio falls back to the previous
generic `_draw_fmc_keypad` surface.
