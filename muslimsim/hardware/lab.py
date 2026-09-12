"""Thread-safe virtual hardware laboratory state and safe action routing."""

from __future__ import annotations

from dataclasses import asdict
import math
import threading
import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from .catalog import (
    ALL_HARDWARE,
    DEFAULT_BINDINGS,
    ControlSpec,
    catalogue_snapshot,
    device_by_key,
    runtime_control_by_key,
)
from .profiles import HardwareProfileStore, MappingBinding, ProfileError
from .practice_echo import PRACTICE_IDLE_SLEEP_SECONDS
from .virtual_zibo import VirtualZiboPreview

# MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
# How often the idle sweep runs.  Well below the sleep timeout so a panel
# goes dark close to when it was actually abandoned, and cheap enough that
# it costs nothing while Practice is open.
PRACTICE_SLEEP_SWEEP_SECONDS = 1.0


class LabError(ValueError):
    """A laboratory request cannot be accepted without guessing hardware behavior."""


BindingSink = Callable[[str, str, MappingBinding, float, str], None]
# Takes the practice snapshot plus an optional ``only_device`` restricting
# which device may actually be written.  Under output authority a Test-mode
# press drives the device being tested and nothing else.
PracticeOutputSink = Callable[..., None]
PracticeInputSink = Callable[[str, str, float, str], None]


