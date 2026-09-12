"""Chained input shaping between a physical control and its mapping.

The profile store answers "what does this control do?" with a single binding:
one command, one dataref, or one registered action.  That is exactly right for
a switch and exactly wrong for a wheel.  A detent that fires one command is
either too coarse to fly with or too fine to spin, and neither the FCU's
altitude knob nor a course wheel is comfortable without shaping in between.

A chain sits between the lab's routed edge and the bridge's binding sink.  It
takes one physical event and produces zero or more emissions, each carrying a
value, a phase and a repeat count.  Nothing in this module knows what a
command is, which simulator is running, or whether hardware is attached.

Additive by construction.  Importing this file changes nothing: it becomes
live only when a caller wraps its own binding sink with `wrap_binding_sink`,
which is one line and reversible.  With no chain configured for a control, an
event passes through byte for byte, so an unconfigured rig behaves exactly as
it does today.

Two conventions are assumed and validated rather than guessed:

  * an axis arrives normalised, either 0.0..1.0 or -1.0..+1.0;
  * a rotary arrives as a signed pulse count, usually -1.0 or +1.0 per detent.

Anything else should be scaled at the device driver, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple
import json
import os
import tempfile
import time

CHAIN_SCHEMA = 1


class ChainError(ValueError):
    """A chain was built from stages or options that cannot be honoured."""


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Emission:
    """One outbound event.

    `repeat` is how many times the binding should be applied.  A wheel spun
    quickly produces one emission with a repeat of eight rather than eight
    emissions, so a caller can send a single burst instead of eight round
    trips through a web API.
    """

    value: float
    phase: str = "change"
    repeat: int = 1

    def as_dict(self) -> Dict[str, Any]:
        return {"value": self.value, "phase": self.phase, "repeat": self.repeat}


class ChainContext:
    """What a conditional stage is allowed to look at.

    Deliberately tiny.  A stage may read another control's last value and the
    set of active layers; it may not read the simulator, the catalogue, or the
    profile store, because a shaping stage that can reach those becomes
    impossible to test offline.
    """

    def __init__(self, values: Optional[Callable[[str], Optional[float]]] = None) -> None:
        self._values = values
        self.layers: Dict[str, bool] = {}

    def value(self, key: str) -> Optional[float]:
        if key.startswith("layer:"):
            return 1.0 if self.layers.get(key[6:], False) else 0.0
        if self._values is None:
            return None
        try:
            return self._values(key)
        except Exception:
            return None


# --------------------------------------------------------------------------
# Stage options, declared so a form can be generated rather than written
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StageOption:
    name: str
    label: str
    kind: str = "float"          # float | int | bool | text | choice
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
                raise ChainError(f"{self.name} must be a number") from exc
            if self.minimum is not None and number < self.minimum:
                raise ChainError(f"{self.name} must be at least {self.minimum}")
            if self.maximum is not None and number > self.maximum:
                raise ChainError(f"{self.name} must be at most {self.maximum}")
            return int(round(number)) if self.kind == "int" else number
        if self.kind == "choice":
            text = str(value)
            if text not in self.choices:
                raise ChainError(f"{self.name} must be one of {', '.join(self.choices)}")
            return text
        return str(value)


@dataclass(frozen=True)
class StageSpec:
    kind: str
    label: str
    applies_to: Tuple[str, ...]      # catalogue control kinds this suits
    summary: str
    options: Tuple[StageOption, ...] = ()
    needs_tick: bool = False


# --------------------------------------------------------------------------
# Stage implementations
#
# Every stage has the same signature so the runner stays a plain loop:
#     fn(state, options, event, now, context) -> list[Emission]
# `state` is a mutable dict private to this (device, control, stage index).
# --------------------------------------------------------------------------


def _st_deadzone(state, o, ev, now, ctx):
    """Ignore travel near centre, and rescale the rest to full range.

    Gating alone would leave a jittering axis writing small non-zero values
    forever; rescaling means the stick still reaches its endpoints.
    """
    t = float(o["threshold"])
    if abs(ev.value) <= t:
        return [replace(ev, value=0.0)]
    sign = 1.0 if ev.value > 0 else -1.0
    return [replace(ev, value=sign * (abs(ev.value) - t) / (1.0 - t))]


def _st_invert(state, o, ev, now, ctx):
    if o["mode"] == "unit":                 # 0..1 travel
        return [replace(ev, value=1.0 - ev.value)]
    return [replace(ev, value=-ev.value)]   # -1..+1 travel


def _st_scale(state, o, ev, now, ctx):
    span = (float(o["in_max"]) - float(o["in_min"])) or 1.0
    x = (ev.value - float(o["in_min"])) / span
    if o["clamp"]:
        x = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
    return [replace(ev, value=float(o["out_min"]) + x * (float(o["out_max"]) - float(o["out_min"])))]


def _st_curve(state, o, ev, now, ctx):
    """Expo shaping.  Above 1.0 softens the centre; below 1.0 sharpens it."""
    g = float(o["gamma"])
    sign = 1.0 if ev.value >= 0 else -1.0
    return [replace(ev, value=sign * (abs(ev.value) ** g))]


def _st_quantize(state, o, ev, now, ctx):
    step = float(o["step"])
    return [replace(ev, value=round(ev.value / step) * step)]


def _st_accumulate(state, o, ev, now, ctx):
    """Sum encoder pulses and emit whole detents only.

    A wheel reporting four pulses per physical click becomes one emission per
    click.  The remainder is carried rather than discarded, so slow turning
    never loses travel.
    """
    step = float(o["step"])
    total = state.get("sum", 0.0) + ev.value
    whole = int(total / step)
    state["sum"] = total - whole * step
    if whole == 0:
        return []
    sign = 1.0 if whole > 0 else -1.0
    return [replace(ev, value=sign, repeat=ev.repeat * abs(whole))]


def _st_accelerate(state, o, ev, now, ctx):
    """Spin faster, step coarser -- what a real FCU knob does.

    An interval at or below `fast_ms` earns the full multiplier; at or above
    `slow_ms` the wheel is treated as deliberate and nothing is multiplied.
    """
    fast = float(o["fast_ms"]) / 1000.0
    slow = float(o["slow_ms"]) / 1000.0
    top = float(o["max_multiplier"])
    last = state.get("t")
    state["t"] = now

    if last is None:
        return [ev]

    dt = now - last
    if dt <= fast:
        mult = top
    elif dt >= slow:
        mult = 1.0
    else:
        fraction = (dt - fast) / ((slow - fast) or 1.0)
        mult = top + (1.0 - top) * fraction

    return [replace(ev, repeat=max(1, int(round(ev.repeat * mult))))]


def _st_direction_hold(state, o, ev, now, ctx):
    """Reject a stray reverse pulse during a fast spin.

    Inexpensive encoders bounce a detent backwards.  A reversal only takes
    effect after `reversals` consecutive pulses the other way, or once the
    wheel has been still for `settle_ms` -- so a genuine change of direction
    is never blocked, only a single bad pulse is.
    """
    need = int(o["reversals"])
    settle = float(o["settle_ms"]) / 1000.0

    sign = 1 if ev.value > 0 else -1 if ev.value < 0 else 0
    if sign == 0:
        return [ev]

    last_t = state.get("t")
    state["t"] = now
    current = state.get("dir", 0)

    if current == 0 or last_t is None or (now - last_t) >= settle:
        state["dir"], state["run"] = sign, 0
        return [ev]

    if sign == current:
        state["run"] = 0
        return [ev]

    state["run"] = state.get("run", 0) + 1
    if state["run"] >= need:
        state["dir"], state["run"] = sign, 0
        return [ev]
    return []


def _st_debounce(state, o, ev, now, ctx):
    gap = float(o["ms"]) / 1000.0
    last = state.get("t")
    if last is not None and (now - last) < gap:
        state["dropped"] = state.get("dropped", 0) + 1
        return []
    state["t"] = now
    return [ev]


def _st_latch(state, o, ev, now, ctx):
    """A momentary button drives a sticky state.

    Only the press edge flips it and the release is swallowed, so the mapping
    downstream sees one clean change rather than two.
    """
    if ev.phase == "release":
        return []
    if ev.phase == "change" and ev.value <= 0.0:
        return []
    on = not bool(state.get("on", False))
    state["on"] = on
    return [replace(ev, value=1.0 if on else 0.0, phase="change")]


def _st_tap(state, o, ev, now, ctx):
    """Split one button into a short tap and a long hold.

    The emission's phase becomes `tap` or `hold`, so a single physical button
    can carry two mappings without a second button existing.
    """
    threshold = float(o["hold_ms"]) / 1000.0

    if ev.phase == "press":
        state["down"] = now
        return []
    if ev.phase != "release":
        return [ev]

    down = state.pop("down", None)
    if down is None:
        return []
    phase = "hold" if (now - down) >= threshold else "tap"
    return [replace(ev, value=1.0, phase=phase)]


def _st_repeat(state, o, ev, now, ctx):
    """Hold a button to repeat its action.

    Needs `ChainRuntime.tick()` to be called; without a tick loop nothing
    repeats and the press still works normally, which is the safe way for an
    optional feature to be absent.
    """
    if ev.phase == "press":
        state["due"] = now + float(o["delay_ms"]) / 1000.0
        state["interval"] = float(o["interval_ms"]) / 1000.0
        return [ev]
    if ev.phase == "release":
        state.pop("due", None)
        return []
    if ev.phase == "repeat":
        # The stage owns its own schedule.  If the tick loop set the next due
        # time instead, this pass would immediately overwrite it with the
        # stale one and every later tick would fire.
        state["due"] = now + float(o["interval_ms"]) / 1000.0
        return [ev]
    return [ev]


def _st_ratelimit(state, o, ev, now, ctx):
    """A ceiling on how often a control may reach the simulator.

    A wheel spun hard can otherwise queue hundreds of web writes that arrive
    long after the knob stopped moving.
    """
    per_second = float(o["per_second"])
    gap = 1.0 / per_second
    last = state.get("t")
    if last is not None and (now - last) < gap:
        state["dropped"] = state.get("dropped", 0) + 1
        return []
    state["t"] = now
    return [ev]


def _st_when(state, o, ev, now, ctx):
    """Pass only while another control or layer holds a value.

    This is how two mappings chain without either knowing about the other: a
    mode selector decides whether a wheel writes at all, and neither binding
    is changed to make that true.
    """
    observed = ctx.value(str(o["key"]))
    if observed is None:
        return [] if o["require_known"] else [ev]

    low, high = float(o["min"]), float(o["max"])
    inside = low <= observed <= high
    return [ev] if inside != bool(o["invert"]) else []


def _st_layer(state, o, ev, now, ctx):
    """This control raises a named layer, turning one panel into two.

    `hold` keeps the layer up while the button is down; `toggle` flips it on
    each press.  Other controls then gate on `layer:NAME` through `when`.
    """
    name = str(o["name"])

    if o["mode"] == "hold":
        if ev.phase == "press" or (ev.phase == "change" and ev.value > 0):
            ctx.layers[name] = True
        elif ev.phase == "release" or (ev.phase == "change" and ev.value <= 0):
            ctx.layers[name] = False
    else:
        if ev.phase == "release":
            return [] if o["swallow"] else [ev]
        ctx.layers[name] = not ctx.layers.get(name, False)

    return [] if o["swallow"] else [ev]


def _st_pickup(state, o, ev, now, ctx):
    """An axis must cross the value it is taking over before it writes.

    The same rule the bridge already applies to the throttle and the pedals,
    available to any axis without that axis having its own implementation.
    """
    if state.get("armed"):
        return [ev]

    reference = ctx.value(str(o["reference"]))
    if reference is None:
        return [] if o["require_known"] else [ev]

    last = state.get("last")
    state["last"] = ev.value
    if last is None:
        return []

    if (last - reference) * (ev.value - reference) <= 0.0:
        state["armed"] = True
        return [ev]
    return []


# --------------------------------------------------------------------------
# The registry.  Adding a stage is one function and one entry.
# --------------------------------------------------------------------------


STAGE_SPECS: Tuple[StageSpec, ...] = (
    StageSpec("deadzone", "Dead zone", ("axis",),
              "Ignore travel near centre and rescale the rest to full range.",
              (StageOption("threshold", "Threshold", "float", 0.02, 0.0, 0.9),)),

    StageSpec("invert", "Invert", ("axis", "rotary"),
              "Reverse the direction of travel.",
              (StageOption("mode", "Travel", "choice", "sign", choices=("sign", "unit")),)),

    StageSpec("scale", "Scale", ("axis", "rotary"),
              "Map an input range onto an output range.",
              (StageOption("in_min", "Input min", "float", 0.0),
               StageOption("in_max", "Input max", "float", 1.0),
               StageOption("out_min", "Output min", "float", 0.0),
               StageOption("out_max", "Output max", "float", 1.0),
               StageOption("clamp", "Clamp to range", "bool", True))),

    StageSpec("curve", "Curve", ("axis",),
              "Soften or sharpen the centre of an axis.",
              (StageOption("gamma", "Gamma", "float", 1.5, 0.1, 6.0),)),

    StageSpec("quantize", "Quantise", ("axis", "rotary"),
              "Snap the value to a step.",
              (StageOption("step", "Step", "float", 0.05, 0.0001, 1000.0),)),

    StageSpec("accumulate", "Accumulate detents", ("rotary",),
              "Sum encoder pulses and emit whole detents, carrying the remainder.",
              (StageOption("step", "Pulses per detent", "float", 1.0, 0.0001, 64.0),)),

    StageSpec("accelerate", "Acceleration", ("rotary",),
              "Spin faster, step coarser -- what a real knob does.",
              (StageOption("fast_ms", "Fast interval (ms)", "float", 30.0, 1.0, 1000.0),
               StageOption("slow_ms", "Slow interval (ms)", "float", 220.0, 2.0, 5000.0),
               StageOption("max_multiplier", "Maximum multiplier", "float", 8.0, 1.0, 64.0))),

    StageSpec("direction_hold", "Reject bounce", ("rotary",),
              "Ignore a stray reverse pulse during a fast spin.",
              (StageOption("reversals", "Pulses to reverse", "int", 2, 1, 8),
               StageOption("settle_ms", "Settle (ms)", "float", 250.0, 10.0, 5000.0))),

    StageSpec("debounce", "Debounce", ("button", "toggle", "selector"),
              "Ignore edges arriving too close together.",
              (StageOption("ms", "Window (ms)", "float", 25.0, 1.0, 2000.0),)),

    StageSpec("latch", "Latch", ("button",),
              "A momentary button drives a sticky on/off state.",
              ()),

    StageSpec("tap", "Tap or hold", ("button",),
              "Split one button into a short tap and a long hold.",
              (StageOption("hold_ms", "Hold after (ms)", "float", 500.0, 80.0, 5000.0),)),

    StageSpec("repeat", "Hold to repeat", ("button",),
              "Repeat while the button is held. Needs the tick loop.",
              (StageOption("delay_ms", "First repeat after (ms)", "float", 400.0, 50.0, 5000.0),
               StageOption("interval_ms", "Then every (ms)", "float", 120.0, 20.0, 2000.0)),
              needs_tick=True),

    StageSpec("ratelimit", "Rate limit", ("axis", "rotary", "button", "toggle", "selector"),
              "A ceiling on how often this control may reach the simulator.",
              (StageOption("per_second", "Maximum per second", "float", 20.0, 0.5, 500.0),)),

    StageSpec("when", "Only when", ("axis", "rotary", "button", "toggle", "selector"),
              "Pass only while another control or layer holds a value.",
              (StageOption("key", "Watched key", "text", ""),
               StageOption("min", "At least", "float", 0.5),
               StageOption("max", "At most", "float", 1.5),
               StageOption("invert", "Invert the test", "bool", False),
               StageOption("require_known", "Block when unknown", "bool", True))),

    StageSpec("layer", "Layer modifier", ("button", "toggle"),
              "Raise a named layer so one panel covers two sets of actions.",
              (StageOption("name", "Layer name", "text", "shift"),
               StageOption("mode", "Behaviour", "choice", "hold", choices=("hold", "toggle")),
               StageOption("swallow", "Do not also run its own mapping", "bool", True))),

    StageSpec("pickup", "Pickup guard", ("axis",),
              "The axis must cross the value it is taking over before it writes.",
              (StageOption("reference", "Reference key", "text", ""),
               StageOption("require_known", "Block when unknown", "bool", True))),
)

_STAGE_FUNCTIONS: Dict[str, Callable[..., List[Emission]]] = {
    "deadzone": _st_deadzone,
    "invert": _st_invert,
    "scale": _st_scale,
    "curve": _st_curve,
    "quantize": _st_quantize,
    "accumulate": _st_accumulate,
    "accelerate": _st_accelerate,
    "direction_hold": _st_direction_hold,
    "debounce": _st_debounce,
    "latch": _st_latch,
    "tap": _st_tap,
    "repeat": _st_repeat,
    "ratelimit": _st_ratelimit,
    "when": _st_when,
    "layer": _st_layer,
    "pickup": _st_pickup,
}

STAGE_BY_KIND: Dict[str, StageSpec] = {spec.kind: spec for spec in STAGE_SPECS}


def stages_for(control_kind: str) -> Tuple[StageSpec, ...]:
    """The stages that suit one catalogue control kind.

    The editor's palette is built from this, so a stage that cannot apply is
    never offered and therefore never has to be refused.
    """
    return tuple(spec for spec in STAGE_SPECS if control_kind in spec.applies_to)


# --------------------------------------------------------------------------
# Chains
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage:
    kind: str
    options: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "options": dict(self.options)}


@dataclass(frozen=True)
class Chain:
    """An ordered set of stages for one control."""

    stages: Tuple[Stage, ...] = ()
    enabled: bool = True
    notes: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "notes": self.notes,
            "stages": [stage.as_dict() for stage in self.stages],
        }

    @property
    def needs_tick(self) -> bool:
        return any(STAGE_BY_KIND[stage.kind].needs_tick for stage in self.stages)

    def describe(self) -> str:
        """One line for a card, in the order the signal travels."""
        if not self.stages:
            return "no shaping"
        return " -> ".join(STAGE_BY_KIND[stage.kind].label.lower() for stage in self.stages)


def build_chain(stages: Iterable[Mapping[str, Any]], *, enabled: bool = True, notes: str = "") -> Chain:
    """Validate and freeze a chain.

    Every option is checked and filled here, so the runner never has to guess
    a default or handle a missing key, and a bad chain is refused with the
    reason rather than silently skipped.
    """
    built: List[Stage] = []
    for index, raw in enumerate(stages):
        kind = str(raw.get("kind", "")).strip()
        spec = STAGE_BY_KIND.get(kind)
        if spec is None:
            raise ChainError(f"stage {index + 1}: unknown kind {kind!r}")

        supplied = dict(raw.get("options") or {})
        unknown = set(supplied) - {option.name for option in spec.options}
        if unknown:
            raise ChainError(f"stage {index + 1} ({kind}): unknown option {sorted(unknown)[0]!r}")

        resolved: Dict[str, Any] = {}
        for option in spec.options:
            resolved[option.name] = option.clamp(supplied.get(option.name, option.default))

        if kind == "accelerate" and resolved["fast_ms"] >= resolved["slow_ms"]:
            raise ChainError("stage acceleration: fast interval must be shorter than slow interval")
        if kind == "when" and not str(resolved["key"]).strip():
            raise ChainError("stage only-when: a watched key is required")
        if kind == "pickup" and not str(resolved["reference"]).strip():
            raise ChainError("stage pickup guard: a reference key is required")
        if kind == "layer" and not str(resolved["name"]).strip():
            raise ChainError("stage layer: a layer name is required")

        built.append(Stage(kind, resolved))

    return Chain(tuple(built), bool(enabled), str(notes))


# --------------------------------------------------------------------------
# Runtime
# --------------------------------------------------------------------------


class ChainRuntime:
    """Runs chains and holds their per-control state.

    One instance per bridge run.  State is keyed by device, control and stage
    position, so re-ordering a chain in the editor cannot leave a stale
    accumulator behind on a stage that no longer sits there.
    """

    def __init__(
        self,
        chains: Optional[Mapping[Tuple[str, str], Chain]] = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        context: Optional[ChainContext] = None,
    ) -> None:
        self.chains: Dict[Tuple[str, str], Chain] = dict(chains or {})
        self.clock = clock
        self.context = context or ChainContext()
        self._state: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
        self._repeats: Dict[Tuple[str, str], Dict[str, float]] = {}

    # -- configuration ----------------------------------------------------

    def set_chain(self, device_key: str, control_key: str, chain: Optional[Chain]) -> None:
        key = (device_key, control_key)
        if chain is None:
            self.chains.pop(key, None)
        else:
            self.chains[key] = chain
        self.forget(device_key, control_key)

    def forget(self, device_key: str, control_key: Optional[str] = None) -> None:
        """Drop accumulated state, the way a device reset drops a baseline."""
        for state_key in list(self._state):
            if state_key[0] == device_key and (control_key is None or state_key[1] == control_key):
                del self._state[state_key]
        for repeat_key in list(self._repeats):
            if repeat_key[0] == device_key and (control_key is None or repeat_key[1] == control_key):
                del self._repeats[repeat_key]

    # -- running ----------------------------------------------------------

    def run(self, device_key: str, control_key: str, value: Any, phase: str = "change") -> List[Emission]:
        """One physical event in, zero or more emissions out."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 1.0 if value else 0.0

        events = [Emission(numeric, str(phase or "change"), 1)]
        chain = self.chains.get((device_key, control_key))
        if chain is None or not chain.enabled or not chain.stages:
            return events

        now = self.clock()
        for index, stage in enumerate(chain.stages):
            function = _STAGE_FUNCTIONS[stage.kind]
            state = self._state.setdefault((device_key, control_key, index), {})
            produced: List[Emission] = []
            for event in events:
                produced.extend(function(state, stage.options, event, now, self.context))

            if stage.kind == "repeat":
                self._arm_repeat(device_key, control_key, state)

            events = produced
            if not events:
                break

        return events

    def _arm_repeat(self, device_key: str, control_key: str, state: Mapping[str, Any]) -> None:
        key = (device_key, control_key)
        due = state.get("due")
        if due is None:
            self._repeats.pop(key, None)
        else:
            self._repeats[key] = {"due": float(due), "interval": float(state.get("interval", 0.12))}

    def tick(self) -> List[Tuple[str, str, Emission]]:
        """Fire any held-button repeats that have come due.

        Returns what should be emitted rather than emitting it, so a caller
        keeps ownership of the sink and this stays testable with a fake clock.
        """
        if not self._repeats:
            return []

        now = self.clock()
        fired: List[Tuple[str, str, Emission]] = []
        for (device_key, control_key), timing in list(self._repeats.items()):
            if now < timing["due"]:
                continue
            # The repeat stage advances its own due time as the event passes
            # through, so this loop only decides when to fire, never when next.
            for emission in self.run(device_key, control_key, 1.0, phase="repeat"):
                fired.append((device_key, control_key, emission))
        return fired

    # -- reporting --------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """What the panel shows about shaping, without exposing internals."""
        return {
            "chains": {
                f"{device}.{control}": chain.describe()
                for (device, control), chain in sorted(self.chains.items())
            },
            "layers": {name: bool(active) for name, active in sorted(self.context.layers.items())},
            "repeats_armed": sorted(f"{d}.{c}" for (d, c) in self._repeats),
            "dropped": {
                f"{key[0]}.{key[1]}": int(state["dropped"])
                for key, state in sorted(self._state.items())
                if state.get("dropped")
            },
        }


