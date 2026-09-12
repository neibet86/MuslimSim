"""Offline proof that a stalled BB35/BB36 display is seen, released and paced.

Three separate defects let one wedged panel stay frozen through a Studio
restart, and they are asserted here so none of them comes back:

  1. BB35 supervision was thread liveness alone.  An output worker parked
     inside a native F0 write to a stalled panel stays alive forever, so the
     router reported a frozen PFP3N as live and never reopened it.
  2. BB35 teardown wrote its darkening reports on the same hidapi handle the
     output worker might still be using, so the panel could be left holding a
     torn native transaction that outlived the handle close.
  3. BB36 retried an impossible USB power cycle every twelve seconds - 2211
     identical failures in one night - and Studio's own status polls wrote the
     supervisor's health verdict from HTTP request threads.

No hardware, simulator or HID handle is opened.
"""

from __future__ import annotations

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from muslimsim.devices import mcdu_bb36_separate_paths as bb36
from muslimsim.devices import pfp_bb35_separate_paths as bb35

CHECKS = 0


def check(condition: bool, description: str) -> None:
    global CHECKS
    if not condition:
        raise AssertionError(description)
    CHECKS += 1


class _FakeThread:
    def __init__(self, alive: bool) -> None:
        self._alive = alive
        self.joins = 0

    def join(self, timeout: float = 0.0) -> None:
        self.joins += 1

    def is_alive(self) -> bool:
        return self._alive


class _FakeDevice:
    def __init__(self) -> None:
        self.writes = []
        self.closed = False

    def write(self, report) -> int:
        self.writes.append(bytes(report))
        return len(report)

    def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# 1. BB35 output-progress watchdog
# ---------------------------------------------------------------------------
def _bb35_path(started_ago: float, heartbeat_ago: float | None):
    path = bb35.BB35PFDPath.__new__(bb35.BB35PFDPath)
    now = time.monotonic()
    path.started_monotonic = now - started_ago
    path.status_lock = __import__("threading").Lock()
    path.status = {}
    if heartbeat_ago is not None:
        path.status["heartbeat_monotonic"] = now - heartbeat_ago
    return path


def test_bb36_stall_threshold() -> None:
    """The threshold must separate a slow frame from a wedged panel.

    Measured on the owner's hardware: genuine wedges publish no heartbeat at
    all after the path starts, so they surface at the 8.0 s startup grace
    (5561 recorded stalls read 8.0/8.1 s).  Live panels having one slow frame
    read 3.0 to 3.6 s (~104 recorded), and every one of those cost a needless
    teardown, reopen and font upload under the old 3.0 s threshold.
    """
    worst_recorded_slow_frame = 3.6
    wedged_panel_reports = 8.0

    check(
        bb36.BB36_PFD_PROGRESS_TIMEOUT_SECONDS > worst_recorded_slow_frame,
        "a recorded slow frame must no longer be treated as a wedged panel",
    )
    check(
        bb36.BB36_PFD_PROGRESS_TIMEOUT_SECONDS < wedged_panel_reports,
        "the threshold must stay below what a wedged panel reports, so a real "
        "wedge is still caught on the first check after the startup grace",
    )
    check(
        bb36.BB36_PFD_PROGRESS_TIMEOUT_SECONDS
        < bb36.BB36_PFD_STARTUP_GRACE_SECONDS,
        "the stall timeout must stay below the startup grace",
    )


def test_bb35_progress_watchdog() -> None:
    progressing = bb35.MuslimSimBB35PathRouter._output_is_progressing

    check(
        bb35.BB35_PFD_PROGRESS_TIMEOUT_SECONDS
        >= bb36.BB36_PFD_PROGRESS_TIMEOUT_SECONDS,
        "BB35's stall timeout must stay at least as generous as BB36's",
    )

    # Inside the startup grace nothing is judged, exactly as BB36 does it.
    check(
        progressing(_bb35_path(1.0, 1.0)),
        "a path still inside its startup grace must never be called stalled",
    )

    # A refreshing panel past the grace is healthy.
    check(
        progressing(
            _bb35_path(bb35.BB35_PFD_STARTUP_GRACE_SECONDS + 5.0, 0.2)
        ),
        "a worker publishing frame heartbeats must stay healthy",
    )

    # A worker parked in a native write is the case is_alive() cannot see.
    check(
        not progressing(
            _bb35_path(
                bb35.BB35_PFD_STARTUP_GRACE_SECONDS + 30.0,
                bb35.BB35_PFD_PROGRESS_TIMEOUT_SECONDS + 5.0,
            )
        ),
        "a stale output heartbeat past the grace must fail the health check",
    )

    # The seed matters: without it a worker that blocks on its very first
    # write leaves the heartbeat at zero, and zero has to keep its historical
    # is_alive()-only meaning rather than being read as a fresh frame.
    check(
        progressing(_bb35_path(60.0, None)),
        "a worker build that publishes no heartbeat keeps its old contract",
    )

    source = Path(bb35.__file__).read_text(encoding="utf-8")
    check(
        'self.status["heartbeat_monotonic"] = _bb35_started' in source,
        "BB35PFDPath.start must seed the heartbeat before the worker starts",
    )


# ---------------------------------------------------------------------------
# 2. BB35 teardown must be the sole writer
# ---------------------------------------------------------------------------
def _bb35_stop_with(worker_alive: bool) -> _FakeDevice:
    path = bb35.BB35PFDPath.__new__(bb35.BB35PFDPath)
    path.stop_evt = __import__("threading").Event()
    path.device = _FakeDevice()
    path.canvas = None
    path.worker = _FakeThread(worker_alive)
    path.keys = _FakeThread(False)
    device = path.device
    path.stop()
    return device


