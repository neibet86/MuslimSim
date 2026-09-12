# MuslimSim

MuslimSim is a Windows desktop application for connecting physical cockpit hardware to flight simulators. It brings device management, control assignments, live input feedback, cockpit displays, and hardware practice into one workspace.

## Project status and why this is public

MuslimSim is a work in progress. **Right now, the priority is getting help to make the software better, more reliable, and easier to use—not selling it.**

This repository is public so people can inspect the project, report problems, share hardware experience, suggest improvements, and discuss development work with the maintainer.

**If MuslimSim becomes a paid product in the future, the intended model is a one-time purchase, not a subscription.** There is no price or release date announced. Publishing the source is not a promise that every future version will be free, nor a promise of lifetime updates or support.

These plans are stated now so anyone considering helping can make an informed choice. Existing third-party license rights remain in place.

## Help improve MuslimSim

Help is especially welcome with:

- Testing supported hardware on different cockpit setups.
- Reproducing bugs and checking whether fixes hold across restarts and reconnects.
- Improving setup instructions and identifying confusing interface behavior.
- Reviewing performance, simulator compatibility, and device support.

[Open an issue](https://github.com/neibet86/MuslimSim/issues/new/choose) with your findings or proposed work. Include the simulator, aircraft, hardware model, and steps to reproduce a problem. Remove credentials, personal details, and device serial numbers from logs before sharing them.

**Before submitting code or other reusable contributions, read [CONTRIBUTING.md](CONTRIBUTING.md) and discuss the terms with the maintainer.** The project is not asking people to contribute under an unstated assumption that it will remain free forever.

## Source visibility and licensing

The source is public for transparency and collaboration discussions. A general open-source license has not been granted for otherwise unlicensed MuslimSim-authored material. See [LICENSING.md](LICENSING.md) for the current position and the included components that already have their own licenses.

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
