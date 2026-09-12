"""Live MOZA AY210 force-feedback engine - drives real effects from an
active `.mslm` profile's datarefs, continuously, instead of replaying one
fixed captured session.

VERIFICATION STATUS: all four effect types are now physically confirmed on
real hardware, live, at proven-comfortable magnitudes - spring (coefficient
28000), trim (CP-Offset +-14745, both fields of the same per-axis
report-0x13 packet as spring - see `_AxisConditionState`), rumble (channel
7's one-time RUMBLE_CHANNEL_ARM definition, discovered only during this
verification pass, then a full runway_rumble preset felt on real hardware),
and constant_force (magnitude up to 32767, an unopposed push - confirmed
too weak below ~8000 to feel on a free yoke at all, and confirmed to trip
the firmware's own "more than one spring force" warning if combined with
an active spring/trim - see `ffb_profiles.py`'s validator). See the staged
build-and-verify plan in this project's FFB-engine plan document and
BUG_REGISTER.md's BUG-21 tenth follow-up for the full history.

Design notes:
* `spring` and `trim` on the same axis are two *fields* of the one report
  0x13 packet for that axis (`CONDITION_EFFECT_BLOCK_INDEX`/
  `ParameterBlockOffset`), not two independent effects - see
  `_AxisConditionState`. Exactly one 0x13 write goes out per axis per tick,
  built from whichever spring/trim effects are configured for that axis.
* The persistent per-power-cycle "force feedback active" latch
  (`ENABLE_FFB_COMMAND`) is always attempted once `Host Connected` is
  observed, and never gated on "did I already send this" state - the
  firmware itself treats a redundant send as a harmless no-op once armed,
  and a stale client-side latch flag would be actively wrong the moment the
  physical device is replugged without this engine restarting. See
  `moza_ay210_ffb_protocol`'s module docstring.
* Curve/gate evaluation reuses `muslimsim/hardware/chains.py`'s
  `ChainRuntime` directly - there is no bespoke curve math in this module.
* A second family of gain parameters - the profile-level `physics` block
  (Spring/Damper/Inertia/Friction/Overall Force Feedback Intensity/Maximum
  Torque Output/Friction Compensation Strength) - was found by watching
  MOZA Cockpit's own panels write them, one slider at a time. See
  `PHYSICS_FIELD_TO_GAIN_PARAM` and `_maybe_sync_gain_params()`: unlike
  spring/trim/rumble/constant_force, these default to a set-once-per-
  connection static value (matching every real capture of Cockpit's own
  behavior), but a profile may bind one to a dataref/curve for genuine live
  control - the same dirty-check-and-resend mechanism handles both. Studio
  can also override any field for the current session via
  `set_physics_override()`, without ever writing to the (bridge-never-
  writes) `.mslm` file itself.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional

from . import moza_ay210_ffb_protocol as proto
from .chains import ChainContext, ChainRuntime
from .ffb_profiles import FfbProfile, PHYSICS_FIELD_DEFAULTS

# Maps each `.mslm` physics field to the raw serial (param, index) pair
# that carries it - see moza_ay210_ffb_protocol.py's GAIN_PARAM_* constants
# for how each byte was found (one MOZA Cockpit slider at a time, live
# USB capture, correlated to its own "Table N, Param M Written" log line).
PHYSICS_FIELD_TO_GAIN_PARAM: Dict[str, tuple] = {
    "spring_gain": (proto.GAIN_PARAM_AF, 0x00),
    "damper": (proto.GAIN_PARAM_DAMPER, 0x00),
    "inertia": (proto.GAIN_PARAM_INERTIA, 0x00),
    "friction": (proto.GAIN_PARAM_FRICTION, 0x00),
    "overall_intensity": (proto.GAIN_PARAM_OVERALL_INTENSITY, 0x00),
    "max_torque": (proto.GAIN_PARAM_MAX_TORQUE, 0x00),
    "friction_compensation": (
        proto.GAIN_PARAM_FRICTION_COMPENSATION,
        proto.GAIN_PARAM_FRICTION_COMPENSATION_INDEX,
    ),
}

DEFAULT_TICK_INTERVAL_SECONDS = 0.030  # matches the real captured ramp's own cadence
HEARTBEAT_INTERVAL_SECONDS = 0.300
CONNECT_TIMEOUT_SECONDS = 15.0

# Ceilings, each raised only as far as has actually been physically
# confirmed - never guessed at. 16384 was the highest coefficient ever seen
# in any capture (both the factory-default baseline and the Centering
# Spring test's own peak), so the engine's very first live test capped gain
# 1.0 there. A dedicated step-up test (16384 -> 20000 -> 24000 -> 28000,
# each held and physically felt) confirmed 28000 - genuinely untested
# territory relative to every capture this project has ever recorded - is
# comfortable, with the owner explicitly preferring it as "strong but
# comfortable" over the lower steps and over the original 16384 baseline.
# 28000 stops short of 32767 (the signed 16-bit ceiling saturation always
# sits at in every capture) to keep a safety margin, since a coefficient at
# or above that boundary risks the field being read as negative by
# firmware that has only ever been observed treating it as positive.
# Owner explicitly sets the ceiling to 32000 on 2026-09-12.
# It remains below the signed 16-bit boundary; profile gain still controls output.
SPRING_COEFFICIENT_CEILING = 32000
SPRING_SATURATION_CEILING = 32767
# The trim capture only ever showed one CP-Offset value (14745, roughly 45%
# of the signed 16-bit range) - this ceiling is a conservative placeholder,
# not something separately justified beyond "stay under the one value ever
# observed working."
TRIM_CP_OFFSET_CEILING = 14745

# The exact captured, already-proven-working Condition baseline
# (CONNECTION_SETUP_SEQUENCE's own "Centering spring.pcapng" reference:
# coefficient 16384, saturation 32767, deadband 1638 on both axes) - reused
# here only as a fallback so a trim's cp_offset has real force to pull
# against when no spring is currently supplying its own coefficient. Not a
# new/stronger value, not a guess.
TRIM_FOLLOW_SUPPORT_COEFFICIENT = 16384
TRIM_FOLLOW_SUPPORT_SATURATION = 32767
TRIM_FOLLOW_SUPPORT_DEADBAND = 1638

# Unlike the other three effects, constant_force has NO fixed engine-side
# ceiling - each effect's own 'max_magnitude' option (ffb_profiles.py,
# default 25000, hard-capped at 32767) is used directly. Real captures only
# ever showed 3623 (~5.5% of the field's range), proven on real hardware to
# be far too weak to feel on a free (unopposed) yoke at all. A step-up test
# (3623 -> 8000 -> 15000 -> 25000 -> 28000 -> 30000 -> 32767) found it
# barely perceptible at 8000, a clear push by 15000, and every step through
# 32767 comfortable. A follow-up test pushing PAST 32767 (32768 -> 33000 ->
# 40000 -> 50000 -> 65535) confirmed this field is genuinely signed
# (int16): the push reversed direction and got progressively WEAKER toward
# 65535 - textbook int16 wraparound. 32767 is therefore the true maximum in
# ffb_profiles.py's schema, not a conservative cutoff.


def _clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def _clamp_signed01(value: float) -> float:
    return -1.0 if value < -1.0 else 1.0 if value > 1.0 else value


@dataclass
class _AxisConditionState:
    cp_offset: int = 0
    coef_pos: int = 0
    coef_neg: int = 0
    sat_pos: int = 0
    sat_neg: int = 0
    deadband: int = 0
    # True only while the engine has supplied a fallback condition baseline
    # to give a trim's cp_offset something to pull against, because either
    # no spring effect is configured on this axis or the configured spring's
    # own gate is closed this tick (its branch never ran, so coef_pos/neg
    # sat at whatever they were - 0 on a freshly created axis). A bare
    # cp_offset with zero coefficient is not force, just a displaced center
    # point: real hardware confirmed a "roll_follow" trim moves nothing at
    # all whenever the paired "roll_spring" effect's own bus_volts gate
    # happens to be closed. Cleared the moment a real spring value (zero or
    # not - the spring branch running at all means it owns these fields) is
    # written for this axis, so an explicit spring is always authoritative.
    implicit_trim_support: bool = False
    dirty: bool = False


@dataclass
class _EngineStatus:
    running: bool = False
    connected: bool = False
    latch_write_sent_this_session: bool = False
    last_host_connected_seen: Optional[float] = None
    active_profile_name: Optional[str] = None
    last_tick_error: Optional[str] = None
    last_effect_values: Dict[str, float] = field(default_factory=dict)


class MozaAy210FfbEngine:
    """Owns the AY210's HID+serial handles and drives effects from the
    active `.mslm` profile on each `tick()` call."""

    def __init__(
        self,
        *,
        serial_port: Optional[str] = None,
        device_profile: "proto.MozaDeviceProfile" = proto.AY210_PROFILE,
    ) -> None:
        # `serial_port=None` resolves against the profile's own default so
        # every existing `MozaAy210FfbEngine()` call keeps opening COM4 via
        # AY210_PROFILE unchanged; pass `device_profile=proto.AB6_PROFILE`
        # to drive an AB6 instead (its own default_serial_port is COM6).
        self._device_profile = device_profile
        self._serial_port = serial_port if serial_port is not None else device_profile.default_serial_port
        self._device: Any = None
        self._serial: Any = None
        self._serial_lock = threading.Lock()
        self._poll_stop = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._connection_log = bytearray()
        self._preconnect_setup_sent = False
        # A gate's "when" stage resolves its 'key' through this - see
        # _lookup_dataref()'s own comment for why a thin indirection is
        # needed instead of constructing ChainContext with read_dataref_fn
        # directly.
        self._current_read_dataref_fn: Optional[Callable[[str], Optional[float]]] = None
        self._runtime = ChainRuntime(context=ChainContext(values=self._lookup_dataref))
        self._profile: Optional[FfbProfile] = None
        self._axis_state: Dict[str, _AxisConditionState] = {}
        self._active_channels: set = set()
        self._armed_rumble_channels: set = set()
        self._sent_physics_bytes: Dict[str, Optional[int]] = {}
        self._physics_override: Dict[str, float] = {}
        # Session-only per-effect gain multiplier (1.0 = unmodified), the
        # same "Studio can tune this live, never written to any .mslm file"
        # idea as _physics_override - the profile's own curve keeps deciding
        # *when* an effect fires and *how it responds* to its dataref; this
        # only scales how strong the result feels.
        self._effect_gain_override: Dict[str, float] = {}
        # Exponential smoothing state for "trim" effects specifically (keyed
        # by effect.id), independent of anything ffb_profiles.py's curve
        # system can express: chains.py has scale/deadzone/ratelimit but no
        # genuine low-pass/glide stage, and a "when" gate plus a bare scale
        # both snap instantly to a new value rather than easing toward it.
        # A live-flight dataref like real control-surface deflection is
        # never perfectly still - even correctly gated and deadzone-
        # filtered, it keeps crossing the deadzone boundary back and forth,
        # so cp_offset was snapping between 0 and a real value tick to
        # tick. Confirmed live as feeling like vibration instead of a
        # smooth pull. See _smooth_trim_gain().
        self._trim_smoothed: Dict[str, float] = {}
        self._next_heartbeat = 0.0
        self._status = _EngineStatus()
        self._lock = threading.Lock()

    # -- lifecycle ----------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._status.running

    def start(self) -> None:
        with self._lock:
            if self._status.running:
                return
            self._device = proto.open_ay210(vid=self._device_profile.vid, pid=self._device_profile.pid)
            self._serial = proto.open_serial(self._serial_port)
            self._connection_log.clear()
            self._preconnect_setup_sent = False
            self._poll_stop.clear()
            self._poll_thread = threading.Thread(
                target=proto.background_poll_loop,
                args=(self._serial, self._poll_stop, self._serial_lock, self._device_profile.connect_poll_loop),
                daemon=True,
            )
            self._poll_thread.start()
            # Preserve whatever profile was already selected (set_active_profile
            # can legitimately be called before start()) - only the
            # connection-related fields are genuinely fresh here.
            previous_profile_name = self._status.active_profile_name
            self._status = _EngineStatus(running=True, active_profile_name=previous_profile_name)

    def stop(self) -> None:
        with self._lock:
            if self._serial is not None:
                try:
                    proto.send_serial(self._serial, self._serial_lock, proto.DISARM_GAIN_COMMAND)
                except Exception:
                    pass
            if self._device is not None:
                try:
                    proto.replay_teardown(self._device, self._device_profile.teardown_sequence)
                except Exception:
                    pass
            self._poll_stop.set()
            if self._poll_thread is not None:
                self._poll_thread.join(timeout=1.0)
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:
                    pass
            if self._device is not None:
                try:
                    self._device.close()
                except Exception:
                    pass
            self._device = None
            self._serial = None
            self._poll_thread = None
            self._axis_state = {}
            self._active_channels = set()
            self._armed_rumble_channels = set()
            self._sent_physics_bytes = {}
            self._physics_override = {}
            self._effect_gain_override = {}
            self._trim_smoothed = {}
            self._status = _EngineStatus(running=False, active_profile_name=self._status.active_profile_name)

    def set_active_profile(self, profile: Optional[FfbProfile]) -> None:
        with self._lock:
            self._profile = profile
            # Drop all per-effect state on a profile switch, but keep the
            # same dataref-lookup wiring a gate's "when" stage depends on.
            self._runtime = ChainRuntime(context=ChainContext(values=self._lookup_dataref))
            self._axis_state = {}
            self._active_channels = set()
            self._armed_rumble_channels = set()
            # A switched-in profile may want a genuinely different value for
            # a field that was already sent under the old profile - force
            # every physics field to re-sync on the next tick. Session-level
            # Studio overrides (_physics_override) deliberately survive a
            # profile switch; only the "what did we last actually write"
            # tracking resets here.
            self._sent_physics_bytes = {}
            self._trim_smoothed = {}
            self._status.active_profile_name = profile.name if profile else None
            if profile is not None:
                for field, setting in profile.physics.items():
                    if setting.dataref and setting.curve is not None:
                        self._runtime.set_chain(profile.name, f"physics.{field}", setting.curve)
                for effect in profile.effects:
                    # Register each effect's curve/gate as its own chain,
                    # keyed by (profile.name, effect.id) - ChainRuntime.run()
                    # is a no-op pass-through for any key it has no chain
                    # registered for, so skipping this silently produces
                    # "curve does nothing" rather than an error.
                    self._runtime.set_chain(profile.name, effect.id, effect.curve)
                    if effect.gate is not None:
                        self._runtime.set_chain(profile.name, f"{effect.id}.gate", effect.gate)
                    for chan, _ in self._channels_for_effect(effect):
                        self._active_channels.add(chan)

    def _channels_for_effect(self, effect):
        if effect.kind in ("spring", "trim"):
            return ((proto.CONDITION_EFFECT_BLOCK_INDEX, None),)
        if effect.kind == "rumble":
            preset = self._rumble_presets().get(effect.options.get("preset"))
            if not preset:
                return ()
            return tuple((chan, code) for chan, code in preset["channels"])
        if effect.kind == "constant_force":
            return ((1, None),)
        return ()

    def _rumble_presets(self):
        return proto.AB6_RUMBLE_PRESETS if self._device_profile is proto.AB6_PROFILE else proto.RUMBLE_PRESETS

    # -- the per-tick entry point --------------------------------------

    def _lookup_dataref(self, key: str) -> Optional[float]:
        """Backs every gate's "when" stage (`ctx.value(key)` in chains.py) -
        a thin indirection onto whatever read_dataref_fn the CURRENT tick()
        call was given, since ChainRuntime/ChainContext are built once (in
        __init__/set_active_profile()) while read_dataref_fn only exists
        for the duration of one tick() call."""

        fn = self._current_read_dataref_fn
        return fn(key) if fn is not None else None

    def tick(self, read_dataref_fn: Callable[[str], Optional[float]]) -> None:
        """Called once per bridge-loop pass while enabled. Reads whatever
        datarefs the active profile's effects need, evaluates each
        effect's curve, and emits exactly the writes that changed."""

        if self._device is None or self._serial is None:
            return

        self._current_read_dataref_fn = read_dataref_fn
        try:
            self._maybe_connect_and_arm()
            if self._status.connected:
                # Effects must never be evaluated on the (possibly many) ticks
                # BEFORE "Host Connected" is observed - a live capture of the
                # rumble arm sequence caught exactly this: several ticks fired
                # _evaluate_effects() while still unconnected, sending channel
                # 7's one-shot arm and marking it armed well before
                # CONNECTION_SETUP_SEQUENCE ever ran. That sequence opens with
                # OPEN_COMMAND ("1c03"), which likely wipes any previously
                # loaded effect block - so the premature arm was almost
                # certainly discarded, and since arming is a sticky flag
                # (never retried once set), channel 7 would then stay
                # unarmed, acknowledged-but-inert, for the rest of the
                # connection. Nothing productive can happen before
                # "connected" anyway, so gating here costs nothing.
                self._maybe_sync_gain_params(read_dataref_fn)
                self._maybe_heartbeat()
                if self._profile is not None:
                    self._evaluate_effects(read_dataref_fn)
            self._status.last_tick_error = None
        except Exception as exc:
            self._status.last_tick_error = str(exc)
            raise

    def _maybe_connect_and_arm(self) -> None:
        if self._status.connected:
            return
        # Non-blocking-ish: wait_for_connected() itself blocks up to its
        # timeout reading the serial port, so this is only worth calling
        # from a tick when not yet connected - once True, never called
        # again for this connection's lifetime.
        #
        # NOTE: once a connect is detected, this blocks the calling bridge
        # tick for roughly the real ~0.67s duration of
        # CONNECTION_SETUP_SEQUENCE - a one-time cost, not a per-tick one,
        # but it does stall every other subsystem sharing the same bridge
        # loop for that single tick. Acceptable for now (this only happens
        # once per connection, and every other bridge subsystem already
        # tolerates the occasional slow tick from device I/O elsewhere in
        # this codebase), but worth revisiting if it proves disruptive.
        def prepare_ab6():
            if self._preconnect_setup_sent:
                return
            # AB6 capture places setup and latch in Host Connecting, before
            # Connected. Waiting for Connected first can deadlock its startup.
            proto.replay_connection_setup(
                self._device, self._serial, self._serial_lock,
                self._device_profile.connection_setup_sequence,
            )
            proto.send_serial(self._serial, self._serial_lock, self._device_profile.enable_ffb_command)
            self._status.latch_write_sent_this_session = True
            self._preconnect_setup_sent = True

        is_ab6 = self._device_profile is proto.AB6_PROFILE
        if proto.wait_for_connected(self._serial, 0.05, buffer=self._connection_log,
                                    on_connecting=prepare_ab6 if is_ab6 else None):
            self._status.connected = True
            self._status.last_host_connected_seen = time.monotonic()
            if is_ab6:
                prepare_ab6()  # warm connection may omit the Connecting line
                proto.replay_connection_setup(self._device, self._serial, self._serial_lock,
                                              proto.AB6_EFFECT_SETUP_SEQUENCE)
            else:
                # Keep AY210's captured post-Connected ordering unchanged.
                proto.send_serial(self._serial, self._serial_lock, self._device_profile.enable_ffb_command)
                self._status.latch_write_sent_this_session = True
                time.sleep(0.05)
                proto.replay_connection_setup(
                    self._device, self._serial, self._serial_lock,
                    self._device_profile.connection_setup_sequence,
                )
            # CONNECTION_SETUP_SEQUENCE zeroes 'af'/'b0'/'b1'/'b2' as part of
            # its fixed replayed bytes (it does NOT touch overall_intensity/
            # max_torque/friction_compensation - those weren't part of the
            # capture it was extracted from) - a fresh connection genuinely
            # resets at least those four, so every physics field must
            # re-sync on the next tick regardless of whether its own desired
            # value has changed since the last connection. Not relying on
            # CONNECTION_SETUP_SEQUENCE's own zeroing for the other three
            # either way: this always (re)sends every field's current
            # desired value fresh, never assumes a starting state.
            self._sent_physics_bytes = {}

    def _maybe_sync_gain_params(self, read_dataref_fn: Callable[[str], Optional[float]]) -> None:
        # Each physics field is a set-once-per-connection calibration
        # constant by default (see PHYSICS_FIELD_TO_GAIN_PARAM's module
        # comment: a real FFB-Bridge flight never adjusted 'af' live) - this
        # only sends a write when the desired value actually differs from
        # what's already been sent this connection, not on every tick like
        # the per-tick effect writes. A profile that binds a field to a
        # dataref/curve instead of a bare number naturally updates live,
        # since its resolved value can then change tick to tick - the same
        # dirty-check either way, just a different source for "desired".
        if self._profile is None:
            return
        # A device profile with a restricted confirmed_physics_fields list
        # (e.g. AB6_PROFILE) means only those (param, index) addresses were
        # ever confirmed for THIS device - see MozaDeviceProfile's own
        # comment. None (the AY210's own default) means every field here is
        # confirmed, so nothing is filtered - zero behavior change.
        confirmed = self._device_profile.confirmed_physics_fields
        for field, (param, index) in PHYSICS_FIELD_TO_GAIN_PARAM.items():
            if confirmed is not None and field not in confirmed:
                continue
            value = self._resolve_physics_field(field, read_dataref_fn)
            desired_byte = int(round(_clamp01(value) * 100))
            if desired_byte != self._sent_physics_bytes.get(field):
                proto.send_serial(
                    self._serial, self._serial_lock,
                    proto.build_gain_param_write(param, index, desired_byte),
                )
                self._sent_physics_bytes[field] = desired_byte

    def _resolve_physics_field(self, field: str, read_dataref_fn: Callable[[str], Optional[float]]) -> float:
        # A live Studio override (see set_physics_override()) always wins -
        # it exists specifically to let Studio tune the current session
        # without editing the (bridge-never-writes) `.mslm` file itself.
        if field in self._physics_override:
            return self._physics_override[field]
        setting = self._profile.physics.get(field) if self._profile is not None else None
        if setting is None:
            return PHYSICS_FIELD_DEFAULTS.get(field, 0.0)
        if setting.dataref:
            raw_value = read_dataref_fn(setting.dataref)
            if raw_value is None:
                return 0.0
            emissions = self._runtime.run(self._profile.name, f"physics.{field}", raw_value)
            return emissions[-1].value if emissions else 0.0
        return float(setting.static or 0.0)

    def set_physics_override(self, overrides: Mapping[str, float]) -> None:
        """Session-only live tuning from Studio - takes priority over the
        active profile's own `physics` block, but is never written back to
        any `.mslm` file (those stay user-authored, never bridge-written)."""

        with self._lock:
            for field, value in overrides.items():
                if field not in PHYSICS_FIELD_TO_GAIN_PARAM:
                    raise ValueError(f"unknown physics field {field!r}")
                self._physics_override[field] = _clamp01(float(value))

    def clear_physics_override(self, field: Optional[str] = None) -> None:
        """Drop a live override (or all of them) and fall back to whatever
        the active profile's own `physics` block says for that field."""

        with self._lock:
            if field is None:
                self._physics_override.clear()
            else:
                self._physics_override.pop(field, None)

    def set_effect_gain_override(self, overrides: Mapping[str, float]) -> None:
        """Session-only live strength tuning for one or more of the active
        profile's own effects (by their `id`) - the profile's curve keeps
        deciding when an effect fires and how it tracks its dataref; this
        only scales the resulting strength, the same way a Studio physics
        slider tunes a gain without touching the `.mslm` file itself.
        Clamped to 0..2 (0-200%): effects were built with headroom below
        their own reference_magnitude/ceiling, so doubling a gain is a real,
        usable range, not just a safety margin.
        """

        with self._lock:
            for effect_id, value in overrides.items():
                self._effect_gain_override[str(effect_id)] = max(0.0, min(2.0, float(value)))

    def clear_effect_gain_override(self, effect_id: Optional[str] = None) -> None:
        """Drop a live effect-gain override (or all of them)."""

        with self._lock:
            if effect_id is None:
                self._effect_gain_override.clear()
            else:
                self._effect_gain_override.pop(effect_id, None)

    def send_raw_hid(self, hexstr: str) -> bool:
        """Diagnostic-only: send one arbitrary HID packet verbatim, exactly
        as captured - used to replay a real captured byte sequence (e.g. a
        Set Effect / report-0x11 definition for a block our own engine
        never arms) without inventing new protocol code first. Returns
        False (no write sent) if not connected yet."""

        with self._lock:
            if self._device is None or not self._status.connected:
                return False
            proto.send_hid(self._device, hexstr)
            return True

    def send_raw_condition(
        self, axis: str, cp_offset: int, coef_pos: int, coef_neg: int,
        sat_pos: int = 32767, sat_neg: int = 32767, deadband: int = 0,
    ) -> bool:
        """Diagnostic-only: send one report-0x13 (Set Condition) write
        directly at caller-specified values, bypassing every profile-side
        gain/ceiling (SPRING_COEFFICIENT_CEILING, TRIM_CP_OFFSET_CEILING) -
        those are self-imposed conservative caps, not hardware limits. Used
        to test the roll axis at its true wire-format maximum (coef up to
        32767, the saturation ceiling every capture has ever shown) since
        every profile-driven test so far only ever reached a fraction of
        that. Returns False (no write sent) if not connected yet."""

        with self._lock:
            if self._device is None or not self._status.connected:
                return False
            offset = proto.AXIS_PARAMETER_BLOCK_OFFSET[axis]
            packet = proto.build_set_condition(
                proto.CONDITION_EFFECT_BLOCK_INDEX, offset,
                int(cp_offset), int(coef_pos), int(coef_neg),
                int(sat_pos), int(sat_neg), int(deadband),
            )
            proto.send_hid(self._device, packet.hex())
            return True

    def send_raw_constant_force(self, magnitude: int, channel: int = 1) -> bool:
        """Diagnostic-only: send one report-0x15 write directly, bypassing
        the active profile entirely. Exists to probe whether a
        never-captured channel number (anything other than 1) does
        anything on real hardware - channel 1 is the only value any real
        capture or profile-driven effect has ever used. Returns False (no
        write sent) if not connected yet."""

        with self._lock:
            if self._device is None or not self._status.connected:
                return False
            packet = proto.build_constant_force(int(magnitude), channel=int(channel))
            proto.send_hid(self._device, packet.hex())
            return True

    def _maybe_heartbeat(self) -> None:
        now = time.monotonic()
        if now < self._next_heartbeat:
            return
        self._next_heartbeat = now + HEARTBEAT_INTERVAL_SECONDS
        proto.send_hid(self._device, "1df2")  # device gain, present in both bases' effect captures
        for chan in sorted(self._active_channels):
            proto.send_hid(self._device, f"1a{chan:02x}0101")

    # Fraction of the remaining distance to the target closed per tick
    # (~30ms ticks): 0.15 reaches ~63% of the way there in about 200ms and
    # is visually/physically settled within roughly a second - a deliberate
    # glide, not a lag the pilot would consciously notice as "slow to
    # respond," but enough to turn tick-to-tick snapping into one smooth
    # motion. Confirmed live this session as the fix for trim-follow
    # feeling like vibration instead of a pull.
    _TRIM_SMOOTHING_ALPHA = 0.15

    def _smooth_trim_gain(self, effect_id: str, target: float) -> float:
        """Ease this trim effect's own cp_offset gain toward ``target``
        instead of snapping to it - see _TRIM_SMOOTHING_ALPHA."""

        previous = self._trim_smoothed.get(effect_id, target)
        smoothed = previous + (target - previous) * self._TRIM_SMOOTHING_ALPHA
        self._trim_smoothed[effect_id] = smoothed
        return smoothed

    def _evaluate_effects(self, read_dataref_fn: Callable[[str], Optional[float]]) -> None:
        if self._profile is None:
            return

        touched_axes: set = set()
        # Same "explicitly return to neutral, don't just stop updating" fix
        # as rumble's armed-channel handling below, for the opposite reason:
        # trim and spring share one axis condition report (cp_offset lives
        # alongside the spring coefficients), and spring keeps re-sending
        # that report every tick on its own. If a gated trim effect (e.g.
        # pitch_follow/roll_follow, gated on autopilot servos_on) goes
        # inactive without this, its last cp_offset stays permanently baked
        # into every subsequent spring write - confirmed live this session
        # as the yoke feeling stiff and off-center after engine shutdown,
        # long after the autopilot (and its trim pull) had disengaged.
        axes_with_active_trim: set = set()
        # An axis lands here only on a tick where its "spring" effect's own
        # branch actually ran - i.e. the effect exists AND its gate (if any)
        # is currently open. A configured-but-currently-gated-closed spring
        # (e.g. roll_spring waiting on bus_volts >= 26) does NOT count: its
        # branch never executes that tick, so coef_pos/coef_neg are left at
        # whatever they last were (0 on a freshly created axis) - exactly
        # the "trim's cp_offset with no force to act on it" gap this engine
        # used to leave open. See the implicit-support pass below.
        axes_with_active_spring: set = set()
        # Keyed by channel, not a flat list: RUMBLE_PRESETS only defines two
        # independently-arm-able periodic channels (7 and 8 - see
        # RUMBLE_CHANNEL_ARM), and most presets share channel 7 (only their
        # frequency_code differs) - a profile with several simultaneously-
        # active rumble effects (e.g. engine_rumble idling while turbulence
        # is also present) would otherwise have whichever effect happened to
        # be LAST in the profile's own effects list silently overwrite every
        # other one's channel-7 write, every single tick - confirmed live
        # this session: adding a turbulence effect after an already-working
        # engine effect made the engine rumble go completely silent, because
        # turbulence's near-zero-but-nonzero reading kept winning that race.
        # The loudest effect on a shared channel wins instead.
        rumble_writes: Dict[int, tuple] = {}
        constant_force_value: Optional[int] = None

        for effect in self._profile.effects:
            raw_value = read_dataref_fn(effect.options.get("dataref", ""))
            if raw_value is None:
                continue

            if effect.gate is not None:
                gated = self._runtime.run(self._profile.name, f"{effect.id}.gate", raw_value)
                if not gated:
                    self._status.last_effect_values[effect.id] = 0.0
                    if effect.kind == "trim":
                        # Glide toward neutral instead of snapping to it -
                        # see _smooth_trim_gain()'s own docstring for why an
                        # instant jump (this effect's previous behaviour)
                        # feels like a jolt, the same problem an un-smoothed
                        # active pull has.
                        axis = effect.options["axis"]
                        state = self._axis_state.setdefault(axis, _AxisConditionState())
                        state.cp_offset = int(round(self._smooth_trim_gain(effect.id, 0.0) * TRIM_CP_OFFSET_CEILING))
                        state.dirty = True
                        touched_axes.add(axis)
                        axes_with_active_trim.add(axis)
                    continue

            emissions = self._runtime.run(self._profile.name, effect.id, raw_value)
            gain = emissions[-1].value if emissions else 0.0
            gain *= self._effect_gain_override.get(effect.id, 1.0)
            self._status.last_effect_values[effect.id] = gain

            if effect.kind == "spring":
                axis = effect.options["axis"]
                state = self._axis_state.setdefault(axis, _AxisConditionState())
                magnitude = int(round(_clamp01(gain) * SPRING_COEFFICIENT_CEILING))
                state.coef_pos = magnitude
                state.coef_neg = magnitude
                state.sat_pos = SPRING_SATURATION_CEILING
                state.sat_neg = SPRING_SATURATION_CEILING
                state.deadband = int(round(_clamp01(float(effect.options.get("deadband", 0.0))) * 65535))
                # A real spring ran this tick - it owns these fields now,
                # even if its own gain happens to be 0 (a deliberately weak
                # spring is still an explicit choice, unlike a gate that
                # never let this branch run at all).
                state.implicit_trim_support = False
                state.dirty = True
                touched_axes.add(axis)
                axes_with_active_spring.add(axis)

            elif effect.kind == "trim":
                axis = effect.options["axis"]
                state = self._axis_state.setdefault(axis, _AxisConditionState())
                smoothed = self._smooth_trim_gain(effect.id, _clamp_signed01(gain))
                state.cp_offset = int(round(smoothed * TRIM_CP_OFFSET_CEILING))
                state.dirty = True
                touched_axes.add(axis)
                axes_with_active_trim.add(axis)

            elif effect.kind == "rumble":
                preset = self._rumble_presets().get(effect.options.get("preset"))
                if preset is None:
                    continue
                magnitude = int(round(_clamp01(gain) * preset["reference_magnitude"]))
                for chan, code in preset["channels"]:
                    if chan not in self._armed_rumble_channels:
                        # One-time per-channel arm (report 0x11) - see
                        # RUMBLE_CHANNEL_ARM's comment: channels 7/8 aren't
                        # covered by CONNECTION_SETUP_SEQUENCE, so a bare
                        # 0x14 write to an unarmed channel is expected to be
                        # acknowledged with zero physical effect.
                        if self._device_profile is proto.AB6_PROFILE:
                            proto.send_feature_report(self._device, '21040000')
                            arm=list(proto.AB6_RUMBLE_ARM)
                            if effect.options.get('preset')=='gear_bumps':
                                arm[-1]='110404ff7f000000000000ffff04e457000000000000'
                            for packet in arm:
                                proto.send_hid(self._device, packet)
                                time.sleep(.015)
                        else:
                            proto.replay_rumble_channel_arm(self._device, chan)
                        self._armed_rumble_channels.add(chan)
                    existing = rumble_writes.get(chan)
                    if existing is None or magnitude > existing[0]:
                        rumble_writes[chan] = (magnitude, code)

            elif effect.kind == "constant_force":
                # Bipolar, like trim's CP-Offset: a real hardware step test
                # confirmed -32768 pushes just as comfortably as +32767 does
                # in the other direction (see max_magnitude's own comment),
                # so a negative curve/dataref value produces a genuine
                # reverse push rather than being discarded.
                max_magnitude = int(effect.options.get("max_magnitude", 25000))
                constant_force_value = int(round(_clamp_signed01(gain) * max_magnitude))

        for effect in self._profile.effects:
            # Rare fallback: a trim effect whose own dataref read failed
            # this tick (raw_value was None) never reaches either of the
            # two branches above, so it never gets a chance to glide toward
            # neutral - still smoothed here for the same reason, not an
            # instant snap.
            if effect.kind != "trim":
                continue
            axis = effect.options["axis"]
            if axis in axes_with_active_trim:
                continue
            state = self._axis_state.get(axis)
            smoothed = self._smooth_trim_gain(effect.id, 0.0)
            if state is not None and (state.cp_offset != 0 or abs(smoothed) > 1e-6):
                state.cp_offset = int(round(smoothed * TRIM_CP_OFFSET_CEILING))
                state.dirty = True
                touched_axes.add(axis)

        # A CP Offset with zero coefficients is a displaced center point,
        # not a force - real hardware confirmed a trim effect moves nothing
        # at all while its axis has no active spring this tick (see
        # axes_with_active_spring's own comment for exactly when that
        # happens). Give it the same proven-working baseline
        # CONNECTION_SETUP_SEQUENCE already uses at connect time, only on
        # axes that actually have a trim effect configured, and only while
        # that trim is still doing something (engaged, or mid-glide back to
        # neutral with a nonzero cp_offset) - never invented for an axis
        # that has no trim at all.
        trim_axes = {e.options["axis"] for e in self._profile.effects if e.kind == "trim"}
        for axis in trim_axes - axes_with_active_spring:
            state = self._axis_state.get(axis)
            if state is None:
                continue
            wants_support = axis in axes_with_active_trim or state.cp_offset != 0
            if wants_support:
                if (
                    not state.implicit_trim_support
                    or state.coef_pos != TRIM_FOLLOW_SUPPORT_COEFFICIENT
                    or state.coef_neg != TRIM_FOLLOW_SUPPORT_COEFFICIENT
                    or state.sat_pos != TRIM_FOLLOW_SUPPORT_SATURATION
                    or state.sat_neg != TRIM_FOLLOW_SUPPORT_SATURATION
                    or state.deadband != TRIM_FOLLOW_SUPPORT_DEADBAND
                ):
                    state.coef_pos = TRIM_FOLLOW_SUPPORT_COEFFICIENT
                    state.coef_neg = TRIM_FOLLOW_SUPPORT_COEFFICIENT
                    state.sat_pos = TRIM_FOLLOW_SUPPORT_SATURATION
                    state.sat_neg = TRIM_FOLLOW_SUPPORT_SATURATION
                    state.deadband = TRIM_FOLLOW_SUPPORT_DEADBAND
                    state.implicit_trim_support = True
                    state.dirty = True
                    touched_axes.add(axis)
            elif state.implicit_trim_support:
                # Trim disengaged and settled at neutral - release the
                # fallback support rather than leaving the axis stiff.
                state.coef_pos = 0
                state.coef_neg = 0
                state.sat_pos = 0
                state.sat_neg = 0
                state.deadband = 0
                state.implicit_trim_support = False
                state.dirty = True
                touched_axes.add(axis)

        # A disabled/gated/missing spring must explicitly relinquish its
        # coefficients, including baseline conditions installed at connection.
        # Constant-force mode owns the same firmware slot: never add a spring
        # condition while that independent mode is configured.
        has_constant = any(effect.kind == "constant_force" for effect in self._profile.effects)
        if not has_constant:
            for axis in ("roll", "pitch"):
                if axis in axes_with_active_spring or axis in axes_with_active_trim:
                    continue
                first_neutral = axis not in self._axis_state
                state = self._axis_state.setdefault(axis, _AxisConditionState())
                if state.cp_offset != 0:
                    continue  # A trim release is still easing to centre.
                if not first_neutral and not any((state.coef_pos, state.coef_neg, state.sat_pos, state.sat_neg, state.deadband)):
                    continue  # Already sent neutral: do not repeat it every tick.
                state.coef_pos = state.coef_neg = 0
                state.sat_pos = state.sat_neg = 0
                state.deadband = 0
                state.implicit_trim_support = False
                state.dirty = True
                touched_axes.add(axis)

        for axis in touched_axes:
            state = self._axis_state[axis]
            if not state.dirty:
                continue
            offset = proto.AXIS_PARAMETER_BLOCK_OFFSET[axis]
            packet = proto.build_set_condition(
                proto.CONDITION_EFFECT_BLOCK_INDEX, offset,
                state.cp_offset, state.coef_pos, state.coef_neg,
                state.sat_pos, state.sat_neg, state.deadband,
            )
            proto.send_hid(self._device, packet.hex())
            state.dirty = False

        # Every armed channel gets a write this tick, not just the ones an
        # effect actively claimed - an armed channel with no current
        # claimant defaults to an explicit magnitude-0 write. Without this,
        # a channel whose last claimant's gain drops to exactly 0 (a gate
        # closing, a dataref settling) simply stops receiving updates -
        # the device has no "stop" concept of its own, so it keeps replaying
        # its last nonzero magnitude forever. Confirmed live this session as
        # engine rumble stuck playing at 0 RPM.
        for chan in self._armed_rumble_channels:
            magnitude, code = rumble_writes.get(chan, (0, 0))
            packet = proto.build_set_periodic(chan, magnitude, code)
            proto.send_hid(self._device, packet.hex())

        if has_constant:
            packet = proto.build_constant_force(constant_force_value or 0)
            proto.send_hid(self._device, packet.hex())

    # -- reporting ------------------------------------------------------

    def status_snapshot(self) -> Dict[str, Any]:
        return {
            "running": self._status.running,
            "connected": self._status.connected,
            "latch_write_sent_this_session": self._status.latch_write_sent_this_session,
            "last_host_connected_seen": self._status.last_host_connected_seen,
            "active_profile": self._status.active_profile_name,
        }

    def diagnostics_snapshot(self) -> Dict[str, Any]:
        return {
            "unsupported_effects": [e.id for e in self._profile.effects
                                    if e.kind=='rumble' and e.options.get('preset') not in self._rumble_presets()] if self._profile else [],
            "last_tick_error": self._status.last_tick_error,
            "last_effect_values": dict(self._status.last_effect_values),
            "active_channels": sorted(self._active_channels),
            # Last byte (0-100) actually written for each physics field this
            # connection, or None if not yet sent - Studio reads this to
            # show real engine state instead of its own last local edit.
            "physics_sent": {field: self._sent_physics_bytes.get(field) for field in PHYSICS_FIELD_TO_GAIN_PARAM},
            "physics_overridden": sorted(self._physics_override),
            "effect_gain_overrides": dict(self._effect_gain_override),
            # The actual per-axis Set Condition fields the next dirty write
            # will encode (cp_offset/coef_pos/coef_neg/sat_pos/sat_neg/
            # deadband) - last_effect_values only shows each effect's own
            # pre-combination gain, not what spring+trim actually combined
            # into for the shared axis report.
            "axis_state": {
                axis: {
                    "cp_offset": state.cp_offset,
                    "coef_pos": state.coef_pos,
                    "coef_neg": state.coef_neg,
                    "sat_pos": state.sat_pos,
                    "sat_neg": state.sat_neg,
                    "deadband": state.deadband,
                    "implicit_trim_support": state.implicit_trim_support,
                    "dirty": state.dirty,
                }
                for axis, state in self._axis_state.items()
            },
        }


__all__ = ("MozaAy210FfbEngine", "DEFAULT_TICK_INTERVAL_SECONDS", "PHYSICS_FIELD_TO_GAIN_PARAM")
