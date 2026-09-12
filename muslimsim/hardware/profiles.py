"""Versioned, validated mapping-profile persistence for the hardware lab."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import tempfile
from typing import Any, Dict, Mapping, Optional

from .catalog import AGP_HID_CONTROL_MAP, ControlSpec, device_by_key, runtime_control_by_key
from .moza_presets import normalise_calibration as normalise_moza_calibration
from .toliss_throttle_calibration import (
    normalise_calibration as normalise_toliss_throttle_calibration,
)

try:  # Keep old BA01 Learn profiles usable after the named-control upgrade.
    from ..devices.fcu_efis_ba01 import control_for_bit
except Exception:  # pragma: no cover - catalogue still validates known maps
    control_for_bit = None


PROFILE_SCHEMA = 7
ALLOWED_BINDING_KINDS = frozenset({"command", "dataref", "action", "disabled"})
ALLOWED_SIMULATORS = frozenset({"xplane", "msfs24"})
ALLOWED_PROTOCOLS = frozenset({"", "xplane", "lvar", "hevent", "fsuipc"})
# These are deliberately small, local, and device-scoped.  Profile files never
# receive a shell command, Python expression, or arbitrary bridge operation.
SAFE_ACTION_TARGETS = frozenset({"lab:reset-device"})


class ProfileError(ValueError):
    """A persisted or submitted profile cannot be used safely."""


@dataclass(frozen=True)
class MappingBinding:
    """A user binding for one mappable input.

    ``command`` is a simulator command path, ``dataref`` can use ``value`` for
    buttons/selectors and the normalized input value for axes, and ``action``
    is a local supported action registered by the bridge.  The bridge never
    executes an arbitrary script from a profile.
    """

    kind: str = "disabled"
    target: str = ""
    value: Optional[float] = None
    invert: bool = False
    deadband: float = 0.0
    scale: float = 1.0
    # A selector can use one library role only at one named detent.  This
    # prevents a START command from firing again when a spring-return switch
    # comes home to OFF.  Buttons and axes leave it unset.
    trigger_value: Optional[float] = None
    # Only verified inputs may request an output mechanism.  Currently the
    # PU engine-start selectors are the sole captured spring-return hardware.
    mechanical: str = "standard"
    # Mapping profiles must not route an MSFS target into X-Plane, or vice
    # versa, even if a profile file is copied between simulator folders.
    simulator: str = "xplane"
    # Kept as descriptive metadata for the future MSFS dispatcher.  It is
    # never executed as code or a shell command.
    protocol: str = ""


def _control(device_key: str, control_key: str) -> ControlSpec:
    if device_by_key(device_key) is None:
        raise ProfileError(f"Unknown device {device_key!r}")
    control = runtime_control_by_key(device_key, control_key)
    if control is None:
        raise ProfileError(f"Unknown control {device_key}.{control_key}")
    return control


def validate_binding(device_key: str, control_key: str, binding: MappingBinding) -> MappingBinding:
    control = _control(device_key, control_key)
    kind = str(binding.kind).strip().lower()
    target = str(binding.target).strip()
    if kind not in ALLOWED_BINDING_KINDS:
        raise ProfileError(f"Unsupported binding kind {kind!r}")
    if not control.remappable:
        raise ProfileError(f"{device_key}.{control_key} is not a verified remappable input")
    if kind == "disabled":
        return MappingBinding()
    if not target:
        raise ProfileError("A command, dataref, or supported action target is required")
    if kind == "action" and target not in SAFE_ACTION_TARGETS:
        raise ProfileError("Unsupported safe action; available action: lab:reset-device")
    if kind == "dataref" and control.kind not in {"axis", "toggle", "selector", "button", "rotary"}:
        raise ProfileError("This control cannot be written as a dataref")
    if kind == "command" and control.kind == "axis":
        raise ProfileError("An axis must use a dataref or supported action, not a command")
    simulator = str(binding.simulator or "xplane").strip().casefold()
    if simulator not in ALLOWED_SIMULATORS:
        raise ProfileError("Mapping simulator must be X-Plane or MSFS 2024")
    protocol = str(binding.protocol or "").strip().casefold()
    if protocol not in ALLOWED_PROTOCOLS:
        raise ProfileError("Unsupported mapping protocol")
    if simulator == "xplane" and protocol not in {"", "xplane"}:
        raise ProfileError("An X-Plane mapping cannot use an MSFS LVAR or event protocol")
    if simulator == "msfs24" and kind == "action":
        raise ProfileError("Local actions are not valid MSFS 2024 simulator mappings")
    mechanical = str(binding.mechanical or "standard").strip().lower()
    if mechanical not in {"standard", "spring_return"}:
        raise ProfileError("Unsupported mechanical behavior")
    if mechanical == "spring_return":
        if (device_key, control_key) not in {
            ("pu_overhead", "engine_start_1"),
            ("pu_overhead", "engine_start_2"),
        }:
            raise ProfileError("Spring return is available only for the verified PU engine-start selectors")
        if kind != "command":
            raise ProfileError("A spring-return selector must be assigned to a simulator command")
    try:
        deadband = max(0.0, min(1.0, float(binding.deadband)))
        scale = float(binding.scale)
        value = None if binding.value is None else float(binding.value)
        trigger_value = None if binding.trigger_value is None else float(binding.trigger_value)
    except (TypeError, ValueError) as exc:
        raise ProfileError("Binding values must be numeric") from exc
    if not -16.0 <= scale <= 16.0:
        raise ProfileError("Binding scale must stay within -16..16")
    return MappingBinding(
        kind, target, value, bool(binding.invert), deadband, scale,
        trigger_value, mechanical, simulator, protocol,
    )


def _default_document() -> Dict[str, Any]:
    return {
        "schema": PROFILE_SCHEMA,
        "active_profile": "Default",
        "profiles": {
            "Default": {
                "bindings": {}, "outputs": {}, "calibration": {}, "learned": {},
                # Missing entries deliberately mean enabled. Existing profiles
                # therefore preserve their behavior until the user turns a
                # device off for one selected aircraft/profile.
                "devices": {},
                # An owner-typed display name for a visual control, keyed the
                # same way as "learned". Purely cosmetic - it never changes
                # which raw contact or simulator function a control uses.
                "labels": {},
            }
        },
    }


def _migrate(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Migrate older profile formats without discarding confirmed mappings."""

    schema = int(raw.get("schema", 1))
    if schema > PROFILE_SCHEMA:
        raise ProfileError("This profile was saved by a newer MuslimSim version")
    if schema == PROFILE_SCHEMA:
        return dict(raw)
    # v1/v2 kept profiles as {name: {"device.control": binding}}. Version 3
    # added explicit disabled bindings; version 4 names all AGP A320 contacts;
    # version 5 adds selector trigger values and the verified spring-return
    # behavior. Version 6 records the target simulator and protocol. Version
    # 7 adds an on/off setting for each device in a profile. Older entries
    # retain safe enabled defaults through an empty ``devices`` section.
    profiles: Dict[str, Any] = {}
    for name, values in dict(raw.get("profiles") or {}).items():
        if not isinstance(values, Mapping):
            continue
        bindings = values.get("bindings", values)
        profiles[str(name)] = {
            "bindings": dict(bindings) if isinstance(bindings, Mapping) else {},
            "outputs": dict(values.get("outputs") or {}),
            "calibration": dict(values.get("calibration") or {}),
            "learned": dict(values.get("learned") or {}),
            "devices": dict(values.get("devices") or {}),
        }
    result = _default_document()
    if profiles:
        result["profiles"] = profiles
    # Before the verified BA01 map, this device persisted names such as
    # raw_bit_17. Translate known historical assignments to their new semantic
    # keys. Unknown bits are intentionally discarded: they were never safe
    # remapping targets, and retaining them would make the profile invalid.
    if control_for_bit is not None:
        for profile in result["profiles"].values():
            bindings = dict(profile.get("bindings") or {})
            translated: Dict[str, Any] = {}
            for compound, value in bindings.items():
                device_key, separator, control_key = str(compound).partition(".")
                if device_key == "fcu_32_efis" and control_key.startswith("raw_bit_"):
                    try:
                        semantic = control_for_bit(int(control_key.removeprefix("raw_bit_")))
                    except ValueError:
                        semantic = "unknown"
                    if semantic.startswith("unknown_bit_"):
                        continue
                    compound = f"{device_key}.{semantic}"
                if device_key == "agp_bb80" and control_key.startswith("raw_bit_"):
                    try:
                        semantic = AGP_HID_CONTROL_MAP.get(
                            int(control_key.removeprefix("raw_bit_")), ""
                        )
                    except ValueError:
                        semantic = ""
                    # A previous Capture result for a now-published AGP A320
                    # contact is still the user's mapping; only its source
                    # name changes.  Unidentified report bits remain valid
                    # only when the then-current catalogue allowed them.
                    if semantic:
                        compound = f"{device_key}.{semantic}"
                translated[compound] = value
            profile["bindings"] = translated
            learned = dict(profile.get("learned") or {})
            fcu_learned = dict(learned.get("fcu_32_efis") or {})
            for visual, raw_control in tuple(fcu_learned.items()):
                raw_key = str(raw_control)
                if not raw_key.startswith("raw_bit_"):
                    continue
                try:
                    semantic = control_for_bit(int(raw_key.removeprefix("raw_bit_")))
                except ValueError:
                    semantic = "unknown"
                if semantic.startswith("unknown_bit_"):
                    fcu_learned.pop(visual, None)
                else:
                    fcu_learned[visual] = semantic
            if fcu_learned:
                learned["fcu_32_efis"] = fcu_learned
            else:
                learned.pop("fcu_32_efis", None)
            agp_learned = dict(learned.get("agp_bb80") or {})
            for visual, raw_control in tuple(agp_learned.items()):
                raw_key = str(raw_control)
                if not raw_key.startswith("raw_bit_"):
                    continue
                try:
                    semantic = AGP_HID_CONTROL_MAP.get(
                        int(raw_key.removeprefix("raw_bit_")), ""
                    )
                except ValueError:
                    semantic = ""
                if semantic:
                    agp_learned[visual] = semantic
                else:
                    agp_learned.pop(visual, None)
            if agp_learned:
                learned["agp_bb80"] = agp_learned
            else:
                learned.pop("agp_bb80", None)
            profile["learned"] = learned
    # v7 activation values are intentionally strict booleans. Discard stale
    # device names during an older-profile migration instead of keeping an
    # unusable entry that could prevent Studio from opening.
    for profile in result["profiles"].values():
        devices = profile.get("devices") or {}
        if not isinstance(devices, Mapping):
            devices = {}
        profile["devices"] = {
            str(device_key): bool(enabled)
            for device_key, enabled in devices.items()
            if device_by_key(str(device_key)) is not None
        }
    requested = str(raw.get("active_profile") or "Default")
    result["active_profile"] = requested if requested in result["profiles"] else next(iter(result["profiles"]))
    return result


