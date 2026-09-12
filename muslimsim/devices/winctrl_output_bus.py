#!/usr/bin/env python3
"""Small per-device arbiter for MuslimSim WinCtrl HID output.

Several WinCtrl displays use multi-report transactions and large font/frame
bursts.  A complete burst must stay ordered for *one physical panel*, but
independent USB panels must never share a lock: a slow or unplugged PFP must
not freeze the PAP3 MCP windows, and a PAP3 LCD update must not hold up a
separate display.

This module does not merge device protocols and never serializes input reads.
It only:

* gives each wrapped HID handle a transparent, locked ``write`` operation;
* lets one physical display hold the same re-entrant lock across a complete
  report burst;
* records lightweight activity information for diagnostics/tests.

The wrapper deliberately delegates every method except output/close, so code
written for ``hid.device`` continues to work unchanged.
"""

from __future__ import annotations

from contextlib import contextmanager
import threading
import time
from typing import Any, Dict, Iterator, Optional

_LOCKS_GUARD = threading.Lock()
_OUTPUT_LOCKS: Dict[str, threading.RLock] = {}
_STATE_LOCK = threading.Lock()
_LAST_WRITE: Dict[str, float] = {}
_WRITE_COUNTS: Dict[str, int] = {}


def _lock_key(label: str) -> str:
    """Return a stable physical-panel key for a writer or transaction label.

    The driver labels deliberately share a family prefix, for example
    ``PAP3-LCD`` and ``PAP3-BF0F`` refer to the same MCP, while ``BB35`` is
    the PFP and ``BB36`` the MCDU.  Keeping the normalization explicit avoids
    silently treating unrelated panels as one bus just because they are both
    WinCtrl products.
    """

    normalized = str(label or "WinCtrl").strip().upper()
    for prefix in ("PAP3", "BB35", "BB36"):
        if normalized == prefix or normalized.startswith(prefix + "-"):
            return prefix
    return normalized


def _output_lock(label: str) -> threading.RLock:
    """Get the re-entrant transaction lock for one physical panel only."""

    key = _lock_key(label)
    with _LOCKS_GUARD:
        lock = _OUTPUT_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _OUTPUT_LOCKS[key] = lock
        return lock


class SerializedHidDevice:
    """Transparent ``hid.device`` proxy with serialized output writes."""

    def __init__(
        self,
        raw_device: Any,
        *,
        label: str,
        product_id: Optional[int] = None,
    ) -> None:
        if isinstance(raw_device, SerializedHidDevice):
            # This branch is normally avoided by wrap_hid_device(), but keeping
            # it harmless makes direct construction safe as well.
            raw_device = raw_device.raw_device
        self.raw_device = raw_device
        self.label = str(label or "WinCtrl")
        self.product_id = None if product_id is None else int(product_id)
        self._output_lock = _output_lock(self.label)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw_device, name)

    def _record_write(self) -> None:
        now = time.monotonic()
        with _STATE_LOCK:
            _LAST_WRITE[self.label] = now
            _WRITE_COUNTS[self.label] = _WRITE_COUNTS.get(self.label, 0) + 1

    def write(self, data: Any) -> Any:
        with self._output_lock:
            result = self.raw_device.write(data)
            self._record_write()
            return result

    def send_feature_report(self, data: Any) -> Any:
        method = getattr(self.raw_device, "send_feature_report")
        with self._output_lock:
            result = method(data)
            self._record_write()
            return result

    def close(self) -> Any:
        # Keep close out of the middle of this panel's atomic report burst.
        with self._output_lock:
            return self.raw_device.close()



def wrap_hid_device(
    device: Any,
    *,
    label: str,
    product_id: Optional[int] = None,
) -> SerializedHidDevice:
    """Return an idempotently wrapped HID device."""

    if isinstance(device, SerializedHidDevice):
        return device
    return SerializedHidDevice(
        device,
        label=label,
        product_id=product_id,
    )


@contextmanager
def output_transaction(
    label: str,
    *,
    settle_after: float = 0.0,
) -> Iterator[None]:
    """Hold one physical panel's output lock across a complete transaction."""

    with _output_lock(label):
        yield
        if settle_after > 0.0:
            time.sleep(max(0.0, float(settle_after)))


def output_activity_snapshot() -> Dict[str, Dict[str, float]]:
    """Return a copy of write counters/timestamps for diagnostics and tests."""

    with _STATE_LOCK:
        labels = set(_LAST_WRITE) | set(_WRITE_COUNTS)
        return {
            label: {
                "last_write": float(_LAST_WRITE.get(label, 0.0)),
                "writes": float(_WRITE_COUNTS.get(label, 0)),
            }
            for label in labels
        }


def reset_output_activity_for_tests() -> None:
    """Clear diagnostics state; not used by production code."""

    with _STATE_LOCK:
        _LAST_WRITE.clear()
        _WRITE_COUNTS.clear()
    with _LOCKS_GUARD:
        _OUTPUT_LOCKS.clear()


__all__ = [
    "SerializedHidDevice",
    "output_activity_snapshot",
    "output_transaction",
    "reset_output_activity_for_tests",
    "wrap_hid_device",
]
