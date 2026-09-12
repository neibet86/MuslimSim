#!/usr/bin/env python3
"""Owner report: "the moza a210 its not moving the aircraft yoke ... it use
to work b4 why i have to assign anything."

Six rounds of live-hardware evidence, in order, before landing on this
design:

1. Writing sim/joystick/yoke_roll_ratio/yoke_pitch_ratio directly, gated by
   a no-jump startup pickup - the yoke never moved the aircraft at all.
2. sim/operation/override/override_joystick armed - the mouse-yoke square
   disappeared (X-Plane now believed something was bound) but the response
   was "chacke very tiny ammount ... not normal".
3. A write-side ease timer (~50Hz) - no change.
4. The ease timer's own tolerance floor lowered - no change.
5. Unconditional writes at ~125Hz, no tolerance gate at all - STILL the
   exact same result: tools/probe_moza_yoke_dataref.py, reading the live
   DataRef straight from X-Plane's own Web API, proved the value was
   snapping to exactly 0.0 between every write regardless of write speed.
6. Research (not another guess) found the actual cause: a documented
   X-Plane plugin-developer report shows Zibo overriding the same DataRef
   even when written on every single flight-loop frame from a native SDK
   plugin - strictly faster than any bridge could manage. Zibo only
   respects X-Plane's own native joystick-axis assignment
   (sim/joystick/joystick_axis_assignments, int[500], one slot per physical
   axis X-Plane has enumerated - the same thing Settings > Joystick writes).

So the bridge now finds which slot is the MOZA A210's roll/pitch itself, by
elimination against sim/joystick/joystick_axis_values (the parallel array of
live raw readings), and writes that slot's assignment once - the same
mechanism a user clicking the assignment in Settings would trigger, which is
the one thing proven to actually work against Zibo. The owner explicitly
asked for a Studio correction UI for when that detection is wrong, since an
algorithm guessing which of ~500 slots is correct is inherently less
reliable than a human looking at what just moved.

This never imports the bridge, opens a HID handle, or touches X-Plane, nor
does it import muslimsim.gui.studio (a full Tk import chain) or start any
control server. Every check reads source only, the same convention as
test_levelup_737_integration.py.

Usage:
    python tools/test_moza_a210_yoke_routing.py
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

FINAL_PATH = PROJECT / "bridge" / "final.py"
SERVER_PATH = PROJECT / "muslimsim" / "control" / "server.py"
STUDIO_PATH = PROJECT / "muslimsim" / "gui" / "studio.py"
SUPERVISOR_PATH = PROJECT / "muslimsim" / "gui" / "supervisor.py"


def _literal_assignment(tree: ast.AST, name: str):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing assignment: {name}")


def _between(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


def _check_constants(source: str, tree: ast.AST) -> int:
    checks = 0

    assign_ref = _literal_assignment(tree, "MOZA_A210_AXIS_ASSIGN_DATAREF")
    assert assign_ref == "sim/joystick/joystick_axis_assignments"
    checks += 1
    values_ref = _literal_assignment(tree, "MOZA_A210_AXIS_VALUES_DATAREF")
    assert values_ref == "sim/joystick/joystick_axis_values"
    checks += 1
    slot_count = _literal_assignment(tree, "MOZA_A210_AXIS_SLOT_COUNT")
    assert slot_count == 500, "must match the documented int[500] array size"
    checks += 1
    function_code = _literal_assignment(tree, "MOZA_A210_AXIS_FUNCTION_CODE")
    assert function_code == {"pitch": 1, "roll": 2}, (
        "must match X-Plane's documented joystick_axis_assignments function enum"
    )
    checks += 1
    ratio_read = _literal_assignment(tree, "MOZA_A210_RATIO_READ_DATAREFS")
    assert ratio_read == {
        "roll": "sim/joystick/yoke_roll_ratio",
        "pitch": "sim/joystick/yoke_pitch_ratio",
    }, "must still read the ratios (read-only) to gate the one-time assignment write on the no-jump pickup check"
    checks += 1

    assert 'parser.add_argument("--moza-yoke", action="store_true",' in source, (
        "must be an explicit opt-in flag, defaulting OFF - the plain write "
        "path is a documented dead end against Zibo at any speed"
    )
    checks += 1
    assert "--no-moza-yoke" not in source, "the old opt-out flag name must not linger anywhere"
    checks += 1
    assert "args.moza_yoke" in source
    checks += 1

    print(f"  [ok] axis-assignment DataRef constants and the opt-in CLI flag are correct ({checks} checks)")
    return checks


def _check_no_leftover_ratio_write_mechanism(source: str) -> int:
    """Every artifact of the five disproven write-side approaches must be
    gone, not just disabled - carrying dead code describing a mechanism that
    is proven not to work would mislead the next reader."""
    checks = 0
    for stale in (
        "MOZA_A210_DATAREFS",
        "MOZA_A210_OVERRIDE_DATAREF",
        "MOZA_A210_VALUE_TOLERANCE",
        "MOZA_A210_EASE_INTERVAL",
        "MOZA_A210_EASE_SPEED",
        "MOZA_A210_EASE_WRITE_TOLERANCE",
        "moza_a210_override_id",
        "_queue_latest_moza_a210_axes",
        '"moza_a210_axes"',
    ):
        assert stale not in source, f"stale artifact of a disproven approach still present: {stale!r}"
        checks += 1
    print(f"  [ok] no leftover artifacts of the five disproven ratio-write approaches ({checks} checks)")
    return checks


def _check_lab_event_reverted_to_visualization_only(source: str) -> int:
    checks = 0
    event_block = _between(
        source,
        "def _muslimsim_moza_a210_lab_event",
        "def _muslimsim_moza_a210_axis_status_snapshot",
    )
    assert "hardware_lab.input(" in event_block
    checks += 1
    assert "event_q" not in event_block, (
        "detection now polls moza_a210_lab_reader.live_snapshot() directly on "
        "its own timer; this callback must stay Studio-visualization-only, "
        "exactly like it was before any of this routing work started"
    )
    checks += 1
    print(f"  [ok] MOZA A210 lab callback reverted to Studio-visualization-only ({checks} checks)")
    return checks


def _check_resolution_block(source: str) -> int:
    checks = 0
    block = _between(
        source,
        'print("Resolving MOZA A210 native joystick-axis assignment...")',
        "# The AGP display is independent",
    )
    assert "MOZA_A210_AXIS_ASSIGN_DATAREF" in block and "MOZA_A210_AXIS_VALUES_DATAREF" in block
    checks += 1
    assert "MOZA_A210_RATIO_READ_DATAREFS" in block
    checks += 1
    assert "except Exception as exc:" in block and "moza_a210_axis_assign_id = None" in block, (
        "a missing/unsupported DataRef must warn and fail open, matching every other optional device"
    )
    checks += 1
    print(f"  [ok] startup resolution block resolves both arrays plus the read-only ratios, fails open ({checks} checks)")
    return checks


def _check_axis_slot_persistence(source: str, tree: ast.AST) -> int:
    """Detection state otherwise lives only in memory: every bridge restart
    would need the yoke moved through its range again before it takes over -
    a real, if smaller, echo of "why do i have to do anything manually" once
    the owner actually has a working setup. A confirmed slot must survive a
    restart on its own."""
    checks = 0

    import importlib.util
    import sys as _sys
    import tempfile

    module_source = _between(
        source,
        "def _load_moza_a210_axis_slots(path: Path)",
        "def _load_starter_retract_pending(path: Path)",
    )
    slot_count = _literal_assignment(tree, "MOZA_A210_AXIS_SLOT_COUNT")
    namespace = {
        "json": __import__("json"),
        "os": __import__("os"),
        "Path": Path,
        "Dict": __import__("typing").Dict,
        "Mapping": __import__("typing").Mapping,
        "MOZA_A210_AXIS_SLOT_COUNT": slot_count,
    }
    exec(compile("from typing import Dict, Mapping\n" + module_source, "<moza_persistence>", "exec"), namespace)
    load_fn = namespace["_load_moza_a210_axis_slots"]
    save_fn = namespace["_save_moza_a210_axis_slots"]

    with tempfile.TemporaryDirectory(prefix="muslimsim-moza-axis-slots-") as folder:
        journal = Path(folder) / "moza_a210_axis_slots.json"
        assert load_fn(journal) == {}, "a missing journal must load as empty, never raise"
        checks += 1
        save_fn(journal, {"roll": 12, "pitch": 340})
        restored = load_fn(journal)
        assert restored == {"roll": 12, "pitch": 340}, "a saved assignment must round-trip exactly"
        checks += 1
        save_fn(journal, {"roll": 99})
        restored = load_fn(journal)
        assert restored == {"roll": 99}, (
            "clearing pitch (omitting it from the saved mapping) must actually "
            "drop it from the journal, not leave a stale slot behind"
        )
        checks += 1
        journal.write_text("not json", encoding="utf-8")
        assert load_fn(journal) == {}, "a corrupt journal must fail open to empty, never crash the bridge"
        checks += 1
        save_fn(journal, {"roll": slot_count + 5})
        assert load_fn(journal) == {}, "an out-of-range slot must not be trusted back in"
        checks += 1

    startup = _between(
        source,
        "moza_a210_axis_slots_path = (",
        "winctrl_trim_left_held = False",
    )
    assert "_load_moza_a210_axis_slots(moza_a210_axis_slots_path)" in startup, (
        "must actually load the journal at startup, not just define the helpers"
    )
    checks += 1
    assert "moza_a210_axis_manual[_axis] = _slot" in startup, (
        "a restored slot must behave exactly like a manual Studio correction - "
        "skip detection, go straight to the pickup-gated one-time write"
    )
    checks += 1

    clear_block = _between(
        source,
        "def _muslimsim_moza_a210_axis_clear",
        "def _muslimsim_moza_a210_axis_command",
    )
    assert "_persist_moza_a210_axis_slots()" in clear_block, (
        "clearing or redetecting an axis must also drop it from the journal, "
        "or a restart would immediately restore the very slot just rejected"
    )
    checks += 1

    print(f"  [ok] MOZA A210 axis-slot journal round-trips, fails open, and is wired into startup/clear ({checks} checks)")
    return checks


def _check_detection_tick(source: str) -> int:
    checks = 0
    tick = _between(
        source,
        "MUSLIMSIM MOZA A210 NATIVE AXIS-ASSIGNMENT V1 >>>",
        "MUSLIMSIM MOZA A210 NATIVE AXIS-ASSIGNMENT V1 <<<",
    )
    assert "args.moza_yoke" in tick
    checks += 1
    assert "moza_a210_lab_reader.live_snapshot()" in tick, (
        "must poll the HID reader directly on its own timer, not react to a queued event"
    )
    checks += 1
    assert (
        "MOZA_A210_AXIS_VALUES_DATAREF" not in tick
        and "moza_a210_axis_values_id}/value" in tick
    ), (
        "must read the live joystick_axis_values array via its resolved id "
        "(moza_a210_axis_values_id), not re-resolve the name by string every tick"
    )
    checks += 1
    assert "MOZA_A210_DETECT_MIN_OUR_DELTA" in tick, "must require a meaningful movement on our own axis before treating it as a signal"
    checks += 1
    assert "MOZA_A210_DETECT_XPLANE_EPSILON" in tick, "must use a scale-agnostic 'changed at all' epsilon on X-Plane's side, since its raw units were never confirmed"
    checks += 1
    assert "if our_moved and not slot_moved:" in tick, (
        "elimination must be one-directional: only eliminate a slot that stayed "
        "completely flat while our own axis moved substantially. Requiring the "
        "reverse too (eliminate a slot that moved while we read 'not moving') was "
        "the bug live testing found - a real slot's own tiny continuous creep "
        "during a slow moment of a genuine sweep can cross the near-zero X-Plane "
        "epsilon on its own even while the coarser 2% our-axis threshold reads "
        "'still', wrongly eliminating the correct slot. A slow pitch sweep lost "
        "every candidate this way while a faster roll sweep never hit it."
    )
    checks += 1
    assert "our_moved == slot_moved" not in tick, (
        "must not still contain the two-directional match that caused the "
        "false-elimination bug"
    )
    checks += 1
    assert "moza_a210_axis_seen_moving" in tick and "survivors & moza_a210_axis_seen_moving[axis]" in tick, (
        "a slot must be accepted only once genuinely seen moving - surviving purely "
        "by inaction (both sides always still) must never count as detection"
    )
    checks += 1
    assert "_winctrl_axis_pickup_reached(" in tick, (
        "the one-time assignment write must reuse the proven no-jump primitive, "
        "since the moment assignment lands X-Plane starts reading real hardware "
        "and could snap a live aircraft to wherever the yoke rests"
    )
    checks += 1
    assert "set_dataref_index(" in tick and "moza_a210_axis_assign_id" in tick, (
        "the actual write must be the per-index array write, not a whole-array replace"
    )
    checks += 1
    assert "MOZA_A210_AXIS_FUNCTION_CODE[axis]" in tick
    checks += 1
    assert 'if moza_a210_axis_status[axis] == "assigned":' in tick, (
        "an already-assigned axis must not be re-written every tick forever"
    )
    checks += 1
    assert 'moza_a210_axis_status[axis] = "assigned"' in tick, (
        "a successful write must actually record 'assigned', or the guard "
        "above can never stop the tick from re-writing it forever"
    )
    checks += 1
    assert "_persist_moza_a210_axis_slots()" in tick, (
        "a fresh assignment must be persisted, or every bridge restart "
        "requires moving the yoke through its range all over again - the "
        "exact 'why do i have to do anything manually' complaint this "
        "whole feature exists to remove"
    )
    checks += 1
    assert "moza_a210_redetect_requested" in tick, "must support Studio asking it to restart detection"
    checks += 1

    print(f"  [ok] detection tick eliminates only genuinely-flat candidates and gates the one-time write on pickup ({checks} checks)")
    return checks


def _check_studio_correction_command(source: str) -> int:
    checks = 0
    handler = _between(
        source,
        "def _muslimsim_moza_a210_axis_command",
        "try:\n            moza_a210_lab_reader = MuslimSimMozaA210(",
    )
    for action in ('"manual"', '"clear"', '"redetect"'):
        assert action in handler, f"missing action branch: {action}"
        checks += 1
    assert 'axis not in ("roll", "pitch")' in handler, "must reject an unknown axis rather than silently doing nothing"
    checks += 1
    assert "0 <= slot < MOZA_A210_AXIS_SLOT_COUNT" in handler, "must reject an out-of-range manual slot"
    checks += 1
    assert "set_dataref_index(api_version, moza_a210_axis_assign_id, slot, 0)" in source, (
        "clearing a correction must actually undo the X-Plane assignment "
        "(write function code 0 / None back to the old slot), not just forget it locally"
    )
    checks += 1
    assert "command=_muslimsim_moza_a210_axis_command," in source, (
        "must be wired through DeviceRegistration.command (the new, unvalidated "
        "passthrough), not output= (rejected by the fixed control catalog) or "
        "calibration= (MOZA's calibration path is a hardcoded FFB/spring schema "
        "in muslimsim/hardware/profiles.py that would reject this payload)"
    )
    checks += 1
    assert '"axis_assignment": _muslimsim_moza_a210_axis_status_snapshot()' in source, (
        "Studio's dialog needs live status - must be published through the "
        "existing moza_a210 status poll, not a separate channel"
    )
    checks += 1

    print(f"  [ok] Studio correction command handles manual/clear/redetect and publishes live status ({checks} checks)")
    return checks


def _check_server_command_verb(source: str) -> int:
    checks = 0
    tree = ast.parse(source, filename=str(SERVER_PATH))
    found_field = any(
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "command"
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "DeviceRegistration"
        for node in ast.walk(node)
    )
    assert found_field, "DeviceRegistration must declare a 'command' field"
    checks += 1

    dispatch = _between(source, 'if command == "device_command":', 'if command == "lab_mode":')
    assert "entry.command is None" in dispatch, "must reject a device with no registered command handler rather than crashing"
    checks += 1
    assert 'request.get("action", "")' in dispatch and 'request.get("payload")' in dispatch
    checks += 1
    assert "entry.command(action, payload)" in dispatch, (
        "must call straight through with no HardwareLab catalog/calibration "
        "validation - that validation is exactly what made lab_output and "
        "calibration_set unusable for this free-form correction payload"
    )
    checks += 1

    print(f"  [ok] muslimsim/control/server.py exposes a validation-free device_command RPC verb ({checks} checks)")
    return checks


def _check_studio_dialog(source: str) -> int:
    checks = 0
    assert "def _open_moza_axis_assignment_dialog" in source
    checks += 1
    assert "def _moza_axis_command" in source
    checks += 1
    dialog = _between(
        source,
        "def _open_moza_axis_assignment_dialog",
        "    # ----- status / profiles",
    )
    for label in ('"Set"', '"Clear"', '"Redetect"'):
        assert label in dialog, f"missing correction button: {label}"
        checks += 1
    assert 'state.get("axis_assignment", {})' in dialog, (
        "must read the live status straight off the top-level moza_a210 "
        "device-state dict (where wrap_status places it), not nested under mirror"
    )
    checks += 1
    assert "dialog.after(500, refresh)" in dialog, "the dialog must be genuinely live, not a one-shot snapshot - the owner explicitly asked for live feedback"
    checks += 1
    assert '"device_command"' in source and 'device="moza_a210"' in source
    checks += 1

    faceplate = _between(
        source,
        "def _draw_moza_a210_yoke_layout",
        "def _draw_moza_max3_layout",
    )
    assert "_open_moza_axis_assignment_dialog" in faceplate, (
        "the correction dialog must be reachable directly from the yoke faceplate, "
        "not only findable by reading source"
    )
    checks += 1

    print(f"  [ok] Studio's axis-assignment dialog is reachable, live-refreshing, and has all three correction actions ({checks} checks)")
    return checks


def _check_supervisor_passes_the_flag(source: str) -> int:
    """--moza-yoke defaults off in the bridge's own argparse (it is a no-op
    without a MOZA A210 present), but Studio launching the bridge without it
    would silently make the whole feature inert for normal use - exactly
    the "why do i have to do anything manually" complaint this was built to
    remove. Caught live: "i see the mouse square" after the rebuild, because
    Studio's own launch command never knew this flag existed."""
    checks = 0
    xplane_block = _between(
        source,
        "if self._simulator == SIMULATOR_XPLANE:",
        "creation_flags = (",
    )
    assert '"--moza-yoke"' in xplane_block, (
        "Studio must pass --moza-yoke itself when launching the bridge for "
        "X-Plane, or the entire native axis-assignment feature never runs "
        "outside a manual command-line test"
    )
    checks += 1
    print(f"  [ok] Studio's own bridge launch passes --moza-yoke ({checks} checks)")
    return checks


def main() -> int:
    print("MOZA A210 native joystick-axis assignment guard:")
    source = FINAL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(FINAL_PATH))
    server_source = SERVER_PATH.read_text(encoding="utf-8")
    studio_source = STUDIO_PATH.read_text(encoding="utf-8")
    supervisor_source = SUPERVISOR_PATH.read_text(encoding="utf-8")

    total = 0
    total += _check_constants(source, tree)
    total += _check_no_leftover_ratio_write_mechanism(source)
    total += _check_lab_event_reverted_to_visualization_only(source)
    total += _check_resolution_block(source)
    total += _check_axis_slot_persistence(source, tree)
    total += _check_detection_tick(source)
    total += _check_studio_correction_command(source)
    total += _check_server_command_verb(server_source)
    total += _check_studio_dialog(studio_source)
    total += _check_supervisor_passes_the_flag(supervisor_source)

    print(f"MOZA A210 native joystick-axis assignment guard passed: {total} checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
