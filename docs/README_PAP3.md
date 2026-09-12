# MuslimSim — WinCtrl PAP3 Boeing 737 MCP Integration

This package adds the **WINCTRL 3N PAP MCP / PAP3** to the existing unified
MuslimSim bridge without replacing or remapping any working PU Overhead,
WinCtrl throttle, PFD, MCDU, AGP, or pedal logic.

## Hardware and simulator target

| Item | Value |
|---|---|
| Device | WINCTRL 3N PAP MCP / PAP3 |
| USB VID | `4098` / `0x4098` |
| USB PID | `BF0F` / `0xBF0F` |
| Aircraft mapping | Zibo 737 and MuslimSim B738-compatible profile |
| X-Plane transport | Web API at `127.0.0.1:8086` |
| Default A/T switch | Magnetic, solenoid-held |

## What is included

The integrated PAP3 manager handles both directions:

- All MCP pushbuttons: N1, SPEED, VNAV, LVL CHG, HDG SEL, LNAV, VOR LOC,
  APP, ALT HLD, V/S, CMD A/B, CWS A/B, C/O, SPD INTV, and ALT INTV.
- All six rotary controls: captain course, speed, heading, altitude, vertical
  speed, and first-officer course.
- Captain and first-officer flight-director switches.
- Five-position 10/15/20/25/30-degree bank-angle selector.
- Autopilot-disconnect bar.
- Magnetic or standard spring-return A/T ARM switch.
- Six native seven-segment windows: captain course, IAS/Mach, heading,
  altitude, vertical speed, and first-officer course.
- MCP mode annunciators, master annunciators, panel backlight, LCD backlight,
  overall LED brightness, display-test behavior, and the magnetic A/T
  solenoid.
- Automatic USB detection, disconnect recovery, X-Plane WebSocket recovery,
  dirty-only output, and clean blackout on shutdown. If X-Plane transport
  drops, the LCD, annunciators, and A/T solenoid are cleared instead of
  showing stale simulator state.

PAP3 remains one module inside the **same MuslimSim process**. It is not a
second permanent bridge.

## Install into `D:\MuslimSim`

1. Extract this package.
2. Close the running MuslimSim bridge and any other program currently owning
   the PAP3 HID device.
3. Open PowerShell in the extracted folder.
4. Run:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\install_pap3.ps1
```

The installer defaults to:

```text
Root:       D:\MuslimSim
Bridge:     D:\MuslimSim\bridge\final.py
A/T type:   magnetic
```

It also recognizes `D:\MuslimSim\final.py`. To patch a different active file:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\install_pap3.ps1 `
  -BridgeFile "D:\MuslimSim\bridge\final(8).py"
```

For a standard momentary/spring-return A/T switch:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\install_pap3.ps1 `
  -ATSwitchType standard
