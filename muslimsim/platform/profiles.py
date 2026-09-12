from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Optional

from .contracts import AdoptedDevice, Capability, DeviceRole, ValidationError

SCHEMA_VERSION = 1


def default_database_path() -> Path:
    appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    base = Path(appdata) if appdata else Path.home() / ".muslimsim"
    return base / "MuslimSim" / "platform_v7.sqlite3"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _now() -> float:
    return time.time()


class ProfileDatabase:
    """Offline-first SQLite store with a short transactional writer path.

    Hardware input threads never call this object.  The platform runtime queues
    profile and cloud changes outside the telemetry journal.  WAL mode permits
    UI reads while a profile mutation is committed.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or default_database_path()).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), timeout=5.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._migrate()
        self.prune_history()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # BUG-16: outbox, device_sightings and audit_log have no natural end -
    # every one of them is an append-only history, and nothing was ever
    # deleting from them. Over 46 hours of real use that put 3.68 million rows
    # in each, a 9.4 GB database file, and turned a bounded-looking COUNT(*)
    # query into a 151 ms one. The write side is fixed separately (BUG-16
    # again: a sighting is now persisted only when something about it actually
    # changed), but a retention limit belongs here regardless - the write side
    # being careful today does not guarantee every future code path will be,
    # and rule 0.3 is that growth must be bounded on purpose, not by
    # everyone's continued carefulness.
    #
    # Run once per process start rather than on any hot path: pruning is
    # O(rows over the limit), which only ever happens right after a burst,
    # and a fresh SQLite connection is the cheapest place to pay for it.
    HISTORY_ROW_LIMIT = 20_000

    def prune_history(self, limit: int | None = None) -> dict[str, int]:
        """Cap outbox, device_sightings and audit_log at ``limit`` rows each.

        Keeps the most recent ``limit`` rows of each table, oldest first out.
        Returns how many rows were removed from each, for the caller to log.
        """

        cap = self.HISTORY_ROW_LIMIT if limit is None else max(0, int(limit))
        removed: dict[str, int] = {}
        with self._lock:
            for table in ("outbox", "device_sightings", "audit_log"):
                cursor = self._conn.execute(
                    f"DELETE FROM {table} WHERE id NOT IN "
                    f"(SELECT id FROM {table} ORDER BY id DESC LIMIT ?)",
                    (cap,),
                )
                removed[table] = int(cursor.rowcount or 0)
            self._conn.commit()
        return removed

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _migrate(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS adopted_devices (
                    adoption_id TEXT PRIMARY KEY,
                    family_key TEXT NOT NULL,
                    portable_key TEXT NOT NULL DEFAULT '',
                    assigned_role TEXT NOT NULL DEFAULT 'unassigned',
                    friendly_name TEXT NOT NULL DEFAULT '',
                    legacy_key TEXT NOT NULL DEFAULT '',
                    driver_id TEXT NOT NULL DEFAULT '',
                    capabilities INTEGER NOT NULL DEFAULT 0,
                    vendor_product TEXT NOT NULL DEFAULT '',
                    vendor_role_hint TEXT NOT NULL DEFAULT 'unassigned',
                    state TEXT NOT NULL DEFAULT 'offline',
                    last_seen REAL NOT NULL DEFAULT 0,
                    local_match_key TEXT NOT NULL DEFAULT '',
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    needs_confirmation INTEGER NOT NULL DEFAULT 0,
                    role_change_detected INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS adopted_devices_portable_idx
                    ON adopted_devices(portable_key) WHERE portable_key <> '';
                CREATE INDEX IF NOT EXISTS adopted_devices_family_idx
                    ON adopted_devices(family_key);

                CREATE TABLE IF NOT EXISTS device_sightings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    adoption_id TEXT,
                    machine_id TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    vendor_id INTEGER,
                    product_id INTEGER,
                    serial_hash TEXT NOT NULL DEFAULT '',
                    product TEXT NOT NULL DEFAULT '',
                    role_hint TEXT NOT NULL DEFAULT 'unassigned',
                    container_hash TEXT NOT NULL DEFAULT '',
                    descriptor_hash TEXT NOT NULL DEFAULT '',
                    observed_at REAL NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(adoption_id) REFERENCES adopted_devices(adoption_id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS device_sightings_adoption_idx
                    ON device_sightings(adoption_id, observed_at DESC);

                CREATE TABLE IF NOT EXISTS profiles (
                    profile_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    aircraft TEXT NOT NULL DEFAULT 'generic',
                    is_active INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 0,
                    cloud_revision INTEGER NOT NULL DEFAULT 0,
                    cloud_id TEXT NOT NULL DEFAULT '',
                    dirty INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(name, aircraft)
                );

                CREATE TABLE IF NOT EXISTS bindings (
                    profile_id TEXT NOT NULL,
                    adoption_id TEXT NOT NULL,
                    device_key TEXT NOT NULL DEFAULT '',
                    control_key TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'disabled',
                    target TEXT NOT NULL DEFAULT '',
                    invert INTEGER NOT NULL DEFAULT 0,
                    scale REAL NOT NULL DEFAULT 1.0,
                    deadband REAL NOT NULL DEFAULT 0.0,
                    value_json TEXT,
                    mechanical TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(profile_id, adoption_id, control_key),
                    FOREIGN KEY(profile_id) REFERENCES profiles(profile_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS learned_controls (
                    profile_id TEXT NOT NULL,
                    adoption_id TEXT NOT NULL,
                    raw_key TEXT NOT NULL,
                    semantic_key TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    signature TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(profile_id, adoption_id, raw_key),
                    FOREIGN KEY(profile_id) REFERENCES profiles(profile_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS calibrations (
                    profile_id TEXT NOT NULL,
                    adoption_id TEXT NOT NULL,
                    control_key TEXT NOT NULL,
                    minimum REAL,
                    center REAL,
                    maximum REAL,
                    deadzone REAL NOT NULL DEFAULT 0.0,
                    invert INTEGER NOT NULL DEFAULT 0,
                    curve_json TEXT NOT NULL DEFAULT '[]',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(profile_id, adoption_id, control_key),
                    FOREIGN KEY(profile_id) REFERENCES profiles(profile_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS cloud_accounts (
                    account_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    project_id TEXT NOT NULL DEFAULT '',
                    auth_base TEXT NOT NULL DEFAULT '',
                    api_base TEXT NOT NULL DEFAULT '',
                    token_ref TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mutation_id TEXT NOT NULL UNIQUE,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    base_revision INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS outbox_created_idx ON outbox(created_at, id);

                CREATE TABLE IF NOT EXISTS conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    local_json TEXT NOT NULL,
                    remote_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    resolved_at REAL
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    entity_type TEXT NOT NULL DEFAULT '',
                    entity_id TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL
                );
                """
            )
            conn.execute(
                "INSERT INTO schema_meta(key,value) VALUES('schema_version',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            row = conn.execute("SELECT profile_id FROM profiles LIMIT 1").fetchone()
            if row is None:
                now = _now()
                conn.execute(
                    "INSERT INTO profiles(profile_id,name,aircraft,is_active,revision,dirty,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), "Default", "generic", 1, 0, 0, now, now),
                )

    def audit(self, event: str, *, entity_type: str = "", entity_id: str = "", details: Any = None) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO audit_log(event,entity_type,entity_id,details_json,created_at) VALUES(?,?,?,?,?)",
                (event, entity_type, entity_id, _json(details or {}), _now()),
            )

    # ------------------------------------------------------------------ devices
    def load_devices(self) -> list[AdoptedDevice]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM adopted_devices ORDER BY friendly_name, adoption_id").fetchall()
        result: list[AdoptedDevice] = []
        for row in rows:
            try:
                assigned = DeviceRole(row["assigned_role"])
            except ValueError:
                assigned = DeviceRole.UNASSIGNED
            try:
                hint = DeviceRole(row["vendor_role_hint"])
            except ValueError:
                hint = DeviceRole.UNASSIGNED
            result.append(AdoptedDevice(
                adoption_id=row["adoption_id"],
                family_key=row["family_key"],
                portable_key=row["portable_key"],
                assigned_role=assigned,
                friendly_name=row["friendly_name"],
                legacy_key=row["legacy_key"],
                driver_id=row["driver_id"],
                capabilities=Capability(int(row["capabilities"])),
                vendor_product=row["vendor_product"],
                vendor_role_hint=hint,
                state=row["state"],
                last_seen=float(row["last_seen"]),
                local_match_key=row["local_match_key"],
                aliases=list(json.loads(row["aliases_json"] or "[]")),
                needs_confirmation=bool(row["needs_confirmation"]),
                role_change_detected=bool(row["role_change_detected"]),
            ))
        return result

    def save_device(self, device: AdoptedDevice, *, queue_sync: bool = True) -> None:
        now = _now()
        payload = device.to_dict()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO adopted_devices(
                    adoption_id,family_key,portable_key,assigned_role,friendly_name,legacy_key,
                    driver_id,capabilities,vendor_product,vendor_role_hint,state,last_seen,
                    local_match_key,aliases_json,needs_confirmation,role_change_detected,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(adoption_id) DO UPDATE SET
                    family_key=excluded.family_key, portable_key=excluded.portable_key,
                    assigned_role=excluded.assigned_role, friendly_name=excluded.friendly_name,
                    legacy_key=excluded.legacy_key, driver_id=excluded.driver_id,
                    capabilities=excluded.capabilities, vendor_product=excluded.vendor_product,
                    vendor_role_hint=excluded.vendor_role_hint, state=excluded.state,
                    last_seen=excluded.last_seen, local_match_key=excluded.local_match_key,
                    aliases_json=excluded.aliases_json, needs_confirmation=excluded.needs_confirmation,
                    role_change_detected=excluded.role_change_detected, updated_at=excluded.updated_at
                """,
                (
                    device.adoption_id, device.family_key, device.portable_key,
                    device.assigned_role.value, device.friendly_name, device.legacy_key,
                    device.driver_id, int(device.capabilities), device.vendor_product,
                    device.vendor_role_hint.value, device.state, device.last_seen,
                    device.local_match_key, _json(device.aliases), int(device.needs_confirmation),
                    int(device.role_change_detected), now,
                ),
            )
            conn.execute(
                "INSERT INTO audit_log(event,entity_type,entity_id,details_json,created_at) VALUES(?,?,?,?,?)",
                ("device-saved", "device", device.adoption_id, _json(payload), now),
            )
            if queue_sync:
                self._queue_outbox_conn(conn, "device", device.adoption_id, 0, payload)

    def record_sighting(self, adoption_id: str | None, machine_id: str, sighting: Mapping[str, Any]) -> None:
        identity = dict(sighting.get("identity") or {})
        serial = str(identity.get("serial_number") or "")
        container = str(identity.get("container_id") or identity.get("instance_id") or identity.get("path") or "")
        import hashlib
        serial_hash = hashlib.sha256(serial.encode()).hexdigest() if serial else ""
        container_hash = hashlib.sha256(container.encode()).hexdigest() if container else ""
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO device_sightings(
                    adoption_id,machine_id,source,transport,vendor_id,product_id,serial_hash,
                    product,role_hint,container_hash,descriptor_hash,observed_at,details_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    adoption_id, machine_id, str(sighting.get("source") or "discovery"),
                    str(identity.get("transport") or "usb"), identity.get("vendor_id"), identity.get("product_id"),
                    serial_hash, str(identity.get("product") or ""), str(sighting.get("vendor_role_hint") or "unassigned"),
                    container_hash, str(identity.get("descriptor_hash") or ""),
                    float(sighting.get("observed_at") or _now()), _json(sighting),
                ),
            )

    # ----------------------------------------------------------------- profiles
    def list_profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM profiles ORDER BY is_active DESC, name COLLATE NOCASE"
            ).fetchall()
        return [dict(row) for row in rows]

    def active_profile(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM profiles WHERE is_active=1 LIMIT 1").fetchone()
        if row is None:
            raise ValidationError("No active MuslimSim platform profile")
        return dict(row)

    def create_profile(self, name: str, aircraft: str = "generic", *, copy_active: bool = True) -> dict[str, Any]:
        name = str(name).strip()
        aircraft = str(aircraft or "generic").strip().lower()
        if not name:
            raise ValidationError("Profile name is required")
        profile_id = str(uuid.uuid4())
        now = _now()
        with self.transaction() as conn:
            source = conn.execute("SELECT profile_id FROM profiles WHERE is_active=1 LIMIT 1").fetchone()
            conn.execute("UPDATE profiles SET is_active=0")
            conn.execute(
                "INSERT INTO profiles(profile_id,name,aircraft,is_active,revision,dirty,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (profile_id, name, aircraft, 1, 1, 1, now, now),
            )
            if copy_active and source:
                source_id = source[0]
                conn.execute(
                    """INSERT INTO bindings(profile_id,adoption_id,device_key,control_key,kind,target,invert,scale,deadband,value_json,mechanical,metadata_json,updated_at)
                       SELECT ?,adoption_id,device_key,control_key,kind,target,invert,scale,deadband,value_json,mechanical,metadata_json,?
                       FROM bindings WHERE profile_id=?""",
                    (profile_id, now, source_id),
                )
                conn.execute(
                    """INSERT INTO learned_controls(profile_id,adoption_id,raw_key,semantic_key,label,signature,confidence,updated_at)
                       SELECT ?,adoption_id,raw_key,semantic_key,label,signature,confidence,?
                       FROM learned_controls WHERE profile_id=?""",
                    (profile_id, now, source_id),
                )
                conn.execute(
                    """INSERT INTO calibrations(profile_id,adoption_id,control_key,minimum,center,maximum,deadzone,invert,curve_json,updated_at)
                       SELECT ?,adoption_id,control_key,minimum,center,maximum,deadzone,invert,curve_json,?
                       FROM calibrations WHERE profile_id=?""",
                    (profile_id, now, source_id),
                )
            payload = {"profile_id": profile_id, "name": name, "aircraft": aircraft, "revision": 1}
            self._queue_outbox_conn(conn, "profile", profile_id, 0, payload)
            conn.execute(
                "INSERT INTO audit_log(event,entity_type,entity_id,details_json,created_at) VALUES(?,?,?,?,?)",
                ("profile-created", "profile", profile_id, _json(payload), now),
            )
        return self.profile_document(profile_id)

    def select_profile(self, profile_id_or_name: str) -> dict[str, Any]:
        value = str(profile_id_or_name).strip()
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT profile_id FROM profiles WHERE profile_id=? OR name=? ORDER BY profile_id=? DESC LIMIT 1",
                (value, value, value),
            ).fetchone()
            if row is None:
                raise ValidationError(f"Unknown profile {value!r}")
            conn.execute("UPDATE profiles SET is_active=0")
            conn.execute("UPDATE profiles SET is_active=1 WHERE profile_id=?", (row[0],))
        return self.profile_document(row[0])

    def _profile_id(self, profile_id: str | None = None) -> str:
        return str(profile_id or self.active_profile()["profile_id"])

    def profile_document(self, profile_id: str | None = None) -> dict[str, Any]:
        pid = self._profile_id(profile_id)
        with self._lock:
            profile = self._conn.execute("SELECT * FROM profiles WHERE profile_id=?", (pid,)).fetchone()
            if profile is None:
                raise ValidationError(f"Unknown profile {pid!r}")
            bindings = self._conn.execute(
                "SELECT * FROM bindings WHERE profile_id=? ORDER BY adoption_id,control_key", (pid,)
            ).fetchall()
            learned = self._conn.execute(
                "SELECT * FROM learned_controls WHERE profile_id=? ORDER BY adoption_id,raw_key", (pid,)
            ).fetchall()
            calibrations = self._conn.execute(
                "SELECT * FROM calibrations WHERE profile_id=? ORDER BY adoption_id,control_key", (pid,)
            ).fetchall()
        return {
            "schema": 1,
            "profile": dict(profile),
            "bindings": [dict(row) for row in bindings],
            "learned_controls": [dict(row) for row in learned],
            "calibrations": [dict(row) for row in calibrations],
        }

    def set_binding(
        self,
        adoption_id: str,
        control_key: str,
        binding: Mapping[str, Any],
        *,
        device_key: str = "",
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        pid = self._profile_id(profile_id)
        control_key = str(control_key).strip()
        if not control_key:
            raise ValidationError("Control key is required")
        kind = str(binding.get("kind") or "disabled")
        target = str(binding.get("target") or "")
        invert = bool(binding.get("invert", False))
        scale = float(binding.get("scale", 1.0))
        deadband = float(binding.get("deadband", 0.0))
        value = binding.get("value")
        mechanical = str(binding.get("mechanical") or "")
        metadata = dict(binding.get("metadata") or {})
        now = _now()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO bindings(profile_id,adoption_id,device_key,control_key,kind,target,invert,scale,deadband,value_json,mechanical,metadata_json,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(profile_id,adoption_id,control_key) DO UPDATE SET
                    device_key=excluded.device_key,kind=excluded.kind,target=excluded.target,
                    invert=excluded.invert,scale=excluded.scale,deadband=excluded.deadband,
                    value_json=excluded.value_json,mechanical=excluded.mechanical,
                    metadata_json=excluded.metadata_json,updated_at=excluded.updated_at
                """,
                (pid, adoption_id, device_key, control_key, kind, target, int(invert), scale, deadband,
                 None if value is None else _json(value), mechanical, _json(metadata), now),
            )
            revision = self._touch_profile_conn(conn, pid)
            payload = {
                "profile_id": pid, "adoption_id": adoption_id, "device_key": device_key,
                "control_key": control_key, "kind": kind, "target": target,
                "invert": invert, "scale": scale, "deadband": deadband,
                "value": value, "mechanical": mechanical, "metadata": metadata,
                "revision": revision,
            }
            self._queue_outbox_conn(conn, "binding", f"{pid}:{adoption_id}:{control_key}", revision - 1, payload)
            conn.execute(
                "INSERT INTO audit_log(event,entity_type,entity_id,details_json,created_at) VALUES(?,?,?,?,?)",
                ("binding-set", "binding", f"{pid}:{adoption_id}:{control_key}", _json(payload), now),
            )
        return payload

    def delete_binding(self, adoption_id: str, control_key: str, *, profile_id: str | None = None) -> None:
        pid = self._profile_id(profile_id)
        now = _now()
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM bindings WHERE profile_id=? AND adoption_id=? AND control_key=?",
                (pid, adoption_id, control_key),
            )
            revision = self._touch_profile_conn(conn, pid)
            payload = {"deleted": True, "profile_id": pid, "adoption_id": adoption_id, "control_key": control_key, "revision": revision}
            self._queue_outbox_conn(conn, "binding", f"{pid}:{adoption_id}:{control_key}", revision - 1, payload)
            conn.execute(
                "INSERT INTO audit_log(event,entity_type,entity_id,details_json,created_at) VALUES(?,?,?,?,?)",
                ("binding-deleted", "binding", f"{pid}:{adoption_id}:{control_key}", _json(payload), now),
            )

    def set_learned_control(
        self,
        adoption_id: str,
        raw_key: str,
        semantic_key: str,
        *,
        label: str = "",
        signature: str = "",
        confidence: float = 1.0,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        pid = self._profile_id(profile_id)
        now = _now()
        payload = {
            "profile_id": pid, "adoption_id": adoption_id, "raw_key": str(raw_key),
            "semantic_key": str(semantic_key), "label": str(label), "signature": str(signature),
            "confidence": max(0.0, min(1.0, float(confidence))),
        }
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO learned_controls(profile_id,adoption_id,raw_key,semantic_key,label,signature,confidence,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(profile_id,adoption_id,raw_key) DO UPDATE SET
                     semantic_key=excluded.semantic_key,label=excluded.label,signature=excluded.signature,
                     confidence=excluded.confidence,updated_at=excluded.updated_at""",
                (pid, adoption_id, str(raw_key), str(semantic_key), str(label), str(signature), payload["confidence"], now),
            )
            revision = self._touch_profile_conn(conn, pid)
            payload["revision"] = revision
            self._queue_outbox_conn(conn, "learned_control", f"{pid}:{adoption_id}:{raw_key}", revision - 1, payload)
            conn.execute(
                "INSERT INTO audit_log(event,entity_type,entity_id,details_json,created_at) VALUES(?,?,?,?,?)",
                ("control-learned", "learned_control", f"{pid}:{adoption_id}:{raw_key}", _json(payload), now),
            )
        return payload

    def set_calibration(
        self,
        adoption_id: str,
        control_key: str,
        calibration: Mapping[str, Any],
        *,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        pid = self._profile_id(profile_id)
        now = _now()
        payload = {
            "profile_id": pid, "adoption_id": adoption_id, "control_key": str(control_key),
            "minimum": calibration.get("minimum"), "center": calibration.get("center"),
            "maximum": calibration.get("maximum"), "deadzone": float(calibration.get("deadzone", 0.0)),
            "invert": bool(calibration.get("invert", False)), "curve": list(calibration.get("curve") or []),
        }
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO calibrations(profile_id,adoption_id,control_key,minimum,center,maximum,deadzone,invert,curve_json,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(profile_id,adoption_id,control_key) DO UPDATE SET
                     minimum=excluded.minimum,center=excluded.center,maximum=excluded.maximum,
                     deadzone=excluded.deadzone,invert=excluded.invert,curve_json=excluded.curve_json,
                     updated_at=excluded.updated_at""",
                (pid, adoption_id, str(control_key), payload["minimum"], payload["center"], payload["maximum"],
                 payload["deadzone"], int(payload["invert"]), _json(payload["curve"]), now),
            )
            revision = self._touch_profile_conn(conn, pid)
            payload["revision"] = revision
            self._queue_outbox_conn(conn, "calibration", f"{pid}:{adoption_id}:{control_key}", revision - 1, payload)
        return payload

    def _touch_profile_conn(self, conn: sqlite3.Connection, profile_id: str) -> int:
        now = _now()
        conn.execute(
            "UPDATE profiles SET revision=revision+1,dirty=1,updated_at=? WHERE profile_id=?",
            (now, profile_id),
        )
        row = conn.execute("SELECT revision FROM profiles WHERE profile_id=?", (profile_id,)).fetchone()
        if row is None:
            raise ValidationError(f"Unknown profile {profile_id!r}")
        return int(row[0])

    # ------------------------------------------------------------------- outbox
    def _queue_outbox_conn(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        base_revision: int,
        payload: Mapping[str, Any],
    ) -> str:
        mutation_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO outbox(mutation_id,entity_type,entity_id,base_revision,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            (mutation_id, entity_type, entity_id, int(base_revision), _json(payload), _now()),
        )
        return mutation_id

    def outbox(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM outbox ORDER BY created_at,id LIMIT ?", (max(1, min(int(limit), 1000)),)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def acknowledge_mutations(self, mutation_ids: Iterable[str]) -> None:
        ids = [str(value) for value in mutation_ids if value]
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self.transaction() as conn:
            conn.execute(f"DELETE FROM outbox WHERE mutation_id IN ({placeholders})", ids)

    def fail_mutation(self, mutation_id: str, error: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE outbox SET attempts=attempts+1,last_error=? WHERE mutation_id=?",
                (str(error)[:2000], str(mutation_id)),
            )

    def record_conflict(self, entity_type: str, entity_id: str, local: Any, remote: Any) -> str:
        conflict_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO conflicts(conflict_id,entity_type,entity_id,local_json,remote_json,created_at) VALUES(?,?,?,?,?,?)",
                (conflict_id, entity_type, entity_id, _json(local), _json(remote), _now()),
            )
        return conflict_id

    # ------------------------------------------------------------- import/export
    def export_profile(self, profile_id: str | None = None) -> dict[str, Any]:
        document = self.profile_document(profile_id)
        document["exported_at"] = _now()
        document["product"] = "MuslimSim"
        document["platform_version"] = 7
        document["devices"] = [device.to_dict() for device in self.load_devices()]
        return document

    def import_profile(self, document: Mapping[str, Any], *, activate: bool = True) -> dict[str, Any]:
        if int(document.get("schema", 0)) != 1:
            raise ValidationError("Unsupported MuslimSim profile schema")
        source = dict(document.get("profile") or {})
        name = str(source.get("name") or "Imported profile").strip()
        aircraft = str(source.get("aircraft") or "generic")
        created = self.create_profile(name, aircraft, copy_active=False)
        pid = created["profile"]["profile_id"]
        for item in document.get("bindings") or []:
            row = dict(item)
            value = row.get("value")
            if value is None and row.get("value_json") not in (None, ""):
                try:
                    value = json.loads(row["value_json"])
                except (TypeError, ValueError):
                    value = None
            self.set_binding(
                str(row.get("adoption_id") or row.get("device_key") or "legacy"),
                str(row.get("control_key") or ""),
                {
                    "kind": row.get("kind", "disabled"), "target": row.get("target", ""),
                    "invert": bool(row.get("invert", False)), "scale": row.get("scale", 1.0),
                    "deadband": row.get("deadband", 0.0), "value": value,
                    "mechanical": row.get("mechanical", ""),
                },
                device_key=str(row.get("device_key") or ""), profile_id=pid,
            )
        for item in document.get("learned_controls") or []:
            row = dict(item)
            self.set_learned_control(
                str(row.get("adoption_id") or row.get("device_key") or "legacy"),
                str(row.get("raw_key") or ""), str(row.get("semantic_key") or ""),
                label=str(row.get("label") or ""), signature=str(row.get("signature") or ""),
                confidence=float(row.get("confidence", 1.0)), profile_id=pid,
            )
        for item in document.get("calibrations") or []:
            row = dict(item)
            curve = row.get("curve")
            if curve is None and row.get("curve_json"):
                try:
                    curve = json.loads(row["curve_json"])
                except (TypeError, ValueError):
                    curve = []
            self.set_calibration(
                str(row.get("adoption_id") or row.get("device_key") or "legacy"),
                str(row.get("control_key") or ""),
                {
                    "minimum": row.get("minimum"), "center": row.get("center"), "maximum": row.get("maximum"),
                    "deadzone": row.get("deadzone", 0.0), "invert": bool(row.get("invert", False)),
                    "curve": curve or [],
                }, profile_id=pid,
            )
        if activate:
            self.select_profile(pid)
        return self.profile_document(pid)

    # ----------------------------------------------------------- legacy adapter
    def import_legacy_snapshot(self, snapshot: Mapping[str, Any]) -> int:
        """Import the existing ``hardware_profiles.json`` shape without deleting it."""
        profiles = dict(snapshot.get("profiles") or {})
        imported = 0
        for name, body in profiles.items():
            body = dict(body or {})
            aircraft = str(body.get("aircraft") or "generic")
            try:
                doc = self.create_profile(str(name), aircraft, copy_active=False)
            except sqlite3.IntegrityError:
                row = next((p for p in self.list_profiles() if p["name"] == str(name) and p["aircraft"] == aircraft), None)
                if row is None:
                    continue
                doc = self.profile_document(row["profile_id"])
            pid = doc["profile"]["profile_id"]
            bindings = dict(body.get("bindings") or {})
            for device_key, controls in bindings.items():
                for control_key, binding in dict(controls or {}).items():
                    self.set_binding(str(device_key), str(control_key), dict(binding or {}), device_key=str(device_key), profile_id=pid)
                    imported += 1
            learned = dict(body.get("learned_controls") or {})
            for device_key, controls in learned.items():
                for raw_key, semantic_key in dict(controls or {}).items():
                    self.set_learned_control(str(device_key), str(raw_key), str(semantic_key), profile_id=pid)
            calibrations = dict(body.get("calibration") or body.get("calibrations") or {})
            for device_key, values in calibrations.items():
                if isinstance(values, Mapping):
                    for control_key, calibration in values.items():
                        if isinstance(calibration, Mapping):
                            self.set_calibration(str(device_key), str(control_key), calibration, profile_id=pid)
        active_name = str(snapshot.get("active_profile") or "")
        if active_name:
            try:
                self.select_profile(active_name)
            except ValidationError:
                pass
        return imported

    # BUG-16: this was ``SELECT COUNT(*) FROM outbox`` with no LIMIT, called on
    # every status poll. Nothing anywhere in MuslimSim reads outbox_count or
    # conflict_count - they are diagnostic fields nobody has ever consumed -
    # yet a full, unfiltered COUNT(*) still costs one pass over the whole
    # table. On a live outbox that had been left to grow to 3.68 million rows
    # by an unrelated bug (see BUG-16 in full), that one query alone measured
    # 151 ms - one and a half times the entire 100 ms status-poll interval, on
    # a single query nobody was looking at.
    #
    # Bounded rather than exact on purpose: a caller that only wants to know
    # "is there a backlog, and is it a large one" is served just as well by
    # "at least 5000" as by an exact count of an unbounded table, and the
    # bounded form costs the same however large history is ever allowed to
    # grow - which is the whole point. Rule 0.3 is that nothing may get
    # slower as the project grows; an exact COUNT(*) on a table with no
    # retention limit cannot make that promise, and a bounded one always can.
    _COUNT_BOUND = 5000

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            outbox_count = int(self._conn.execute(
                f"SELECT COUNT(*) FROM (SELECT 1 FROM outbox LIMIT {self._COUNT_BOUND})"
            ).fetchone()[0])
            conflict_count = int(self._conn.execute(
                "SELECT COUNT(*) FROM (SELECT 1 FROM conflicts WHERE resolved_at IS NULL "
                f"LIMIT {self._COUNT_BOUND})"
            ).fetchone()[0])
        return {
            "schema": SCHEMA_VERSION,
            "path": str(self.path),
            "profiles": self.list_profiles(),
            "active": self.active_profile(),
            "outbox_count": outbox_count,
            "outbox_count_is_a_lower_bound": outbox_count >= self._COUNT_BOUND,
            "conflict_count": conflict_count,
            "conflict_count_is_a_lower_bound": conflict_count >= self._COUNT_BOUND,
        }
