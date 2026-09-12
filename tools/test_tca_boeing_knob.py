"""Exercise the TCA Boeing knob dispatcher without a simulator or hardware.

The select knob picks a function and the top encoder adjusts it, which makes
the encoder's meaning depend on another control's state.  That is the one part
of the quadrant that cannot be a MappingBinding, so it is real code in
bridge/final.py and needs a real test.

The dispatcher's simulator calls are replaced here with recorders, so this
proves the decisions -- which command, which dataref, which direction, and when
to stay out of the way -- without sending anything anywhere.

Usage:
    python tools/test_tca_boeing_knob.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

# bridge/final.py guards its entry point with __main__ and executes nothing at
# module level beyond its docstring, so importing it is side-effect free.  This
# is the same loader tools/probe_mcdu_ack.py uses.
_spec = importlib.util.spec_from_file_location(
    "_tca_knob_bridge", PROJECT / "bridge" / "final.py"
)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


class FakeStore:
    """Stands in for the profile store's one question: did the owner speak?"""

    def __init__(self, saved=()):
        self.saved = set(saved)

    def has_binding(self, device_key, control_key):
        return control_key in self.saved


class Sim:
    """Records what the dispatcher would have sent."""

    def __init__(self, is_mach=0.0, speed=250.0):
        self.commands = []
        self.writes = []
        self.values = {
            "sim/cockpit/autopilot/airspeed_is_mach": float(is_mach),
            "laminar/B738/autopilot/mcp_speed_dial_kts": float(speed),
            "laminar/B738/autopilot/mcp_speed_dial_kts_mach": float(speed),
        }
        self._ids = {}

    def install(self):
        names = {}

        def resolve_dataref_id(_api, name):
            self._ids.setdefault(name, len(self._ids) + 1)
            names[self._ids[name]] = name
            return self._ids[name]

        def read_dataref(_api, ref_id, timeout=None):
            return self.values[names[ref_id]]

        def set_dataref(_api, ref_id, value):
            self.writes.append((names[ref_id], value))
            self.values[names[ref_id]] = value

        def resolve_command_id(_api, name):
            return name

        def activate_command(_api, command_id, _duration):
            self.commands.append(command_id)

        bridge.resolve_dataref_id = resolve_dataref_id
        bridge.read_dataref = read_dataref
        bridge.set_dataref = set_dataref
        bridge.resolve_command_id = resolve_command_id
        bridge.activate_command = activate_command


def reset_knob():
    with bridge._TCA_BOEING_KNOB_LOCK:
        bridge._TCA_BOEING_KNOB_STATE["function"] = None


def observe(store, index, pressed=True, live=True, api="v3"):
    return bridge._tca_boeing_knob_observe(
        store, api, "1&2", index, pressed, live=live
    )


