"""Read the complete ToLiss FMGS route from its own situation autosave.

ToLiss A321 1.8 keeps the expanded active and temporary flight plans inside
``Resources/plugins/ToLissData/Situations/A321_AUTOSAVED_SITUATION.qps``.
The public dataref catalogue exposes only the active WPT identifier,
course and distance.  This module therefore reads the already-written ToLiss
autosave; it never writes the simulator, presses an MCDU key, or asks ToLiss to
save more often.

The QPS container is a sequence of bounded records::

    uint32 id, uint32 element_size, uint32 count, uint32 capacity, payload

The route is identified structurally as adjacent latitude/longitude/name
records with matching dimensions and the current live WPT identifier.  No
record number or byte offset is assumed, so a changed ToLiss build fails closed
instead of interpreting unrelated situation data as a route.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import os
from pathlib import Path
import struct
import threading
import time
from typing import Iterable, Optional, Sequence, Tuple


_QPS_HEADER = struct.Struct("<4I")
_MAX_QPS_BYTES = 64 * 1024 * 1024
_MAX_RECORD_ELEMENTS = 1_000_000
_MAX_ELEMENT_BYTES = 4096
_MIN_ROUTE_SLOTS = 8
_MAX_ROUTE_SLOTS = 1000
_PATH_PROBE_SECONDS = 1.0
_MODEL_TOKENS = ("A321", "A320", "A319", "A346", "A340", "A339", "A330")


@dataclass(frozen=True)
class TolissRouteSnapshot:
    latitudes: Tuple[float, ...]
    longitudes: Tuple[float, ...]
    waypoint_ids: Tuple[str, ...]
    # True at source index N means there is no route connector from the prior
    # valid waypoint to N.  Blank QPS slots between valid fixes set this bit.
    break_before: Tuple[bool, ...]
    active_index: int
    source_path: str
    source_modified_ns: int


@dataclass(frozen=True)
class _Record:
    record_id: int
    element_size: int
    count: int
    capacity: int
    payload: bytes


_cache_lock = threading.Lock()
_cached_signature: Optional[Tuple[str, int, int]] = None
_cached_snapshot: Optional[TolissRouteSnapshot] = None
_cached_active_probe = ""
_last_path_probe = 0.0
_cached_path: Optional[Path] = None


def _normalise_wpt_id(value: object) -> str:
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="ignore")
    return str(value or "").split("\x00", 1)[0].strip().upper()


def _records(blob: bytes) -> Tuple[_Record, ...]:
    offset = 0
    records = []
    while offset < len(blob):
        if len(blob) - offset < _QPS_HEADER.size:
            raise ValueError("truncated QPS record header")
        record_id, element_size, count, capacity = _QPS_HEADER.unpack_from(blob, offset)
        if not (0 < element_size <= _MAX_ELEMENT_BYTES):
            raise ValueError(f"unsafe QPS element size {element_size}")
        if count > _MAX_RECORD_ELEMENTS:
            raise ValueError(f"unsafe QPS element count {count}")
        payload_size = element_size * count
        start = offset + _QPS_HEADER.size
        end = start + payload_size
        if end > len(blob):
            raise ValueError("truncated QPS record payload")
        records.append(_Record(record_id, element_size, count, capacity, blob[start:end]))
        offset = end
    return tuple(records)


def _float_array(record: _Record) -> Tuple[float, ...]:
    return tuple(value[0] for value in struct.iter_unpack("<f", record.payload))


def _text_array(record: _Record) -> Tuple[str, ...]:
    width = record.element_size
    return tuple(
        record.payload[index:index + width]
        .split(b"\x00", 1)[0]
        .decode("ascii", errors="ignore")
        .strip()
        for index in range(0, len(record.payload), width)
    )


def _coordinate_valid(latitude: float, longitude: float) -> bool:
    return (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and abs(latitude) <= 90.0
        and abs(longitude) <= 180.0
        and not (abs(latitude) < 0.001 and abs(longitude) < 0.001)
    )


def _candidate_routes(records: Sequence[_Record], active_wpt_id: str) -> Iterable[tuple]:
    for latitude_record, longitude_record, name_record in zip(records, records[1:], records[2:]):
        if latitude_record.element_size != 4 or longitude_record.element_size != 4:
            continue
        if name_record.element_size not in (5, 10, 20):
            continue
        if not (
            latitude_record.count == longitude_record.count == name_record.count
            and latitude_record.capacity == longitude_record.capacity == name_record.capacity
            and _MIN_ROUTE_SLOTS <= latitude_record.count <= _MAX_ROUTE_SLOTS
        ):
            continue
        latitudes = _float_array(latitude_record)
        longitudes = _float_array(longitude_record)
        names = _text_array(name_record)
        normalised = tuple(_normalise_wpt_id(name) for name in names)
        valid_named = sum(
            bool(name) and _coordinate_valid(latitude, longitude)
            for name, latitude, longitude in zip(normalised, latitudes, longitudes)
        )
        active_matches = tuple(index for index, name in enumerate(normalised) if name == active_wpt_id)
        if valid_named < 4 or not active_matches:
            continue
        yield valid_named, latitudes, longitudes, normalised, active_matches


def parse_toliss_qps_route(
    path: os.PathLike[str] | str,
    active_wpt_id: object,
) -> Optional[TolissRouteSnapshot]:
    """Return the structurally matched active route, or ``None`` safely."""
    active = _normalise_wpt_id(active_wpt_id)
    if not active:
        return None
    source = Path(path)
    try:
        stat = source.stat()
        if stat.st_size <= 0 or stat.st_size > _MAX_QPS_BYTES:
            return None
        blob = source.read_bytes()
        candidates = list(_candidate_routes(_records(blob), active))
    except (OSError, ValueError, struct.error):
        return None
    if not candidates:
        return None

    _score, latitudes, longitudes, names, matches = max(candidates, key=lambda item: item[0])
    meaningful = [
        index
        for index, (name, latitude, longitude) in enumerate(zip(names, latitudes, longitudes))
        if name and _coordinate_valid(latitude, longitude)
    ]
    if len(meaningful) < 4:
        return None
    last = meaningful[-1]
    latitudes = latitudes[:last + 1]
    longitudes = longitudes[:last + 1]
    names = names[:last + 1]

    breaks = [False] * len(names)
    prior_valid: Optional[int] = None
    for index, (name, latitude, longitude) in enumerate(zip(names, latitudes, longitudes)):
        valid = bool(name) and _coordinate_valid(latitude, longitude)
        if not valid:
            continue
        if prior_valid is not None and index != prior_valid + 1:
            breaks[index] = True
        prior_valid = index

    active_index = next((index for index in matches if index <= last), -1)
    if active_index < 0:
        return None
    return TolissRouteSnapshot(
        tuple(latitudes), tuple(longitudes), tuple(names), tuple(breaks),
        active_index, str(source), stat.st_mtime_ns,
    )


def _model_prefix(aircraft_path: object) -> str:
    upper = str(aircraft_path or "").upper()
    return next((token for token in _MODEL_TOKENS if token in upper), "A321")


def _installed_roots() -> Tuple[Path, ...]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return ()
    locations = Path(local_app_data) / "x-plane_install_12.txt"
    try:
        lines = locations.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ()
    return tuple(Path(line.strip()) for line in lines if line.strip())


def _find_autosave(aircraft_path: object) -> Optional[Path]:
    model = _model_prefix(aircraft_path)
    relative_aircraft = str(aircraft_path or "").replace("/", os.sep)
    if not relative_aircraft:
        return None
    candidates = []
    for root in _installed_roots():
        if relative_aircraft and not (root / relative_aircraft).is_file():
            continue
        candidate = root / "Resources" / "plugins" / "ToLissData" / "Situations" / f"{model}_AUTOSAVED_SITUATION.qps"
        try:
            candidates.append((candidate.stat().st_mtime_ns, candidate))
        except OSError:
            continue
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def read_toliss_autosaved_route(
    aircraft_path: object,
    active_wpt_id: object,
) -> Optional[TolissRouteSnapshot]:
    """Read once per changed autosave and rematch the moving active waypoint."""
    global _cached_active_probe, _cached_path, _cached_signature, _cached_snapshot, _last_path_probe
    active = _normalise_wpt_id(active_wpt_id)
    if not active:
        return None
    now = time.monotonic()
    with _cache_lock:
        if _cached_path is None or now - _last_path_probe >= _PATH_PROBE_SECONDS:
            _cached_path = _find_autosave(aircraft_path)
            _last_path_probe = now
        path = _cached_path
        if path is None:
            return None
        try:
            stat = path.stat()
        except OSError:
            return None
        signature = (str(path), stat.st_mtime_ns, stat.st_size)
        if signature != _cached_signature or (_cached_snapshot is None and active != _cached_active_probe):
            _cached_snapshot = parse_toliss_qps_route(path, active)
            _cached_signature = signature
            _cached_active_probe = active
        snapshot = _cached_snapshot
        if snapshot is None:
            return None
        matches = [index for index, name in enumerate(snapshot.waypoint_ids) if name == active]
        if not matches:
            # A changed FMGS plan can precede ToLiss's next automatic save.
            # Do not show a stale plan with a mismatched active leg.
            return None
        return replace(snapshot, active_index=matches[0])
