# Current A321 native instrument regions — measured September 10, 2026

Atlas:4096x4096. Evidence preserved in
`Backup/ecam_fullscreen_pages_20260910_195125/verified_native_atlas.png`.
These replace obsolete upstream2048 coordinates. Bounds are half-open PNG
top-left coordinates. Conversion: GL bottom =4096-PNG bottom.

| Region | PNG bounds | GL x,y,width,height | Verification |
|---|---|---|---|
| Upper-left PFD |6,512,756,1262|6,2834,750,750|Pixel boundaries measured; captain adjacency inferred from matching ND row; cockpit-side verification pending|
| Upper-left ND |764,512,1514,1262|764,2834,750,750|Pixel boundaries; displayed range agrees with NDrangeCapt4 (FO2 differs)|
| Lower-left PFD |6,1269,756,2019|6,2077,750,750|Pixel boundaries measured; side verification pending|
| Lower-left ND |764,1269,1514,2019|764,2077,750,750|Pixel boundaries; different range consistent with FO|
| EWD |1521,1050,2141,1670|1521,2426,620,620|Native engine/warning image inspected|
| SD |2151,1050,2771,1670|2151,2426,620,620|BLEED native image physically confirmed on both LCDs|

Live page-command probes: SelectEnginePage0, SelectBleedPage1, SelectPressPage2,
SelectElecACPage3, SelectHydraulicPage4, SelectFuelPage5, SelectAPUPage6,
SelectConditioningPage7, SelectDoorOxyPage8, SelectWheelPage9,
SelectFlightControlPage10, SelectStatusPage12. Restored BLEED afterwards.
No other aircraft system controls changed. Automatic CRUISE has no verified
selection command in the live catalogue; do not infer its ID from the gap.

Current plugin streams SD only, max2Hz. PFD/ND/EWD regions are research results,
not enabled output. The current native PFD/ND show ATT/HDG-invalid and MAP NOT
AVAIL. A valid moving PFD, capture stall timings, USB throughput and latency
are required before replacing the existing working numerical PFD/ND renderer.
CDU native-text path remains working and unchanged. No guessed coordinates or
unverified slow raster path should be described as a completed PFD conversion.
