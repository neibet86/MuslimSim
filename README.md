# MuslimSim

MuslimSim is a Windows desktop application for connecting physical cockpit hardware to flight simulators. It brings device management, control assignments, live input feedback, cockpit displays, and hardware practice into one workspace.

## What you can do

- **Manage your cockpit:** view connected supported devices and their status, with device-specific faceplates and controls.
- **Assign controls:** connect hardware inputs to simulator functions, keep existing assignments, and reassign controls when needed.
- **See physical input live:** watch buttons, switches, rotary controls, throttles, and pedals respond, including when the simulator is disconnected.
- **Practise and test:** explore supported hardware in Practice mode without changing saved simulator assignments.
- **Use cockpit displays and lighting:** drive supported instruments, display panels, indicators, and backlights from available simulator data.
- **Diagnose hardware:** use calibration, capture, and diagnostic tools to investigate device behavior.

## Simulator and hardware support

The project includes X-Plane integration and a dedicated Microsoft Flight Simulator 2024 bridge. Available functions and display coverage depend on the simulator, aircraft, and device implementation.

Hardware support spans flight controls, throttles, rudder pedals, overhead and systems panels, flight-control panels, and cockpit displays. The project includes integrations for WINCTRL, Thrustmaster TCA, HOWALT, and other supported equipment.

See the [device reference](DEVICE_REFERENCE.md) for supported models, verified controls, and device-specific limitations.

## Getting started

This repository contains the project source. Running it requires Windows and the configured MuslimSim Python environment; the Studio launcher currently expects Python 3.11 under the user's local Python installation.

1. Connect your supported cockpit hardware.
2. Open `MuslimSim Studio.pyw` from the project folder.
3. Use Studio to review connected devices and control assignments.
4. Use Practice mode to check hardware feedback, or connect to your simulator for Live operation.

Studio manages the hardware bridge. Run one bridge at a time so hardware readers do not compete for the same device.

## Project layout

| Folder | Contents |
| --- | --- |
| `muslimsim/` | Studio, device support, hardware discovery, profiles, and control services |
| `bridge/` | Simulator integration and hardware communication |
| `assets/` and `PNG/` | Display and interface resources |
| `tools/` | Offline checks, calibration, captures, and diagnostics |
| `docs/` | Detailed integration and development documentation |

## Documentation

- [Device reference](DEVICE_REFERENCE.md)
- [System architecture](SYSTEM_ARCHITECTURE.md)
- [Control panel guide](CONTROL_PANEL.md)
- [Project history](PROJECT_HISTORY.md)
- [Changelog](CHANGELOG.md)

## Development

Read [AGENTS.md](AGENTS.md) before making changes. It describes the project's preservation rules, hardware ownership, backup requirements, and validation workflow.

Run the offline regression suite from the project folder using the configured Python environment:

```powershell
python -B tools/test_known_regressions.py
```

Offline checks complement live hardware and simulator testing. Third-party components retain their own licenses and attribution.

Local backups, raw diagnostic recordings, generated builds, and credentials are excluded from this repository. User profiles are stored in the local application settings folder.
