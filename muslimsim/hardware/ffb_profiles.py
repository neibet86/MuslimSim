"""User-authored MuslimSim force-feedback profiles (the ".mslm" format).

A `.mslm` file describes force-feedback *effects* in named, human terms - a
dataref, a response curve, and an effect type ("spring", "trim", "rumble",
"constant_force") - never raw protocol bytes, channel numbers, or report
formats. Translating a named effect into the actual MOZA AY210 wire protocol
is `muslimsim/hardware/moza_ay210_ffb_engine.py`'s job, not this module's or
the user's.

This is deliberately modeled on `muslimsim/hardware/chains.py`'s
`StageSpec`/`StageOption`/`build_chain` pattern - the curve and gate fields
on every effect are literally `chains.py` stage lists, reused as-is, so
there is zero new curve-shaping code in this feature: deadzone, curve
(expo), scale, ratelimit, and "when" (for gating, e.g. a rumble effect only
while weight-on-wheels is true) all already exist and are already tested.

Profiles are auto-discovered from a drop-in folder (see
`FfbProfileStore.discover`), the same way `muslimsim/platform/registry.py`'s
`discover_manifests` scans for `*.muslimsim-device.json` plug-in manifests -
one bad file is isolated and reported, never blocking discovery of the
others. Unlike `ChainStore`/`HardwareProfileStore`, this store has no
`save()` - `.mslm` files are user-authored and dropped in, not written by
the bridge. What the bridge does own is a tiny separate sidecar recording
which discovered profile is currently active (see
`load_active_profile_name`/`save_active_profile_name`), using the exact same
schema-versioned, fail-open-on-any-read-error, atomic-temp-file-then-replace
idiom as `moza_a210_axis_slots.json`/`starter_return_state.json` in
`bridge/final.py`.

All four effect types (spring, trim, rumble, constant_force) are now
physically confirmed on real hardware, live, at proven-comfortable
magnitudes - see `moza_ay210_ffb_protocol.py`'s module docstring and
BUG_REGISTER.md's BUG-21 tenth follow-up for the full story. `spring` and
`constant_force` cannot be combined in the same profile - confirmed on real
hardware that both together trip the firmware's own "more than one spring
force" warning (see the validator in `build_profile`).

A profile may also carry a top-level `physics` block - a second family of
gain parameters (Spring/Damper/Inertia/Friction/Overall Force Feedback
Intensity/Maximum Torque Output/Friction Compensation Strength) found by
watching MOZA Cockpit's own "Basic Settings"/"Physics Model Settings"
panels write them, one slider at a time, via live USB capture. Unlike the
per-axis `spring`/`trim` effects above, these are confirmed on real
hardware to affect BOTH axes at once (not one axis's own condition
report), so they live at the profile level, not inside one effect. See
`PHYSICS_FIELD_DEFAULTS` below.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
import json
import os

from .chains import Chain, ChainError, build_chain
from .moza_ay210_ffb_protocol import RUMBLE_PRESETS

MSLM_SCHEMA = 1

ALLOWED_DEVICES: Tuple[str, ...] = ("moza_a210", "moza_ab6")
ALLOWED_AXES: Tuple[str, ...] = ("pitch", "roll")
RUMBLE_PRESET_NAMES: Tuple[str, ...] = tuple(sorted(RUMBLE_PRESETS))


class FfbProfileError(ValueError):
    """A `.mslm` profile was built from data that cannot be honoured."""


# ---------------------------------------------------------------------------
# Effect options/specs, mirroring chains.py's StageOption/StageSpec exactly
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectOption:
    name: str
    label: str
    kind: str = "float"  # float | int | bool | text | choice
    default: Any = 0.0
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    choices: Tuple[str, ...] = ()
    help: str = ""

    def clamp(self, value: Any) -> Any:
        if self.kind == "bool":
            return bool(value)
        if self.kind in ("float", "int"):
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise FfbProfileError(f"{self.name} must be a number") from exc
            if self.minimum is not None and number < self.minimum:
                raise FfbProfileError(f"{self.name} must be at least {self.minimum}")
            if self.maximum is not None and number > self.maximum:
                raise FfbProfileError(f"{self.name} must be at most {self.maximum}")
            return int(round(number)) if self.kind == "int" else number
        if self.kind == "choice":
            text = str(value)
            if text not in self.choices:
                raise FfbProfileError(f"{self.name} must be one of {', '.join(self.choices)}")
            return text
        return str(value)


@dataclass(frozen=True)
class EffectSpec:
    kind: str
    label: str
    summary: str
    options: Tuple[EffectOption, ...] = ()


EFFECT_SPECS: Tuple[EffectSpec, ...] = (
    EffectSpec(
        "spring", "Centering spring",
        "Stiffens/loosens the yoke's centering spring on one axis, driven "
        "by a dataref. Physically confirmed on real hardware, including at "
        "the full 28000 coefficient ceiling. For the separate 'Spring' "
        "force-gain multiplier Cockpit itself exposes (confirmed as raw "
        "serial parameter 'af'), see the profile-level 'physics.spring_gain' "
        "field, not an option here - it affects both axes, not one.",
        (
            EffectOption("axis", "Axis", "choice", "pitch", choices=ALLOWED_AXES),
            EffectOption("dataref", "Dataref", "text", ""),
            EffectOption("deadband", "Dead band (0-1)", "float", 0.05, 0.0, 1.0),
        ),
    ),
    EffectSpec(
        "trim", "Trim",
        "Shifts the yoke's centered (trimmed) position on one axis. Shares "
        "the same underlying report as 'spring' on that axis - only one "
        "'spring' and one 'trim' effect are allowed per axis.",
        (
            EffectOption("axis", "Axis", "choice", "pitch", choices=ALLOWED_AXES),
            EffectOption("dataref", "Dataref", "text", ""),
        ),
    ),
    EffectSpec(
        "rumble", "Rumble / buffet",
        "One of the 14 named periodic effects decoded from FFB-Bridge's own "
        "bench tests (runway rumble, stall buffet, etc.) - not yet "
        "physically verified under live dataref-driven control.",
        (
            EffectOption("preset", "Preset", "choice", RUMBLE_PRESET_NAMES[0], choices=RUMBLE_PRESET_NAMES),
            EffectOption("dataref", "Dataref", "text", ""),
        ),
    ),
    EffectSpec(
        "constant_force", "Constant force",
        "A steady directional push (e.g. airspeed/control loading) on the "
        "yoke's single global constant-force channel. Physically confirmed "
        "on real hardware - gain 1.0 scales onto 'max_magnitude'. At most "
        "one per profile (the channel is global), and cannot be combined "
        "with 'spring'/'trim' in the same profile (confirmed on real "
        "hardware to trip the firmware's own 'more than one spring force' "
        "warning).",
        (
            EffectOption("dataref", "Dataref", "text", ""),
            EffectOption(
                "max_magnitude", "Max magnitude (0-32767)", "int", 25000, 0, 32767,
                help=(
                    "Step-tested comfortable up to 32767 (25000/28000/30000/32767 all "
                    "confirmed fine on real hardware). 32767 is the true maximum, not "
                    "a conservative cutoff: a follow-up step test confirmed this field "
                    "is signed (int16) by pushing through the u16 boundary and watching "
                    "the effect reverse direction and get progressively WEAKER "
                    "approaching 65535 (classic int16 wraparound - 32768 reads back as "
                    "-32768, 65535 as -1). There is no value beyond 32767 that means "
                    "'stronger push' - only 'reversed and weaker'."
                ),
            ),
        ),
    ),
)
EFFECT_BY_KIND: Dict[str, EffectSpec] = {spec.kind: spec for spec in EFFECT_SPECS}


# ---------------------------------------------------------------------------
# The profile-level "physics" block - Cockpit's own Spring/Damper/Inertia/
# Friction/Overall Force Feedback Intensity/Maximum Torque Output/Friction
# Compensation Strength sliders, found this session by watching MOZA
# Cockpit write them one at a time. Each is a plain 0.0-1.0 gain; unlike a
# real capture ever showed Cockpit itself do (values set once per profile,
# never adjusted live), a `.mslm` profile may optionally bind one to a
# dataref/curve instead of a bare number, for genuinely live control -
# capability Cockpit itself has no way to offer since it has no access to
# sim telemetry. `overall_intensity`/`max_torque` default to 1.0 (a
# profile that omits them should not silently zero out all force output);
# every other field defaults to 0.0, matching "nothing configured, nothing
# added" everywhere else in this schema.
# ---------------------------------------------------------------------------

PHYSICS_FIELD_DEFAULTS: Dict[str, float] = {
    "spring_gain": 0.0,
    "damper": 0.0,
    "inertia": 0.0,
    "friction": 0.0,
    "overall_intensity": 1.0,
    "max_torque": 1.0,
    "friction_compensation": 0.0,
}


@dataclass(frozen=True)
class PhysicsSetting:
    """One resolved `physics.*` field: a bare static gain, or a live
    dataref/curve - never both. `moza_ay210_ffb_engine.py` evaluates the
    curve each tick when `dataref` is set, otherwise just uses `static`."""

    static: Optional[float]
    dataref: str = ""
    curve: Optional[Chain] = None


# ---------------------------------------------------------------------------
# Built, validated documents
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Effect:
    id: str
    kind: str
    options: Mapping[str, Any]
    curve: Chain
    gate: Optional[Chain] = None


@dataclass(frozen=True)
class FfbProfile:
    name: str
    device: str
    effects: Tuple[Effect, ...]
    physics: Mapping[str, PhysicsSetting] = None  # type: ignore[assignment]
    source_path: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.physics is None:
            object.__setattr__(self, "physics", {
                field: PhysicsSetting(static=default)
                for field, default in PHYSICS_FIELD_DEFAULTS.items()
            })


def _build_physics(raw: Mapping[str, Any]) -> Dict[str, PhysicsSetting]:
    physics_raw = raw.get("physics")
    if physics_raw is None:
        physics_raw = {}
    if not isinstance(physics_raw, Mapping):
        raise FfbProfileError("'physics' must be an object")
    unknown = set(physics_raw) - set(PHYSICS_FIELD_DEFAULTS)
    if unknown:
        raise FfbProfileError(f"physics: unknown field {sorted(unknown)[0]!r}")

    resolved: Dict[str, PhysicsSetting] = {}
    for field, default in PHYSICS_FIELD_DEFAULTS.items():
        value = physics_raw.get(field, default)
        if isinstance(value, Mapping):
            dataref = str(value.get("dataref", "")).strip()
            if not dataref:
                raise FfbProfileError(f"physics.{field}: 'dataref' is required for a dynamic value")
            curve_raw = value.get("curve") or []
            try:
                curve = build_chain(curve_raw)
            except ChainError as exc:
                raise FfbProfileError(f"physics.{field} curve: {exc}") from exc
            resolved[field] = PhysicsSetting(static=None, dataref=dataref, curve=curve)
        else:
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise FfbProfileError(f"physics.{field} must be a number or {{dataref, curve}}") from exc
            if not 0.0 <= number <= 1.0:
                raise FfbProfileError(f"physics.{field} must be between 0 and 1")
            resolved[field] = PhysicsSetting(static=number)
    return resolved


def build_profile(raw: Mapping[str, Any], *, name_hint: str = "") -> FfbProfile:
    """Validate and freeze a `.mslm` document. Raises FfbProfileError with a
    1-based effect index on anything that cannot be honoured - never
    silently drops or coerces bad input, mirroring chains.py's build_chain."""

    if not isinstance(raw, Mapping):
        raise FfbProfileError("top-level document must be an object")

    schema = int(raw.get("schema", 0) or 0)
    if schema > MSLM_SCHEMA:
        raise FfbProfileError(f"written by a newer version of MuslimSim (schema {schema})")

    device = str(raw.get("device", "")).strip()
    if device not in ALLOWED_DEVICES:
        raise FfbProfileError(f"unknown or missing device {device!r} (expected one of {ALLOWED_DEVICES})")

    name = str(raw.get("name") or name_hint or "Untitled").strip() or "Untitled"

    effects_raw = raw.get("effects")
    if not isinstance(effects_raw, list):
        raise FfbProfileError("'effects' must be a list")

    built: List[Effect] = []
    axis_effect_seen: Dict[Tuple[str, str], int] = {}
    constant_force_seen: Optional[int] = None
    spring_or_trim_seen: Optional[int] = None

    for index, item in enumerate(effects_raw):
        position = index + 1
        if not isinstance(item, Mapping):
            raise FfbProfileError(f"effect {position}: must be an object")

        kind = str(item.get("kind", "")).strip()
        spec = EFFECT_BY_KIND.get(kind)
        if spec is None:
            raise FfbProfileError(f"effect {position}: unknown kind {kind!r}")

        supplied = dict(item)
        supplied.pop("kind", None)
        curve_raw = supplied.pop("curve", None) or []
        gate_raw = supplied.pop("gate", None)
        effect_id = str(supplied.pop("id", "") or f"{kind}_{position}")

        unknown = set(supplied) - {option.name for option in spec.options}
        if unknown:
            raise FfbProfileError(f"effect {position} ({kind}): unknown option {sorted(unknown)[0]!r}")

        resolved: Dict[str, Any] = {}
        for option in spec.options:
            resolved[option.name] = option.clamp(supplied.get(option.name, option.default))

        if kind in ("spring", "trim"):
            axis_key = (kind, resolved["axis"])
            if axis_key in axis_effect_seen:
                raise FfbProfileError(
                    f"effect {position}: only one {kind!r} effect is allowed per axis "
                    f"(already defined at effect {axis_effect_seen[axis_key]})"
                )
            axis_effect_seen[axis_key] = position
            if constant_force_seen is not None:
                raise FfbProfileError(
                    f"effect {position} ({kind}): cannot be combined with 'constant_force' "
                    f"(already defined at effect {constant_force_seen}) - confirmed on real "
                    f"hardware that running both together trips the firmware's own "
                    f"'FFB effect have more than one spring force' warning; it treats "
                    f"constant force as competing for the same force slot as spring, not "
                    f"as an independent push layered on top of it"
                )
            spring_or_trim_seen = position

        if kind == "constant_force":
            if constant_force_seen is not None:
                raise FfbProfileError(
                    f"effect {position}: only one constant_force effect is allowed per profile "
                    f"(already defined at effect {constant_force_seen})"
                )
            if spring_or_trim_seen is not None:
                raise FfbProfileError(
                    f"effect {position} (constant_force): cannot be combined with "
                    f"'spring'/'trim' (already defined at effect {spring_or_trim_seen}) - "
                    f"confirmed on real hardware that running both together trips the "
                    f"firmware's own 'FFB effect have more than one spring force' warning; "
                    f"it treats constant force as competing for the same force slot as "
                    f"spring, not as an independent push layered on top of it"
                )
            constant_force_seen = position

        if not str(resolved.get("dataref", "")).strip():
            raise FfbProfileError(f"effect {position} ({kind}): 'dataref' is required")

        try:
            curve = build_chain(curve_raw)
        except ChainError as exc:
            raise FfbProfileError(f"effect {position} ({kind}) curve: {exc}") from exc

        gate: Optional[Chain] = None
        if gate_raw:
            try:
                gate = build_chain(gate_raw)
            except ChainError as exc:
                raise FfbProfileError(f"effect {position} ({kind}) gate: {exc}") from exc

        built.append(Effect(effect_id, kind, resolved, curve, gate))

    physics = _build_physics(raw)

    return FfbProfile(name, device, tuple(built), physics)


