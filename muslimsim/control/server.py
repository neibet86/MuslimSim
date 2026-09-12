"""A small authenticated loopback JSON-lines server inside the bridge."""

from __future__ import annotations

from dataclasses import dataclass
import socketserver
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional

from .protocol import PROTOCOL_VERSION, ProtocolError, decode, encode, new_token
from ..hardware.lab import HardwareLab, LabError
from ..hardware.profiles import MappingBinding, ProfileError


StatusCallback = Callable[[], Any]
ActionCallback = Callable[[], Any]
OutputCallback = Callable[[str, Any], Any]
PowerCycleCallback = Callable[[], Any]
CalibrationCallback = Callable[[Mapping[str, Any]], Any]
CommandCallback = Callable[[str, Mapping[str, Any]], Any]
FunctionCatalogCallback = Callable[[str, int, str], Mapping[str, Any]]
HardwareDiscoveryCallback = Callable[[], Mapping[str, Any]]


@dataclass(frozen=True)
class DeviceRegistration:
    """Bridge callbacks for a device manager, kept independent from its driver."""

    key: str
    start: Optional[ActionCallback] = None
    stop: Optional[ActionCallback] = None
    status: Optional[StatusCallback] = None
    diagnostics: Optional[StatusCallback] = None
    output: Optional[OutputCallback] = None
    power_cycle: Optional[PowerCycleCallback] = None
    calibration: Optional[CalibrationCallback] = None
    # A free-form (action, payload) -> result passthrough with no HardwareLab
    # catalog/calibration-schema validation, for device-specific corrective
    # actions that are neither a cataloged numeric/boolean output nor a
    # Moza-style bounded calibration setting - e.g. MOZA A210's Studio axis-
    # assignment correction (see bridge/final.py's
    # _muslimsim_moza_a210_axis_calibration). Dispatched the same
    # deliberately raw way power_cycle already is.
    command: Optional[CommandCallback] = None


DEVICE_STATUS_TTL_SECONDS = 0.5