# --------------------------------------------------------------------------
# The one-line opt-in
# --------------------------------------------------------------------------


def wrap_binding_sink(
    inner: Callable[..., Any],
    runtime: ChainRuntime,
    *,
    max_repeat: int = 64,
) -> Callable[..., Any]:
    """Put a runtime in front of an existing binding sink.

    The wrapped sink keeps the same signature the lab already calls, so this
    is genuinely one line at the call site and removing that line restores
    today's behaviour exactly.

    `max_repeat` is a hard ceiling, not a tuning knob: acceleration multiplies
    counts, and a stuck encoder must not be able to send an unbounded burst.
    """

    def sink(device_key, control_key, binding, value, phase):
        for emission in runtime.run(device_key, control_key, value, phase):
            for _ in range(min(max(1, emission.repeat), max_repeat)):
                inner(device_key, control_key, binding, emission.value, emission.phase)

    return sink


# --------------------------------------------------------------------------
# Persistence -- a separate file, so nothing existing has to change
# --------------------------------------------------------------------------


class ChainStore:
    """Chains on disk, beside the hardware profiles but never inside them.

    A separate document means adopting this needs no migration of the profile
    schema and deleting it restores the previous behaviour, which is what
    "additive" has to mean in practice.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._document: Dict[str, Any] = {"schema": CHAIN_SCHEMA, "profiles": {}}

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ChainError(f"{self.path.name} could not be read: {exc}") from exc

        schema = int(raw.get("schema", 0))
        if schema > CHAIN_SCHEMA:
            raise ChainError(
                f"{self.path.name} was written by a newer version (schema {schema})"
            )
        self._document = {"schema": CHAIN_SCHEMA, "profiles": dict(raw.get("profiles") or {})}

    def save(self) -> None:
        """Write atomically, so an interrupted save cannot lose the file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(self._document, stream, indent=2, sort_keys=True)
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def chains_for(self, profile: str) -> Dict[Tuple[str, str], Chain]:
        built: Dict[Tuple[str, str], Chain] = {}
        for path, raw in (self._document["profiles"].get(profile) or {}).items():
            device_key, _, control_key = str(path).partition(".")
            if not device_key or not control_key:
                raise ChainError(f"{path!r} is not a device.control key")
            built[(device_key, control_key)] = build_chain(
                raw.get("stages") or (),
                enabled=bool(raw.get("enabled", True)),
                notes=str(raw.get("notes", "")),
            )
        return built

    def set_chain(self, profile: str, device_key: str, control_key: str, chain: Optional[Chain]) -> None:
        section = self._document["profiles"].setdefault(profile, {})
        path = f"{device_key}.{control_key}"
        if chain is None or not chain.stages:
            section.pop(path, None)
        else:
            section[path] = chain.as_dict()

    def snapshot(self) -> Mapping[str, Any]:
        return json.loads(json.dumps(self._document))


