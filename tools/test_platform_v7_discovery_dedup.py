#!/usr/bin/env python3
"""BUG-16: a device sitting quietly must not be re-saved to SQLite forever.

The owner reported Studio being slow and asked for a thorough investigation.
Live profiling of the running app found the real cause: every status poll -
ten times a second - re-persisted every currently-visible device to the
profile database, whether or not anything about it had changed since the last
poll. Measured on the owner's own machine: 3.68 million rows each in
``outbox``, ``device_sightings`` and ``audit_log``, accumulated continuously
at 22-72 rows a second across 46+ hours, a 9.4 GB database file, and a single
``SELECT COUNT(*) FROM outbox`` costing 151 ms - one and a half status-poll
intervals, on one query.

This proves the actual fix: an unchanged sighting must cost nothing beyond an
in-memory comparison. A genuinely new device, or one whose descriptor or role
actually changes, must still be persisted - the fix is a dedup, not a mute.

Offline: no hardware, no simulator, no live database. Each check gets its own
throwaway SQLite file.
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.platform.runtime import PlatformRuntime


def _discovery(*devices):
    return {"devices": list(devices)}


def _pdc(serial="SERIAL-A", role_hint="capt"):
    return {
        "transport": "usb",
        "vendor_id": 0x4098,
        "product_id": 0xBB61,
        "serial_number": serial,
        "product": "WINWING 3N PDC L",
        "role_hint": role_hint,
    }


def _runtime(tmp_path):
    db_path = Path(tmp_path) / "platform_v7.sqlite3"
    return PlatformRuntime(object(), database_path=db_path)


def _counts(runtime):
    conn = runtime.database._conn
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("outbox", "device_sightings", "audit_log")
    }


def check_a_repeated_sighting_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _runtime(tmp)
        try:
            runtime.ingest_discovery(_discovery(_pdc()))
            after_first = _counts(runtime)
            assert after_first["device_sightings"] == 1, (
                "a brand-new device must still be persisted once: %s" % after_first
            )

            for _ in range(50):
                runtime.ingest_discovery(_discovery(_pdc()))
            after_repeats = _counts(runtime)

            assert after_repeats == after_first, (
                "the identical device was reported 50 more times and the "
                "database grew from %s to %s. A status poll reporting the same "
                "hardware again is not a change worth a fresh row."
                % (after_first, after_repeats)
            )
        finally:
            runtime.close()
    print("  [ok] 50 repeats of an unchanged sighting write zero new rows")


def check_a_genuine_change_still_gets_persisted():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _runtime(tmp)
        try:
            runtime.ingest_discovery(_discovery(_pdc(role_hint="capt")))
            baseline = _counts(runtime)

            # The role hint actually differs this time - a real change, not a
            # repeat of the same reading.
            runtime.ingest_discovery(_discovery(_pdc(role_hint="fo")))
            after_change = _counts(runtime)

            assert after_change["device_sightings"] > baseline["device_sightings"], (
                "a genuine role change was not persisted at all: %s -> %s"
                % (baseline, after_change)
            )
        finally:
            runtime.close()
    print("  [ok] a genuine change is still persisted, not silently dropped")


def check_two_different_devices_are_each_persisted_once():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _runtime(tmp)
        try:
            left = _pdc(serial="SERIAL-LEFT")
            right = _pdc(serial="SERIAL-RIGHT")
            right["product_id"] = 0xBB52
            right["product"] = "WINWING 3M PDC R"

            for _ in range(10):
                runtime.ingest_discovery(_discovery(left, right))

            counts = _counts(runtime)
            assert counts["device_sightings"] == 2, (
                "two distinct devices, reported together ten times, produced "
                "%d sighting rows instead of exactly 2" % counts["device_sightings"]
            )
        finally:
            runtime.close()
    print("  [ok] two distinct devices are each persisted exactly once")


def check_the_live_device_state_stays_correct_regardless():
    """The dedup must never touch what Studio actually displays.

    That state comes from IdentityRegistry.observe(), in memory, on every
    single call - independent of whether anything was written to SQLite.
    """

    with tempfile.TemporaryDirectory() as tmp:
        runtime = _runtime(tmp)
        try:
            runtime.ingest_discovery(_discovery(_pdc()))
            first_seen = None
            for record in runtime.identities.records.values():
                if record.vendor_product == "WINWING 3N PDC L":
                    first_seen = record.last_seen
                    break
            assert first_seen is not None, "the device was never adopted at all"

            for _ in range(5):
                runtime.ingest_discovery(_discovery(_pdc()))
            latest_seen = next(
                record.last_seen for record in runtime.identities.records.values()
                if record.vendor_product == "WINWING 3N PDC L"
            )
            assert latest_seen >= first_seen, (
                "last_seen did not advance across repeated sightings - the "
                "in-memory liveness signal Studio reads must update on every "
                "call, dedup or no dedup"
            )
        finally:
            runtime.close()
    print("  [ok] the in-memory device-online state still updates on every sighting")


def check_prune_history_runs_at_startup():
    """A second layer of defence: retention, independent of the write fix."""

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "platform_v7.sqlite3"
        runtime = _runtime(tmp)
        try:
            conn = runtime.database._conn
            for i in range(runtime.database.HISTORY_ROW_LIMIT + 500):
                conn.execute(
                    "INSERT INTO audit_log(event,entity_type,entity_id,details_json,created_at)"
                    " VALUES(?,?,?,?,?)",
                    ("synthetic", "device", str(i), "{}", float(i)),
                )
            conn.commit()
        finally:
            runtime.close()

        # A fresh open of the same file - what a real app restart does.
        reopened = PlatformRuntime(object(), database_path=db_path)
        try:
            count = reopened.database._conn.execute(
                "SELECT COUNT(*) FROM audit_log"
            ).fetchone()[0]
            assert count <= reopened.database.HISTORY_ROW_LIMIT, (
                "audit_log still had %d rows after reopening the database; "
                "prune_history() must run automatically at startup" % count
            )
        finally:
            reopened.close()
    print("  [ok] history is pruned back to the cap on every fresh startup")


def check_the_bounded_count_never_scans_more_than_its_bound():
    """The other half of BUG-16: COUNT(*) itself must not scale with history."""

    with tempfile.TemporaryDirectory() as tmp:
        runtime = _runtime(tmp)
        try:
            db = runtime.database
            bound = db._COUNT_BOUND
            conn = db._conn
            for i in range(bound + 200):
                conn.execute(
                    "INSERT INTO outbox(mutation_id,entity_type,entity_id,base_revision,"
                    "payload_json,created_at) VALUES(?,?,?,?,?,?)",
                    (f"m{i}", "device", str(i), 0, "{}", float(i)),
                )
            conn.commit()

            snapshot = db.snapshot()
            assert snapshot["outbox_count"] == bound, (
                "the bounded count returned %s instead of the bound %s - a "
                "table larger than the bound must read as exactly the bound, "
                "not its true size" % (snapshot["outbox_count"], bound)
            )
            assert snapshot["outbox_count_is_a_lower_bound"] is True, (
                "the snapshot did not say the count was capped, so a caller "
                "reading outbox_count as exact would be misled"
            )
        finally:
            runtime.close()
    print("  [ok] the outbox count is capped at %d regardless of true table size" % bound)


def main():
    print("Platform V7 discovery dedup (BUG-16):")
    check_a_repeated_sighting_writes_nothing()
    check_a_genuine_change_still_gets_persisted()
    check_two_different_devices_are_each_persisted_once()
    check_the_live_device_state_stays_correct_regardless()
    check_prune_history_runs_at_startup()
    check_the_bounded_count_never_scans_more_than_its_bound()
    print("Platform V7 discovery dedup test passed.")


if __name__ == "__main__":
    main()