class HardwareLab:
    """State shared by virtual controls, physical diagnostics, and the channel.

    The lab does not open hardware itself.  The running bridge remains the sole
    owner of serial/HID/SDL devices.  This object is intentionally lock-based
    and quick: callers may use it from HID workers, the TCP control server, or
    the UI's background workers without ever touching a UI thread.
    """

    def __init__(
        self,
        profile_store: Optional[HardwareProfileStore] = None,
        *,
        binding_sink: Optional[BindingSink] = None,
        practice_input_sink: Optional[PracticeInputSink] = None,
    ) -> None:
        self.profile_store = profile_store
        self.binding_sink = binding_sink
        self._lock = threading.RLock()
        self._inputs: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._outputs: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._diagnostics: list[Dict[str, Any]] = []
        self._mode = "live"
        self._simulator_connected = False
        # Read-only identity supplied by the bridge after X-Plane publishes
        # its loaded .acf path.  Studio uses this to select the matching,
        # isolated mapping workspace automatically; it never tells X-Plane
        # to load or change an aircraft.
        self._aircraft_context: Dict[str, str] = {
            "profile": "unresolved",
            "path": "",
            "mapping_aircraft": "",
        }
        # The test cockpit belongs to the bridge, alongside the real HID
        # input streams.  Studio receives this snapshot but never needs to be
        # alive for a physical input to update a supported display.
        self._practice_preview = VirtualZiboPreview()
        self._practice_output_sink: Optional[PracticeOutputSink] = None
        # Device drivers may optionally react to a *known* practice input
        # (for example the PU's documented timed starter retract).  The
        # callback never receives raw protocol access and is called only in
        # Test mode, after the input has been recorded.
        self._practice_input_sink = practice_input_sink
        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        self._practice_sweeper: Optional[threading.Thread] = None
        self._practice_sweep_stop: Optional[threading.Event] = None
        self._device_status: Dict[str, Dict[str, Any]] = {
            item.key: {"state": "unregistered", "detail": "bridge manager not registered"}
            for item in ALL_HARDWARE
        }

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    def set_mode(self, mode: str) -> str:
        normalized = str(mode).strip().lower()
        if normalized not in {"live", "test"}:
            raise LabError("Lab mode must be 'live' or 'test'")
        with self._lock:
            previous = self._mode
            self._mode = normalized
        self.record_diagnostic("lab", "mode", normalized)
        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # Test mode no longer mirrors the virtual practice cockpit to physical
        # output automatically.  Only an explicit lab_output/lab_output_test
        # request may light a tested output; everything else remains dark/off.
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<
        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        # Practice is an experiment sandbox and owns nothing once it ends:
        # leaving it darkens every panel Practice lit, and entering it starts
        # the idle sweeper that darkens a panel you have stopped using.
        if normalized == "test":
            self._start_practice_sweeper()
        elif previous == "test":
            self._stop_practice_sweeper()
            self._darken_practice_devices(self._practice_preview.sleep_all())
        return normalized

    def _start_practice_sweeper(self) -> None:
        with self._lock:
            thread = self._practice_sweeper
            if thread is not None and thread.is_alive():
                return
            self._practice_sweep_stop = threading.Event()
            stop = self._practice_sweep_stop
            self._practice_sweeper = threading.Thread(
                target=self._practice_sweep,
                args=(stop,),
                name="MuslimSim-practice-sleep",
                daemon=True,
            )
            thread = self._practice_sweeper
        thread.start()

    def _stop_practice_sweeper(self) -> None:
        with self._lock:
            stop = self._practice_sweep_stop
            self._practice_sweeper = None
            self._practice_sweep_stop = None
        if stop is not None:
            stop.set()

    def _practice_sweep(self, stop: "threading.Event") -> None:
        """Return each idle practised device to its sleeping state."""

        while not stop.wait(PRACTICE_SLEEP_SWEEP_SECONDS):
            with self._lock:
                if self._mode != "test":
                    continue
            try:
                self._darken_practice_devices(self._practice_preview.expire())
            except Exception as exc:
                self.record_diagnostic("lab", "practice-sleep-error", str(exc))

    def practice_wake(self, device_key: str) -> Dict[str, Any]:
        """Light one device's indicators because its page is being practised.

        MUSLIMSIM_PRACTICE_ALL_DEVICES_V1: exercising a control is not the only
        way to ask a device to prove itself - opening its page is too, and for
        a device whose inputs are not catalogued yet (ECAM32) it is the only
        way.  Refused outside Practice, and the device sleeps on its own.
        """

        self._device(device_key)
        with self._lock:
            if self._mode != "test":
                self.record_diagnostic(device_key, "practice-wake-ignored", {
                    "mode": self._mode,
                })
                return {"device": device_key, "awake": False, "mode": self._mode}
            if not self.device_enabled(device_key):
                return {
                    "device": device_key, "awake": False, "disabled": True,
                }
            self._practice_preview.wake(device_key)
            snapshot = self._practice_preview.snapshot()
            sink = self._practice_output_sink

        if sink is not None:
            self._emit_practice_snapshot(sink, snapshot, only_device=device_key)
        self.record_diagnostic(device_key, "practice-wake", {"awake": True})
        return {"device": device_key, "awake": True, "mode": "test"}

    def _darken_practice_devices(self, devices: "Iterable[str]") -> None:
        """Publish the dark frame for devices whose practice session ended."""

        for device_key in tuple(devices):
            with self._lock:
                snapshot = self._practice_preview.snapshot()
                sink = self._practice_output_sink
            if sink is None:
                continue
            self._emit_practice_snapshot(
                sink, snapshot, only_device=device_key
            )

    def set_practice_output_sink(self, sink: Optional[PracticeOutputSink]) -> None:
        """Attach the bridge-owned adapter for verified practice outputs.

        The callback only receives the declarative snapshot; it decides which
        driver APIs are actually supported.  This keeps virtual cockpit state
        independent from both Tk and raw HID writes.
        """

        with self._lock:
            self._practice_output_sink = sink
        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # Registering a physical output sink must not wake hardware simply
        # because Test mode is active.  Explicit tests still use lab_output.
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<

    def set_practice_input_sink(self, sink: Optional[PracticeInputSink]) -> None:
        """Register a bridge-owned response for captured Test-mode inputs."""

        with self._lock:
            self._practice_input_sink = sink

    def practice_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return the bridge-owned simulator-down cockpit snapshot."""

        with self._lock:
            return {key: dict(value) for key, value in self._practice_preview.snapshot().items()}

    def _emit_practice_snapshot(
        self,
        sink: PracticeOutputSink,
        snapshot: Mapping[str, Mapping[str, Any]],
        *,
        only_device: Optional[str] = None,
    ) -> None:
        try:
            sink(snapshot, only_device=only_device)
        except Exception as exc:
            # A missing/unsupported physical adapter must never stop the real
            # control reader or discard the visual laboratory state.
            self.record_diagnostic("lab", "practice-output-error", str(exc))

    def _advance_practice(
        self,
        device_key: str,
        control_key: str,
        phase: str,
    ) -> None:
        """Apply a physical or virtual press to the bridge practice model."""

        if phase == "release":
            return
        with self._lock:
            if self._mode != "test":
                return
            self._practice_preview.activate(device_key, control_key)
            snapshot = self._practice_preview.snapshot()
            sink = self._practice_output_sink
        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # Test mode is active-test-only, but pressing a control *is* asking to
        # test it, so the device that was pressed still updates.  The emission
        # is restricted to that one device: a single press must never wake
        # every screen and lamp in the practice snapshot, which is what the
        # unscoped mirror used to do.
        if sink is not None:
            self._emit_practice_snapshot(sink, snapshot, only_device=device_key)
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<

    def set_simulator_connected(self, connected: bool) -> None:
        with self._lock:
            self._simulator_connected = bool(connected)

    def set_aircraft_context(
        self,
        profile: str,
        path: str = "",
        mapping_aircraft: str = "",
    ) -> None:
        """Publish the detected aircraft identity without creating a write path."""

        with self._lock:
            self._aircraft_context = {
                "profile": str(profile or "unresolved"),
                "path": str(path or ""),
                "mapping_aircraft": str(mapping_aircraft or ""),
            }

    def set_device_status(self, device_key: str, state: str, detail: str = "") -> None:
        self._device(device_key)
        with self._lock:
            self._device_status[device_key] = {"state": str(state), "detail": str(detail)}

    def device_enabled(self, device_key: str) -> bool:
        """Whether the active profile permits this device to operate."""

        self._device(device_key)
        if self.profile_store is None:
            return True
        return self.profile_store.device_enabled(device_key)

    def configure_device_enabled(self, device_key: str, enabled: bool) -> bool:
        """Persist a device's active-profile on/off selection."""

        self._device(device_key)
        if self.profile_store is None:
            raise LabError("No hardware profile store is attached")
        try:
            result = self.profile_store.set_device_enabled(device_key, enabled)
            self.profile_store.save()
        except ProfileError as exc:
            raise LabError(str(exc)) from exc
        self.record_diagnostic(device_key, "device-enabled", result)
        return result

    def _device(self, device_key: str):
        device = device_by_key(device_key)
        if device is None:
            raise LabError(f"Unknown device {device_key!r}")
        return device

    def _control(self, device_key: str, control_key: str) -> ControlSpec:
        self._device(device_key)
        control = runtime_control_by_key(device_key, control_key)
        if control is None:
            raise LabError(f"Unknown control {device_key}.{control_key}")
        return control

    @staticmethod
    def _number(value: Any) -> float:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise LabError("Control value must be numeric") from exc
        if not math.isfinite(result):
            raise LabError("Control value must be finite")
        return result

    def record_diagnostic(self, device: str, event: str, detail: Any) -> None:
        item = {"time": time.time(), "device": str(device), "event": str(event), "detail": detail}
        with self._lock:
            self._diagnostics.append(item)
            del self._diagnostics[:-200]

    def _binding(self, device_key: str, control_key: str) -> MappingBinding:
        if self.profile_store is None:
            return MappingBinding()
        # A saved entry is the owner's explicit choice and always wins, even
        # when it is ``disabled``.  Only when the profile says nothing about
        # this control may a declared device default apply -- which preserves
        # the existing meaning of an absent entry for every other device,
        # since ``DEFAULT_BINDINGS`` names only hardware that has no bridge
        # dispatcher of its own to fall through to.
        if not self.profile_store.has_binding(device_key, control_key):
            default = DEFAULT_BINDINGS.get(device_key, {}).get(control_key)
            if default is not None:
                return MappingBinding(**default)
        return self.profile_store.binding(device_key, control_key)

    def active_binding(self, device_key: str, control_key: str) -> MappingBinding:
        """Return one validated saved role for bridge-owned mechanics.

        Drivers use this only to decide whether a captured mechanical behavior
        (currently the PU starter's timed return) is requested.  The binding
        itself still routes through ``input`` and the normal safety checks.
        """

        return self._binding(device_key, control_key)

    def _route_binding(
        self,
        device_key: str,
        control_key: str,
        value: float,
        phase: str,
    ) -> bool:
        binding = self._binding(device_key, control_key)
        if binding.kind == "disabled" or self.binding_sink is None:
            return False
        try:
            self.binding_sink(device_key, control_key, binding, value, phase)
        except Exception as exc:
            self.record_diagnostic(device_key, "binding-error", str(exc))
            raise LabError(f"Mapping action failed: {exc}") from exc
        self.record_diagnostic(device_key, "binding", {"control": control_key, "kind": binding.kind, "target": binding.target})
        return True

    def input(
        self,
        device_key: str,
        control_key: str,
        value: Any,
        *,
        phase: str = "change",
        source: str = "virtual",
        route: bool = True,
    ) -> Dict[str, Any]:
        control = self._control(device_key, control_key)
        if not control.is_input:
            raise LabError(f"{device_key}.{control_key} is not an input")
        if control.status != "implemented":
            raise LabError(f"{device_key}.{control_key} is {control.status}; its behavior is intentionally not guessed")
        numeric = self._number(value)
        phase = str(phase or "change")
        if not self.device_enabled(device_key):
            # Returning routed=True tells the established bridge wrappers to
            # stop here instead of falling through to an older device-default
            # dispatcher. This applies to both physical and virtual input.
            self.record_diagnostic(device_key, "input-ignored-disabled", {
                "control": control_key, "value": numeric, "phase": phase, "source": source,
            })
            return {
                "control": control_key, "value": numeric, "phase": phase,
                "routed": True, "disabled": True,
            }
        current = {"value": numeric, "phase": phase, "source": source, "updated": time.time()}
        with self._lock:
            self._inputs.setdefault(device_key, {})[control_key] = current
        routed = self._route_binding(device_key, control_key, numeric, phase) if route else False
        self.record_diagnostic(device_key, "input", {"control": control_key, "value": numeric, "phase": phase, "source": source, "routed": routed})
        self._advance_practice(device_key, control_key, phase)
        with self._lock:
            practice_sink = self._practice_input_sink if self._mode == "test" else None
        if practice_sink is not None:
            try:
                practice_sink(device_key, control_key, numeric, phase)
            except Exception as exc:
                self.record_diagnostic(device_key, "practice-input-error", str(exc))
        return {"control": control_key, "value": numeric, "phase": phase, "routed": routed}

    def practice_input(
        self,
        device_key: str,
        control_key: str,
        value: Any,
        *,
        phase: str = "change",
        source: str = "virtual",
    ) -> Dict[str, Any]:
        """Accept a virtual control only while Test mode is authoritative.

        Studio lever motion is sent on short-lived loopback connections, and
        the control server intentionally handles those connections in parallel.
        Holding the Lab lock across the mode check and ``input`` call prevents
        a delayed Practice sample from crossing a simultaneous Test -> Live
        transition.  The lock is re-entrant because ``input`` and the binding
        sink read the same Lab state while this safety boundary is held.
        """

        with self._lock:
            if self._mode != "test":
                numeric = self._number(value)
                phase = str(phase or "change")
                self.record_diagnostic(device_key, "practice-input-ignored", {
                    "control": control_key,
                    "value": numeric,
                    "phase": phase,
                    "source": source,
                    "mode": self._mode,
                })
                return {
                    "control": control_key,
                    "value": numeric,
                    "phase": phase,
                    "routed": False,
                    "ignored": True,
                    "mode": self._mode,
                }
            return self.input(
                device_key,
                control_key,
                value,
                phase=phase,
                source=source,
            )

    def output(
        self,
        device_key: str,
        control_key: str,
        value: Any,
        *,
        source: str = "virtual",
    ) -> Dict[str, Any]:
        control = self._control(device_key, control_key)
        if not control.is_output:
            raise LabError(f"{device_key}.{control_key} is not an output")
        if control.status != "implemented" or not control.testable:
            message = control.notes or "No safe output driver is available"
            raise LabError(f"{device_key}.{control_key} cannot be driven: {message}")
        if not self.device_enabled(device_key):
            raise LabError(f"{device_key} is off in the active profile")
        # Displays can be text/number/pattern models; digital and analogue
        # outputs accept numeric or boolean values.  The actual driver adapter
        # decides whether the present hardware can receive this test state.
        if control.kind not in {"display"}:
            value = self._number(value)
        item = {"value": value, "source": source, "updated": time.time()}
        with self._lock:
            self._outputs.setdefault(device_key, {})[control_key] = item
        self.record_diagnostic(device_key, "output", {"control": control_key, "value": value, "source": source})
        return {"control": control_key, **item}

    def output_test(self, device_key: str, action: str, payload: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Apply a virtual-only standard display/indicator test pattern.

        A bridge adapter may mirror this to the physical device only when that
        driver's protocol is already known.  The requested output state is
        still visible in the panel when hardware is absent.
        """

        self._device(device_key)
        if not self.device_enabled(device_key):
            raise LabError(f"{device_key} is off in the active profile")
        payload = dict(payload or {})
        action = str(action).strip().lower()
        if action not in {"all_on", "all_off", "checker", "text", "values", "reset"}:
            raise LabError("Unknown output test action")
        self.set_mode("test")
        controls = device_by_key(device_key).controls  # type: ignore[union-attr]
        applied = []
        for control in controls:
            if not control.is_output or control.status != "implemented" or not control.testable:
                continue
            if action == "all_on":
                value: Any = "888888" if control.kind == "display" else 1.0
            elif action in {"all_off", "reset"}:
                value = "" if control.kind == "display" else 0.0
            elif action == "checker":
                value = "CHECKER" if control.kind == "display" else 1.0
            elif action == "text":
                value = str(payload.get("text", "MUSLIMSIM")) if control.kind == "display" else 1.0
            else:
                value = payload.get(control.key, payload.get("value", "0" if control.kind == "display" else 0.0))
            self.output(device_key, control.key, value, source=f"test:{action}")
            applied.append(control.key)
        return {"device": device_key, "action": action, "applied": applied, "virtual_only": True}

    def reset_device(self, device_key: str) -> None:
        self._device(device_key)
        with self._lock:
            self._inputs.pop(device_key, None)
            self._outputs.pop(device_key, None)
        self.record_diagnostic(device_key, "reset", "laboratory state reset")

    def restore_profile_defaults(self) -> None:
        if self.profile_store is None:
            raise LabError("No hardware profile store is attached")
        self.profile_store.restore_defaults()
        self.profile_store.save()
        self.record_diagnostic("lab", "profile-reset", self.profile_store.active_profile)

    def create_profile(self, name: str, *, copy_active: bool = True) -> Dict[str, Any]:
        """Create and select a named mapping/calibration profile atomically."""

        if self.profile_store is None:
            raise LabError("No hardware profile store is attached")
        try:
            self.profile_store.create(name, copy_active=copy_active)
            self.profile_store.save()
        except ProfileError as exc:
            raise LabError(str(exc)) from exc
        self.record_diagnostic("lab", "profile-created", self.profile_store.active_profile)
        return self.profile_store.snapshot()

    def select_profile(self, name: str) -> Dict[str, Any]:
        """Select a saved profile before applying any device calibration."""

        if self.profile_store is None:
            raise LabError("No hardware profile store is attached")
        try:
            self.profile_store.select(name)
            self.profile_store.save()
        except ProfileError as exc:
            raise LabError(str(exc)) from exc
        self.record_diagnostic("lab", "profile-selected", self.profile_store.active_profile)
        return self.profile_store.snapshot()

    def active_calibration(self, device_key: str) -> Dict[str, Any]:
        if self.profile_store is None:
            return {}
        values = self.profile_store.calibration(device_key)
        # This is the bridge's documented neutral timing, not a guessed motor
        # setting.  Selecting a profile without a PU override must not retain
        # the previous profile's actuator timing in memory.
        if device_key == "pu_overhead" and not values:
            return {"starter_retract_ms": 310}
        return values

    def configure_binding(self, device_key: str, control_key: str, binding: MappingBinding) -> MappingBinding:
        if self.profile_store is None:
            raise LabError("No hardware profile store is attached")
        try:
            checked = self.profile_store.set_binding(device_key, control_key, binding)
            self.profile_store.save()
        except ProfileError as exc:
            raise LabError(str(exc)) from exc
        self.record_diagnostic(device_key, "binding-saved", {"control": control_key, "binding": asdict(checked)})
        return checked

    def configure_learned_control(self, device_key: str, visual_key: str, raw_control: str) -> str:
        """Persist a user-confirmed visual-control to raw-HID relationship."""

        if self.profile_store is None:
            raise LabError("No hardware profile store is attached")
        try:
            assigned = self.profile_store.set_learned_control(device_key, visual_key, raw_control)
            self.profile_store.save()
        except ProfileError as exc:
            raise LabError(str(exc)) from exc
        self.record_diagnostic(device_key, "control-learned", {"visual": visual_key, "raw": assigned})
        return assigned

    def learned_controls(self, device_key: str) -> Dict[str, str]:
        if self.profile_store is None:
            return {}
        return self.profile_store.learned_controls(device_key)

    def configure_custom_label(self, device_key: str, visual_key: str, label: str) -> str:
        """Persist an owner-typed display name; purely cosmetic."""

        if self.profile_store is None:
            raise LabError("No hardware profile store is attached")
        try:
            saved = self.profile_store.set_custom_label(device_key, visual_key, label)
            self.profile_store.save()
        except ProfileError as exc:
            raise LabError(str(exc)) from exc
        self.record_diagnostic(device_key, "label-saved", {"visual": visual_key, "label": saved})
        return saved

    def configure_calibration(self, device_key: str, values: Mapping[str, Any]) -> None:
        if self.profile_store is None:
            raise LabError("No hardware profile store is attached")
        try:
            self.profile_store.set_calibration(device_key, values)
            self.profile_store.save()
        except ProfileError as exc:
            raise LabError(str(exc)) from exc
        self.record_diagnostic(device_key, "calibration-saved", dict(values))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode,
                "simulator_connected": self._simulator_connected,
                "aircraft": dict(self._aircraft_context),
                "device_status": {key: dict(value) for key, value in self._device_status.items()},
                "device_enabled": {
                    item.key: self.device_enabled(item.key) for item in ALL_HARDWARE
                },
                "inputs": {device: {key: dict(item) for key, item in values.items()} for device, values in self._inputs.items()},
                "outputs": {device: {key: dict(item) for key, item in values.items()} for device, values in self._outputs.items()},
                "practice_preview": {key: dict(value) for key, value in self._practice_preview.snapshot().items()},
                "practice_preview_owner": "bridge",
                "diagnostics": list(self._diagnostics[-100:]),
                "profile": self.profile_store.snapshot() if self.profile_store is not None else None,
            }

    def catalogue(self) -> Dict[str, Any]:
        return dict(catalogue_snapshot())

    def self_test(self) -> Dict[str, Any]:
        """A no-hardware consistency test used by the GUI and CLI check."""

        errors: list[str] = []
        for device in ALL_HARDWARE:
            seen = set()
            for control in device.controls:
                if control.key in seen:
                    errors.append(f"duplicate control {device.key}.{control.key}")
                seen.add(control.key)
                if control.remappable and (not control.is_input or control.status != "implemented"):
                    errors.append(f"invalid remappable flag {device.key}.{control.key}")
        if self.profile_store is not None:
            try:
                self.profile_store._validate_document()  # Internal validation without writing.
            except ProfileError as exc:
                errors.append(str(exc))
        return {"ok": not errors, "errors": errors, "devices": len(ALL_HARDWARE)}
