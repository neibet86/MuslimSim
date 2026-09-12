"""Saved configuration for the control panel, and the command line it builds.

Two jobs:

  * remember what the user chose -- which devices are on, what each one's
    options are set to -- across sessions, in one readable JSON file they can
    inspect or delete;
  * turn those choices into the launcher's arguments, using the catalogue's
    own option definitions so a new device needs no code here at all.

Profiles exist because the useful configurations are few and switching
between them by hand is tedious: a full cockpit, displays only, and a
no-hardware dry run for testing against the sim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from ..hardware import catalog
from ..hardware.catalog import DeviceSpec, GLOBAL_OPTIONS, Option
from ..hardware.throttle import ThrottleCalibration

SETTINGS_VERSION = 1
SETTINGS_FILENAME = "muslimsim_panel.json"


def default_settings_path(project_root: Path) -> Path:
    return Path(project_root) / SETTINGS_FILENAME


@dataclass
class Settings:
    """Everything the panel remembers."""

    #: device key -> enabled
    enabled: Dict[str, bool] = field(default_factory=dict)
    #: device key -> {flag: value}
    options: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    #: {flag: value} for options that belong to no device
    globals: Dict[str, Any] = field(default_factory=dict)
    #: device key -> extra verbose logging
    diagnose: Dict[str, bool] = field(default_factory=dict)
    #: free-form extra arguments, for anything the catalogue does not model
    extra_arguments: str = ""
    #: controller name -> {axis index: calibration}.  Keyed by name rather
    #: than SDL index, because SDL renumbers devices when one is unplugged and
    #: a calibration that jumped to another device would be worse than none.
    axis_calibrations: Dict[str, Dict[str, dict]] = field(default_factory=dict)
    #: The WinCtrl quadrant's measured IDLE and REV IDLE detents.  Not
    #: optional for a 737: without them the below-idle split sits at the
    #: wrong raw counts and idle is not idle.
    throttle: ThrottleCalibration = field(default_factory=ThrottleCalibration)
    #: name -> a whole saved copy of the above
    profiles: Dict[str, dict] = field(default_factory=dict)
    active_profile: str = ""

    # -- defaults ----------------------------------------------------------

    @classmethod
    def defaults(cls) -> "Settings":
        settings = cls()

        for device in catalog.implemented():
            # A device that needs an explicit flag to come on starts off,
            # matching the launcher's own default.
            settings.enabled[device.key] = device.enable_flag is None
            settings.options[device.key] = {}
            settings.diagnose[device.key] = False

        settings.globals = {}
        return settings

    # -- persistence -------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": SETTINGS_VERSION,
            "enabled": dict(self.enabled),
            "options": {k: dict(v) for k, v in self.options.items()},
            "globals": dict(self.globals),
            "diagnose": dict(self.diagnose),
            "extra_arguments": self.extra_arguments,
            "axis_calibrations": {
                name: {str(axis): dict(body) for axis, body in axes.items()}
                for name, axes in self.axis_calibrations.items()
            },
            "throttle": self.throttle.as_dict(),
            "profiles": {k: dict(v) for k, v in self.profiles.items()},
            "active_profile": self.active_profile,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Settings":
        settings = cls.defaults()

        if not isinstance(payload, Mapping):
            return settings

        for key, value in (payload.get("enabled") or {}).items():
            if key in settings.enabled:
                settings.enabled[key] = bool(value)

        for key, values in (payload.get("options") or {}).items():
            if key in settings.options and isinstance(values, Mapping):
                settings.options[key] = dict(values)

        for key, value in (payload.get("diagnose") or {}).items():
            if key in settings.diagnose:
                settings.diagnose[key] = bool(value)

        if isinstance(payload.get("globals"), Mapping):
            settings.globals = dict(payload["globals"])

        settings.extra_arguments = str(payload.get("extra_arguments", "") or "")

        stored = payload.get("axis_calibrations")

        if isinstance(stored, Mapping):
            for name, axes in stored.items():
                if isinstance(axes, Mapping):
                    settings.axis_calibrations[str(name)] = {
                        str(axis): dict(body)
                        for axis, body in axes.items()
                        if isinstance(body, Mapping)
                    }
        settings.throttle = ThrottleCalibration.from_dict(payload.get("throttle"))
        settings.active_profile = str(payload.get("active_profile", "") or "")

        profiles = payload.get("profiles")

        if isinstance(profiles, Mapping):
            settings.profiles = {
                str(name): dict(body)
                for name, body in profiles.items()
                if isinstance(body, Mapping)
            }

        return settings

    @classmethod
    def load(cls, path: Path) -> "Settings":
        """Read the file, falling back to defaults rather than failing."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls.defaults()
        except Exception:
            # A corrupted settings file must never stop the panel opening.
            return cls.defaults()

        return cls.from_dict(payload)

    def save(self, path: Path) -> Optional[str]:
        """Write atomically.  Returns an error message, or None on success."""
        target = Path(path)
        temporary = target.with_suffix(target.suffix + ".tmp")

        try:
            temporary.write_text(
                json.dumps(self.to_dict(), indent=2), encoding="utf-8"
            )
            temporary.replace(target)
            return None
        except Exception as exc:
            return str(exc)

    # -- profiles ----------------------------------------------------------

    def snapshot(self) -> dict:
        """The current choices, without the profile list itself."""
        body = self.to_dict()
        body.pop("profiles", None)
        body.pop("active_profile", None)
        # Calibration describes the physical hardware, not a choice of which
        # devices to run, so switching profiles must never discard it.
        body.pop("axis_calibrations", None)
        # Same reasoning for the throttle: it describes the quadrant on
        # the desk, not a choice of which devices to run.
        body.pop("throttle", None)
        return body

    def save_profile(self, name: str) -> None:
        self.profiles[str(name)] = self.snapshot()
        self.active_profile = str(name)

    def load_profile(self, name: str) -> bool:
        body = self.profiles.get(str(name))

        if body is None:
            return False

        restored = Settings.from_dict(body)
        self.enabled = restored.enabled
        self.options = restored.options
        self.globals = restored.globals
        self.diagnose = restored.diagnose
        self.extra_arguments = restored.extra_arguments
        self.active_profile = str(name)
        return True

    def delete_profile(self, name: str) -> bool:
        if str(name) in self.profiles:
            del self.profiles[str(name)]

            if self.active_profile == str(name):
                self.active_profile = ""

            return True

        return False

    # -- option access -----------------------------------------------------

    def option(self, device_key: str, option: Option) -> Any:
        stored = self.options.get(device_key, {})

        if option.flag in stored:
            return stored[option.flag]

        return option.default

    def set_option(self, device_key: str, option: Option, value: Any) -> None:
        self.options.setdefault(device_key, {})[option.flag] = option.clamp(value)

    def global_option(self, option: Option) -> Any:
        if option.flag in self.globals:
            return self.globals[option.flag]

        return option.default

    def set_global_option(self, option: Option, value: Any) -> None:
        self.globals[option.flag] = option.clamp(value)

    def is_enabled(self, device_key: str) -> bool:
        """Enabled, and every device it depends on also enabled."""
        device = catalog.get(device_key)

        if device is None or not device.implemented:
            return False

        if not self.enabled.get(device_key, False):
            return False

        for parent in device.requires:
            if not self.enabled.get(parent, False):
                return False

        return True

    def blocked_by(self, device_key: str) -> tuple[str, ...]:
        """Which disabled parents are holding this device down."""
        device = catalog.get(device_key)

        if device is None:
            return ()

        return tuple(
            parent for parent in device.requires
            if not self.enabled.get(parent, False)
        )

    # -- command line ------------------------------------------------------

    def build_arguments(self) -> list[str]:
        """The launcher arguments these settings describe.

        Only the launcher's own vocabulary is emitted here; `launch.py` maps
        its `--without-*` switches onto the engine's `--no-*` flags, and the
        per-device options go straight through as unrecognised arguments,
        which is exactly how the launcher is designed to forward them.
        """
        arguments: list[str] = []

        for device in catalog.implemented():
            enabled = self.enabled.get(device.key, False)

            if enabled:
                if device.enable_flag:
                    arguments.append(device.enable_flag)
            else:
                if device.disable_flag:
                    arguments.append(device.disable_flag)

                # A disabled device contributes nothing else.
                continue

            for option in device.options:
                value = self.option(device.key, option)

                if value is None or value == "":
                    continue

                # An option whose value equals the default is left off, so
                # the command line shows only what was deliberately changed.
                if not isinstance(value, bool) and value == option.default:
                    continue

                arguments.extend(option.to_arguments(value))

            if self.diagnose.get(device.key) and device.diagnose_flag:
                arguments.append(device.diagnose_flag)

        for option in GLOBAL_OPTIONS:
            value = self.global_option(option)

            if value is None or value == "":
                continue

            if not isinstance(value, bool) and value == option.default:
                continue

            arguments.extend(option.to_arguments(value))

        # The throttle calibration is imposed whenever the quadrant is in
        # use.  It is not a preference: the WinCtrl is an Airbus quadrant
        # driving a 737, and without the measured detents the split between
        # thrust and reverse sits at the wrong raw counts -- which on this
        # machine meant 1.9% thrust with the lever in its idle detent.
        if self.enabled.get("winctrl", False) and self.throttle.calibrated:
            ok, _why = self.throttle.valid()

            if ok:
                arguments.extend(self.throttle.to_arguments())

        extra = (self.extra_arguments or "").split()
        arguments.extend(extra)

        return arguments

    def throttle_needs_calibration(self) -> bool:
        """True when the quadrant is in use but has never been measured."""
        if not self.enabled.get("winctrl", False):
            return False

        ok, _why = self.throttle.valid()
        return not (self.throttle.calibrated and ok)


#: Ready-made profiles offered the first time the panel runs.
STARTER_PROFILES: Dict[str, Dict[str, Any]] = {
    "Full cockpit": {
        "enabled": {
            "pu_overhead": True, "winctrl": True, "pedals": True,
            "agp": True, "pfp": True, "mcdu": True, "pap3": True, "pdc": True,
        },
    },
    "Displays only": {
        "enabled": {
            "pu_overhead": False, "winctrl": True, "pedals": False,
            "agp": False, "pfp": True, "mcdu": True, "pap3": False,
            "pdc": False,
        },
    },
    "Dry run (no hardware)": {
        "enabled": {key: False for key in catalog.DEVICES_BY_KEY},
        "globals": {"--dry-run": True},
    },
}


def apply_starter_profiles(settings: Settings) -> None:
    """Seed the built-in profiles, without disturbing the user's own."""
    for name, body in STARTER_PROFILES.items():
        if name in settings.profiles:
            continue

        seeded = Settings.defaults()

        for key, value in (body.get("enabled") or {}).items():
            if key in seeded.enabled:
                seeded.enabled[key] = bool(value)

        seeded.globals = dict(body.get("globals") or {})
        settings.profiles[name] = seeded.snapshot()
