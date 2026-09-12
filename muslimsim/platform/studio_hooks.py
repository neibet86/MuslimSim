from __future__ import annotations

import subprocess
import sys
from functools import wraps
from pathlib import Path
from typing import Any, Mapping, MutableMapping


def _latest_to_inputs(platform: Mapping[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    telemetry = dict(platform.get("telemetry") or {})
    latest = dict(telemetry.get("latest") or {})
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for device, controls in latest.items():
        if not isinstance(controls, Mapping):
            continue
        target: dict[str, dict[str, Any]] = {}
        for control, sample in controls.items():
            if not isinstance(sample, Mapping):
                continue
            target[str(control)] = {
                "value": sample.get("value"),
                "phase": sample.get("phase", "change"),
                "source": sample.get("source", "physical"),
                "updated": sample.get("timestamp", 0.0),
                "sequence": sample.get("sequence", 0),
            }
        if target:
            result[str(device)] = target
    return result


def _merge_inputs(response: MutableMapping[str, Any], platform: Mapping[str, Any]) -> None:
    lab = response.setdefault("lab", {})
    if not isinstance(lab, MutableMapping):
        lab = {}
        response["lab"] = lab
    inputs = lab.setdefault("inputs", {})
    if not isinstance(inputs, MutableMapping):
        inputs = {}
        lab["inputs"] = inputs
    physical = _latest_to_inputs(platform)
    for device, controls in physical.items():
        target = inputs.setdefault(device, {})
        if not isinstance(target, MutableMapping):
            target = {}
            inputs[device] = target
        for control, sample in controls.items():
            existing = target.get(control)
            existing_seq = int(existing.get("sequence", 0)) if isinstance(existing, Mapping) else 0
            if int(sample.get("sequence", 0)) >= existing_seq:
                target[control] = dict(sample)
    telemetry = dict(platform.get("telemetry") or {})
    # Same key, same summary shape as the bridge produces. Writing the raw
    # per-control mapping here overwrote the counts Studio reads immediately
    # after, so the header could never show a physical total.
    lab["physical_telemetry"] = {
        "sequence": int(telemetry.get("cursor", 0)),
        "devices": {device: len(controls) for device, controls in physical.items()},
        "owner": "platform_v7_studio",
    }
    lab["physical_sequence"] = int(telemetry.get("cursor", 0))
    lab["platform"] = dict(platform)


def install_on_class(cls: type) -> bool:
    if getattr(cls, "_muslimsim_platform_v7", False):
        return False
    receive = getattr(cls, "_receive_status", None)
    if not callable(receive):
        return False

    @wraps(receive)
    def receive_status(self: Any, response: MutableMapping[str, Any]) -> Any:
        platform = response.get("platform")
        if not isinstance(platform, Mapping):
            lab = response.get("lab")
            platform = lab.get("platform") if isinstance(lab, Mapping) else None
        if isinstance(platform, Mapping):
            _merge_inputs(response, platform)
            setattr(self, "_platform_v7", dict(platform))
        result = receive(self, response)
        if isinstance(platform, Mapping):
            telemetry = dict(platform.get("telemetry") or {})
            count = int(telemetry.get("control_count", 0))
            sequence = int(telemetry.get("cursor", 0))
            authority = dict(platform.get("authority") or {})
            mode = str(authority.get("mode") or "live").title()
            # This used to append "Platform V7 - <mode> - Physical N - #seq"
            # to the Studio header on every status reply. At a 10 Hz poll the
            # changing sequence number rewrote the label constantly and the
            # header visibly flickered. The same values are kept on the
            # instance so the Device Manager and diagnostics can read them
            # without anything blinking in the corner of the owner's eye.
            setattr(self, "_platform_v7_mode", mode)
            setattr(self, "_platform_v7_control_count", count)
            setattr(self, "_platform_v7_sequence", sequence)
        return result

    cls._receive_status = receive_status

    original_init = getattr(cls, "__init__", None)
    if callable(original_init):
        @wraps(original_init)
        def init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            try:
                self.bind_all("<Control-Shift-D>", lambda _event: _launch_manager())
            except Exception:
                pass
        cls.__init__ = init

    mirror = getattr(cls, "_device_mirror", None)
    if callable(mirror):
        @wraps(mirror)
        def device_mirror(self: Any, device_key: str) -> dict[str, Any]:
            value = mirror(self, device_key)
            result = dict(value or {})
            platform = getattr(self, "_platform_v7", {})
            physical = _latest_to_inputs(platform).get(str(device_key), {})
            if physical:
                result["physical_values"] = {key: state.get("value") for key, state in physical.items()}
                result["physical_inputs"] = physical
            return result
        cls._device_mirror = device_mirror

    cls._muslimsim_platform_v7 = True
    return True


def _launch_manager() -> None:
    root = Path(__file__).resolve().parents[3]
    candidates = [
        root / "MuslimSim Device Manager.pyw",
        root / "tools" / "muslimsim_platform_manager.py",
    ]
    target = next((path for path in candidates if path.is_file()), None)
    if target is None:
        return
    executable = sys.executable
    try:
        subprocess.Popen([executable, str(target)], cwd=str(root), close_fds=True)
    except Exception:
        pass


def auto_install(namespace: Mapping[str, Any]) -> int:
    installed = 0
    for value in list(namespace.values()):
        if isinstance(value, type) and hasattr(value, "_receive_status") and hasattr(value, "_draw_faceplate"):
            if install_on_class(value):
                installed += 1
    return installed