class HardwareProfileStore:
    """Atomic JSON persistence scoped to the panel, not to the bridge process."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._document: Dict[str, Any] = _default_document()

    @property
    def active_profile(self) -> str:
        return str(self._document["active_profile"])

    def load(self) -> None:
        if not self.path.exists():
            self._document = _default_document()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileError(f"Could not read hardware profiles: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise ProfileError("Hardware profile file must contain an object")
        self._document = _migrate(raw)
        self._validate_document()

    def _validate_document(self) -> None:
        profiles = self._document.get("profiles")
        if not isinstance(profiles, Mapping) or not profiles:
            raise ProfileError("At least one hardware profile is required")
        for name, profile in profiles.items():
            if not str(name).strip() or not isinstance(profile, Mapping):
                raise ProfileError("Hardware profiles need non-empty names")
            for compound, raw in dict(profile.get("bindings") or {}).items():
                if not isinstance(raw, Mapping) or "." not in str(compound):
                    raise ProfileError(f"Invalid binding entry {compound!r}")
                device_key, control_key = str(compound).split(".", 1)
                validate_binding(device_key, control_key, MappingBinding(**dict(raw)))
            learned = profile.get("learned") or {}
            if not isinstance(learned, Mapping):
                raise ProfileError("Learned control assignments must be an object")
            for device_key, visual_map in learned.items():
                if not isinstance(visual_map, Mapping):
                    raise ProfileError(f"Learned controls for {device_key!r} must be an object")
                for visual_key, raw_control in visual_map.items():
                    if not str(visual_key).strip():
                        raise ProfileError("Learned visual controls need a name")
                    control = _control(str(device_key), str(raw_control))
                    if not control.remappable:
                        raise ProfileError(f"{device_key}.{raw_control} cannot be learned/mapped")
            labels = profile.get("labels") or {}
            if not isinstance(labels, Mapping):
                raise ProfileError("Custom control names must be an object")
            for device_key, visual_map in labels.items():
                if not isinstance(visual_map, Mapping):
                    raise ProfileError(f"Custom names for {device_key!r} must be an object")
                for visual_key, label in visual_map.items():
                    if not str(visual_key).strip():
                        raise ProfileError("A custom name needs a visual control")
                    if len(str(label)) > 40:
                        raise ProfileError(f"Custom name for {device_key}.{visual_key} is too long")
            devices = profile.get("devices") or {}
            if not isinstance(devices, Mapping):
                raise ProfileError("Device activation settings must be an object")
            for device_key, enabled in devices.items():
                if device_by_key(str(device_key)) is None:
                    raise ProfileError(f"Unknown device activation entry {device_key!r}")
                if not isinstance(enabled, bool):
                    raise ProfileError(f"Device activation for {device_key!r} must be on or off")
        if self.active_profile not in profiles:
            self._document["active_profile"] = next(iter(profiles))

    def save(self) -> None:
        self._validate_document()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(self.path.parent),
            prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            json.dump(self._document, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(self.path)

    def names(self) -> tuple[str, ...]:
        return tuple(str(name) for name in self._document["profiles"])

    def select(self, name: str) -> None:
        if name not in self._document["profiles"]:
            raise ProfileError(f"Unknown profile {name!r}")
        self._document["active_profile"] = name

    def create(self, name: str, *, copy_active: bool = True) -> None:
        name = str(name).strip()
        if not name or name in self._document["profiles"]:
            raise ProfileError("Choose a new, non-empty profile name")
        source = self._document["profiles"][self.active_profile] if copy_active else {}
        self._document["profiles"][name] = json.loads(json.dumps(source)) if source else {
            "bindings": {}, "outputs": {}, "calibration": {}, "learned": {}, "devices": {}, "labels": {},
        }
        self._document["active_profile"] = name

    def restore_defaults(self, profile: Optional[str] = None) -> None:
        name = profile or self.active_profile
        if name not in self._document["profiles"]:
            raise ProfileError(f"Unknown profile {name!r}")
        self._document["profiles"][name] = {
            "bindings": {}, "outputs": {}, "calibration": {}, "learned": {}, "devices": {}, "labels": {},
        }

    def binding(self, device_key: str, control_key: str, *, profile: Optional[str] = None) -> MappingBinding:
        name = profile or self.active_profile
        raw = self._document["profiles"][name]["bindings"].get(f"{device_key}.{control_key}")
        return MappingBinding(**raw) if isinstance(raw, Mapping) else MappingBinding()

    def has_binding(self, device_key: str, control_key: str, *, profile: Optional[str] = None) -> bool:
        """Whether this profile deliberately overrides the device default."""

        name = profile or self.active_profile
        bindings = self._document["profiles"][name].get("bindings") or {}
        return f"{device_key}.{control_key}" in bindings

    def set_binding(self, device_key: str, control_key: str, binding: MappingBinding, *, profile: Optional[str] = None) -> MappingBinding:
        name = profile or self.active_profile
        checked = validate_binding(device_key, control_key, binding)
        bindings = self._document["profiles"][name].setdefault("bindings", {})
        compound = f"{device_key}.{control_key}"
        # Keep disabled bindings.  The absence of an entry means "use the
        # declared device default"; an explicit disabled entry means the
        # user intentionally asked for no action until defaults are restored.
        bindings[compound] = asdict(checked)
        return checked

    def device_enabled(self, device_key: str, *, profile: Optional[str] = None) -> bool:
        """Return this profile's activation choice for one known device."""

        if device_by_key(device_key) is None:
            raise ProfileError(f"Unknown device {device_key!r}")
        values = self._document["profiles"][profile or self.active_profile].get("devices") or {}
        # Profiles made before v7 have no entries and are therefore fully on.
        return bool(dict(values).get(device_key, True))

    def set_device_enabled(
        self, device_key: str, enabled: bool, *, profile: Optional[str] = None,
    ) -> bool:
        if device_by_key(device_key) is None:
            raise ProfileError(f"Unknown device {device_key!r}")
        if not isinstance(enabled, bool):
            raise ProfileError("Device activation must be on or off")
        values = self._document["profiles"][profile or self.active_profile].setdefault("devices", {})
        values[device_key] = enabled
        return enabled

    def learned_controls(self, device_key: str, *, profile: Optional[str] = None) -> Dict[str, str]:
        values = self._document["profiles"][profile or self.active_profile].get("learned", {}).get(device_key, {})
        return {str(visual): str(raw) for visual, raw in dict(values or {}).items()}

    def set_learned_control(
        self,
        device_key: str,
        visual_key: str,
        raw_control: str,
        *,
        profile: Optional[str] = None,
    ) -> str:
        visual_key = str(visual_key).strip()
        if not visual_key:
            raise ProfileError("Choose a visual control before learning")
        control = _control(device_key, raw_control)
        if not control.remappable:
            raise ProfileError(f"{device_key}.{raw_control} cannot be learned/mapped")
        learned = self._document["profiles"][profile or self.active_profile].setdefault("learned", {})
        learned.setdefault(device_key, {})[visual_key] = control.key
        return control.key

    def custom_labels(self, device_key: str, *, profile: Optional[str] = None) -> Dict[str, str]:
        values = self._document["profiles"][profile or self.active_profile].get("labels", {}).get(device_key, {})
        return {str(visual): str(label) for visual, label in dict(values or {}).items()}

    def custom_label(self, device_key: str, visual_key: str, *, profile: Optional[str] = None) -> str:
        return self.custom_labels(device_key, profile=profile).get(str(visual_key), "")

    def set_custom_label(
        self,
        device_key: str,
        visual_key: str,
        label: str,
        *,
        profile: Optional[str] = None,
    ) -> str:
        """Persist an owner-typed display name; an empty label clears it."""

        visual_key = str(visual_key).strip()
        if not visual_key:
            raise ProfileError("Choose a visual control before naming it")
        label = str(label).strip()
        if len(label) > 40:
            raise ProfileError("Custom names are limited to 40 characters")
        labels = self._document["profiles"][profile or self.active_profile].setdefault("labels", {})
        if label:
            labels.setdefault(device_key, {})[visual_key] = label
        else:
            device_labels = labels.get(device_key)
            if isinstance(device_labels, dict):
                device_labels.pop(visual_key, None)
                if not device_labels:
                    labels.pop(device_key, None)
        return label

    def calibration(self, device_key: str, *, profile: Optional[str] = None) -> Dict[str, Any]:
        return dict(self._document["profiles"][profile or self.active_profile].get("calibration", {}).get(device_key) or {})

    def set_calibration(self, device_key: str, settings: Mapping[str, Any], *, profile: Optional[str] = None) -> None:
        # Only settings backed by a real driver control are persisted.  The PU
        # bridge exposes a retract duration; it does not expose motor strength,
        # endpoints, direction, or solenoid force.
        if device_key in {"moza_a210", "moza_ab6"}:
            # Presets define an intentional Studio configuration surface, not
            # a direct device protocol.  Validation stays deliberately local
            # and bounded to the exact settings represented by the supplied
            # Moza files.
            try:
                normalised = normalise_moza_calibration(device_key, settings)
            except ValueError as exc:
                raise ProfileError(str(exc)) from exc
            target = self._document["profiles"][profile or self.active_profile].setdefault("calibration", {})
            target[device_key] = normalised
            return
        if device_key == "winctrl_throttle":
            # This schema is intentionally marked with its aircraft family.
            # The ToLiss workspace has its own hardware_profiles_toliss.json,
            # so it can never replace the established Zibo/LevelUp endpoints.
            try:
                normalised = normalise_toliss_throttle_calibration(settings)
            except ValueError as exc:
                raise ProfileError(str(exc)) from exc
            target = self._document["profiles"][profile or self.active_profile].setdefault("calibration", {})
            target[device_key] = normalised
            return
        if device_key != "pu_overhead":
            raise ProfileError("No captured actuator calibration API exists for this device")
        permitted = {"starter_retract_ms"}
        unknown = set(settings) - permitted
        if unknown:
            raise ProfileError("Unsupported PU actuator settings: " + ", ".join(sorted(unknown)))
        value = int(settings.get("starter_retract_ms", 310))
        if not 50 <= value <= 1000:
            raise ProfileError("PU starter retract timing must be between 50 and 1000 ms")
        target = self._document["profiles"][profile or self.active_profile].setdefault("calibration", {})
        target[device_key] = {"starter_retract_ms": value}

    def snapshot(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._document))