class ControlServer:
    """Owns only the loopback listener, never a device or a UI thread."""

    def __init__(
        self,
        lab: HardwareLab,
        *,
        port: int = 0,
        token: Optional[str] = None,
        shutdown: Optional[Callable[[], None]] = None,
        function_catalog: Optional[FunctionCatalogCallback] = None,
        hardware_discovery: Optional[HardwareDiscoveryCallback] = None,
    ) -> None:
        self.lab = lab
        self.requested_port = int(port)
        self.token = str(token or new_token())
        self.shutdown_callback = shutdown
        self.function_catalog = function_catalog
        self.hardware_discovery = hardware_discovery
        self._lock = threading.RLock()
        # HID and Windows-controller enumeration can take noticeably longer
        # than a normal status pulse.  Cache it briefly so Studio gets the
        # same inventory through both Rescan and regular status updates,
        # without making its 70 ms UI pulse wait for USB enumeration.
        self._hardware_discovery_lock = threading.Lock()
        self._hardware_discovery_at = 0.0
        self._hardware_discovery_cache: Dict[str, Any] = {
            "devices": [], "source": "unavailable",
        }
        self._hardware_discovery_refreshing = False
        # Device status/diagnostics callbacks talk to real hardware.  One slow
        # driver made the whole status reply exceed Studio's client timeout, so
        # every poll failed and the UI stopped receiving live physical input.
        # Collect them on the same cached/background pattern as discovery.
        self._device_status_lock = threading.Lock()
        self._device_status_at = 0.0
        self._device_status_cache: Dict[str, Any] = {}
        self._device_status_refreshing = False
        self._devices: Dict[str, DeviceRegistration] = {}
        # Devices stopped by the selected profile. This state is deliberately
        # kept in the bridge—not Tk—so a profile change remains safe while
        # Studio is closed or reconnecting.
        self._disabled_by_profile: set[str] = set()
        self._server: Optional[socketserver.ThreadingTCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._practice_signature = ""

    @property
    def port(self) -> Optional[int]:
        with self._lock:
            if self._server is None:
                return None
            return int(self._server.server_address[1])

    def start(self) -> int:
        with self._lock:
            if self._server is not None:
                return int(self._server.server_address[1])
            parent = self

            class Handler(socketserver.StreamRequestHandler):
                def handle(self) -> None:  # pragma: no cover - integration-tested via client
                    self.connection.settimeout(1.5)
                    line = self.rfile.readline()
                    try:
                        request = decode(line)
                        response = parent.handle(request)
                    except ProtocolError as exc:
                        response = {"ok": False, "error": str(exc)}
                    except Exception:
                        # Deliberately avoid leaking a bridge traceback over the
                        # local socket.  The bridge owns detailed diagnostics.
                        response = {"ok": False, "error": "Request failed"}
                    try:
                        self.wfile.write(encode(response))
                    except OSError:
                        pass

            class Server(socketserver.ThreadingTCPServer):
                allow_reuse_address = True
                daemon_threads = True

            self._server = Server(("127.0.0.1", self.requested_port), Handler)
            self._thread = threading.Thread(target=self._server.serve_forever, name="MuslimSim-Control", daemon=True)
            self._thread.start()
            # Do the first potentially-slow Windows controller read in a
            # background bridge worker.  The server starts immediately, so
            # Studio never mistakes one slow USB enumeration for a freeze.
            self._schedule_hardware_inventory(force=True)
            return int(self._server.server_address[1])

    def stop(self) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=1.5)

    def register(self, registration: DeviceRegistration) -> None:
        with self._lock:
            self._devices[registration.key] = registration
        if self.lab.device_enabled(registration.key):
            with self._lock:
                self._disabled_by_profile.discard(registration.key)
            self.lab.set_device_status(registration.key, "registered")
        else:
            # Most managers are constructed before they can be registered.
            # Stop this fresh instance immediately when the active profile
            # says it is off, rather than waiting for the first UI status poll.
            self._apply_device_enabled(registration.key, False, force=True)
        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # Test mode is active-test-only.  A late-registering driver must not be
        # given the whole practice snapshot, because that wakes outputs the user
        # did not request to test.  Explicit lab_output/lab_output_test remains
        # the only physical Test-mode output path.
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<

    def unregister(self, key: str) -> None:
        with self._lock:
            self._devices.pop(key, None)
        self.lab.set_device_status(key, "unregistered")

    def _authorised(self, request: Mapping[str, Any]) -> bool:
        supplied = request.get("token")
        # compare_digest avoids making token probing timing-visible.
        import hmac
        return isinstance(supplied, str) and hmac.compare_digest(supplied, self.token)

    def _device(self, key: Any) -> DeviceRegistration:
        with self._lock:
            device = self._devices.get(str(key))
        if device is None:
            raise LabError(f"Device {key!r} is not registered by this bridge")
        return device

    @staticmethod
    def _status_value(callback: Optional[StatusCallback], fallback: str) -> Dict[str, Any]:
        if callback is None:
            return {"state": fallback}
        value = callback()
        return dict(value) if isinstance(value, Mapping) else {"state": str(value)}

    def _device_statuses(self) -> Dict[str, Any]:
        with self._lock:
            entries = list(self._devices.items())
        result: Dict[str, Any] = {}
        for key, entry in entries:
            try:
                if not self.lab.device_enabled(key):
                    state = {"state": "disabled", "detail": "off in the active aircraft/profile"}
                    result[key] = state
                    self.lab.set_device_status(key, "disabled", state["detail"])
                    continue
                state = self._status_value(entry.status, "registered")
                if entry.diagnostics is not None:
                    detail = entry.diagnostics()
                    if detail is not None:
                        state["diagnostics"] = detail
                result[key] = state
                self.lab.set_device_status(key, str(state.get("state", "registered")), str(state.get("detail", "")))
            except Exception as exc:
                result[key] = {"state": "error", "detail": str(exc)}
        return result

    def _refresh_device_statuses(self) -> None:
        """Collect every device status outside the request-response path."""

        started = time.monotonic()
        slow: Dict[str, float] = {}
        with self._lock:
            entries = list(self._devices.items())
        result: Dict[str, Any] = {}
        for key, entry in entries:
            began = time.monotonic()
            try:
                if not self.lab.device_enabled(key):
                    state = {"state": "disabled", "detail": "off in the active aircraft/profile"}
                    result[key] = state
                    self.lab.set_device_status(key, "disabled", state["detail"])
                    continue
                state = self._status_value(entry.status, "registered")
                if entry.diagnostics is not None:
                    detail = entry.diagnostics()
                    if detail is not None:
                        state["diagnostics"] = detail
                result[key] = state
                self.lab.set_device_status(key, str(state.get("state", "registered")), str(state.get("detail", "")))
            except Exception as exc:
                result[key] = {"state": "error", "detail": str(exc)}
            finally:
                spent = time.monotonic() - began
                if spent >= 0.25:
                    slow[key] = round(spent, 3)
        with self._device_status_lock:
            self._device_status_cache = result
            self._device_status_at = time.monotonic()
            self._device_status_refreshing = False
        if slow:
            try:
                self.lab.record_diagnostic("control_server", "slow-device-status", {
                    "total": round(time.monotonic() - started, 3), "devices": slow,
                })
            except Exception:
                pass

    def _schedule_device_statuses(self, *, force: bool = False) -> None:
        """Start one background status sweep when the cache is stale."""

        now = time.monotonic()
        with self._device_status_lock:
            if self._device_status_refreshing or (
                not force and now - self._device_status_at < DEVICE_STATUS_TTL_SECONDS
            ):
                return
            self._device_status_refreshing = True
        threading.Thread(
            target=self._refresh_device_statuses,
            name="MuslimSim-Device-Status",
            daemon=True,
        ).start()

    def _device_statuses_cached(self) -> Dict[str, Any]:
        """Return the last good statuses immediately and refresh in background."""

        with self._device_status_lock:
            populated = self._device_status_at > 0.0
            cached = dict(self._device_status_cache)
        if not populated:
            # Studio builds its device list from the first reply, so that one
            # is collected synchronously rather than answered empty.
            self._refresh_device_statuses()
            with self._device_status_lock:
                return dict(self._device_status_cache)
        self._schedule_device_statuses()
        return cached

    def _refresh_hardware_inventory(self) -> None:
        """Refresh the physical inventory outside the request-response path."""

        try:
            result = dict(self.hardware_discovery()) if self.hardware_discovery is not None else {
                "devices": [], "source": "unavailable",
            }
            devices = result.get("devices")
            if not isinstance(devices, list):
                result["devices"] = list(devices or ())
            result.setdefault("source", "bridge-hid")
            failed = False
        except Exception:
            result = None
            failed = True
        with self._hardware_discovery_lock:
            if result is not None:
                self._hardware_discovery_cache = result
            elif self._hardware_discovery_cache:
                self._hardware_discovery_cache = dict(self._hardware_discovery_cache)
                self._hardware_discovery_cache["stale"] = True
            self._hardware_discovery_at = time.monotonic()
            self._hardware_discovery_refreshing = False

    def _schedule_hardware_inventory(self, *, force: bool = False) -> None:
        """Start one read-only inventory refresh when the cache is stale."""

        if self.hardware_discovery is None:
            return
        now = time.monotonic()
        with self._hardware_discovery_lock:
            # Windows' generic-controller query is deliberately read-only
            # but can take around a second.  Three seconds keeps routine
            # status pulses instant; Rescan can always request a fresh read.
            if self._hardware_discovery_refreshing or (
                not force and now - self._hardware_discovery_at < 3.0
            ):
                return
            self._hardware_discovery_refreshing = True
        threading.Thread(
            target=self._refresh_hardware_inventory,
            name="MuslimSim-Hardware-Discovery",
            daemon=True,
        ).start()

    def _hardware_inventory(self, *, force: bool = False) -> Dict[str, Any]:
        """Return the last good inventory immediately and refresh in background."""

        if self.hardware_discovery is None:
            return {"devices": [], "source": "unavailable"}
        self._schedule_hardware_inventory(force=force)
        with self._hardware_discovery_lock:
            result = dict(self._hardware_discovery_cache)
            if self._hardware_discovery_refreshing:
                result["refreshing"] = True
            return result

    def _run_device_action(self, request: Mapping[str, Any], action: str) -> Mapping[str, Any]:
        entry = self._device(request.get("device"))
        if action == "start" and not self.lab.device_enabled(entry.key):
            raise LabError(f"{entry.key} is off in the active profile; turn it on first")
        callback = getattr(entry, action)
        if callback is None:
            raise LabError(f"{entry.key} does not support {action}")
        callback()
        state = self._status_value(entry.status, "running" if action in {"start", "restart"} else "stopped")
        self.lab.set_device_status(entry.key, str(state.get("state", "unknown")), str(state.get("detail", "")))
        return {"device": entry.key, "state": state}

    def _apply_device_enabled(self, device_key: str, enabled: bool, *, force: bool = False) -> Dict[str, Any]:
        """Start/stop a registered manager for the active profile selection.

        A driver without a captured stop callback is still made inert by the
        lab's device gate. We never invent a low-level USB stop sequence.
        """

        try:
            entry = self._device(device_key)
        except LabError:
            # The choice may be made before a panel is connected. Persist it
            # now; registration will honour it later in this same bridge.
            state = {
                "state": "disabled" if not enabled else "unregistered",
                "detail": "off in the active aircraft/profile" if not enabled else "waiting for this device to connect",
            }
            self.lab.set_device_status(device_key, state["state"], state["detail"])
            return {"device": device_key, "enabled": enabled, "state": state}
        with self._lock:
            was_disabled = entry.key in self._disabled_by_profile
        if not enabled:
            if force or not was_disabled:
                if entry.stop is not None:
                    entry.stop()
                self.lab.reset_device(entry.key)
            with self._lock:
                self._disabled_by_profile.add(entry.key)
            state = {"state": "disabled", "detail": "off in the active aircraft/profile"}
            self.lab.set_device_status(entry.key, state["state"], state["detail"])
            return {"device": entry.key, "enabled": False, "state": state}

        if was_disabled and entry.start is not None:
            entry.start()
        with self._lock:
            self._disabled_by_profile.discard(entry.key)
        state = self._status_value(entry.status, "running" if entry.start is not None else "registered")
        self.lab.set_device_status(entry.key, str(state.get("state", "registered")), str(state.get("detail", "")))
        return {"device": entry.key, "enabled": True, "state": state}

    def _apply_profile_device_enablement(self) -> None:
        """Reconcile every registered device after a profile change."""

        with self._lock:
            keys = tuple(self._devices)
        for key in keys:
            self._apply_device_enabled(key, self.lab.device_enabled(key))

    def _apply_output(self, device_key: str, control_key: str, value: Any) -> None:
        """Forward a test state only to the driver's explicitly registered API."""

        with self._lock:
            entry = self._devices.get(device_key)
        if entry is not None and entry.output is not None:
            entry.output(control_key, value)

    def apply_lab_output(
        self,
        device_key: str,
        control_key: str,
        value: Any,
        *,
        source: str,
    ) -> Dict[str, Any]:
        """Store and forward a supported output through one safe path."""

        result = self.lab.output(device_key, control_key, value, source=source)
        self._apply_output(device_key, control_key, result["value"])
        return result

    def apply_practice_snapshot(
        self,
        snapshot: Mapping[str, Mapping[str, Any]],
        *,
        force: bool = False,
        only_device: Optional[str] = None,
    ) -> None:
        """Mirror bridge-owned practice state only through captured drivers.

        It contains no raw HID protocol.  Unsupported or not-yet-registered
        controls remain visible in the snapshot but are never guessed at.
        """

        fcu = dict(snapshot.get("fcu_32_efis") or {})
        pap = dict(snapshot.get("pap3_mag") or {})
        agp = dict(snapshot.get("agp_bb80") or {})
        pfp = dict(snapshot.get("pfp3n_bb35") or {})
        mcdu = dict(snapshot.get("mcdu32_bb36") or {})
        fcu_values = dict(fcu.get("values") or {})
        pap_values = dict(pap.get("values") or {})
        agp_values = tuple(str(value) for value in list(agp.get("values") or ())[:3])
        pfp_lines = list(pfp.get("lines") or ())
        mcdu_lines = list(mcdu.get("lines") or ())
        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # ``only_device`` restricts the mirror to the device actually being
        # tested.  It is part of the signature because the same snapshot
        # scoped to a different device is a different physical write, and a
        # cached signature must not suppress it.
        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        # Every device's capture-proven lamp/LED practice state, including the
        # twelve that have no authored practice page here.  Collected before
        # the signature so a lamp going dark is never suppressed as unchanged.
        echo_outputs = {
            str(device): dict(entry.get("outputs") or {})
            for device, entry in snapshot.items()
            if isinstance(entry, Mapping) and entry.get("outputs")
        }
        signature = repr(
            (
                fcu_values, pap_values, agp_values, pfp_lines, mcdu_lines,
                echo_outputs, only_device,
            )
        )
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<
        with self._lock:
            if not force and signature == self._practice_signature:
                return
            self._practice_signature = signature

        updates: list[tuple[str, str, Any]] = [
            ("fcu_32_efis", "fcu_windows", fcu_values),
            # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
            # These two backlights were written unconditionally on every
            # mirror, which is one of the "woken with non-zero brightness
            # before power is known" cases the authority exists to stop.  They
            # are still needed to *see* the device under test, so they are kept
            # and the whole update list is scoped to that device below.
            ("fcu_32_efis", "backlight", 180),
            # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<
            ("pap3_mag", "lcd", pap_values),
            ("pap3_mag", "backlight", 1),
        ]
        if len(agp_values) == 3:
            updates.extend(("agp_bb80", key, value) for key, value in zip(("chr", "utc", "et"), agp_values))
        for device_key, lines in (("pfp3n_bb35", pfp_lines), ("mcdu32_bb36", mcdu_lines)):
            if len(lines) == 14:
                updates.append((device_key, "screen", {"lines": lines}))
        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        # These go through the same single safe path as everything above:
        # apply_lab_output, which refuses any control the catalogue has not
        # marked implemented and testable.  No vendor packet is invented here.
        for device_key, controls in sorted(echo_outputs.items()):
            for control_key, value in sorted(controls.items()):
                updates.append((device_key, control_key, value))
        for device_key, control_key, value in updates:
            if only_device is not None and device_key != only_device:
                continue
            try:
                self.apply_lab_output(device_key, control_key, value, source="bridge-practice")
            except LabError:
                # Registered devices are allowed to expose a smaller output
                # surface than the virtual cockpit.  Their unimplemented
                # screen/control remains explicitly virtual.
                continue

    def _apply_active_calibrations(self) -> None:
        """Apply the selected profile only through registered driver hooks."""

        with self._lock:
            entries = list(self._devices.values())
        for entry in entries:
            if entry.calibration is None:
                continue
            settings = self.lab.active_calibration(entry.key)
            if settings:
                entry.calibration(settings)

    def handle(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        command = str(request.get("cmd") or "").strip().lower()
        if not self._authorised(request):
            return {"ok": False, "error": "Not authorised"}
        try:
            if command == "ping":
                return {"ok": True, "protocol": PROTOCOL_VERSION, "devices": list(self._devices), "mode": self.lab.mode}
            if command == "device_diagnostics":
                # Targeted read of the existing owner's in-memory diagnostics.
                # No enumeration, output, profile write or second input reader.
                entry = self._device(request.get("device"))
                if entry.diagnostics is None:
                    raise LabError(f"{entry.key} has no diagnostics snapshot")
                return {"ok": True, "device": entry.key, "mode": self.lab.mode,
                        "diagnostics": self._status_value(entry.diagnostics, "unknown")}
            if command == "catalog":
                return {"ok": True, "catalog": self.lab.catalogue()}
            if command == "hardware_discovery":
                # The bridge runtime has the actual HID dependencies even
                # when Studio is running under a UI-only Python build.  This
                # read-only endpoint makes newly attached panels visible
                # without opening a handle, changing device state, or
                # requiring an already-registered manager.
                result = self._hardware_inventory(force=bool(request.get("force", False)))
                result["ok"] = True
                return result
            if command == "function_catalog":
                # The catalogue provider is bridge-owned because only the
                # child bridge knows which X-Plane/Zibo session is currently
                # running.  It returns choices only; selecting one still
                # goes through the normal validated binding path below.
                if self.function_catalog is None:
                    return {"ok": True, "functions": [], "source": "unavailable"}
                query = str(request.get("query") or "")
                aircraft = str(request.get("aircraft") or "")
                try:
                    limit = max(1, min(1000, int(request.get("limit", 700))))
                except (TypeError, ValueError):
                    limit = 700
                result = dict(self.function_catalog(query, limit, aircraft))
                result["ok"] = True
                return result
            if command in {"status", "telemetry", "lab_state"}:
                # Include the cached physical inventory here too.  It makes
                # newly connected generic controllers appear even if a
                # one-off Rescan request occurs during bridge startup.
                return {
                    "ok": True,
                    "devices": self._device_statuses_cached(),
                    "hardware_discovery": self._hardware_inventory(),
                    "lab": self.lab.snapshot(),
                }
            if command in {"start", "stop", "restart"}:
                if command == "restart":
                    entry = self._device(request.get("device"))
                    if entry.stop is None or entry.start is None:
                        raise LabError(f"{entry.key} cannot be restarted")
                    entry.stop()
                    entry.start()
                    state = self._status_value(entry.status, "running")
                    return {"ok": True, "device": entry.key, "state": state}
                return {"ok": True, **self._run_device_action(request, command)}
            if command == "device_enable_set":
                device_key = str(request.get("device", ""))
                enabled = request.get("enabled")
                if not isinstance(enabled, bool):
                    raise LabError("Device activation must be on or off")
                self.lab.configure_device_enabled(device_key, enabled)
                result = self._apply_device_enabled(device_key, enabled)
                # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
                # Enabling a device in Test mode must not automatically replay
                # the practice cockpit to its physical outputs.
                # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<
                return {"ok": True, **result, "profile": self.lab.profile_store.snapshot() if self.lab.profile_store is not None else None}
            if command == "power_cycle":
                entry = self._device(request.get("device"))
                if entry.power_cycle is None:
                    raise LabError(f"{entry.key} does not have a verified power-cycle path")
                return {"ok": True, "device": entry.key, "result": entry.power_cycle()}
            if command == "device_command":
                entry = self._device(request.get("device"))
                if entry.command is None:
                    raise LabError(f"{entry.key} does not accept device commands")
                action = str(request.get("action", ""))
                payload = dict(request.get("payload") or {})
                return {"ok": True, "device": entry.key, "result": entry.command(action, payload)}
            if command == "lab_mode":
                mode = self.lab.set_mode(str(request.get("mode", "")))
                # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
                # Entering Test mode no longer wakes every registered output.
                # The user must request a specific output test.
                # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<
                return {"ok": True, "mode": mode}
            if command == "practice_wake":
                # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
                # Opening a device's page in Practice is asking that device to
                # show it works, which is the whole purpose of Practice.  It is
                # refused outside Practice, and the device sleeps again on its
                # own once the page is left.  ECAM32 in particular has no
                # catalogued input yet, so this is its only way to respond.
                return {
                    "ok": True,
                    **self.lab.practice_wake(str(request.get("device", ""))),
                }
            if command == "lab_input":
                apply_input = (
                    self.lab.practice_input
                    if bool(request.get("practice_only"))
                    else self.lab.input
                )
                result = apply_input(
                    str(request.get("device", "")),
                    str(request.get("control", "")),
                    request.get("value", 0),
                    phase=str(request.get("phase", "change")),
                    source="virtual",
                )
                return {"ok": True, "result": result}
            if command == "lab_output":
                device_key = str(request.get("device", ""))
                control_key = str(request.get("control", ""))
                result = self.apply_lab_output(
                    device_key, control_key, request.get("value", 0), source="virtual",
                )
                return {"ok": True, "result": result}
            if command == "lab_output_test":
                device_key = str(request.get("device", ""))
                result = self.lab.output_test(device_key, str(request.get("action", "")), request.get("payload"))
                snapshot = self.lab.snapshot().get("outputs", {}).get(device_key, {})
                for control_key, item in snapshot.items():
                    self._apply_output(device_key, control_key, item.get("value"))
                return {"ok": True, "result": result}
            if command == "lab_reset":
                self.lab.reset_device(str(request.get("device", "")))
                return {"ok": True}
            if command == "profile_create":
                profile = self.lab.create_profile(
                    str(request.get("name", "")),
                    copy_active=bool(request.get("copy_active", True)),
                )
                self._apply_active_calibrations()
                self._apply_profile_device_enablement()
                return {"ok": True, "profile": profile}
            if command == "profile_select":
                profile = self.lab.select_profile(str(request.get("name", "")))
                self._apply_active_calibrations()
                self._apply_profile_device_enablement()
                return {"ok": True, "profile": profile}
            if command == "binding_set":
                raw = dict(request.get("binding") or {})
                binding = MappingBinding(**raw)
                checked = self.lab.configure_binding(str(request.get("device", "")), str(request.get("control", "")), binding)
                return {"ok": True, "binding": checked.__dict__}
            if command == "learn_set":
                device_key = str(request.get("device", ""))
                assigned = self.lab.configure_learned_control(
                    device_key,
                    str(request.get("visual", "")),
                    str(request.get("raw_control", "")),
                )
                return {"ok": True, "device": device_key, "raw_control": assigned}
            if command == "label_set":
                device_key = str(request.get("device", ""))
                saved = self.lab.configure_custom_label(
                    device_key,
                    str(request.get("visual", "")),
                    str(request.get("label", "")),
                )
                return {"ok": True, "device": device_key, "label": saved}
            if command == "calibration_set":
                device_key = str(request.get("device", ""))
                values = dict(request.get("values") or {})
                self.lab.configure_calibration(device_key, values)
                with self._lock:
                    entry = self._devices.get(device_key)
                if entry is not None and entry.calibration is not None:
                    entry.calibration(values)
                return {"ok": True}
            if command == "restore_defaults":
                self.lab.restore_profile_defaults()
                self._apply_active_calibrations()
                self._apply_profile_device_enablement()
                return {"ok": True}
            if command == "self_test":
                return {"ok": True, "result": self.lab.self_test()}
            if command == "shutdown":
                if self.shutdown_callback is not None:
                    threading.Thread(target=self.shutdown_callback, name="MuslimSim-Control-Shutdown", daemon=True).start()
                return {"ok": True, "state": "stopping"}
            raise LabError("Unknown command")
        except (LabError, ProfileError) as exc:
            return {"ok": False, "error": str(exc)}
