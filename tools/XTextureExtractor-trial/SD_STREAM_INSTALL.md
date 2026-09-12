# Staged BLEED LCD stream — September 10, 2026

Installed September 10 at 18:46 after verifying both applications closed.
Installed checksum matches the artifact below. Backup of previous DLL/config:
`D:/MuslimSim/Backup/ecam_stream_install_20260910_184651/`.
Live acceptance remains pending. The following installation procedure is
retained for future reinstallation, not a statement that deployment is pending.

Built artifact: `win-sd-stream.xpl`

SHA256: `AD5C3412D25DD90FE9B5C75C36C5B69578912C4133B7121C5FBB191ED62C7F55`

Dependencies: OPENGL32.dll, XPLM_64.dll, KERNEL32.dll. No sockets/network module.
New source `muslimsim_sd_stream.h` shares the containing plugin's GPL-3.0 license.

Reinstallation: do not replace a loaded DLL. When Studio and X-Plane
are CLOSED, back up the installed isolated trial's `64/win.xpl`, then replace
only that DLL with this staged artifact. Keep its measured `a321.acf.tex` and
licenses. Do not edit other plugins or use the global XTE/plugin reload command.

Start X-Plane, then Studio; select BLEED on the native SD and both LCDs. Keep
one extractor window visible. Confirm local shared mapping
`Local\MuslimSim.ToLiss.SD.v1` has valid version 1, even sequence, page 1,
620x620 dimensions and advancing uptime timestamps. First page change incurs
one capture interval of settling. Inspect `capture_us` and simulator frame
time; GL readback on Vulkan has NOT yet been acceptance-tested in this build.

The LCD adapter uses existing native colour/fill/refresh only; no new USB
commands. BLEED alone is enabled, at 448x448 with no palette reduction. Full
image can take seconds. Unknown/stale source falls back to numeric BLEED and
may show XX; disconnected/unpowered DU blacks through the original bridge
gate. Tests: exact pixel/decode/delta/report-framing, display regression,
71-key BB35/BB36-default isolation and mandatory known regressions passed.

Rollback while both apps are closed: restore the backed-up plugin DLL. With
no producer, the bridge automatically retains its old numeric rendering.
