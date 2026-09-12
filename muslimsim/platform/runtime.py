from __future__ import annotations

import hashlib
import inspect
import json
import os
import queue
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

from .authority import AuthorityCoordinator
from .cloud import RabtaClient, RabtaConfig, SecureTokenStore
from .contracts import (
    AdoptedDevice,
    Capability,
    DeviceRole,
    DeviceSighting,
    InputEvent,
    PlatformError,
    RuntimeMode,
    TransportIdentity,
    ValidationError,
)
from .identity import IdentityResolver, family_key, role_hint_from_text, sighting_from_mapping
from .learning import LearningEngine
from .profiles import ProfileDatabase, default_database_path
from .registry import PluginRegistry
from .telemetry import TelemetryJournal


def _machine_id() -> str:
    raw = ""
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                raw = str(winreg.QueryValueEx(key, "MachineGuid")[0])
        except Exception:
            raw = ""
    raw = raw or f"{socket.gethostname()}|{os.environ.get('USERNAME') or os.environ.get('USER') or ''}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _known_capabilities(device_key: str) -> Capability:
    base = Capability.DISCOVERY | Capability.INPUT | Capability.LEARNING | Capability.HOTPLUG
    output_devices = {
        "pu_overhead", "winctrl_throttle", "agp_bb80", "fcu_32_efis", "ecam32",
        "pap3_mag", "pfp3n_bb35", "mcdu32_bb36", "pdc_bb61_left", "pdc_bb52_right",
    }
    display_devices = {"pu_overhead", "agp_bb80", "fcu_32_efis", "pap3_mag", "pfp3n_bb35", "mcdu32_bb36"}
    lighting_devices = output_devices | {"pdc_bb61_left", "pdc_bb52_right"}
    calibration_devices = {"winctrl_throttle", "winctrl_pedals", "tca_boeing", "moza_a210", "moza_ab6", "pu_overhead"}
    actuator_devices = {"pu_overhead", "pap3_mag"}
    if device_key in output_devices:
        base |= Capability.OUTPUT
    if device_key in display_devices:
        base |= Capability.DISPLAY
    if device_key in lighting_devices:
        base |= Capability.LIGHTING
    if device_key in calibration_devices:
        base |= Capability.CALIBRATION
    if device_key in actuator_devices:
        base |= Capability.ACTUATOR
    return base


def _sighting_signature(sighting: Mapping[str, Any]) -> tuple:
    """What actually identifies a change worth persisting.

    Excludes ``observed_at``: that timestamp is fresh on every single call by
    construction, so including it would make every sighting look "changed" and
    defeat the whole comparison (BUG-16).
    """

    return (
        json.dumps(sighting.get("identity") or {}, sort_keys=True),
        str(sighting.get("source") or ""),
        str(sighting.get("legacy_key") or ""),
        int(sighting.get("capabilities") or 0),
        sighting.get("vendor_role_hint"),
        str(sighting.get("driver_id") or ""),
    )