def test_bb35_teardown_sole_writer() -> None:
    # Established case: the worker exited, so the three proven darkening
    # reports are sent exactly as before and the handle is released.
    settled = _bb35_stop_with(worker_alive=False)
    check(
        len(settled.writes) == 3,
        "a settled BB35 teardown must still send its three blackout reports",
    )
    check(
        all(report[6] == 0x49 for report in settled.writes),
        "BB35 blackout reports must remain the captured brightness form",
    )
    check(
        settled.writes[1][8] == 0 and settled.writes[2][8] == 0,
        "BB35 blackout must still drive both brightness channels to zero",
    )
    check(settled.closed, "a settled BB35 teardown must close the handle")

    # Stalled case: the worker may still be inside a native F0 burst, so
    # nothing else may write on that handle.  Closing it is what unblocks the
    # stalled write, so it must still happen.
    stalled = _bb35_stop_with(worker_alive=True)
    check(
        not stalled.writes,
        "a stalled BB35 teardown must not interleave writes with its worker",
    )
    check(stalled.closed, "a stalled BB35 teardown must still close the handle")


# ---------------------------------------------------------------------------
# 3. BB36 read-only health and recovery backoff
# ---------------------------------------------------------------------------
def _bb36_router():
    router = bb36.MuslimSimBB36PathRouter.__new__(bb36.MuslimSimBB36PathRouter)
    router.active = None
    router._health_failure_detail = "untouched"
    router._recovery_failure_count = 0
    router._recovery_failure_detail = ""
    return router


def test_bb36_read_only_health() -> None:
    router = _bb36_router()
    present = bb36._bb36_present
    logged = []
    log = bb36._bb36_live_owner_v3_log
    bb36._bb36_present = lambda: True
    bb36._bb36_live_owner_v3_log = logged.append
    try:
        path = bb36.BB36PFDPath.__new__(bb36.BB36PFDPath)
        now = time.monotonic()
        path.device = _FakeDevice()
        path.worker = _FakeThread(True)
        path.key_reader = _FakeThread(True)
        path.started_monotonic = now - 60.0
        path.key_heartbeat_monotonic = now
        path.status_lock = __import__("threading").Lock()
        path.status = {"heartbeat_monotonic": now - 30.0}
        router.active = path

        # Studio's HTTP status threads observe, they do not record.
        check(
            not router._active_is_healthy(record=False),
            "a stalled BB36 path must read as unhealthy from a status poll",
        )
        check(
            router._health_failure_detail == "untouched",
            "a status poll must not overwrite the supervisor's health reason",
        )
        check(
            not logged,
            "a status poll must not write PFD HEALTH FAILURE log lines",
        )

        # The supervisor's own check still records and logs exactly as before.
        check(
            not router._active_is_healthy(),
            "the supervisor must still see the stalled path",
        )
        check(
            "output heartbeat stale" in router._health_failure_detail,
            "the supervisor must still record why the path failed",
        )
        check(
            any("PFD HEALTH FAILURE" in entry for entry in logged),
            "the supervisor must still log the health failure",
        )

        source = Path(bb36.__file__).read_text(encoding="utf-8")
        check(
            "self._active_is_healthy(record=False)" in source,
            "live_snapshot must use the read-only health check",
        )
    finally:
        bb36._bb36_present = present
        bb36._bb36_live_owner_v3_log = log


def test_bb36_recovery_backoff() -> None:
    router = _bb36_router()

    check(
        router._recovery_backoff_seconds() == 1.50,
        "the first BB36 recovery retry must keep its established 1.50 s wait",
    )

    waits = []
    for _ in range(12):
        router._recovery_failure_count += 1
        waits.append(router._recovery_backoff_seconds())

    check(
        waits[0] == 3.0 and waits[1] == 6.0,
        "consecutive failed recoveries must back off rather than repeat",
    )
    check(
        max(waits) <= bb36.BB36_RECOVERY_BACKOFF_MAX_SECONDS,
        "the backoff must be capped so a wedged BB36 is still retried",
    )
    check(
        waits[-1] == bb36.BB36_RECOVERY_BACKOFF_MAX_SECONDS,
        "a persistently unrecoverable BB36 must settle at the backoff ceiling",
    )

    # Log volume: the first few attempts stay verbatim, then one in twenty.
    router._recovery_failure_count = 0
    loggable = []
    for attempt in range(1, 61):
        if router._recovery_attempt_is_loggable():
            loggable.append(attempt)
        router._recovery_failure_count += 1
    check(
        loggable[:3] == [1, 2, 3],
        "the first three recovery attempts must still be logged verbatim",
    )
    check(
        len(loggable) < 10,
        "a repeating recovery failure must not fill the log with duplicates",
    )

    # A path that recovers clears the backoff, so a later unrelated wedge
    # still gets its fast first retry.
    source = Path(bb36.__file__).read_text(encoding="utf-8")
    check(
        "self._recovery_failure_count = 0" in source,
        "a healthy BB36 path must reset the recovery backoff",
    )


def main() -> None:
    test_bb36_stall_threshold()
    test_bb35_progress_watchdog()
    test_bb35_teardown_sole_writer()
    test_bb36_read_only_health()
    test_bb36_recovery_backoff()
    print(
        f"Display stall recovery self-test passed: {CHECKS} checks. "
        "A stalled BB35 is now seen instead of reported live, no teardown "
        "writes while its worker might still own the handle, and BB36 no "
        "longer retries an impossible recovery every twelve seconds. "
        "No hardware or simulator touched."
    )


if __name__ == "__main__":
    main()
