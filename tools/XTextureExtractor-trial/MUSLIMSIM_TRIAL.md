# Isolated ECAM texture feasibility trial

Upstream: https://github.com/waynepiekarski/XTextureExtractor
Commit: 9cba63f4c2243d86d877fee85cffd5cec3e0c0a8, GPL-3.0.

Build `XTextureExtractor.cpp` and `lodepng/lodepng.cpp` with
`MUSLIMSIM_LOCAL_TRIAL`, XPLM200/210/300/301 and IBM=1. Link OpenGL32,
XPLM_64 and XPWidgets_64. Do not compile the networking source for this trial.
The macro excludes network startup and continuous image readback. Original
upstream sources are available in git; pre-edit source also backed up under
`D:/MuslimSim/Backup/ecam_trial_20260910_170802/`.

Power gate: bounded 16-element AC-bus read. Missing/invalid/off supply blacks
the trial window before its content/buttons. No hardware outputs or aircraft
commands are added. Native instrument imagery owns individual DU brightness
and self-test appearance. Battery-only supply may correctly leave DUs dark.

Installed September 10 after verifying X-Plane closed, in
`Resources/plugins/MuslimSimECAMTextureTrial/`. Installed SHA256:
`0F593866E3FF6E0A899CEE431FFB774B5D3C7EC5F5DF3FE0E67E1493344B853F`.
Live acceptance pending. Reinstallation instructions: only install when
X-Plane has closed. Copy the trial binary
as `64/win.xpl` into a NEW plugin folder with COPYING, LICENSE and README.
Use `muslimsim-trial-a321.tex` as `a321.acf.tex`. Its full 4096-square atlas
is for measuring regions, not a guessed ECAM crop. The plugin's one-time
snapshot saves the actual rendered texture. Do not use old 2048 coordinates.

Acceptance: same aircraft/view/settings before and after; compare frame time,
check power-off black, identify true EWD/SD crops, compare BLEED while APU off
and supplying air, then all 12 pages. No claim of BB35/BB36 raster support or
numeric telemetry until separately tested. Only the selected native SD page
is expected in its texture. Remove the isolated plugin folder after closing
X-Plane to roll back. Do not hot-delete a loaded DLL.