# ---------------------------------------------------------------------------
# Discovery - a drop-in folder, not a single edited document
# ---------------------------------------------------------------------------


class FfbProfileStore:
    """`.mslm` profiles auto-discovered from a drop-in folder.

    No `save()` - these files are user-authored and dropped in, never
    written by the bridge. One bad file is isolated into `errors` and never
    blocks discovery of the others, matching
    `muslimsim/platform/registry.py`'s `discover_manifests`.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.profiles: Dict[str, FfbProfile] = {}
        self.errors: List[Dict[str, str]] = []

    def discover(self) -> None:
        self.profiles = {}
        self.errors = []
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.glob("*.mslm")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                profile = build_profile(raw, name_hint=path.stem)
            except (OSError, ValueError, FfbProfileError) as exc:
                self.errors.append({"source": str(path), "error": str(exc)})
                continue
            name = profile.name
            if name in self.profiles:
                name = f"{profile.name} ({path.stem})"
            self.profiles[name] = FfbProfile(name, profile.device, profile.effects, profile.physics, path)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "profiles": [
                {
                    "name": name,
                    "device": p.device,
                    "effect_count": len(p.effects),
                    "source": str(p.source_path) if p.source_path else None,
                }
                for name, p in sorted(self.profiles.items())
            ],
            "errors": list(self.errors),
        }


def default_ffb_profile_dir(device: str = "moza_a210") -> Path:
    """Beside the hardware profiles, under the user's own application data.

    `device` picks which device's own drop-in subfolder to use - defaults to
    "moza_a210" so every existing caller keeps today's exact path
    (.../MuslimSim/ffb_profiles) unchanged. Any other device (e.g.
    "moza_ab6") gets its own sibling folder so two devices' profiles never
    collide in the same discover() listing.
    """
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    if device == "moza_a210":
        return root / "MuslimSim" / "ffb_profiles"
    return root / "MuslimSim" / f"ffb_profiles_{device}"


# ---------------------------------------------------------------------------
# Active-profile sidecar - bridge-owned state (which discovered profile is
# selected), same idiom as moza_a210_axis_slots.json / starter_return_state.json
# in bridge/final.py: schema-versioned, fail-open on any read error, atomic
# write via a .tmp file + os.replace().
# ---------------------------------------------------------------------------


def load_active_profile_name(path: Path) -> Optional[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping) or int(payload.get("schema", 0)) != 1:
            return None
        name = payload.get("active")
        return str(name) if isinstance(name, str) and name else None
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return None


def save_active_profile_name(path: Path, name: Optional[str]) -> None:
    payload = {"schema": 1, "active": name}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        print(f"WARNING: could not persist FFB active profile: {exc}")


def default_active_profile_path(device: str = "moza_a210") -> Path:
    if device == "moza_a210":
        return default_ffb_profile_dir(device).parent / "ffb_active_profile.json"
    return default_ffb_profile_dir(device).parent / f"ffb_active_profile_{device}.json"


# ---------------------------------------------------------------------------
# Presets - measured starting points, not invented defaults
# ---------------------------------------------------------------------------


PRESETS: Mapping[str, Mapping[str, Any]] = {
    "spring-only-starter": {
        "device": "moza_a210",
        "name": "Spring Only (starter)",
        "effects": [
            {
                "kind": "spring",
                "id": "pitch_spring",
                "axis": "pitch",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "deadband": 0.05,
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 200.0, "out_min": 0.1, "out_max": 1.0}},
                ],
            },
        ],
    },
    # Reinterpreted, not transcribed, from two owner-supplied MOZA Cockpit
    # presets ("iFly B737MAX tony v1.2.preset" / "PMDG B777 tony v1.2.preset",
    # see moza_presets.py's MOZA_UI_PRESETS - those numbers are the real
    # reference point below). Cockpit's own values were static, one-time
    # percentages with no access to sim telemetry; these instead drive the
    # SAME intent live from real datarefs, which is the actual capability
    # gap this whole `.mslm` project exists to close. Both jets share
    # nearly identical physics (damper=inertia=100%, friction=0%,
    # spring=50%, overall/max_torque=100%) in Tony's own numbers - the real
    # differentiators are stall_buffet_strength (20 vs 100) and
    # speedbrake_buffet_enabled (False vs True/100), so that's where these
    # two profiles are deliberately built differently, not just re-scaled.
    #
    # Tony's own presets also enabled 'g_force' (constant_force) alongside
    # spring - omitted here on purpose: this session confirmed on real
    # hardware that spring/trim and constant_force together trip the
    # firmware's own "more than one spring force" warning (see
    # build_profile's validator), so Cockpit's own choice cannot be
    # reproduced as configured. 'turbulence' was disabled in both of Tony's
    # presets, so it's omitted here too, matching that choice rather than
    # inventing a feature Tony never turned on.
    "b737_max_tony": {
        "device": "moza_a210",
        "name": "Boeing 737-800",
        # spring_gain/damper/inertia were static and stayed at full strength
        # even fully unpowered/parked. A first attempt gated these on plain
        # main-bus voltage - wrong, since battery-only power already reads
        # the bus fully hot (~24V) with no boost actually present. A second
        # attempt gated on engine-running alone - closer, but missed a real
        # case: the APU alone (engines still off) also provides real boost
        # via an electric hydraulic pump, and produces no reaction under an
        # engine-only gate. Confirmed live: this aircraft's main bus reads a
        # clearly different, higher voltage once a real generator (APU or
        # engine-driven) comes online - 24.0V on battery alone vs 28.5V the
        # moment the APU generator connects - so bus voltage, thresholded
        # above battery level, is actually the single signal that already
        # captures either source, without needing to check engine and APU
        # state separately.
        "physics": {
            "spring_gain": {
                "dataref": "sim/cockpit2/electrical/bus_volts",
                "curve": [{"kind": "scale", "options": {"in_min": 26.0, "in_max": 27.0, "out_min": 0.0, "out_max": 0.5}}],
            },
            "damper": {
                "dataref": "sim/cockpit2/electrical/bus_volts",
                "curve": [{"kind": "scale", "options": {"in_min": 26.0, "in_max": 27.0, "out_min": 0.0, "out_max": 1.0}}],
            },
            "inertia": {
                "dataref": "sim/cockpit2/electrical/bus_volts",
                "curve": [{"kind": "scale", "options": {"in_min": 26.0, "in_max": 27.0, "out_min": 0.0, "out_max": 1.0}}],
            },
            "friction": 0.0,
            "overall_intensity": 1.0,
            "max_torque": 1.0,
        },
        "effects": [
            {
                # out_min was 0.1, then 0.0 ("zero airspeed means zero
                # aerodynamic loading" - still true) - but confirmed live
                # this made trim (pitch_follow/roll_follow) completely
                # inert on the ground: trim only shifts the spring's own
                # center point, and a spring with zero stiffness produces
                # zero force no matter where its center point sits. A real
                # 737's hydraulic feel unit has a baseline spring rate of
                # its own, independent of dynamic pressure - it isn't a
                # pure function of airspeed the way an unboosted GA
                # aircraft's cable-actuated controls are (contrast the
                # C172 profile, correctly still 0.0 there for exactly that
                # reason). Gated on the same bus-voltage threshold as the
                # physics block above, so it still goes fully loose with no
                # hydraulic power, but stays felt on the ground once
                # powered instead of only above some airspeed.
                "kind": "spring", "id": "pitch_spring", "axis": "pitch",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "deadband": 0.05,
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 200.0, "out_min": 0.4, "out_max": 1.0}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/cockpit2/electrical/bus_volts", "min": 26.0, "max": 999.0}}],
            },
            {
                # Every preset built this session originally shipped pitch
                # spring only - real live-flight testing showed roll input
                # produced no felt force at all, since nothing was ever bound
                # to the roll axis. Same airspeed curve as pitch: dynamic
                # pressure stiffens aileron feel the same way it stiffens
                # elevator feel. See pitch_spring's own comment for the
                # baseline-floor-once-powered reasoning.
                "kind": "spring", "id": "roll_spring", "axis": "roll",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "deadband": 0.05,
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 200.0, "out_min": 0.4, "out_max": 1.0}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/cockpit2/electrical/bus_volts", "min": 26.0, "max": 999.0}}],
            },
            {
                # This jet had spring stiffness on roll but nothing that
                # actually moved the physical yoke - confirmed live: using
                # the new WinCtrl aileron-trim feature visibly turned the
                # sim's own control wheel but the MOZA yoke stayed put.
                # aileron_trim (not the primary aileron ratio) is
                # deliberately the source: it only reflects genuine trim
                # bias, never the pilot's own moment-to-moment hand
                # position on the primary controls, so this can't fight a
                # manual input the way following raw aileron deflection
                # would - same reasoning as the C172 profile's own
                # roll_follow (phi-based there; there is no autopilot-vs-
                # manual distinction to gate on here since trim state means
                # the same thing regardless of who commanded it).
                "kind": "trim", "id": "roll_follow", "axis": "roll",
                "dataref": "sim/cockpit2/controls/aileron_trim",
                "curve": [
                    {"kind": "scale", "options": {"in_min": -1.0, "in_max": 1.0, "out_min": -0.3, "out_max": 0.3}},
                ],
            },
            {
                # 20% - Tony's own stall_buffet_strength for this jet.
                "kind": "rumble", "id": "stall", "preset": "stall_buffet",
                "dataref": "sim/cockpit2/annunciators/stall_warning",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 0.20}}],
            },
            {
                # Rate-limited on top of the scale, smoothing the buzz as
                # groundspeed changes rather than letting it step raggedly
                # tick to tick - a structural choice, not just a number.
                "kind": "rumble", "id": "runway", "preset": "runway_rumble",
                "dataref": "sim/flightmodel/position/groundspeed",
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 30.0, "out_min": 0.0, "out_max": 1.0}},
                    {"kind": "ratelimit", "options": {"per_second": 8.0}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/flightmodel/failures/onground_any", "min": 0.5, "max": 1.5}}],
            },
            {
                # Taxi-oriented bumps, matching "gear_motion" as Tony named
                # it - contrast the B777 profile below, which uses the
                # in-flight gear_buffet preset instead for the same field.
                "kind": "rumble", "id": "gear", "preset": "gear_bumps",
                "dataref": "sim/flightmodel/position/groundspeed",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 15.0, "out_min": 0.0, "out_max": 0.10}}],
                "gate": [{"kind": "when", "options": {"key": "sim/flightmodel/failures/onground_any", "min": 0.5, "max": 1.5}}],
            },
            {
                "kind": "rumble", "id": "flaps", "preset": "flap_buffet",
                "dataref": "sim/cockpit2/controls/flap_ratio",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 0.10}}],
                "gate": [{"kind": "when", "options": {"key": "sim/flightmodel/position/indicated_airspeed", "min": 100.0, "max": 999.0}}],
            },
            {
                # "Parked with the engine running, a steady low rumble" -
                # the on-ground flag itself is the trigger, no separate gate
                # needed.
                "kind": "rumble", "id": "engine", "preset": "engine_rumble",
                "dataref": "sim/flightmodel/failures/onground_any",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 0.10}}],
            },
        ],
    },
    "b777_tony": {
        "device": "moza_a210",
        "name": "Boeing 777-300ER",
        # See b737_max_tony's own physics-block comment - same bus-voltage-
        # threshold gate (catches either APU or engine generator), same
        # reasoning.
        "physics": {
            "spring_gain": {
                "dataref": "sim/cockpit2/electrical/bus_volts",
                "curve": [{"kind": "scale", "options": {"in_min": 26.0, "in_max": 27.0, "out_min": 0.0, "out_max": 0.5}}],
            },
            "damper": {
                "dataref": "sim/cockpit2/electrical/bus_volts",
                "curve": [{"kind": "scale", "options": {"in_min": 26.0, "in_max": 27.0, "out_min": 0.0, "out_max": 1.0}}],
            },
            "inertia": {
                "dataref": "sim/cockpit2/electrical/bus_volts",
                "curve": [{"kind": "scale", "options": {"in_min": 26.0, "in_max": 27.0, "out_min": 0.0, "out_max": 1.0}}],
            },
            "friction": 0.0,
            "overall_intensity": 1.0,
            "max_torque": 1.0,
        },
        "effects": [
            {
                # See b737_max_tony's own pitch_spring comment - baseline
                # hydraulic feel-unit floor once powered, gated the same way.
                "kind": "spring", "id": "pitch_spring", "axis": "pitch",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "deadband": 0.05,
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 200.0, "out_min": 0.4, "out_max": 1.0}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/cockpit2/electrical/bus_volts", "min": 26.0, "max": 999.0}}],
            },
            {
                # See b737_max_tony's own roll_spring comment - no preset
                # this session bound anything to the roll axis until real
                # live-flight testing surfaced it; same baseline-floor fix.
                "kind": "spring", "id": "roll_spring", "axis": "roll",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "deadband": 0.05,
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 200.0, "out_min": 0.4, "out_max": 1.0}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/cockpit2/electrical/bus_volts", "min": 26.0, "max": 999.0}}],
            },
            {
                # See b737_max_tony's own roll_follow comment - same gap,
                # same fix, same reasoning.
                "kind": "trim", "id": "roll_follow", "axis": "roll",
                "dataref": "sim/cockpit2/controls/aileron_trim",
                "curve": [
                    {"kind": "scale", "options": {"in_min": -1.0, "in_max": 1.0, "out_min": -0.3, "out_max": 0.3}},
                ],
            },
            {
                # 100% - Tony's own stall_buffet_strength for this jet, a
                # heavier buffet than the 737's 20%. Rate-limited too, since
                # a full-strength buffet stepping raggedly tick to tick
                # would feel like chatter rather than a buffet.
                "kind": "rumble", "id": "stall", "preset": "stall_buffet",
                "dataref": "sim/cockpit2/annunciators/stall_warning",
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 1.0}},
                    {"kind": "ratelimit", "options": {"per_second": 12.0}},
                ],
            },
            {
                "kind": "rumble", "id": "runway", "preset": "runway_rumble",
                "dataref": "sim/flightmodel/position/groundspeed",
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 30.0, "out_min": 0.0, "out_max": 1.0}},
                    {"kind": "ratelimit", "options": {"per_second": 8.0}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/flightmodel/failures/onground_any", "min": 0.5, "max": 1.5}}],
            },
            {
                # In-flight, gear-extended buffet rather than taxi bumps -
                # a heavier long-haul jet's gear buffet in flight is the
                # more notable feel, unlike the 737 profile's taxi-bump
                # choice for the same Tony field.
                "kind": "rumble", "id": "gear", "preset": "gear_buffet",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "curve": [{"kind": "scale", "options": {"in_min": 100.0, "in_max": 250.0, "out_min": 0.10, "out_max": 0.0}}],
            },
            {
                "kind": "rumble", "id": "flaps", "preset": "flap_buffet",
                "dataref": "sim/cockpit2/controls/flap_ratio",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 0.10}}],
                "gate": [{"kind": "when", "options": {"key": "sim/flightmodel/position/indicated_airspeed", "min": 100.0, "max": 999.0}}],
            },
            {
                "kind": "rumble", "id": "engine", "preset": "engine_rumble",
                "dataref": "sim/flightmodel/failures/onground_any",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 0.10}}],
            },
            {
                # 100%, enabled - unlike the 737 profile, where Tony left
                # speedbrake_buffet disabled entirely (respected there by
                # omitting the effect, not by setting it to 0).
                "kind": "rumble", "id": "speedbrake", "preset": "spoiler_buffet",
                "dataref": "sim/cockpit2/controls/speedbrake_ratio",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 1.0}}],
            },
        ],
    },
    # Built from three real captures, not the owner-supplied-numbers path the
    # two Tony jets used (no MOZA Cockpit profile exists for this add-on -
    # that is the actual reason this whole engine exists): "GearBumps_AB6.
    # pcapng" and "RunwayRumble_AB6.pcapng" independently confirm the exact
    # same channel/frequency_code/magnitude already in RUMBLE_PRESETS
    # (runway_rumble's captured peak was 6881 - an exact match; gear_bumps'
    # was 3766 against a recorded 3734, ~1% off) - captured against the AB6,
    # which uses channel 4 for both instead of the AY210's channel 7, so only
    # the channel-independent frequency_code/magnitude carried over, not the
    # channel number itself (this device's own mapping stays separate, see
    # moza_ab6_calibration_notes.md). A third ~51-minute "real flight take
    # off-auto pilot.pcapng" capture of an actual Airfoillabs C172 NG Digital
    # flight was checked for live spring/rumble/trim traffic and found none -
    # whatever was connected during that flight opened only the AY210's
    # serial/CDC channel (heartbeat + one stray gain-param write) and never
    # the raw HID report interface these effects ride on, meaning nothing
    # drove this aircraft's own dynamic FFB during that session. So the
    # physics block and effect selection below are reasoned from the
    # airframe's real characteristics, not transcribed from a capture: a
    # fixed-gear single with unboosted cable controls should feel light and
    # crisp, not damped like a boosted airliner, so damper/inertia/spring_gain
    # sit well below the Tony jets' values; there is no retractable gear or
    # speedbrake to buffet, so gear_buffet/spoiler_buffet are omitted
    # entirely rather than zeroed; and the piston engine's idle vibration
    # carries into the airframe far more than a jet's, so engine_rumble sits
    # higher instead.
    "c172ng_airfoillabs": {
        "device": "moza_a210",
        "name": "Cessna 172 NG Digital (Airfoillabs)",
        # spring_gain/damper/inertia were briefly gated on engine-running,
        # on the theory that a fully mechanical, cable-driven yoke like this
        # airframe's should go loose whenever it isn't "really flying." That
        # theory doesn't survive contact with how a cable-actuated control
        # system actually works: the mechanical resistance of the cables,
        # pulleys, and control column itself doesn't come from the engine at
        # all, so it doesn't disappear just because the engine is off - a
        # real C172's yoke feels the same, engine running or not, parked or
        # not. Only the AERODYNAMIC loading changes with the engine/airspeed,
        # and that's already handled entirely separately, below, by
        # pitch_spring/roll_spring's own airspeed-driven curves. So these
        # three stay plain static constants, same as every other airframe's
        # baseline mechanical feel in this file.
        "physics": {
            "spring_gain": 0.35,
            "damper": 0.25,
            "inertia": 0.25,
            "friction": 0.0,
            "overall_intensity": 1.0,
            "max_torque": 1.0,
            "friction_compensation": 0.0,
        },
        # Every effect this hardware can do that actually applies to this
        # airframe is wired below, built and verified live during a real
        # flight (not just at a desk), including two rounds of live
        # correction (engine was originally gated on onground_any, a wrong
        # stand-in for "running"; turbulence was first skipped, believing
        # array-typed datarefs weren't readable - both wrong, both fixed
        # live, see their own comments below). Three from RUMBLE_PRESETS are
        # still deliberately left out, not forgotten:
        #   - gear_buffet / spoiler_buffet: this airframe has fixed gear and
        #     no speedbrakes, so neither condition can ever occur.
        #   - reverse_rumble: fixed-pitch prop, no thrust reversers.
        #   - mach_buffet: this airframe never approaches transonic speed.
        #   - constant_force (g_force): confirmed on real hardware this
        #     session to conflict with spring/trim - trips the firmware's own
        #     "more than one spring force" warning - so it is not
        #     combinable with the spring/trim effects below at all.
        "effects": [
            {
                # Same shape as the jets' pitch spring, but in_max follows
                # this airframe's own Vne (~163 KIAS for the NG Digital)
                # rather than a jet's, so the ramp actually spans the speeds
                # this aircraft flies instead of maxing out around Vr.
                # out_min was originally 0.1 (copied from the jets' own
                # curve, which never got reconsidered for this airframe) -
                # wrong for a fully mechanical, unboosted control system:
                # this airframe's yoke stiffness comes entirely from
                # aerodynamic loading (dynamic pressure), not from any
                # electric/hydraulic assist, so at zero airspeed it should
                # be completely loose, not held at a 10% floor. Confirmed
                # live as a "still stiff with the engine off" complaint,
                # unrelated to autopilot/trim at all - purely this floor.
                "kind": "spring", "id": "pitch_spring", "axis": "pitch",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "deadband": 0.05,
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 160.0, "out_min": 0.0, "out_max": 1.0}},
                ],
            },
            {
                # Confirmed missing live, mid-flight: turning the yoke left
                # or right produced no felt force at all, since no preset
                # this session bound anything to the roll axis - pitch was
                # the only one ever wired. Same airspeed curve as pitch,
                # including the out_min=0.0 fix - see pitch_spring's comment.
                "kind": "spring", "id": "roll_spring", "axis": "roll",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "deadband": 0.05,
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 160.0, "out_min": 0.0, "out_max": 1.0}},
                ],
            },
            {
                # Repurposes the same CP-Offset trim mechanism physically
                # confirmed earlier this session (a fixed one-time shift the
                # yoke passively returns to) - driven live instead of set
                # once, it continuously re-centers on wherever the autopilot
                # is currently commanding, so the physical yoke is pulled
                # toward it in real time. This is the actual answer to "I
                # should see the yoke moving": this hardware has no true
                # position servo (everything reverse-engineered this session
                # is a force/resistance effect, never an absolute-position
                # command), so a live trim pull is the closest real
                # approximation available.
                #
                # Three rounds of live-flight correction went into this
                # exact shape:
                #   1. sim/cockpit2/controls/yoke_pitch_ratio/yoke_roll_ratio
                #      seemed like the obvious dataref, but this airframe's
                #      own autopilot drives the control surfaces directly
                #      and never moves that dataref at all - confirmed live
                #      by watching wing1l_elv1def/wing2r_ail1def move
                #      substantially while yoke_*_ratio stayed near zero
                #      during a real autopilot turn. Switched to the real
                #      surface-deflection datarefs below.
                #   2. Full +-1.0 output felt exaggerated; settled on +-0.3
                #      after several live rounds of turning it down.
                #   3. With autopilot OFF, surface deflection is driven by
                #      the pilot's own hand on this same physical yoke -
                #      without a gate, that closes a feedback loop (a small
                #      hand movement reads as "input", pulls the yoke, which
                #      changes the reading again), confirmed live as a rapid
                #      flip between this curve's own -0.3/+0.3 extremes with
                #      autopilot disengaged. Gating on servos_on breaks the
                #      loop: this effect goes fully quiet the instant the
                #      autopilot lets go, and only pulls while it actually
                #      has control.
                # A fourth live round after those three: even correctly
                # gated on servos_on, a real autopilot is never perfectly
                # still - it is constantly making small corrective
                # aileron/elevator nudges even in level cruise, and every
                # one of those was translating directly into a felt trim
                # pull, reading as a continuous shake rather than a
                # deliberate turn. Confirmed live as "shakes all the time
                # in normal cruise" with no stall or turbulence present.
                # A deadzone stage (chains.py's own docstring: "Gating alone
                # would leave a jittering axis writing small non-zero values
                # forever") filters that noise out; because deadzone's own
                # rescaling assumes a normalized +-1 input, it sits between
                # two scale stages - the first normalizes this effect's own
                # raw units to +-1, the second brings the post-deadzone
                # +-1 back down to the actual trim range.
                #
                # A fifth round found a deeper problem with using *surface
                # deflection* at all: it only shows a real signal while a
                # control is actively being moved to change bank/pitch, not
                # while a bank or climb is being held - a stabilized,
                # coordinated turn needs only a small sustained aileron
                # input (often near zero) to hold a constant bank angle,
                # aerodynamically, so surface deflection is silent during
                # exactly the sustained part of a turn that makes it
                # "obvious." Confirmed live as an obvious, sustained turn
                # producing no felt pull at all. Switched to attitude
                # instead of control input: sim/flightmodel/position/phi
                # (bank angle) directly reflects the aircraft's own current
                # state throughout a whole turn, not just its onset. Pitch
                # could not use the equivalent sim/flightmodel/position/
                # theta the same way - unlike bank angle, which is genuinely
                # near zero for nearly all of normal flight, pitch attitude
                # is *never* naturally near zero (a C172 cruises a few
                # degrees nose-up even in level, unaccelerated flight), so
                # raw theta would keep a permanent nonzero pull the whole
                # flight. sim/flightmodel/position/vh_ind_fpm (vertical
                # speed) reads near zero in level flight regardless of
                # pitch attitude, and only shows a real signal during an
                # actual climb or descent - the true pitch equivalent of
                # "near zero except when actually maneuvering."
                "kind": "trim", "id": "pitch_follow", "axis": "pitch",
                "dataref": "sim/flightmodel/position/vh_ind_fpm",
                "curve": [
                    {"kind": "scale", "options": {"in_min": -800.0, "in_max": 800.0, "out_min": -1.0, "out_max": 1.0}},
                    {"kind": "deadzone", "options": {"threshold": 0.15}},
                    {"kind": "scale", "options": {"in_min": -1.0, "in_max": 1.0, "out_min": -0.3, "out_max": 0.3}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/cockpit2/autopilot/servos_on", "min": 0.5, "max": 1.5}}],
            },
            {
                # See pitch_follow's own comment for the full story behind
                # this dataref choice, scale, gate, and deadzone - bank
                # angle (unlike pitch attitude) genuinely sits near zero for
                # almost all of normal flight, so it needed no vertical-
                # speed-style substitution, just the switch away from raw
                # aileron surface deflection.
                "kind": "trim", "id": "roll_follow", "axis": "roll",
                "dataref": "sim/flightmodel/position/phi",
                "curve": [
                    {"kind": "scale", "options": {"in_min": -30.0, "in_max": 30.0, "out_min": -1.0, "out_max": 1.0}},
                    {"kind": "deadzone", "options": {"threshold": 0.15}},
                    {"kind": "scale", "options": {"in_min": -1.0, "in_max": 1.0, "out_min": -0.3, "out_max": 0.3}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/cockpit2/autopilot/servos_on", "min": 0.5, "max": 1.5}}],
            },
            {
                # Driven by angle of attack rather than the binary
                # stall_warning flag every other preset this session used -
                # a real approach-to-stall buffet builds gradually as flow
                # separation begins well before the actual stall, not as a
                # step function, and this doubles as the "slow speed live
                # feedback" the owner asked for (the same effect gets
                # stronger as AoA rises at low speed, exactly when it should
                # be felt). 10-16 degrees is a reasoned estimate for this
                # airframe's own clean-configuration critical AoA (~15-16
                # degrees), not a captured measurement.
                "kind": "rumble", "id": "stall", "preset": "stall_buffet",
                "dataref": "sim/flightmodel/position/alpha",
                "curve": [{"kind": "scale", "options": {"in_min": 10.0, "in_max": 16.0, "out_min": 0.0, "out_max": 0.30}}],
            },
            {
                # Captured peak (6881) is an exact match for
                # RUMBLE_PRESETS["runway_rumble"]["reference_magnitude"] -
                # this row's own curve just decides how groundspeed reaches
                # that confirmed peak, not the peak itself.
                "kind": "rumble", "id": "runway", "preset": "runway_rumble",
                "dataref": "sim/flightmodel/position/groundspeed",
                "curve": [
                    {"kind": "scale", "options": {"in_min": 0.0, "in_max": 25.0, "out_min": 0.0, "out_max": 1.0}},
                    {"kind": "ratelimit", "options": {"per_second": 8.0}},
                ],
                "gate": [{"kind": "when", "options": {"key": "sim/flightmodel/failures/onground_any", "min": 0.5, "max": 1.5}}],
            },
            {
                # "Gear bumps" here means wheel/ground-contact bumps while
                # rolling, not retraction motion - this airframe's gear is
                # fixed and never moves, so that reading is the only one
                # that applies. Captured peak (3766) matches the existing
                # reference_magnitude (3734) to within about 1%. Raised from
                # 0.15 to 0.25 (see engine's own comment below) so ground
                # texture stays the clearly dominant feel over idle engine
                # hum, not a similar or weaker one.
                "kind": "rumble", "id": "taxi_bumps", "preset": "gear_bumps",
                "dataref": "sim/flightmodel/position/groundspeed",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 15.0, "out_min": 0.0, "out_max": 0.25}}],
                "gate": [{"kind": "when", "options": {"key": "sim/flightmodel/failures/onground_any", "min": 0.5, "max": 1.5}}],
            },
            {
                # A light single on thin tires transmits far more brake
                # shudder into the airframe than a heavy jet on oleo struts
                # does - only the left toe brake is read since most pilots
                # brake with both feet together, but either foot alone still
                # produces the real mechanism this models. Originally gated
                # on-ground alone, which meant a parked aircraft sitting
                # still with the parking brake set would shudder just from
                # the pedal/lever being held - confirmed live as wrong: real
                # brake shudder comes from the disc/wheel interaction while
                # actually rolling and decelerating, not from a static hold.
                # A second "when" stage requiring genuine groundspeed fixes
                # it - chains.py's "when" stages AND together in a gate list
                # (each independently passes or drops the event; only
                # dropped if every stage agrees), so this is additive, not a
                # separate mechanism.
                "kind": "rumble", "id": "brakes", "preset": "brake_shudder",
                "dataref": "sim/cockpit2/controls/left_brake_ratio",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 0.20}}],
                "gate": [
                    {"kind": "when", "options": {"key": "sim/flightmodel/failures/onground_any", "min": 0.5, "max": 1.5}},
                    {"kind": "when", "options": {"key": "sim/flightmodel/position/groundspeed", "min": 2.0, "max": 999.0}},
                ],
            },
            {
                # A direct-linkage nosewheel (no hydraulic damping, unlike a
                # jet's steering) is the classic case for shimmy. 5-25 kt is
                # a reasoned taxi-speed-band estimate, not a measured trigger
                # speed - no capture this session caught shimmy in progress.
                "kind": "rumble", "id": "nosewheel", "preset": "nosewheel_shimmy",
                "dataref": "sim/flightmodel/position/groundspeed",
                "curve": [{"kind": "scale", "options": {"in_min": 5.0, "in_max": 25.0, "out_min": 0.0, "out_max": 0.12}}],
                "gate": [{"kind": "when", "options": {"key": "sim/flightmodel/failures/onground_any", "min": 0.5, "max": 1.5}}],
            },
            {
                # 150 KIAS to this airframe's own ~163 KIAS Vne - a real
                # structural warning cue as the red line approaches.
                "kind": "rumble", "id": "overspeed", "preset": "overspeed_buffet",
                "dataref": "sim/flightmodel/position/indicated_airspeed",
                "curve": [{"kind": "scale", "options": {"in_min": 150.0, "in_max": 163.0, "out_min": 0.0, "out_max": 0.30}}],
            },
            {
                # No airspeed gate: the jets gated this above 100 KIAS
                # (a high-speed flap-extended buffet), but this airframe's
                # own flap speeds top out well under 110 KIAS, so that gate
                # would never open here. Driven by flap position alone.
                "kind": "rumble", "id": "flaps", "preset": "flap_buffet",
                "dataref": "sim/cockpit2/controls/flap_ratio",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 0.12}}],
            },
            {
                # Higher than the jets' 10%: a four-cylinder piston at idle
                # puts far more felt vibration through a light airframe than
                # a turbine ever does. Originally gated on onground_any
                # (a stand-in for "engine running" that was wrong: it fired
                # whenever parked, engine on or off, and stayed silent
                # in flight) - corrected live to actual RPM, confirmed
                # resolving correctly (sim/cockpit2/engine/indicators/
                # engine_speed_rpm is a float_array; read_dataref()'s REST
                # fallback already takes element [0] via unwrap_value(), so
                # array datarefs work today - the "arrays aren't supported"
                # note that used to justify skipping turbulence below was
                # wrong and has been corrected).
                #
                # Two more live rounds after that: "preset" here is only a
                # lookup key into RUMBLE_PRESETS (channel + frequency_code +
                # reference_magnitude), completely independent of this
                # effect's own "id"/dataref/curve - engine_rumble's own
                # (channel 7, freq 30) was never physically confirmed on
                # this hardware before tonight and turned out too weak to
                # feel even at a real, non-trivial magnitude (confirmed via
                # live USB capture: the actual wire bytes matched the
                # computed gain exactly, ruling out a software bug), while
                # brake_shudder's (channel 7, freq 110) was independently
                # confirmed strong and clear the same session - reusing it
                # here for genuinely stronger felt vibration. And out_min
                # was 0.05 (a nonzero floor even at 0 RPM), which meant the
                # engine effect could never go fully silent when shut down -
                # confirmed live as vibration that persisted after shutdown.
                #
                # out_max came down again after that, from 0.65 to 0.18:
                # once cranking (below) and the ground-texture effects above
                # were both working, idle/running engine hum at 0.65 read as
                # comparable to or louder than runway/taxi bumps despite
                # being the background layer, not the main feel - confirmed
                # live as "should vibrate less once running, and only
                # vibrate more for an actual runway/wheel/grass/gravel
                # bump." Ground texture should clearly dominate; the engine
                # should be a felt-but-subtle hum underneath it.
                "kind": "rumble", "id": "engine", "preset": "brake_shudder",
                "dataref": "sim/cockpit2/engine/indicators/engine_speed_rpm",
                "curve": [{"kind": "scale", "options": {"in_min": 200.0, "in_max": 2700.0, "out_min": 0.0, "out_max": 0.18}}],
            },
            {
                # RPM alone leaves the starter-cranking phase silent (RPM
                # typically stays under the "engine" effect's own 200 RPM
                # floor while cranking, before the engine actually catches),
                # but a real crank is felt through the airframe regardless
                # of whether it's turning fast enough to register as
                # "running" yet. sim/flightmodel2/engines/starter_is_running
                # is a clean boolean (int_array, element [0]) for exactly
                # this - independent of RPM entirely, so it fires the
                # instant the starter engages and stops the instant it
                # releases (whether the engine catches or not).
                "kind": "rumble", "id": "cranking", "preset": "brake_shudder",
                "dataref": "sim/flightmodel2/engines/starter_is_running",
                "curve": [{"kind": "scale", "options": {"in_min": 0.0, "in_max": 1.0, "out_min": 0.0, "out_max": 0.6}}],
            },
            {
                # sim/weather/aircraft/turbulence is a 13-element float_array;
                # confirmed live that it resolves the same way engine RPM
                # does. 0.03-0.3 is a reasoned range from what a calm flight
                # actually read (~0.02-0.03) - no capture this session caught
                # strong turbulence to calibrate the true ceiling against.
                "kind": "rumble", "id": "turbulence", "preset": "turbulence",
                "dataref": "sim/weather/aircraft/turbulence",
                "curve": [{"kind": "scale", "options": {"in_min": 0.03, "in_max": 0.3, "out_min": 0.0, "out_max": 0.4}}],
            },
        ],
    },
}


def preset(name: str) -> FfbProfile:
    if name not in PRESETS:
        raise FfbProfileError(f"unknown preset {name!r}")
    return build_profile(PRESETS[name], name_hint=name)


__all__ = (
    "MSLM_SCHEMA", "ALLOWED_DEVICES", "ALLOWED_AXES", "RUMBLE_PRESET_NAMES",
    "FfbProfileError", "EffectOption", "EffectSpec", "EFFECT_SPECS", "EFFECT_BY_KIND",
    "PHYSICS_FIELD_DEFAULTS", "PhysicsSetting",
    "Effect", "FfbProfile", "build_profile",
    "FfbProfileStore", "default_ffb_profile_dir",
    "load_active_profile_name", "save_active_profile_name", "default_active_profile_path",
    "PRESETS", "preset",
)
