from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from .contracts import DeviceSighting
from .identity import sighting_from_mapping


class DiscoverySource(Protocol):
    source_id: str
    def scan(self) -> Sequence[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class DiscoveryCycle:
    generation: int
    started_at: float
    finished_at: float
    sightings: int
    errors: tuple[str, ...]


class DiscoveryCoordinator:
    """Slow health scan plus immediate requested rescans.

    Existing device owners remain responsible for opening hardware. Discovery
    sources enumerate metadata only; they must not claim HID/SDL/serial handles.
    """

    def __init__(
        self,
        sink: Callable[[list[DeviceSighting]], Any],
        *,
        interval: float = 15.0,
    ) -> None:
        self.sink = sink
        self.interval = max(1.0, float(interval))
        self.sources: list[DiscoverySource] = []
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._generation = 0
        self._last_cycle: DiscoveryCycle | None = None

    def register(self, source: DiscoverySource) -> None:
        with self._lock:
            if any(item.source_id == source.source_id for item in self.sources):
                raise ValueError(f"Duplicate discovery source {source.source_id}")
            self.sources.append(source)

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="MuslimSim-Discovery", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread:
            thread.join(timeout=2.0)

    def rescan(self) -> None:
        self._wake.set()

    def scan_once(self) -> DiscoveryCycle:
        started = time.time()
        sightings: list[DeviceSighting] = []
        errors: list[str] = []
        with self._lock:
            sources = list(self.sources)
        for source in sources:
            try:
                for row in source.scan():
                    sightings.append(sighting_from_mapping(row, source=source.source_id))
            except Exception as exc:
                errors.append(f"{source.source_id}: {exc}")
        if sightings:
            self.sink(sightings)
        with self._lock:
            self._generation += 1
            self._last_cycle = DiscoveryCycle(
                generation=self._generation,
                started_at=started,
                finished_at=time.time(),
                sightings=len(sightings),
                errors=tuple(errors),
            )
            return self._last_cycle

    def _run(self) -> None:
        while not self._stop.is_set():
            self.scan_once()
            self._wake.wait(self.interval)
            self._wake.clear()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            cycle = self._last_cycle
            return {
                "generation": self._generation,
                "running": bool(self._thread and self._thread.is_alive()),
                "sources": [source.source_id for source in self.sources],
                "last_cycle": None if cycle is None else {
                    "generation": cycle.generation,
                    "started_at": cycle.started_at,
                    "finished_at": cycle.finished_at,
                    "sightings": cycle.sightings,
                    "errors": list(cycle.errors),
                },
            }
