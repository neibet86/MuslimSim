"""Offline checks for smooth TCA Boeing Practice lever travel.

No SDL handle, hardware process, simulator, or network listener is opened.
"""

from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import tempfile
import threading
import time
import types

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui.studio import MuslimSimStudio as Studio  # noqa: E402
from muslimsim.hardware.lab import HardwareLab  # noqa: E402
from muslimsim.hardware.profiles import HardwareProfileStore  # noqa: E402

_bridge_spec = importlib.util.spec_from_file_location(
    "_tca_practice_bridge", PROJECT / "bridge" / "final.py"
)
bridge = importlib.util.module_from_spec(_bridge_spec)
_bridge_spec.loader.exec_module(bridge)


class Flag:
    def __init__(self, value):
        self.value = bool(value)

    def get(self):
        return self.value


class Text:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = str(value)


class MovingCanvas:
    def __init__(self):
        self.moves = []

    def move(self, tag, dx, dy):
        self.moves.append((tag, float(dx), float(dy)))


class Client:
    def __init__(self):
        self.requests = []

    def request(self, command, **fields):
        self.requests.append((command, dict(fields), time.monotonic()))
        return {"ok": True}


def main() -> int:
    checks = 0
    failures = []

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    # 1. Pointer motion changes only the handle group and uses the exact live
    # raw convention. The harness deliberately has no redraw method: any old
    # full-canvas redraw behavior raises immediately.
    harness = types.SimpleNamespace()
    harness.practice_mode = Flag(True)
    harness._selected_device = "tca_boeing"
    harness._selected_visual = None
    harness._tca_axis_tracks = {
        "bank12_axis_4": {
            "top": 100.0,
            "bottom": 500.0,
            "current_y": 500.0,
            "move_tag": "tca-handle:bank12_axis_4",
        }
    }
    harness._tca_practice_axes = {"bank12_axis_4": 1.0}
    harness.faceplate = MovingCanvas()
    harness.footer = Text()
    harness._show_selection = lambda: None
    routed = []
    harness._queue_tca_practice_route = lambda key, value, final: routed.append((key, value, final))
    harness._set_tca_practice_axis = types.MethodType(Studio._set_tca_practice_axis, harness)

    check(harness._set_tca_practice_axis("bank12_axis_4", 300.0), "mid-travel drag was rejected")
    check(harness.faceplate.moves == [("tca-handle:bank12_axis_4", 0.0, -200.0)], "drag did not move only the tagged handle group")
    check(abs(harness._tca_practice_axes["bank12_axis_4"]) < 1e-9, "mid travel did not produce raw 0.0")
    check(routed[-1][0] == "bank12_axis_4" and abs(routed[-1][1]) < 1e-9, "continuous raw value was not posted")

    harness._set_tca_practice_axis("bank12_axis_4", 296.0)
    check(abs(harness.faceplate.moves[-1][2] + 4.0) < 1e-9, "a small pointer move jumped instead of moving four pixels")
    check(abs(harness._tca_practice_axes["bank12_axis_4"] + 0.02) < 1e-9, "small pointer travel was quantized like a switch")
    harness._set_tca_practice_axis("bank12_axis_4", 100.0, final=True)
    check(abs(harness._tca_practice_axes["bank12_axis_4"] + 1.0) < 1e-9, "top stop is not raw -1.0")
    harness._set_tca_practice_axis("bank12_axis_4", 500.0, final=True)
    check(abs(harness._tca_practice_axes["bank12_axis_4"] - 1.0) < 1e-9, "bottom/rest stop is not raw +1.0")

    # 2. The background drain sends the newest value once, marks it Practice
    # only, and does not create one request for every discarded pointer sample.
    sender = types.SimpleNamespace()
    sender._tca_route_lock = threading.Lock()
    sender._tca_route_epoch = 7
    sender._tca_route_worker_running = True
    sender._TCA_AXIS_INTERVAL = 0.015
    sender._tca_route_latest = {
        "bank34_axis_3": (20, -0.73, "change", 7),
    }
    sender._drain_tca_practice_routes = types.MethodType(Studio._drain_tca_practice_routes, sender)
    client = Client()
    result = sender._drain_tca_practice_routes(client, 7)
    check(result["sent"] == 1 and len(client.requests) == 1, "coalesced route did not send exactly one newest sample")
    if client.requests:
        command, fields, _sent_at = client.requests[0]
        check(command == "lab_input", "Practice lever used the wrong control command")
        check(fields.get("practice_only") is True, "Practice lever is not protected by the server-side Test gate")
        check(fields.get("control") == "bank34_axis_3", "selected 3&4 lever lost its catalogue key")
        check(abs(float(fields.get("value")) + 0.73) < 1e-9, "newest 3&4 value was not preserved")

    # 3. The Lab's server-side boundary ignores a delayed Practice packet in
    # Live and accepts the exact same packet in Test. This is independent of
    # any Studio BooleanVar timing.
    sink_calls = []
    store = HardwareProfileStore(Path(tempfile.mkdtemp()) / "profiles.json")
    lab = HardwareLab(store, binding_sink=lambda *args: sink_calls.append(args))
    ignored = lab.practice_input("tca_boeing", "bank12_axis_4", 0.25)
    check(ignored.get("ignored") is True and not sink_calls, "Practice input crossed into Live routing")
    lab.set_mode("test")
    accepted = lab.practice_input("tca_boeing", "bank12_axis_4", 0.25)
    check(not accepted.get("ignored", False), "Test mode rejected a valid Practice lever value")
    check(len(sink_calls) == 1, "Test mode did not exercise the saved/default binding path")

    # 4. Switching the owner's one quadrant to 3&4 must make that bank the
    # authoritative mirror without losing the separate 1&2 namespace.
    bridge._tca_boeing_update_connection(False)
    bridge._tca_boeing_update_connection(
        True,
        bank="3&4",
        product="TCA Quadrant Boeing 3&4",
        instance_id=34,
        axes=(1.0, 1.0, 0.0, -0.4, 0.2, 0.8),
        buttons=(False,) * 17,
    )
    status = bridge._tca_boeing_studio_status()
    mirror = dict(status.get("mirror") or {})
    check(status.get("active_bank") == "3&4", "3&4 enumeration did not become the active bank")
    check(mirror.get("bank34_connected") is True, "3&4 connection is missing from the Studio mirror")
    check(abs(float(mirror.get("bank34_axis_3")) + 0.4) < 1e-9, "3&4 axis value was not kept independent")
    check(mirror.get("bank12_connected") is False, "an absent 1&2 unit was reported connected")
    bridge._tca_boeing_update_connection(False, bank="3&4")

    if failures:
        print("TCA Boeing Practice self-test FAILED:", file=sys.stderr)
        for failure in failures:
            print("  - " + failure, file=sys.stderr)
        return 1

    print(
        "TCA Boeing Practice self-test passed: %d checks. Handle motion is "
        "continuous, routing is coalesced at the live-reader cadence, bank "
        "3&4 keeps its own key, and delayed Practice input cannot enter Live. "
        "No hardware or simulator touched." % checks
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
