from __future__ import annotations

import os
import threading
import weakref
from pathlib import Path
from typing import Any, Mapping

from .locator import remove_locator, write_locator
from .runtime import PlatformRuntime

_INSTALL_LOCK = threading.RLock()
_INSTALLED = False
_RUNTIMES: "weakref.WeakKeyDictionary[Any, PlatformRuntime]" = weakref.WeakKeyDictionary()


def runtime_for(lab: Any, *, create: bool = True) -> PlatformRuntime | None:
    with _INSTALL_LOCK:
        runtime = _RUNTIMES.get(lab)
        if runtime is not None or not create:
            return runtime
        profile_store = getattr(lab, "profile_store", None)
        profile_path = getattr(profile_store, "path", None)
        database_path = None
        if profile_path:
            try:
                database_path = Path(profile_path).expanduser().resolve().with_name("platform_v7.sqlite3")
            except Exception:
                database_path = None
        runtime = PlatformRuntime(lab, database_path=database_path)
        _RUNTIMES[lab] = runtime
        return runtime


def _server_lab(server: Any) -> Any | None:
    for name in ("lab", "hardware_lab", "_lab"):
        value = getattr(server, name, None)
        if value is not None:
            return value
    return None


def _authorized(server: Any, request: Mapping[str, Any]) -> bool:
    expected = str(getattr(server, "token", "") or getattr(server, "_token", ""))
    supplied = str(request.get("token") or "")
    return bool(expected and supplied and secrets_compare(expected, supplied))


def secrets_compare(left: str, right: str) -> bool:
    import hmac
    return hmac.compare_digest(str(left), str(right))


def _merge_telemetry_into_lab(lab_payload: dict[str, Any], runtime: PlatformRuntime) -> None:
    # Existing Studio versions already understand HardwareLab's ``inputs``
    # shape.  Merge the platform journal into that shape so every faceplate can
    # benefit without being rewritten at once.
    physical = runtime.telemetry.legacy_inputs()
    inputs = lab_payload.setdefault("inputs", {})
    if not isinstance(inputs, dict):
        inputs = {}
        lab_payload["inputs"] = inputs
    for device, controls in physical.items():
        target = inputs.setdefault(device, {})
        if not isinstance(target, dict):
            target = {}
            inputs[device] = target
        for control, state in controls.items():
            existing = target.get(control)
            existing_seq = int(existing.get("sequence", 0)) if isinstance(existing, Mapping) else 0
            if int(state.get("sequence", 0)) >= existing_seq:
                target[control] = dict(state)
    # The per-control records were just merged into ``inputs`` above, so
    # sending them again under this key duplicated the largest part of the
    # payload ten times a second and grew with every control ever touched.
    # Studio reads a summary here - ``devices`` counts and a ``sequence`` - and
    # this used to overwrite that summary with the raw mapping, which is why the
    # physical counters always read zero.
    lab_payload["physical_telemetry"] = {
        "sequence": runtime.telemetry.sequence,
        "devices": {device: len(controls) for device, controls in physical.items()},
        "owner": "platform_v7",
    }
    lab_payload["physical_sequence"] = runtime.telemetry.sequence
    lab_payload["platform_version"] = "7.0.0"


