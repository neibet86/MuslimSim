# MuslimSim Hardware Laboratory

The Hardware Laboratory is a simulator-independent configuration and test layer. The panel starts the bridge as a child process and communicates over its authenticated loopback JSON-lines control channel. The UI never opens COM, HID, SDL, or X-Plane connections itself.

Start the panel with:

```powershell
& "C:\Users\noureddine aidoudi\AppData\Local\Programs\Python\Python311\python.exe" -B .\muslimsim_panel.py
```

Use `--check` or `launch.py --test-hardware-lab` for a no-hardware check.

## Portable product identity

The Hardware Lab profile key is the supported MuslimSim product key. Runtime
locators such as COM number, HID path and SDL instance are not stored as the
identity of the device. The shared `hardware/product_registry.py` and
`hardware/device_manager.py` resolve those locators at runtime, so a replacement
unit of the same supported product inherits the existing mappings. Serial
numbers are diagnostic information only.

## Catalogue policy

The catalogue is generated from current bridge/device descriptors. It contains the connected WINCTRL 32 FCU + 32 EFIS L/R (`4098:BA01`), WINCTRL 3N PDC / Airbus EFIS BB62 (`4098:BB62`), PAP3 MAG / MCP (`4098:BF0F`), PU Overhead, WinCtrl throttle, pedals, AGP BB80, PFP3N BB35, MCDU32 BB36, and ECAM32 (`4098:BB70`).

The new FCU/EFIS unit reports a verified 64-byte HID input frame, but no published control-bit table was present in this codebase. MuslimSim Studio shows its visual faceplate and uses **Learn physical control** to bind the exact pressed raw input to a visible knob/button. Only then can it be mapped to a Zibo action; no Airbus/Boeing default is guessed.

BB62 has its capture-verified 37 controls and every remaining descriptor bit is labelled unknown. PAP3 has its captured input bits, six numeric windows, lamps, backlight, and binary A/T solenoid. PFP/MCDU key maps are not guessed; their driver-owned inputs stay explicitly unknown. ECAM32 learns its BB70 12-byte key contacts before they receive a face-button name. Its capture-proven host keepalive wakes the panel, and its recorded lamp addresses `04` through `11` are available for safe test output; any unrecorded lamp address remains blocked.

## Profiles and remapping

Profiles are saved atomically in `%APPDATA%\MuslimSim\hardware_profiles.json` unless a caller passes `--lab-profile`. Create or switch named profiles from the panel toolbar; a new profile copies the current per-device mappings and the one verified PU timing setting. Each verified input may be assigned to a simulator command, writable dataref, or the registered local action `lab:reset-device`. Unsupported or unprobed controls cannot be saved as mappings.

BB62 and PAP3 custom mappings route live post-baseline physical edges through the existing bridge command/dataref helpers. The bridge retains its established default whenever a control has no custom mapping. Verified PU command pulses, brightness, engine-start selectors, and discrete throttle controls are also recorded live; a custom single-control mapping can replace that legacy event without changing other devices.

## Test mode and outputs

Test mode makes virtual controls update live panel state without default simulator writes. The BB62's independent HID reader also starts while the bridge is waiting for X-Plane, so its post-baseline physical controls are visible and safely remappable in the laboratory before a simulator connection. PAP3's confirmed controls join the same live panel once its normal manager is active. Virtual screens accept all-on, all-off, checker/pattern, text, and value states even when no hardware is connected.

The bridge mirrors a test state to physical hardware only where it has a confirmed driver entry point. PAP3 can receive all-segment/blank LCD patterns, annunciator tests, backlight tests, and its binary A/T solenoid test. ECAM32 can receive only its captured wake keepalive and the recorded individual/all-lamp test packets. PDC output selector meanings and arbitrary BB35/BB36 display injection remain blocked because this checkout has no verified runtime API for them.

PU actuator configuration is intentionally limited to its documented timed P1 engine-start return pulse (`50–1000 ms`). There is no driver protocol for motor force, endpoint calibration, direction, or arbitrary solenoid strength, so those controls are not invented. PAP3's A/T solenoid is binary only.

## Reset and power cycle

`Restart device` uses the registered manager's normal `stop()` then `start()` path when a device owns one. `Power cycle` targets only a known `USB\VID...` parent, requires Administrator rights, and verifies that the device leaves then returns to the bus. It refuses to report success if Windows does not actually re-enumerate the device.

## Control channel

The bridge starts its channel before the X-Plane wait and prints:

```text
CONTROL CHANNEL PORT 50366
CONTROL CHANNEL TOKEN <per-run-token>
```

It accepts `ping`, `status`, `catalog`, per-device lifecycle calls, `lab_input`, `lab_output`, output tests, mappings, calibrations, self-test, and graceful shutdown. It binds only to `127.0.0.1`; every request must carry the per-run token.

## Portable identity and Hardware Lab profiles

Hardware Lab mappings remain keyed by the stable MuslimSim device key. Phase 2
makes HID paths and SDL indices/instance IDs/GUIDs explicit runtime locators,
so replacing a supported unit of the same model does not require a new mapping
profile. Explicit user mappings still outrank native defaults exactly as before.
