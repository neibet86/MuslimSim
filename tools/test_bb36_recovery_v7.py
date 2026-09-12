#!/usr/bin/env python3
"""Offline BB36 recovery V7 contract checks.

No physical HID device or simulator is opened.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.devices import mcdu_bb36_separate_paths as bb36


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "_bb36_recovery_v7_bridge_test",
        ROOT / "bridge" / "final.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Alive:
    def is_alive(self):
        return True


class FakeCloseDevice:
    def __init__(self):
        self.closed = threading.Event()
        self.close_count = 0

    def close(self):
        self.close_count += 1
        self.closed.set()


def main() -> int:
    checks = 0

    # ------------------------------------------------------------------
    # Real F0 progress callback: it fires only after accepted writes.
    # ------------------------------------------------------------------
    bridge = load_bridge()

    class WriteDevice:
        def __init__(self):
            self.writes = []

        def write(self, report):
            data = bytes(report)
            self.writes.append(data)
            return len(data)

    device = WriteDevice()
    canvas = bridge._PfpNativeCanvas(
        device,
        identifier=bridge.MCDU_PFD_IDENTIFIER,
    )
    progress = []
    canvas.set_progress_callback(lambda: progress.append(time.monotonic()))
    canvas.fill(0, 0, 2, 2)
    canvas.command(0x103)
    check(device.writes, "BB36 native canvas emitted no F0 writes")
    check(
        len(progress) == len(device.writes),
        "accepted-F0 progress callback count does not match successful reports",
    )
    checks += 2

    # A failed write must not report progress for the failed packet.
    class FailDevice:
        def __init__(self):
            self.calls = 0

        def write(self, report):
            self.calls += 1
            return -1

    failed = FailDevice()
    failed_canvas = bridge._PfpNativeCanvas(
        failed,
        identifier=bridge.MCDU_PFD_IDENTIFIER,
    )
    failed_progress = []
    failed_canvas.set_progress_callback(
        lambda: failed_progress.append(1)
    )
    failed_canvas.fill(0, 0, 1, 1)
    try:
        failed_canvas.flush()
    except OSError:
        pass
    else:
        raise AssertionError("negative F0 result did not raise")
    check(
        not failed_progress,
        "failed F0 write incorrectly published successful progress",
    )
    checks += 1

    # ------------------------------------------------------------------
    # Health supervisor uses real output progress, not frame completion only.
    # ------------------------------------------------------------------
    original_present = bb36._bb36_present
    bb36._bb36_present = lambda: True
    try:
        router = bb36.MuslimSimBB36PathRouter(
            "http://127.0.0.1:8086",
            "v3",
            ".",
            lambda: (None, None),
            lambda *args: None,
            {},
            0.12,
        )
        path = bb36.BB36PFDPath(
            lambda: (None, None),
            lambda *args: None,
            "v3",
            {},
            0.12,
            lambda: None,
        )
        path.device = object()
        path.worker = Alive()
        path.key_reader = Alive()
        now = time.monotonic()
        path.started_monotonic = now - 20.0
        path.key_heartbeat_monotonic = now
        with path.status_lock:
            path.status["heartbeat_monotonic"] = now - 10.0
            path.status["output_progress_monotonic"] = now - 1.0
            path.status["input_recovering"] = False

        router.active = path
        check(
            router._active_is_healthy(record=True),
            "fresh accepted-F0 progress did not keep BB36 healthy",
        )
        checks += 1

        with path.status_lock:
            path.status["output_progress_monotonic"] = now - 10.0
        check(
            not router._active_is_healthy(record=True),
            "stale frame+F0 progress was not detected",
        )
        check(
            "output progress stale" in router._health_failure_detail,
            "health detail still reports frame-only heartbeat wording",
        )
        checks += 2

        # Recovery state must survive short reopen periods and clear only after
        # a sustained healthy run.
        router._unstable_path_count = 3
        router._recovery_failure_count = 2
        router._automatic_power_cycle_blocked = True
        path.started_monotonic = time.monotonic() - (
            bb36.BB36_RECOVERY_STABILITY_SECONDS + 1.0
        )
        path.key_heartbeat_monotonic = time.monotonic()
        with path.status_lock:
            path.status["heartbeat_monotonic"] = time.monotonic()
            path.status["output_progress_monotonic"] = time.monotonic()
        check(
            router._active_is_healthy(record=True),
            "sustained healthy path was not healthy",
        )
        check(
            router._unstable_path_count == 0
            and router._recovery_failure_count == 0
            and not router._automatic_power_cycle_blocked,
            "120-second stable window did not clear recovery circuit",
        )
        checks += 2
    finally:
        bb36._bb36_present = original_present

    # ------------------------------------------------------------------
    # Verified recovery closes the output handle BEFORE waiting on the output
    # worker, allowing a blocked native call to unwind.
    # ------------------------------------------------------------------
    fake_device = FakeCloseDevice()
    recovery_path = bb36.BB36PFDPath(
        lambda: (None, None),
        lambda *args: None,
        "v3",
        {},
        0.12,
        lambda: None,
    )
    recovery_path.device = fake_device
    recovery_path.input_device = fake_device
    recovery_path.input_device_is_shared = True

    def blocked_until_close():
        fake_device.closed.wait(5.0)

    worker = threading.Thread(
        target=blocked_until_close,
        name="BB36-V7-Blocked-Write-Test",
        daemon=True,
    )
    worker.start()
    recovery_path.worker = worker

    clean = recovery_path.stop(recovery=True)
    check(fake_device.close_count >= 1, "recovery did not close stale output handle")
    check(clean, "output worker did not quiesce after stale handle close")
    check(not worker.is_alive(), "old output worker survived verified recovery retire")
    checks += 3

    # If a retired worker is still alive, the router must keep a reference and
    # block a replacement owner.
    stuck_path = bb36.BB36PFDPath(
        lambda: (None, None),
        lambda *args: None,
        "v3",
        {},
        0.12,
        lambda: None,
    )
    stuck_path.retired_output_worker = Alive()
    router = bb36.MuslimSimBB36PathRouter(
        "http://127.0.0.1:8086",
        "v3",
        ".",
        lambda: (None, None),
        lambda *args: None,
        {},
        0.12,
    )
    router._retired_path = stuck_path
    check(
        not router._retired_path_quiesced(wait_seconds=0.0),
        "router lost track of a still-alive retired output worker",
    )
    checks += 1

    # ------------------------------------------------------------------
    # Source-level recovery ordering and bounded retry contract.
    # ------------------------------------------------------------------
    source = (
        ROOT / "muslimsim" / "devices" / "mcdu_bb36_separate_paths.py"
    ).read_text(encoding="utf-8")
    required = (
        "PFD RECOVERY RETIRE: closing stale output handle before joins",
        "BB36_RECOVERY_STABILITY_SECONDS = 120.0",
        "BB36_RECOVERY_SOFT_RESTART_LIMIT = 1",
        "BB36_RECOVERY_CIRCUIT_OPEN_SECONDS = 60.0",
        "RECOVERY SOFT REOPEN",
        "RECOVERY CIRCUIT OPEN",
        "_automatic_power_cycle_blocked",
        "_retired_path_quiesced",
        "resume_display_page",
    )
    for token in required:
        check(token in source, f"V7 recovery contract missing: {token}")
        checks += 1

    # Power-cycle must occur after the active path is retired in the path-failed
    # branch. Compare source positions inside the V7 recovery block.
    subclass_run = source.rindex("    def _run(self) -> None:")
    marker = source.index(
        "# MUSLIMSIM_BB36_RECOVERY_V7",
        subclass_run,
    )
    retire_pos = source.index(
        "self._stop_active_path(\n                    recovery=True",
        marker,
    )
    power_pos = source.index(
        "self._attempt_firmware_power_cycle(",
        retire_pos,
    )
    check(
        retire_pos < power_pos,
        "BB36 still attempts firmware power-cycle before releasing HID owner",
    )
    checks += 1

    # No duplicate owner is permitted while a retired worker is alive.
    loop_start = source.rindex("    def _run(self) -> None:")
    loop_segment = source[loop_start:loop_start + 14000]
    check(
        "Previous BB36 output worker is still retiring;" in loop_segment
        and "replacement owner is blocked" in loop_segment,
        "supervisor does not block replacement owner during old-thread retire",
    )
    checks += 1

    # Existing safety/mapping contracts remain intact.
    check(bb36.BB36_PERIOD_INDEX == 41, "PERIOD index changed")
    check(bb36.BB36_DISPLAY_SLASH_INDEX == 70, "SLASH index changed")
    check(bb36.BB36_EXEC_DASH_LIGHT_CHANNEL == 15, "EXEC light channel changed")
    checks += 3

    print(f"BB36 recovery V7: {checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