def install_bridge_hooks() -> None:
    """Install additive hooks around HardwareLab and ControlServer once."""

    global _INSTALLED
    with _INSTALL_LOCK:
        if _INSTALLED:
            return
        from muslimsim.hardware.lab import HardwareLab
        from muslimsim.control.server import ControlServer

        if getattr(HardwareLab, "_muslimsim_platform_v7", False):
            _INSTALLED = True
            return

        original_lab_init = HardwareLab.__init__
        original_input = HardwareLab.input
        original_snapshot = HardwareLab.snapshot
        original_set_mode = getattr(HardwareLab, "set_mode", None)
        original_reset = getattr(HardwareLab, "reset_device", None)

        def lab_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_lab_init(self, *args, **kwargs)
            try:
                runtime_for(self)
            except Exception as exc:
                # The legacy bridge must remain operational even if the new
                # profile database cannot initialize.  A visible diagnostic is
                # preferable to disabling all hardware.
                try:
                    self.record_diagnostic("platform_v7", "startup-error", str(exc))
                except Exception:
                    pass

        def lab_input(
            self: Any,
            device_key: str,
            control_key: str,
            value: Any,
            *,
            phase: str = "change",
            source: str = "virtual",
            route: bool = True,
            **kwargs: Any,
        ) -> dict[str, Any]:
            runtime = runtime_for(self)
            observed: dict[str, Any] = {}
            if runtime is not None:
                observed = runtime.observe(
                    device_key, control_key, value,
                    phase=phase, source=source,
                    raw_signature=str(kwargs.pop("raw_signature", "") or ""),
                    kind=str(kwargs.pop("kind", "") or ""),
                )
            try:
                result = original_input(
                    self, device_key, control_key, value,
                    phase=phase, source=source, route=route, **kwargs,
                )
            except Exception as exc:
                # Physical truth must survive a stale catalogue or mapping.
                # Practice is fail-closed: a validation failure is consumed and
                # can never fall through to X-Plane.
                mode = str(getattr(self, "mode", "live") or "live").lower()
                if runtime is not None:
                    runtime._record_error(f"input:{device_key}.{control_key}", exc)
                if mode in {"test", "practice"}:
                    return {
                        "control": str(control_key), "value": value, "phase": phase,
                        "routed": True, "platform_observed": True,
                        "validation_error": str(exc), **observed,
                    }
                raise
            if isinstance(result, dict):
                result.setdefault("platform_observed", True)
                result.update({key: value for key, value in observed.items() if key not in result})
            return result

        def lab_snapshot(self: Any) -> dict[str, Any]:
            result = original_snapshot(self)
            if not isinstance(result, dict):
                result = dict(result or {})
            runtime = runtime_for(self, create=False)
            if runtime is not None:
                runtime.update_runtime_from_lab(result)
                _merge_telemetry_into_lab(result, runtime)
                result["platform"] = runtime.snapshot()
            return result

        def lab_set_mode(self: Any, mode: str, *args: Any, **kwargs: Any) -> Any:
            value = original_set_mode(self, mode, *args, **kwargs) if original_set_mode else None
            runtime = runtime_for(self, create=False)
            if runtime is not None:
                runtime.set_mode(mode)
            return value

        HardwareLab.__init__ = lab_init
        HardwareLab.input = lab_input
        HardwareLab.snapshot = lab_snapshot
        if original_set_mode is not None:
            HardwareLab.set_mode = lab_set_mode
        HardwareLab._muslimsim_platform_v7 = True

        original_handle = ControlServer.handle
        original_start = ControlServer.start
        original_stop = getattr(ControlServer, "stop", None)
        original_close = getattr(ControlServer, "close", None)

        def server_handle(self: Any, request: Mapping[str, Any]) -> dict[str, Any]:
            command = str(request.get("cmd") or "")
            if command.startswith("platform_"):
                if not _authorized(self, request):
                    return {"ok": False, "error": "unauthorized"}
                lab = _server_lab(self)
                if lab is None:
                    return {"ok": False, "error": "HardwareLab is unavailable"}
                runtime = runtime_for(lab)
                try:
                    payload = runtime.handle(command, request)
                    return {"ok": True, **(payload if isinstance(payload, dict) else {"result": payload})}
                except Exception as exc:
                    runtime._record_error(f"command:{command}", exc)
                    return {"ok": False, "error": str(exc), "type": type(exc).__name__}

            response = original_handle(self, request)
            if command == "status" and isinstance(response, dict) and response.get("ok"):
                lab = _server_lab(self)
                runtime = runtime_for(lab) if lab is not None else None
                if runtime is not None:
                    discovery = response.get("hardware_discovery")
                    if discovery:
                        try:
                            runtime.ingest_discovery(discovery)
                        except Exception as exc:
                            runtime._record_error("status-discovery", exc)
                    lab_payload = response.get("lab")
                    if isinstance(lab_payload, dict):
                        runtime.update_runtime_from_lab(lab_payload)
                        _merge_telemetry_into_lab(lab_payload, runtime)
                    # BUG-16: this used to call runtime.snapshot() again here,
                    # on top of the call ``lab_snapshot`` already made just
                    # above it, inside ``original_handle``'s own
                    # ``self.lab.snapshot()`` - three identical, independently
                    # computed copies of the same payload per status reply
                    # in total, each one running the profile database's own
                    # queries fresh. Studio's own status handler already falls
                    # back to ``lab["platform"]`` whenever the top-level key is
                    # absent (studio_hooks.py), so that copy alone is
                    # sufficient; nothing needs computing twice, let alone
                    # three times.
                    if isinstance(lab_payload, dict) and isinstance(lab_payload.get("platform"), dict):
                        response.setdefault("platform", lab_payload["platform"])
            return response

        def server_start(self: Any, *args: Any, **kwargs: Any) -> Any:
            port = original_start(self, *args, **kwargs)
            try:
                token = str(getattr(self, "token", "") or getattr(self, "_token", ""))
                write_locator(int(port), token, pid=os.getpid(), root=str(Path.cwd()))
            except Exception:
                pass
            return port

        def _shutdown_runtimes() -> None:
            for runtime in list(_RUNTIMES.values()):
                try:
                    runtime.close()
                except Exception:
                    pass
            remove_locator(pid=os.getpid())

        def server_stop(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                return original_stop(self, *args, **kwargs) if original_stop else None
            finally:
                _shutdown_runtimes()

        def server_close(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                return original_close(self, *args, **kwargs) if original_close else None
            finally:
                _shutdown_runtimes()

        ControlServer.handle = server_handle
        ControlServer.start = server_start
        if original_stop is not None:
            ControlServer.stop = server_stop
        if original_close is not None:
            ControlServer.close = server_close
        ControlServer._muslimsim_platform_v7 = True
        _INSTALLED = True

# >>> MUSLIMSIM_PLATFORM_V7_PROCESS_WIDE_PRACTICE_GATE >>>
# This is the final authority boundary. Device adapters may still perform their
# own early Practice checks, but every established simulator-write helper is
# also blocked here. Physical panel output functions are deliberately excluded.
import atexit as _platform_v7_atexit
import functools as _platform_v7_functools
import threading as _platform_v7_threading
from typing import Any as _PlatformV7Any, Mapping as _PlatformV7Mapping

_PLATFORM_V7_PRACTICE_GATE = _platform_v7_threading.Event()
_PLATFORM_V7_GATE_LOCK = _platform_v7_threading.RLock()
_PLATFORM_V7_WRITE_NAMES = (
    "set_dataref",
    "set_dataref_index",
    "activate_command",
    "activate_command_begin",
    "activate_command_end",
    "command_once",
    "write_dataref",
)


def platform_v7_practice_gate_active() -> bool:
    """Return the process-wide Practice authority state."""
    return _PLATFORM_V7_PRACTICE_GATE.is_set()


def _platform_v7_mode_text(value: _PlatformV7Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower().replace("_", "-")


def _platform_v7_record_blocked_write(name: str) -> None:
    try:
        from .runtime import record_global_blocked_write
        record_global_blocked_write(str(name))
    except Exception:
        # The safety decision must never depend on diagnostics being available.
        pass


def _platform_v7_wrap_writer(name: str, original: _PlatformV7Any) -> _PlatformV7Any:
    if not callable(original) or getattr(original, "__muslimsim_platform_v7_gate__", False):
        return original

    @_platform_v7_functools.wraps(original)
    def guarded(*args: _PlatformV7Any, **kwargs: _PlatformV7Any) -> _PlatformV7Any:
        if _PLATFORM_V7_PRACTICE_GATE.is_set():
            _platform_v7_record_blocked_write(name)
            return None
        return original(*args, **kwargs)

    guarded.__muslimsim_platform_v7_gate__ = True
    guarded.__muslimsim_platform_v7_original__ = original
    return guarded


def _platform_v7_wrap_lab_mode(lab_cls: _PlatformV7Any) -> None:
    original = getattr(lab_cls, "set_mode", None)
    if not callable(original) or getattr(original, "__muslimsim_platform_v7_mode_gate__", False):
        return

    @_platform_v7_functools.wraps(original)
    def guarded_set_mode(self: _PlatformV7Any, mode: _PlatformV7Any, *args: _PlatformV7Any,
                         **kwargs: _PlatformV7Any) -> _PlatformV7Any:
        requested = _platform_v7_mode_text(mode)
        practice = requested in {"test", "practice"}
        previous = _PLATFORM_V7_PRACTICE_GATE.is_set()
        # Set before the legacy transition so no concurrent dispatch can escape
        # during the Live -> Practice boundary.
        if practice:
            _PLATFORM_V7_PRACTICE_GATE.set()
        try:
            result = original(self, mode, *args, **kwargs)
        except Exception:
            if previous:
                _PLATFORM_V7_PRACTICE_GATE.set()
            else:
                _PLATFORM_V7_PRACTICE_GATE.clear()
            raise
        if not practice:
            # Clear only after the legacy layer has completed its transition and
            # discarded pending Practice actions.
            _PLATFORM_V7_PRACTICE_GATE.clear()
        return result

    guarded_set_mode.__muslimsim_platform_v7_mode_gate__ = True
    guarded_set_mode.__muslimsim_platform_v7_original__ = original
    setattr(lab_cls, "set_mode", guarded_set_mode)


def _platform_v7_wrap_server_stop(server_cls: _PlatformV7Any) -> None:
    original = getattr(server_cls, "stop", None)
    if not callable(original) or getattr(original, "__muslimsim_platform_v7_stop_gate__", False):
        return

    @_platform_v7_functools.wraps(original)
    def guarded_stop(self: _PlatformV7Any, *args: _PlatformV7Any,
                     **kwargs: _PlatformV7Any) -> _PlatformV7Any:
        try:
            return original(self, *args, **kwargs)
        finally:
            _PLATFORM_V7_PRACTICE_GATE.clear()

    guarded_stop.__muslimsim_platform_v7_stop_gate__ = True
    guarded_stop.__muslimsim_platform_v7_original__ = original
    setattr(server_cls, "stop", guarded_stop)


def install_runtime_gates(namespace: _PlatformV7Mapping[str, _PlatformV7Any] | dict[str, _PlatformV7Any]) -> dict[str, _PlatformV7Any]:
    """Install the process-wide Practice write barrier into one bridge module.

    The function is idempotent and intentionally accepts the bridge's globals()
    mapping. It wraps simulator writes only; device HID/serial/display output is
    still governed by the existing capture-proven output authority.
    """
    with _PLATFORM_V7_GATE_LOCK:
        mutable = namespace
        wrapped: list[str] = []
        for name in _PLATFORM_V7_WRITE_NAMES:
            original = mutable.get(name)
            guarded = _platform_v7_wrap_writer(name, original)
            if guarded is not original:
                mutable[name] = guarded
                wrapped.append(name)
        lab_cls = mutable.get("HardwareLab")
        if lab_cls is not None:
            _platform_v7_wrap_lab_mode(lab_cls)
        server_cls = mutable.get("ControlServer")
        if server_cls is not None:
            _platform_v7_wrap_server_stop(server_cls)
        return {
            "practice": _PLATFORM_V7_PRACTICE_GATE.is_set(),
            "wrapped": tuple(wrapped),
        }


_platform_v7_atexit.register(_PLATFORM_V7_PRACTICE_GATE.clear)
# <<< MUSLIMSIM_PLATFORM_V7_PROCESS_WIDE_PRACTICE_GATE <<<