class PlatformRuntime:
    """Stable product layer around the existing MuslimSim hardware owners."""

    def __init__(
        self,
        lab: Any,
        *,
        database_path: str | Path | None = None,
        plugin_directories: list[str | Path] | None = None,
    ) -> None:
        self.lab = lab
        self.machine_id = _machine_id()
        self.telemetry = TelemetryJournal()
        self.authority = AuthorityCoordinator()
        self.learning = LearningEngine()
        self.database = ProfileDatabase(database_path or default_database_path())
        self.identities = IdentityResolver(self.database.load_devices())
        self.plugins = PluginRegistry()
        self.plugins.discover_entry_points()
        roots = list(plugin_directories or [])
        roots.extend([
            Path.cwd() / "plugins",
            Path(os.environ.get("PROGRAMDATA") or Path.home()) / "MuslimSim" / "plugins",
            self.database.path.parent / "plugins",
        ])
        self.plugins.discover_manifests(roots)
        self._lock = threading.RLock()
        self._legacy_to_adoption: dict[str, str] = {
            record.legacy_key: record.adoption_id
            for record in self.identities.records.values()
            if record.legacy_key
        }
        self._sightings: dict[str, dict[str, Any]] = {}
        # BUG-16: a device present in the (cached) hardware_discovery
        # payload was re-saved to SQLite on every single status poll -
        # 10 times a second, forever, whether or not anything about it had
        # changed since the last poll. This is the signature of what was
        # last actually PERSISTED for each device, so a repeat sighting can
        # be told apart from a real change without touching the database at
        # all.
        self._sighting_signatures: dict[str, tuple] = {}
        self._errors: list[dict[str, Any]] = []
        self._writer_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue(maxsize=1024)
        self._stop = threading.Event()
        self._writer = threading.Thread(target=self._writer_loop, name="MuslimSim-Platform-ProfileWriter", daemon=True)
        self._writer.start()
        token_path = self.database.path.with_name("rabta_tokens.v7")
        self._rabta_config = RabtaConfig()
        self.cloud = RabtaClient(self._rabta_config, SecureTokenStore(token_path))
        self._last_cloud_cursor = ""
        self._legacy_imported = False
        self._import_legacy_profile_snapshot()

    # --------------------------------------------------------------- lifecycle
    def close(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        try:
            self._writer_queue.put_nowait(("stop", None))
        except queue.Full:
            pass
        self._writer.join(timeout=2.0)
        self.database.close()

    def _writer_loop(self) -> None:
        while not self._stop.is_set():
            try:
                operation, value = self._writer_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if operation == "stop":
                return
            try:
                if operation == "save-device":
                    self.database.save_device(value)
                elif operation == "sighting":
                    adoption_id, sighting = value
                    self.database.record_sighting(adoption_id, self.machine_id, sighting)
                elif operation == "audit":
                    event, entity_type, entity_id, details = value
                    self.database.audit(event, entity_type=entity_type, entity_id=entity_id, details=details)
            except Exception as exc:
                self._record_error("profile-writer", exc)

    def _enqueue(self, operation: str, value: Any) -> None:
        try:
            self._writer_queue.put_nowait((operation, value))
        except queue.Full:
            self._record_error("profile-writer-queue-full", f"Dropped non-hot-path operation {operation}")

    def _record_error(self, source: str, error: Any) -> None:
        with self._lock:
            self._errors.append({"source": str(source), "error": str(error), "at": time.time()})
            del self._errors[:-100]

    # -------------------------------------------------------------- identities
    def _legacy_sighting(self, device_key: str) -> DeviceSighting:
        label = str(device_key).replace("_", " ")
        identity = TransportIdentity(
            transport="legacy-bridge",
            product=label,
            manufacturer="MuslimSim",
            descriptor_hash=hashlib.sha256(str(device_key).encode()).hexdigest(),
            extra={"legacy_key": device_key},
        )
        return DeviceSighting(
            identity=identity,
            source="bridge-event",
            observed_at=time.time(),
            legacy_key=str(device_key),
            capabilities=_known_capabilities(str(device_key)),
            vendor_role_hint=role_hint_from_text(label),
            driver_id=f"legacy:{device_key}",
        )

    def _ensure_device(self, device_key: str) -> AdoptedDevice:
        device_key = str(device_key)
        with self._lock:
            adoption_id = self._legacy_to_adoption.get(device_key)
            if adoption_id and adoption_id in self.identities.records:
                record = self.identities.records[adoption_id]
                record.state = "online"
                record.last_seen = time.time()
                return record

            sighting = self._legacy_sighting(device_key)
            matched, reason = self.identities.observe(sighting)
            if matched is None:
                matched = self.identities.adopt(
                    sighting,
                    friendly_name=device_key.replace("_", " ").title(),
                )
                reason = "auto-adopt-known-bridge-key"
            self._legacy_to_adoption[device_key] = matched.adoption_id
            self._enqueue("save-device", matched)
            self._enqueue("sighting", (matched.adoption_id, sighting.to_dict()))
            self._enqueue("audit", ("device-auto-adopted", "device", matched.adoption_id, {"legacy_key": device_key, "reason": reason}))
            return matched

    def ingest_discovery(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, Mapping):
            records = payload.get("devices") or payload.get("hardware") or payload.get("items") or []
            if isinstance(records, Mapping):
                records = [dict(value, key=key) if isinstance(value, Mapping) else {"key": key} for key, value in records.items()]
        elif isinstance(payload, list):
            records = payload
        else:
            records = []
        seen: set[str] = set()
        adopted = 0
        ambiguous: list[dict[str, Any]] = []
        for raw in records:
            if not isinstance(raw, Mapping):
                continue
            try:
                sighting = sighting_from_mapping(raw, source="bridge-discovery")
                match, reason = self.identities.observe(sighting)
                if match is None:
                    candidates = [
                        record.to_dict() for record in self.identities.records.values()
                        if record.family_key == family_key(sighting.identity)
                    ]
                    if candidates:
                        ambiguous.append({"sighting": sighting.to_dict(), "reason": reason, "candidates": candidates})
                        continue
                    match = self.identities.adopt(sighting)
                    adopted += 1
                seen.add(match.adoption_id)
                if sighting.legacy_key:
                    self._legacy_to_adoption[sighting.legacy_key] = match.adoption_id
                sighting_dict = sighting.to_dict()
                self._sightings[match.adoption_id] = sighting_dict
                # The device-online state Studio actually shows comes from
                # identities.observe() above, in memory, every call - that part
                # must stay unconditional. Only the SQLite audit trail is
                # gated: it exists to record when something about a device
                # actually changed, not to log an identical "still there"
                # sample every 100 ms forever. observed_at always differs, so
                # it is excluded from the comparison on purpose.
                signature = _sighting_signature(sighting_dict)
                if (
                    self._sighting_signatures.get(match.adoption_id) != signature
                    or match.role_change_detected
                ):
                    self._sighting_signatures[match.adoption_id] = signature
                    self.database.save_device(match)
                    self.database.record_sighting(match.adoption_id, self.machine_id, sighting_dict)
            except Exception as exc:
                self._record_error("discovery", exc)
        self.identities.offline_unseen(seen)
        return {"seen": len(seen), "adopted": adopted, "ambiguous": ambiguous}

    # -------------------------------------------------------------- telemetry
    def observe(
        self,
        device_key: str,
        control_key: str,
        value: Any,
        *,
        phase: str = "change",
        source: str = "physical",
        raw_signature: str = "",
        kind: str = "",
    ) -> dict[str, Any]:
        record = self._ensure_device(device_key)
        if not kind:
            try:
                control = self.lab._control(device_key, control_key)
                kind = str(getattr(control, "kind", "") or "")
            except Exception:
                kind = ""
        sample = self.telemetry.publish(
            device_key,
            control_key,
            value,
            phase=phase,
            source=source,
            kind=kind,
            raw_signature=raw_signature,
        )
        event = InputEvent(
            device_key=str(device_key), control_key=str(control_key), value=value,
            phase=str(phase), source=str(source), timestamp=sample.timestamp,
            raw_signature=str(raw_signature), kind=kind,
        )
        self.learning.observe(event)
        record.state = "online"
        record.last_seen = sample.timestamp
        return {"sequence": sample.sequence, "adoption_id": record.adoption_id, "kind": kind}

    # --------------------------------------------------------- authority state
    def set_mode(self, mode: str) -> dict[str, Any]:
        normalized = "practice" if str(mode).lower() in {"test", "practice"} else "live"
        return self.authority.set_mode(RuntimeMode(normalized), reason="hardware-lab").__dict__

    def update_runtime_from_lab(self, snapshot: Mapping[str, Any]) -> None:
        simulator = bool(snapshot.get("simulator_connected", False))
        loaded = bool(snapshot.get("aircraft_loaded", simulator))
        powered = bool(
            snapshot.get("aircraft_powered", False)
            or snapshot.get("output_powered", False)
            or snapshot.get("common_power", False)
        )
        self.authority.update_runtime(
            simulator_connected=simulator,
            aircraft_loaded=loaded,
            aircraft_powered=powered,
            reason="lab-snapshot",
        )
        mode = str(snapshot.get("mode") or "live")
        self.set_mode(mode)

    # -------------------------------------------------------------- legacy map
    def _import_legacy_profile_snapshot(self) -> None:
        store = getattr(self.lab, "profile_store", None)
        if store is None or self._legacy_imported:
            return
        try:
            snapshot = store.snapshot()
            if isinstance(snapshot, Mapping):
                self.database.import_legacy_snapshot(snapshot)
            self._legacy_imported = True
        except Exception as exc:
            self._record_error("legacy-profile-import", exc)

    @staticmethod
    def _mapping_binding(payload: Mapping[str, Any]) -> Any:
        from muslimsim.hardware.profiles import MappingBinding
        values = {
            "kind": str(payload.get("kind") or "disabled"),
            "target": str(payload.get("target") or ""),
            "invert": bool(payload.get("invert", False)),
            "scale": float(payload.get("scale", 1.0)),
            "deadband": float(payload.get("deadband", 0.0)),
            "value": payload.get("value"),
            "mechanical": str(payload.get("mechanical") or ""),
        }
        try:
            signature = inspect.signature(MappingBinding)
            allowed = {name for name in signature.parameters if name != "self"}
            return MappingBinding(**{key: value for key, value in values.items() if key in allowed})
        except Exception:
            # Historical MappingBinding revisions accept the first six fields.
            return MappingBinding(
                values["kind"], values["target"], values["invert"],
                values["scale"], values["deadband"], values["value"],
            )

    def _legacy_device_key(self, adoption_id: str, fallback: str = "") -> str:
        record = self.identities.records.get(str(adoption_id))
        return str((record.legacy_key if record else "") or fallback or adoption_id)

    def apply_binding(self, adoption_id: str, control_key: str, binding: Mapping[str, Any], *, device_key: str = "") -> dict[str, Any]:
        legacy_key = self._legacy_device_key(adoption_id, device_key)
        mapping = self._mapping_binding(binding)
        # The existing engine remains authoritative for routing. This call is
        # the critical bridge that makes downloaded/reassigned profiles active.
        self.lab.configure_binding(legacy_key, str(control_key), mapping)
        return self.database.set_binding(adoption_id, control_key, binding, device_key=legacy_key)

    def delete_binding(self, adoption_id: str, control_key: str) -> None:
        legacy_key = self._legacy_device_key(adoption_id)
        mapping = self._mapping_binding({"kind": "disabled"})
        self.lab.configure_binding(legacy_key, str(control_key), mapping)
        self.database.delete_binding(adoption_id, control_key)

    def apply_active_profile_to_legacy(self) -> dict[str, Any]:
        document = self.database.profile_document()
        applied = 0
        errors: list[dict[str, str]] = []
        for row in document["bindings"]:
            try:
                value = None
                if row.get("value_json") not in (None, ""):
                    value = json.loads(row["value_json"])
                self.lab.configure_binding(
                    str(row.get("device_key") or self._legacy_device_key(row["adoption_id"])),
                    str(row["control_key"]),
                    self._mapping_binding({
                        "kind": row["kind"], "target": row["target"], "invert": bool(row["invert"]),
                        "scale": row["scale"], "deadband": row["deadband"], "value": value,
                        "mechanical": row.get("mechanical", ""),
                    }),
                )
                applied += 1
            except Exception as exc:
                errors.append({"control": str(row.get("control_key")), "error": str(exc)})
        return {"applied": applied, "errors": errors}

    # -------------------------------------------------------------- cloud config
    def configure_cloud(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        current = self._rabta_config
        self._rabta_config = RabtaConfig(
            auth_base=str(payload.get("auth_base") or current.auth_base),
            api_base=str(payload.get("api_base") or current.api_base),
            project_id=str(payload.get("project_id") or current.project_id),
            public_api_key=str(payload.get("public_api_key") or current.public_api_key),
            client_name="MuslimSim Studio",
            timeout_seconds=float(payload.get("timeout_seconds") or current.timeout_seconds),
        ).normalized()
        token_store = self.cloud.token_store
        self.cloud = RabtaClient(self._rabta_config, token_store)
        return self.cloud.status()

    # --------------------------------------------------------------- commands
    def handle(self, command: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        cmd = str(command).removeprefix("platform_")
        if cmd in {"status", "snapshot"}:
            return self.snapshot()
        if cmd == "poll":
            return self.telemetry.poll(
                int(payload.get("cursor", 0)),
                timeout=float(payload.get("timeout", 0.75)),
                max_events=int(payload.get("max_events", 512)),
            )
        if cmd == "ingest_discovery":
            return self.ingest_discovery(payload.get("discovery") or payload)
        if cmd == "devices":
            return {"devices": self.identities.snapshot(), "sightings": dict(self._sightings)}
        if cmd == "adopt":
            sighting = sighting_from_mapping(dict(payload.get("sighting") or payload), source="user-adoption")
            role = DeviceRole(str(payload.get("role") or "unassigned"))
            record = self.identities.adopt(sighting, role=role, friendly_name=str(payload.get("friendly_name") or ""))
            self.database.save_device(record)
            self.database.record_sighting(record.adoption_id, self.machine_id, sighting.to_dict())
            if record.legacy_key:
                self._legacy_to_adoption[record.legacy_key] = record.adoption_id
            return {"device": record.to_dict()}
        if cmd == "set_role":
            record = self.identities.set_role(str(payload["adoption_id"]), DeviceRole(str(payload["role"])))
            self.database.save_device(record)
            return {"device": record.to_dict()}
        if cmd == "learn_start":
            session = self.learning.start(
                device_key=str(payload.get("device_key") or ""),
                expected_kind=str(payload.get("expected_kind") or "any"),
                timeout=float(payload.get("timeout", 15.0)),
                replace_control=str(payload.get("replace_control") or ""),
                baseline=self.telemetry.legacy_inputs(),
            )
            return session.to_dict()
        if cmd == "learn_status":
            return self.learning.status()
        if cmd == "learn_cancel":
            self.learning.cancel()
            return {"status": "cancelled"}
        if cmd == "learn_commit":
            candidate = self.learning.complete()
            record = self._ensure_device(candidate.device_key)
            semantic = str(payload.get("semantic_key") or candidate.control_key).strip()
            learned = self.database.set_learned_control(
                record.adoption_id,
                candidate.control_key,
                semantic,
                label=str(payload.get("label") or semantic),
                signature=candidate.raw_signature,
                confidence=min(1.0, max(0.1, candidate.score / 20.0)),
            )
            binding_payload = payload.get("binding")
            applied = None
            if isinstance(binding_payload, Mapping):
                applied = self.apply_binding(record.adoption_id, candidate.control_key, binding_payload, device_key=candidate.device_key)
            return {"candidate": candidate.to_dict(), "learned": learned, "binding": applied}
        if cmd == "binding_set":
            return self.apply_binding(
                str(payload["adoption_id"]), str(payload["control_key"]),
                dict(payload.get("binding") or {}), device_key=str(payload.get("device_key") or ""),
            )
        if cmd == "binding_delete":
            self.delete_binding(str(payload["adoption_id"]), str(payload["control_key"]))
            return {"deleted": True}
        if cmd == "profiles":
            return self.database.snapshot()
        if cmd == "profile_create":
            created = self.database.create_profile(
                str(payload.get("name") or ""), str(payload.get("aircraft") or "generic"),
                copy_active=bool(payload.get("copy_active", True)),
            )
            self._legacy_create_or_select(str(created["profile"]["name"]), create=True, copy_active=bool(payload.get("copy_active", True)))
            return created
        if cmd == "profile_select":
            selected = self.database.select_profile(str(payload.get("profile_id") or payload.get("name") or ""))
            self._legacy_create_or_select(str(selected["profile"]["name"]), create=False)
            applied = self.apply_active_profile_to_legacy()
            return {"profile": selected, "legacy": applied}
        if cmd == "profile_export":
            return self.database.export_profile(str(payload.get("profile_id") or "") or None)
        if cmd == "profile_import":
            imported = self.database.import_profile(dict(payload.get("document") or {}), activate=bool(payload.get("activate", True)))
            applied = self.apply_active_profile_to_legacy() if payload.get("activate", True) else {"applied": 0, "errors": []}
            return {"profile": imported, "legacy": applied}
        if cmd == "calibration_set":
            return self.database.set_calibration(
                str(payload["adoption_id"]), str(payload["control_key"]), dict(payload.get("calibration") or {})
            )
        if cmd == "cloud_configure":
            return self.configure_cloud(payload)
        if cmd == "cloud_status":
            return self.cloud.status()
        if cmd == "cloud_signup":
            return self.cloud.signup(str(payload.get("email") or ""), str(payload.get("password") or ""), display_name=str(payload.get("display_name") or ""))
        if cmd == "cloud_login":
            return self.cloud.login(str(payload.get("email") or ""), str(payload.get("password") or ""))
        if cmd == "cloud_logout":
            self.cloud.logout()
            return self.cloud.status()
        if cmd == "cloud_sync":
            result = self.cloud.sync(self.database, self._last_cloud_cursor)
            self._last_cloud_cursor = str(result.get("cursor") or self._last_cloud_cursor)
            result["legacy"] = self.apply_active_profile_to_legacy()
            return result
        raise ValidationError(f"Unknown MuslimSim Platform command {command!r}")

    def _legacy_create_or_select(self, name: str, *, create: bool, copy_active: bool = True) -> None:
        store = getattr(self.lab, "profile_store", None)
        if store is None:
            return
        try:
            if create and hasattr(store, "create"):
                store.create(name, copy_active=copy_active)
            elif hasattr(store, "select"):
                store.select(name)
            if hasattr(store, "save"):
                store.save()
        except Exception as exc:
            self._record_error("legacy-profile-select", exc)

    # --------------------------------------------------------------- snapshots
    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "platform_version": "7.0.0",
            "machine_id": self.machine_id,
            "telemetry": self.telemetry.snapshot(),
            "devices": self.identities.snapshot(),
            "authority": self.authority.to_dict(),
            "learning": self.learning.status(),
            "profiles": self.database.snapshot(),
            "cloud": self.cloud.status(),
            "plugins": self.plugins.snapshot(),
            "errors": list(self._errors),
        }


# MUSLIMSIM_PLATFORM_V7_GLOBAL_BLOCKED_WRITE_DIAGNOSTIC
_PLATFORM_V7_ACTIVE_RUNTIME = None

def set_global_runtime_for_diagnostics(runtime):
    global _PLATFORM_V7_ACTIVE_RUNTIME
    _PLATFORM_V7_ACTIVE_RUNTIME = runtime


def record_global_blocked_write(name: str) -> None:
    runtime = _PLATFORM_V7_ACTIVE_RUNTIME
    if runtime is None:
        return
    recorder = getattr(runtime, "record_global_blocked_write", None)
    if callable(recorder):
        recorder(str(name))
