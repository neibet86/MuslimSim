"""Bridge-local physical telemetry safety layer for MuslimSim Studio.

This module owns no HID, SDL, serial, simulator, or device handle.  It wraps the
existing HardwareLab instance so a physical sample remains visible to Studio even
when semantic/catalog validation rejects the mapping path.  The wrapped lab still
owns mapping, Practice behaviour, device enable/disable state, and simulator
routing decisions.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict


class PhysicalTelemetryLabProxy:
    """Delegate to HardwareLab while retaining the latest physical/baseline sample."""

    _VISIBLE_SOURCES = frozenset({"physical", "baseline"})

    def __init__(self, lab: Any) -> None:
        object.__setattr__(self, "_lab", lab)
        object.__setattr__(self, "_telemetry_lock", threading.RLock())
        object.__setattr__(self, "_telemetry_inputs", {})
        object.__setattr__(self, "_telemetry_sequence", 0)
        object.__setattr__(self, "_telemetry_last_update", 0.0)

    @property
    def wrapped_lab(self) -> Any:
        return object.__getattribute__(self, "_lab")

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_lab"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_telemetry_") or name == "_lab":
            object.__setattr__(self, name, value)
            return
        setattr(object.__getattribute__(self, "_lab"), name, value)

    @staticmethod
    def _safe_value(value: Any) -> Any:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return float(value) if math.isfinite(value) else None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    def _device_enabled(self, device_key: str) -> bool:
        try:
            return bool(self.wrapped_lab.device_enabled(device_key))
        except Exception:
            # Unknown controls may still belong to a known device.  Do not make
            # a telemetry-only failure disable the underlying routing path.
            return True

    def _record_physical(
        self,
        device_key: str,
        control_key: str,
        value: Any,
        *,
        phase: str,
        source: str,
    ) -> None:
        source_name = str(source or "").casefold()
        if source_name not in self._VISIBLE_SOURCES or not self._device_enabled(str(device_key)):
            return
        safe = self._safe_value(value)
        if safe is None:
            return
        now = time.time()
        item = {
            "value": safe,
            "phase": str(phase or "change"),
            "source": source_name,
            "updated": now,
            "telemetry_shadow": True,
        }
        with object.__getattribute__(self, "_telemetry_lock"):
            store: Dict[str, Dict[str, Dict[str, Any]]] = object.__getattribute__(self, "_telemetry_inputs")
            store.setdefault(str(device_key), {})[str(control_key)] = item
            object.__setattr__(self, "_telemetry_sequence", int(object.__getattribute__(self, "_telemetry_sequence")) + 1)
            object.__setattr__(self, "_telemetry_last_update", now)

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
        # Record first.  If HardwareLab later rejects an unknown/stale catalogue
        # relation, Studio still sees the physical truth; routing remains rejected.
        self._record_physical(
            device_key, control_key, value,
            phase=phase, source=source,
        )
        try:
            return self.wrapped_lab.input(
                device_key, control_key, value,
                phase=phase, source=source, route=route,
            )
        except Exception as exc:
            # Mapping/catalogue errors must never become a simulator escape hatch
            # in Practice.  The physical sample is already retained above, so
            # consume it as telemetry-only while leaving Live's established
            # fallback behavior unchanged.
            source_name = str(source or "").casefold()
            try:
                practice = str(getattr(self.wrapped_lab, "mode", "")).casefold() == "test"
            except Exception:
                practice = False
            if practice and source_name in self._VISIBLE_SOURCES:
                try:
                    self.wrapped_lab.record_diagnostic(
                        str(device_key),
                        "physical-telemetry-validation",
                        {
                            "control": str(control_key),
                            "error": str(exc),
                            "consumed_in_practice": True,
                        },
                    )
                except Exception:
                    pass
                return {
                    "control": str(control_key),
                    "value": self._safe_value(value),
                    "phase": str(phase or "change"),
                    "routed": True,
                    "telemetry_only": True,
                }
            raise

    def snapshot(self) -> Dict[str, Any]:
        snapshot = dict(self.wrapped_lab.snapshot())
        existing = snapshot.get("inputs")
        inputs: Dict[str, Dict[str, Dict[str, Any]]] = {
            str(device): {
                str(control): dict(item)
                for control, item in dict(values or {}).items()
                if isinstance(item, dict)
            }
            for device, values in dict(existing or {}).items()
            if isinstance(values, dict)
        }
        with object.__getattribute__(self, "_telemetry_lock"):
            shadow = {
                str(device): {str(control): dict(item) for control, item in values.items()}
                for device, values in object.__getattribute__(self, "_telemetry_inputs").items()
            }
            sequence = int(object.__getattribute__(self, "_telemetry_sequence"))
            last_update = float(object.__getattribute__(self, "_telemetry_last_update"))
        for device, controls in shadow.items():
            target = inputs.setdefault(device, {})
            for control, item in controls.items():
                current = target.get(control)
                try:
                    current_updated = float(current.get("updated", 0.0)) if isinstance(current, dict) else 0.0
                except (TypeError, ValueError):
                    current_updated = 0.0
                if current is None or float(item.get("updated", 0.0)) >= current_updated:
                    target[control] = item
        snapshot["inputs"] = inputs
        snapshot["physical_telemetry"] = {
            "sequence": sequence,
            "last_update": last_update,
            "devices": {
                device: len(controls) for device, controls in shadow.items()
            },
            "owner": "bridge",
        }
        return snapshot