def main() -> int:
    checks = 0
    failures = []

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    store = FakeStore()

    # 1. Nothing is assumed before the select knob has been seen in a detent.
    reset_knob()
    sim = Sim()
    sim.install()
    observe(store, 15)
    check(
        not sim.commands and not sim.writes,
        "the encoder acted before any select position was known",
    )

    # 2. A select detent is a local state change and never a simulator write.
    reset_knob()
    sim = Sim()
    sim.install()
    handled = observe(store, 12)
    check(handled, "a select detent must be owned by the dispatcher")
    check(
        not sim.commands and not sim.writes,
        "choosing a function wrote to the simulator",
    )
    check(
        bridge._tca_boeing_knob_selected() == "heading",
        "select button 12 did not select HDG/TRK",
    )

    # 3. HDG and ALT step through commands, in the right direction.
    for select, index, expected in (
        (12, 15, "sim/autopilot/heading_up"),
        (12, 14, "sim/autopilot/heading_down"),
        (13, 15, "laminar/B738/autopilot/altitude_up"),
        (13, 14, "laminar/B738/autopilot/altitude_dn"),
    ):
        reset_knob()
        sim = Sim()
        sim.install()
        observe(store, select)
        check(observe(store, index), f"encoder {index} was not handled")
        check(
            sim.commands == [expected],
            f"select {select} + button {index} sent {sim.commands}, expected [{expected}]",
        )

    # 4. Speed is a read-modify-write on the Zibo dial, not a command, and it
    #    must follow the unit the dial is actually showing.
    reset_knob()
    sim = Sim(is_mach=0.0, speed=250.0)
    sim.install()
    observe(store, 11)
    observe(store, 15)
    check(not sim.commands, "the speed detent sent a command instead of writing")
    check(
        sim.writes == [("laminar/B738/autopilot/mcp_speed_dial_kts", 251.0)],
        f"IAS step wrote {sim.writes}, expected 250 -> 251 kt",
    )

    reset_knob()
    sim = Sim(is_mach=0.0, speed=250.0)
    sim.install()
    observe(store, 11)
    observe(store, 14)
    check(
        sim.writes == [("laminar/B738/autopilot/mcp_speed_dial_kts", 249.0)],
        f"IAS down-step wrote {sim.writes}, expected 250 -> 249 kt",
    )

    reset_knob()
    sim = Sim(is_mach=1.0, speed=0.78)
    sim.install()
    observe(store, 11)
    observe(store, 15)
    check(
        sim.writes and sim.writes[0][0] == "laminar/B738/autopilot/mcp_speed_dial_kts_mach",
        f"Mach mode wrote to {sim.writes and sim.writes[0][0]}, expected the Mach dial",
    )
    check(
        sim.writes and abs(sim.writes[0][1] - 0.79) < 1e-9,
        f"Mach step wrote {sim.writes}, expected 0.78 -> 0.79",
    )

    # 5. The knob button engages whatever the selected window is showing.
    for select, expected in (
        (11, "laminar/B738/autopilot/spd_interv"),
        (12, "laminar/B738/autopilot/hdg_sel_press"),
        (13, "laminar/B738/autopilot/alt_interv"),
    ):
        reset_knob()
        sim = Sim()
        sim.install()
        observe(store, select)
        check(observe(store, 16), "the knob button was not handled")
        check(
            sim.commands == [expected],
            f"knob press at select {select} sent {sim.commands}, expected [{expected}]",
        )

    # 6. A release must not repeat the action a press already performed.
    reset_knob()
    sim = Sim()
    sim.install()
    observe(store, 12)
    observe(store, 15, pressed=True)
    before = len(sim.commands)
    observe(store, 15, pressed=False)
    check(
        len(sim.commands) == before,
        "releasing the encoder repeated the command",
    )

    # 7. Baseline phase tracks the detent but must not act.
    reset_knob()
    sim = Sim()
    sim.install()
    observe(store, 13, live=False)
    check(
        bridge._tca_boeing_knob_selected() == "altitude",
        "the detent sampled at connect was not remembered",
    )
    check(not sim.commands, "a baseline sample wrote to the simulator")

    # 8. A saved binding is the owner's decision and outranks the dispatcher.
    reset_knob()
    sim = Sim()
    sim.install()
    owned = FakeStore(saved={"bank12_button_15"})
    observe(owned, 12)
    check(
        not observe(owned, 15),
        "the dispatcher overrode a saved user binding on the encoder",
    )
    check(
        not sim.commands,
        "the dispatcher acted on a control the owner had rebound",
    )

    # 9. Contacts that are not the knob are left entirely alone.
    reset_knob()
    for index in (1, 2, 4, 5, 6, 7, 8, 9, 10):
        check(
            not observe(store, index),
            f"button {index} is not a knob control but the dispatcher claimed it",
        )

    # 10. Without a simulator connection nothing is attempted.
    reset_knob()
    sim = Sim()
    sim.install()
    observe(store, 12)
    check(
        not observe(store, 15, api=None),
        "the encoder acted with no simulator connection",
    )
    check(not sim.commands, "a command was sent with no API version")

    if failures:
        print("TCA Boeing knob dispatcher self-test FAILED:", file=sys.stderr)
        for line in failures:
            print("  - " + line, file=sys.stderr)
        return 1

    print(
        "TCA Boeing knob dispatcher self-test passed: %d checks. Select picks, "
        "encoder adjusts, speed follows the dial's own unit, and a saved "
        "binding still wins. No hardware or simulator touched." % checks
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
