# MuslimSim PAP3 / BB35 PFD-PFP repair

Repair version: **2026.08.27.2**

Target installation:

```text
D:\MuslimSim
```

This package repairs the display corruption that appeared after the WinCtrl
PAP3 was added to the same MuslimSim process:

- black speckles or rectangular holes on the graphical BB35 PFD;
- white speckles remaining over the BB35 PFP/FMC page;
- triple-period switching from PFP/FMC back to PFD leaving BB35 black;
- PAP3 output bursts occurring while BB35 is uploading a font, clearing a
  plane, or committing a graphical frame.

## Confirmed black-return failure

The current MuslimSim graphical display worker has a ninth required argument,
`display_page_getter`.  The installed BB35 separate-path router still launches
it with the older eight-argument call.  On a PFP/FMC -> PFD handoff the new
thread can therefore stop immediately, leaving a valid but black BB35 session.

The repair detects the worker signature at runtime:

- old eight-argument worker: receives the original eight arguments;
- current nine-argument worker: additionally receives a callback returning
  `"pfd"`.

No PFD drawing code, telemetry interpolation, X-Plane dataref, or page layout is
replaced.

## Persistent display-plane cleanup

BB35 keeps two independent display planes in firmware:

- native graphical **F0** commands used by the PFD;
- character-grid **F2** reports used by the PFP/FMC.

Closing and reopening the HID handle does not guarantee those planes are
cleared.  The repaired handoff performs this sequence while the screen is dark:

1. hide the persistent F2 grid at off-screen coordinates;
2. repaint the complete 640x480 F0 plane twice with the established MuslimSim
   background colour;
3. initialize only the incoming mode;
4. restore LCD brightness after initialization is complete.

Leaving PFP/FMC also blanks its full F2 page before hiding the grid.  Leaving
PFD clears the F0 plane before closing its handle.

## PAP3 output isolation

The updated PAP3 module and repaired BB35 router share one small, process-wide
WinCtrl output arbiter.  Input reads remain independent.  Only HID writes are
serialized, and each multi-report transaction stays together:

- one complete BB35 F0 graphical frame;
- one complete BB35 F2 page;
- BB35 font and mode-entry bursts;
- one complete four-report PAP3 LCD transaction.

PAP3 also waits three seconds before its first output, uses a 0.12-second
minimum dirty LCD interval, and replaces the old large initialization blackout
with a compact nine-report sequence.  The PAP3 buttons, encoders, displays,
annunciators and A/T solenoid remain enabled.

## Install

Close the running MuslimSim bridge and any application controlling the WinCtrl
panels.  Extract this ZIP, then double-click:

```text
repair_pap3_pfd_pfp.cmd
```

Or run from PowerShell:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\repair_pap3_pfd_pfp.ps1
```

The default root is `D:\MuslimSim`.  The installer searches for the newest
`final*.py` that already contains the MuslimSim PAP3 startup marker, so it can
find an active file such as `bridge\final(8).py` instead of blindly choosing an
older `final.py`.

To name the active bridge explicitly:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\repair_pap3_pfd_pfp.ps1 `
  -Root "D:\MuslimSim" `
  -BridgeFile "D:\MuslimSim\bridge\final(8).py"
```

For a standard spring-return PAP3 A/T switch:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\repair_pap3_pfd_pfp.ps1 `
  -ATSwitchType standard
```

A validation-only run makes no changes:

```powershell
py .\tools\repair_muslimsim_pap3_pfd_pfp.py `
  --root "D:\MuslimSim" `
  --dry-run
```

## Installer safety

Before changing the installation, the repair:

1. compiles every repair module and patcher;
2. runs the full 26-test offline suite;
3. dry-runs the PAP3 bridge transformation against the selected active bridge;
4. dry-runs the BB35 transformation against the installed router;
5. creates a transactional backup under:

```text
D:\MuslimSim\backups\pap3-pfd-pfp-repair-YYYYMMDD-HHMMSS
```

If any copy, patch or final compilation fails, every touched file is restored
automatically.  Marker-based patches are idempotent, so running the repair
again updates the existing repair block rather than duplicating it.

## First hardware test

Restart the bridge with PAP3 diagnostics:

```powershell
py "D:\MuslimSim\bridge\final(8).py" --diagnose-pap3 --diagnose-pfp-fmc
```

Use the exact active bridge path printed by the installer.

Test in this order:

1. Let the graphical PFD run for at least 30 seconds.  It should contain no
   unexplained black holes.
2. Press the physical PERIOD (`.`) key three times.  PFP/FMC should initialize
   on a clean character page without white debris from the PFD.
3. Press PERIOD three times again.  The log should show a clean handoff back to
   PFD, and the PFD worker should stay alive.
4. Repeat the round trip at least three times.
5. During the test, rotate PAP3 speed, heading and altitude encoders and verify
   that PAP3 remains responsive.

Expected repaired messages include:

```text
BB35 PATH -> PFD (clean F0; F2 hidden; v46 page-selector compatible; PERIOD x3 for PFP/FMC)
BB35 PATH -> PFP/FMC (F0 cleared; clean F2 page; PERIOD x3 for PFD)
BB35 HANDOFF: PFD -> FMC
BB35 HANDOFF: FMC -> PFD
```

If a display worker exits unexpectedly, the router now prints a warning and
performs a clean same-mode restart rather than leaving BB35 black indefinitely.

## Restore

To restore the newest pre-repair transaction:

```text
restore_pap3_pfd_pfp_repair.cmd
```

Or:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\restore_pap3_pfd_pfp_repair.ps1
```

The restore tool first saves the currently repaired files into a separate
`pre-restore-current-*` directory, then restores exactly the files listed in
the selected backup manifest.

## Files installed or updated

```text
D:\MuslimSim\muslimsim\devices\pap3_mcp.py
D:\MuslimSim\muslimsim\devices\winctrl_output_bus.py
D:\MuslimSim\muslimsim\devices\pfp_bb35_separate_paths.py   (marker patch only)
D:\MuslimSim\tools\patch_muslimsim_pap3.py
D:\MuslimSim\tools\patch_bb35_pfd_pfp_handoff.py
D:\MuslimSim\tools\winctrl_pap3_probe.py
D:\MuslimSim\docs\README_PAP3_PFD_PFP_REPAIR.md
```

The active bridge receives an updated PAP3 argument/startup block with the new
safe refresh and startup-delay defaults.  Its working PU Overhead, throttle,
AGP, pedals, BB35/BB36 setup and shutdown paths remain in place.