```

The installer:

1. Runs all **17 offline PAP3 protocol, manager, and patcher tests**.
2. Copies `pap3_mcp.py` into `D:\MuslimSim\muslimsim\devices`.
3. Copies the read-only probe into `D:\MuslimSim\tools`.
4. Adds guarded import, arguments, startup, and shutdown blocks to the active
   bridge.
5. Compiles the module and patched bridge before replacing the original.
6. Creates a timestamped backup beside the bridge:
   `final.py.before-pap3-YYYYMMDD-HHMMSS.bak`.

Re-running the installer is safe. The bridge patch is marker-based and
idempotent.

PAP3 uses the same Python HID/WebSocket libraries already expected by the
current MuslimSim hardware modules. If startup reports a missing dependency,
install only the missing package:

```powershell
py -m pip install hidapi websocket-client
```

## Start MuslimSim

PAP3 starts automatically when the selected aircraft profile is Zibo or
B738-compatible:

```powershell
py "D:\MuslimSim\bridge\final.py"
```

The first diagnostic run should use:

```powershell
py "D:\MuslimSim\bridge\final.py" --diagnose-pap3
```

Expected startup messages include:

```text
PAP3 MCP manager enabled: ...
PAP3 MCP CONNECTED: WINCTRL 4098:BF0F, ...
PAP3 X-Plane WebSocket CONNECTED: ...
```

The bridge can start before the panel is plugged in. It will display:

```text
PAP3 MCP: waiting for WINCTRL 3N PAP MCP (4098:BF0F).
```

and connect automatically when the panel appears.

## Startup safety

The first valid PAP3 input report is captured only as a **baseline**. MuslimSim
does not move the simulator's flight directors, A/T switch, AP disconnect bar,
or bank-angle selector at startup.

After the baseline, only a real physical movement is sent. Events that happen
while X-Plane's WebSocket is disconnected are discarded rather than replayed
later. Maintained switches compare against the latest simulator state and use a
toggle command only when the simulator differs from the requested physical
position.

## A/T switch modes

### Magnetic — default

```powershell
py "D:\MuslimSim\bridge\final.py" --pap3-at-switch magnetic
```

- ARMED physical line requests Zibo A/T ARM ON.
- DISARMED physical line requests Zibo A/T ARM OFF.
- The PAP3 solenoid follows Zibo's actual A/T ARM state.

### Standard spring-return

```powershell
py "D:\MuslimSim\bridge\final.py" --pap3-at-switch standard
```

- Each ARMED rising edge toggles Zibo A/T ARM.
- The spring-back/DISARMED line is ignored so it cannot immediately undo the
  command.
- The magnetic solenoid output stays off.

## Read-only hardware probe

The probe never sends an output report and never talks to X-Plane. Close the
bridge first, then run:

```powershell
py "D:\MuslimSim\tools\winctrl_pap3_probe.py"
```

To include raw reports:

```powershell
py "D:\MuslimSim\tools\winctrl_pap3_probe.py" --raw
```

The confirmed PAP3 hardware indices are:

| Index | Function |
|---:|---|
| 0–16 | MCP pushbuttons through ALT INTV |
| 17/18 | Captain course decrease/increase |
| 19/20 | Speed decrease/increase |
| 21/22 | Heading decrease/increase |
| 23/24 | Altitude decrease/increase |
| 25/26 | First-officer course decrease/increase |
| 27 | FD captain |
| 29 | FD first officer |
| 31/32 | AP disconnect down/up lines |
| 33–37 | Bank-angle 10/15/20/25/30 |
| 38/39 | Vertical speed decrease/increase |
| 40/41 | A/T armed/disarmed lines |

## First functional test

Use a cold-and-dark or parked Zibo aircraft:

1. Start X-Plane and load the Zibo 737 completely.
2. Confirm X-Plane's Web API is running on port `8086`.
3. Start MuslimSim with `--diagnose-pap3`.
4. Turn avionics and the main electrical bus on.
5. Verify captain course, speed, heading, altitude, V/S, and FO course match
   the virtual MCP.
6. Turn the MCP panel-light control and confirm PAP3 backlight follows it.
7. Press each mode button and verify both Zibo and the matching PAP3
   annunciator.
8. Rotate each encoder one slow detent in each direction.
9. Move both FD switches, the bank-angle selector, AP disconnect bar, and A/T
   switch.
10. Use Zibo's display-test control and verify all PAP3 segments and
    annunciators illuminate.

## Troubleshooting

### PAP3 keeps saying “waiting”

Run the read-only probe. If it also cannot find `4098:BF0F`, verify the USB
connection in Windows Device Manager and close any application that has the
panel open.

### Required Zibo DataRefs are unavailable

The PAP3 manager intentionally waits rather than guessing. Load the Zibo 737
fully and verify the same X-Plane Web API used by the existing MuslimSim bridge
is reachable at `http://127.0.0.1:8086`.

### Buttons work but displays are dark

Check Zibo avionics power, main-bus power, MCP panel brightness, and display
test. The integration follows those simulator values rather than forcing
brightness on.

### Duplicate turns or double button presses

Only one driver may control the PAP3. Do not run another PAP3 X-Plane plugin,
SimAppPro PAP3 binding, or a second PAP3 Python script at the same time as
MuslimSim.

### Restore the bridge

The installer includes:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\restore_before_pap3.ps1
```

For a non-default active bridge such as `final(8).py`, specify it explicitly:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\restore_before_pap3.ps1 `
  -BridgeFile "D:\MuslimSim\bridge\final(8).py"
```

It restores the newest `before-pap3` bridge backup and saves the currently
patched file as another timestamped backup.

## Added bridge arguments

```text
--no-pap3
--pap3-refresh 0.04
--pap3-at-switch magnetic|standard
--diagnose-pap3
```

`--no-winctrl` also disables PAP3 because it remains part of MuslimSim's
WinCtrl device family.

## Package validation and live-test boundary

The included Python module, HID/LCD packet builders, manager behavior, and
marker-based bridge patcher pass 17 offline tests. Those tests cover input-bit
decoding, native LCD transactions, IAS/Mach rendering, LED packets, command
phases, maintained switches, bank-angle stepping, disconnected-output blanking,
UTF-8 BOM/CRLF preservation, backup creation, dry-run behavior, and repeated
installation.

This build environment cannot open the user's physical Windows USB device or
write directly to `D:\MuslimSim`. The installer therefore performs the same
compile/tests again on the user's PC before modifying the active bridge. The
first physical verification should be performed parked with
`--diagnose-pap3`, following the checklist above.

## Files in this package

```text
install_pap3.cmd                 double-click/Command Prompt wrapper
install_pap3.ps1                 Windows installer
restore_before_pap3.ps1          bridge-backup restore helper
muslimsim/devices/pap3_mcp.py   integrated PAP3 manager
tools/winctrl_pap3_probe.py      read-only hardware input probe
tools/patch_muslimsim_pap3.py    tested, idempotent bridge patcher
tests/                           17 offline tests
requirements-pap3.txt            optional dependency list
THIRD_PARTY_NOTICES.md           protocol-source and license notice
```