def default_chain_path() -> Path:
    """Beside the hardware profiles, under the user's own application data."""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "MuslimSim" / "hardware_chains.json"


# --------------------------------------------------------------------------
# Presets -- measured starting points, not invented defaults
# --------------------------------------------------------------------------


PRESETS: Mapping[str, Tuple[Mapping[str, Any], ...]] = {
    "fcu-altitude-knob": (
        {"kind": "direction_hold", "options": {"reversals": 2, "settle_ms": 250.0}},
        {"kind": "accumulate", "options": {"step": 1.0}},
        {"kind": "accelerate", "options": {"fast_ms": 30.0, "slow_ms": 220.0, "max_multiplier": 10.0}},
        {"kind": "ratelimit", "options": {"per_second": 25.0}},
    ),
    "course-wheel": (
        {"kind": "direction_hold", "options": {"reversals": 2, "settle_ms": 200.0}},
        {"kind": "accumulate", "options": {"step": 1.0}},
        {"kind": "accelerate", "options": {"fast_ms": 40.0, "slow_ms": 260.0, "max_multiplier": 5.0}},
        {"kind": "ratelimit", "options": {"per_second": 20.0}},
    ),
    "baro-knob-fine": (
        {"kind": "accumulate", "options": {"step": 1.0}},
        {"kind": "ratelimit", "options": {"per_second": 30.0}},
    ),
    "guarded-button": (
        {"kind": "debounce", "options": {"ms": 30.0}},
        {"kind": "tap", "options": {"hold_ms": 600.0}},
    ),
    "shift-modifier": (
        {"kind": "layer", "options": {"name": "shift", "mode": "hold", "swallow": True}},
    ),
    "trim-axis": (
        {"kind": "deadzone", "options": {"threshold": 0.03}},
        {"kind": "curve", "options": {"gamma": 1.6}},
        {"kind": "ratelimit", "options": {"per_second": 30.0}},
    ),
}


def preset(name: str) -> Chain:
    if name not in PRESETS:
        raise ChainError(f"unknown preset {name!r}")
    return build_chain(PRESETS[name])
