"""BUG-39: real BB35 HID edges must reach ToLiss MCDU1, without BB36 hardware."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from muslimsim.devices import mcdu_bb36_toliss_paths as paths
from muslimsim.devices.pfp_bb35_separate_paths import PFP3_KEYS


class Feed:
    def start(self):
        pass


def bb35(**kwargs):
    return paths.TolissBB35DisplayPath(
        open_pfd=lambda: (None, None), draw_worker=lambda *args: None,
        blackout=lambda *args: None, feed=Feed(), refresh_interval=0.1,
        api_root="http://127.0.0.1:8086", api_version="v2", **kwargs,
    )


def report(bits):
    return b"\x01" + bits.to_bytes(12, "little")


def read_reports(router, reports):
    pending = iter(reports)

    def read(_size):
        try:
            return next(pending)
        except StopIteration:
            router.stop_evt.set()
            return []

    router.device = SimpleNamespace(read=read)
    router._reader()
    router.stop_evt.clear()


class Timeout(Exception):
    pass


def dispatch(router, key_map, *, missing=()):
    """Run the production command loop with no network or hardware access."""
    requests = []
    now = [10.0]
    receives = [0]
    actions = sorted({action for _label, action in key_map.values() if action})
    ids = {action: index + 100 for index, action in enumerate(actions)}
    reverse_ids = {value: key for key, value in ids.items()}

    def resolve(_root, _version, action):
        if action in missing:
            raise LookupError(action)
        return ids[action]

    def recv():
        receives[0] += 1
        now[0] += 1.0  # expire partial gestures without wall-clock sleeps
        if receives[0] >= 4:
            router.stop_evt.set()
        raise Timeout()

    socket = SimpleNamespace(
        send=lambda payload: requests.append(json.loads(payload)),
        recv=recv, settimeout=lambda _seconds: None, close=lambda: None,
    )
    sockets = SimpleNamespace(
        create_connection=lambda *args, **kwargs: socket,
        WebSocketTimeoutException=Timeout,
    )
    with patch.object(paths, "websocket", sockets), patch.object(
        paths, "_resolve_command_id", side_effect=resolve,
    ) as resolver, patch("time.monotonic", side_effect=lambda: now[0]):
        router._key_command_worker()
    router.stop_evt.clear()
    for request in requests:
        assert request["type"] == "command_set_is_active"
        assert len(request["params"]["commands"]) == 1
    phases = [request["params"]["commands"][0] for request in requests]
    return [
        (reverse_ids[phase["id"]].removeprefix("AirbusFBW/MCDU1"), phase["is_active"])
        for phase in phases
    ], resolver.call_count


def tap_reports(indices):
    result = [report(0)]
    for index in indices:
        result.extend((report(1 << index), report(1 << index), report(0)))
    return result


def main():
    key_map = paths.TOLISS_BB35_KEY_MAP
    assert set(key_map) == set(PFP3_KEYS) == set(range(71))
    expected = (
        [f"LSK{i}{side}" for side in ("L", "R") for i in range(1, 7)]
        + ["Init", "Fpln", "Perf", "FuelPred", "Prog", "KeyDim", "KeyBright",
           "Menu", "Fpln", "Airport", "SecFpln", "Prog", "DirTo", "Data",
           "RadNav", "SlewLeft", "SlewRight"]
        + [f"Key{i}" for i in range(1, 10)]
        + ["KeyDecimal", "Key0", "KeyPM"]
        + [f"Key{letter}" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
        + ["KeySpace", "KeyOverfly", "KeySlash", "KeyClear"]
    )
    assert [key_map[i][1] for i in range(71)] == [
        "AirbusFBW/MCDU1" + suffix for suffix in expected
    ]
    catalogue = json.loads(
        (PROJECT / "muslimsim/hardware/xplane_command_catalog.json").read_text(encoding="utf-8")
    )
    known = {item["target"] for item in catalogue["functions"] if item.get("aircraft") == "toliss"}
    assert {action for _label, action in key_map.values()} <= known

    observed = []
    router = bb35(input_sink=lambda index, edge: observed.append((index, edge)))
    # An already-held A is a startup baseline. Its first release must also
    # be silent. F0 ACKs, short reports and unknown bit 95 are not MCDU keys.
    baseline = [b"\xf0" + bytes(12), b"\x01", report(1 << 41), report(0),
                report(1 << 95), report(0)]
    read_reports(router, baseline + tap_reports(range(71)))
    actual, resolved = dispatch(router, key_map)
    assert actual == [(suffix, active) for suffix in expected for active in (True, False)]
    assert resolved == len({action for _label, action in key_map.values()})
    assert len(observed) == 143  # 142 deliberate edges plus baseline-key release
    assert router.get_display_page() == "cdu"

    # A lone punctuation key is delivered on timeout; shortcuts consume only
    # their own taps and alter this panel's display, not the other panel's.
    for taps, page, phases in (
        ([69], "cdu", [("KeySlash", True), ("KeySlash", False)]),
        ([38], "cdu", [("KeyDecimal", True), ("KeyDecimal", False)]),
        ([38, 38], "cdu", [("KeyDecimal", v) for v in (True, False, True, False)]),
        ([69, 69], "pfd", []),
        ([38, 38, 38], "pfd", []),
        ([69, 41], "cdu", [("KeySlash", True), ("KeySlash", False),
                             ("KeyA", True), ("KeyA", False)]),
    ):
        router = bb35()
        read_reports(router, tap_reports(taps))
        actual, _ = dispatch(router, key_map)
        assert actual == phases, (taps, actual)
        assert router.get_display_page() == page

    router = bb35()
    router.request_page("fctl")
    read_reports(router, tap_reports([12, 70]))
    actual, _ = dispatch(router, key_map)
    assert actual == [(name, v) for name in ("Init", "KeyClear") for v in (True, False)]
    assert router.get_display_page() == "fctl"  # keypad remains live on ECAM

    # Shutdown releases a command still held by this keypad, and unavailable
    # ToLiss command IDs appear in status rather than another silent failure.
    router = bb35()
    read_reports(router, [report(0), report(1 << 70)])
    actual, _ = dispatch(router, key_map)
    assert actual == [("KeyClear", True), ("KeyClear", False)]
    router = bb35()
    read_reports(router, tap_reports([12]))
    actual, _ = dispatch(router, key_map, missing={"AirbusFBW/MCDU1Init"})
    assert not actual
    assert "MCDU1Init" in router.service_snapshot()["keypad_error"]

    # Existing BB36 callers retain their original defaults and exact commands.
    other = paths.TolissBB36MirrorPath(
        open_pfd=lambda: (None, None), draw_worker=lambda *args: None,
        content_drawer=lambda *args: None, api_root="http://127.0.0.1:8086",
        api_version="v2", refresh_interval=0.1, feed=Feed(),
    )
    for index in (0, 15, 32, 44, 69, 73):
        other.key_queue.put(("press", index))
        other.key_queue.put(("release", index))
    actual, _ = dispatch(other, paths.TOLISS_MCDU_KEY_MAP)
    assert actual == [(name, v) for name in ("LSK1L", "Init", "Key1", "KeyA", "KeyZ", "KeyClear")
                      for v in (True, False)]
    assert other.get_display_page() == "cdu"

    # Start and stop the actual BB35 lifecycle with one fake HID handle and
    # no BB36 present. This proves the command worker is wired into start(),
    # not only callable by this test, and stale pre-restart keys are discarded.
    delivered = threading.Event()
    pending = iter(tap_reports([12]))
    lifecycle_packets = []
    blackouts = []
    closed = []
    router = bb35()
    fake_device = SimpleNamespace(
        read=lambda _size: next(pending, []),
        close=lambda: closed.append(True),
    )
    router.open_pfd = lambda: (fake_device, object())
    router.blackout = lambda *_args: blackouts.append(True)
    router.key_queue.put(("press", 66))  # previous-session Z must be discarded

    def send(payload):
        lifecycle_packets.append(json.loads(payload))
        if len(lifecycle_packets) >= 2:
            delivered.set()

    def recv():
        router.stop_evt.wait(0.001)
        raise Timeout()

    socket = SimpleNamespace(send=send, recv=recv, settimeout=lambda _: None, close=lambda: None)
    with patch.object(paths, "websocket", SimpleNamespace(
        create_connection=lambda *a, **kw: socket, WebSocketTimeoutException=Timeout,
    )), patch.object(paths, "_resolve_command_id", return_value=123), patch.object(
        paths, "_open_bb36", side_effect=AssertionError("BB35 must not open BB36"),
    ):
        try:
            router.start()
            assert delivered.wait(3.0), "BB35 start did not wire its keypad command worker"
        finally:
            router.stop()
    assert len(lifecycle_packets) == 2
    assert [item["params"]["commands"][0]["is_active"] for item in lifecycle_packets] == [True, False]
    assert closed == blackouts == [True]
    assert router.reader_thread is router.key_command_thread is router.output_thread is None

    print(f"BUG-39 BB35 keypad passed: 71 keys, 142 exact command phases, "
          f"{resolved} command IDs resolved once; baseline/hold/gestures/ECAM/"
          "shutdown/error status and BB36 defaults verified. No hardware or simulator opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
