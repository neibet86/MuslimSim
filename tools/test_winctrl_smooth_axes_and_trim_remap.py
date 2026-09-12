#!/usr/bin/env python3
"""Owner report: "thrustmaster TCA and the winctrl Minor throttle and Moza ab6
they all choppy i feel like they jump one inch each time they move they have
to move smoothly no shopping nothing at all."

Each of those three faceplates read its axis straight from the last status
poll (about 10Hz) and drew it immediately, so a real, continuous physical
motion looked like discrete hops - once per poll instead of once per frame.
The MOZA yoke had already solved exactly this for roll/scale with
``_pdc_flat_animate`` running at ~60fps via ``self.after(16, ...)``,
decoupled from the poll rate.  ``_axis_ease``/``_axis_ease_request_frame``
generalise that same primitive to a 0..1 (or -1..1) axis fraction for any
device, and are now wired into the WinCtrl throttle's three continuous axes,
the AB6's stick/slider/dial, and the TCA quadrant's three levers (skipped
only while the owner is actively dragging that lever in Practice, so
dragging still feels 1:1).

Same request, second half: "on the winctrl thrust change the pitch angle
trigger to Crank ... make Mode Norm the rudder Trim ... change the IGN/
Strat to be aileron trim." The MODE selector's trim-role map is CRANK=pitch,
NORM=rudder, IGN/START=aileron - a full pitch/roll/yaw set. Pitch does not
get a second, disconnected local number: it reuses "STAB", the value/display
channel a separate, already-proven fix (WINCTRL PITCH TRIM WHEEL V1) already
drives from the real stabilizer-trim rocker, so CRANK's LCD shows the
already-working live pitch readout rather than a new fake one. That rocker
has no real "centre" command for electric trim, so RESET stays a deliberate
no-op for the pitch role, in both Practice and Live.

This test never imports the bridge, opens a HID handle, or touches X-Plane.
The bridge/final.py checks read source only, the same way
test_levelup_737_integration.py does. The Studio checks import
muslimsim.gui.studio and drive its pure-logic methods directly (no Tk
canvas is needed for any of them).
"""

from __future__ import annotations

import ast
import time
import types
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui import studio as studio_module  # noqa: E402

Studio = studio_module.MuslimSimStudio
FINAL_PATH = PROJECT / "bridge" / "final.py"
STUDIO_PATH = PROJECT / "muslimsim" / "gui" / "studio.py"


# --------------------------------------------------------------------------
# Part A: the three faceplates must ease between polls, not snap to them.
# --------------------------------------------------------------------------

class AxisEaseHarness:
    """Just enough Studio to drive ``_axis_ease`` with no Tk canvas at all."""

    def __init__(self, selected_device: str = "winctrl_throttle") -> None:
        self._selected_device = selected_device
        self.after_calls: list = []
        self.draw_calls = 0
        for name in ("_axis_ease", "_axis_ease_request_frame", "_pdc_flat_animate", "_pdc_flat_request_frame"):
            setattr(self, name, types.MethodType(getattr(Studio, name), self))

    def after(self, _ms: int, fn):
        self.after_calls.append(fn)
        return f"after-{len(self.after_calls)}"

    def _draw_faceplate(self) -> None:
        self.draw_calls += 1


def _check_axis_easing() -> int:
    checks = 0

    h = AxisEaseHarness()
    first = h._axis_ease("winctrl_throttle", "left_thrust", 0.20)
    assert abs(first - 0.20) < 1e-9, "the very first read has nothing to ease from and must land exactly on target"
    checks += 1

    jumped = h._axis_ease("winctrl_throttle", "left_thrust", 0.90)
    assert 0.20 < jumped < 0.90, (
        "a single poll-sized jump must ease across frames, not land on the new "
        "value in one redraw - landing in one redraw is the reported choppiness"
    )
    assert h.after_calls, "an in-progress ease must schedule another ~60fps frame"
    pending_after_first_jump = len(h.after_calls)
    checks += 2

    # Debounced: repeated draws before the scheduled frame fires must not
    # pile up more `self.after` calls for the same device/key.
    for _ in range(30):
        h._axis_ease("winctrl_throttle", "left_thrust", 0.90)
    assert len(h.after_calls) == pending_after_first_jump, (
        "one still-pending frame must not be re-requested on every redraw"
    )
    checks += 1

    value = h._axis_ease("winctrl_throttle", "left_thrust", 0.90)
    for _ in range(80):
        value = h._axis_ease("winctrl_throttle", "left_thrust", 0.90)
    assert abs(value - 0.90) < 0.01, "the eased value must eventually converge on the real target"
    checks += 1

    # Independent namespaces: easing one device/key must not perturb another.
    h._axis_ease("moza_ab6", "axis_x", 0.10)
    other = h._axis_ease("moza_ab6", "axis_x", 0.95)
    assert 0.10 < other < 0.95
    same_key_again = h._axis_ease("winctrl_throttle", "left_thrust", 0.90)
    assert abs(same_key_again - 0.90) < 0.01, "an unrelated device/key must not disturb an already-settled axis"
    checks += 1

    # The scheduled frame only redraws while still on the eased device.
    h2 = AxisEaseHarness(selected_device="winctrl_throttle")
    h2._axis_ease("winctrl_throttle", "flap_axis", 0.0)  # seed - nothing to ease from yet
    h2._axis_ease("winctrl_throttle", "flap_axis", 1.0)  # now a real jump to ease
    assert h2.after_calls, "expected a scheduled frame for an in-progress ease"
    callback = h2.after_calls[-1]
    callback()
    assert h2.draw_calls == 1, "the scheduled frame must redraw while its device is still selected"
    h2._selected_device = "moza_a210"
    h2._axis_ease("winctrl_throttle", "flap_axis", 1.0)
    callback2 = h2.after_calls[-1]
    callback2()
    assert h2.draw_calls == 1, "switching device before the frame fires must skip the now-stale redraw"
    checks += 2

    print(f"  [ok] _axis_ease smooths a poll-sized jump across frames instead of snapping to it ({checks} checks)")
    return checks


def _check_axis_easing_wiring() -> int:
    """The three reported-choppy faceplates must actually call _axis_ease."""

    source = STUDIO_PATH.read_text(encoding="utf-8")
    required = (
        'fraction = self._axis_ease("winctrl_throttle", key, self._throttle_axis_fraction(key))',
        'spoiler = self._axis_ease("winctrl_throttle", "speedbrake", self._throttle_axis_fraction("speedbrake"))',
        'flap = self._axis_ease("winctrl_throttle", "flap_axis", self._throttle_axis_fraction("flap_axis"))',
        'stick_x_fraction = self._axis_ease("moza_ab6", "axis_x", float(axes.get("axis_x", .5)))',
        'stick_y_fraction = self._axis_ease("moza_ab6", "axis_y", float(axes.get("axis_y", .5)))',
        'fraction = self._axis_ease("moza_ab6", key, max(0.0, min(1.0, float(axes.get(key, .5)))))',
        'dragging_this_axis = self._selected_device == "tca_boeing" and self._tca_drag_axis == axis_key',
        'raw_value = self._axis_ease("tca_boeing", axis_key, raw_value)',
    )
    for snippet in required:
        assert snippet in source, f"missing choppy-motion fix wiring: {snippet!r}"
    print(f"  [ok] all three faceplates (WinCtrl throttle, AB6, TCA) call _axis_ease ({len(required)} checks)")
    return len(required)


# --------------------------------------------------------------------------
# Part C: the MODE selector's trim-role remap and the LCD announce timer.
# --------------------------------------------------------------------------

class ThrottleTrimHarness:
    """Just enough Studio to drive the trim-role selector, no canvas needed."""

    def __init__(self) -> None:
        self._throttle_trim_selector = "trim_mode_norm"
        self._throttle_trim_mode = "RUDDER"
        self._throttle_trim_values = {"STAB": 4.9, "RUDDER": 0.0, "AILERON": 0.0}
        self._throttle_trim_label_until = 0.0
        self._selected_device = "winctrl_throttle"
        self._device_states: dict = {}
        self.after_calls: list = []
        self._number = Studio._number
        for name in (
            "_set_throttle_trim_selector", "_throttle_trim_request_frame",
            "_apply_throttle_trim_visual", "_throttle_trim_display_value",
        ):
            setattr(self, name, types.MethodType(getattr(Studio, name), self))

    def after(self, _ms: int, fn):
        self.after_calls.append(fn)

    def _draw_faceplate(self) -> None:
        pass


def _check_trim_role_remap() -> int:
    checks = 0

    h = ThrottleTrimHarness()
    before = time.monotonic()
    h._set_throttle_trim_selector("trim_mode_crank")
    assert h._throttle_trim_mode == "STAB", "CRANK must select pitch trim, reusing the proven STAB value"
    assert h._throttle_trim_selector == "trim_mode_crank"
    assert h._throttle_trim_label_until > before, "switching modes must start the ~1s name-announce window"
    assert h.after_calls, "switching modes must schedule the LCD's name-to-number flip"
    checks += 4

    h._set_throttle_trim_selector("trim_mode_norm")
    assert h._throttle_trim_mode == "RUDDER", "NORM must now select rudder trim, not aileron"
    checks += 1

    h._set_throttle_trim_selector("trim_mode_ign_start")
    assert h._throttle_trim_mode == "AILERON", "IGN/START must now select aileron trim, not stay neutral"
    checks += 1

    print(f"  [ok] MODE selector: CRANK=pitch(STAB), NORM=rudder, IGN/START=aileron ({checks} checks)")
    return checks


def _check_reset_and_clamp_behaviour() -> int:
    checks = 0

    stab = ThrottleTrimHarness()
    stab._set_throttle_trim_selector("trim_mode_crank")
    stab._throttle_trim_values["STAB"] = 4.9
    stab._apply_throttle_trim_visual("rudder_trim_reset")
    assert stab._throttle_trim_values["STAB"] == 4.9, (
        "RESET must stay a no-op for pitch (STAB) - there is no real centre "
        "command for electric trim, live or in practice"
    )
    checks += 1

    stab._apply_throttle_trim_visual("rudder_trim_left")
    assert stab._throttle_trim_values["STAB"] == 4.8
    for _ in range(400):
        stab._apply_throttle_trim_visual("rudder_trim_left")
    assert stab._throttle_trim_values["STAB"] == 0.0, "pitch trim must clamp at its real minimum, not go negative"
    for _ in range(400):
        stab._apply_throttle_trim_visual("rudder_trim_right")
    assert stab._throttle_trim_values["STAB"] == 19.9, "pitch trim must clamp at its real maximum (19.9 units)"
    checks += 3

    rud = ThrottleTrimHarness()
    rud._set_throttle_trim_selector("trim_mode_norm")
    rud._apply_throttle_trim_visual("rudder_trim_left")
    assert rud._throttle_trim_values["RUDDER"] == -0.1
    rud._apply_throttle_trim_visual("rudder_trim_reset")
    assert rud._throttle_trim_values["RUDDER"] == 0.0, "RESET must still zero the rudder/aileron roles as before"
    checks += 2

    print(f"  [ok] RESET is a no-op only for pitch; rudder/aileron and pitch's own clamp range are correct ({checks} checks)")
    return checks


def _check_display_channel_readback() -> int:
    h = ThrottleTrimHarness()
    h._device_states = {
        "winctrl_throttle": {"mirror": {"values": {"trim_role": "STAB", "rudder_trim_display": 7.2}}},
    }
    value = h._throttle_trim_display_value("STAB", 4.9)
    assert value == 7.2, (
        "the bridge always reports the one physical window's value under "
        "'rudder_trim_display', even for the STAB/pitch role - there is no "
        "separate mirror key for it"
    )
    print("  [ok] Studio reads the live pitch number back from the one real display channel (1 check)")
    return 1


def _check_selector_caption_labels() -> int:
    source = STUDIO_PATH.read_text(encoding="utf-8")
    nl = chr(92) * 2 + "n"  # the file's literal two-backslash "\\n" line break
    required = (f'"CRANK{nl}PITCH"', f'"NORM{nl}RUD"', f'"IGN/START{nl}AIL"')
    for snippet in required:
        assert snippet in source, f"missing MODE selector caption: {snippet!r}"
    print(f"  [ok] MODE selector captions read CRANK/PITCH, NORM/RUD, IGN-START/AIL ({len(required)} checks)")
    return len(required)


# --------------------------------------------------------------------------
# bridge/final.py: source-only checks, exactly like test_levelup_737_integration.py
# --------------------------------------------------------------------------

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


def _check_bridge_trim_role_wiring() -> int:
    checks = 0
    source = FINAL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(FINAL_PATH))

    buttons = _literal_assignment(tree, "WINCTRL_TRIM_ROLE_BUTTONS")
    assert buttons == {
        7: ("trim_mode_crank", "STAB"),
        8: ("trim_mode_norm", "RUDDER"),
        9: ("trim_mode_ign_start", "AILERON"),
    }, "WinCtrl MODE contact map must be CRANK=pitch(STAB) / NORM=rudder / IGN-START=aileron"
    checks += 1

    self_test_block = _between(
        source,
        "def _run_winctrl_trim_display_self_test",
        'raise AssertionError("WinCtrl MODE trim-role contact map is incorrect")',
    )
    assert '7: ("trim_mode_crank", "STAB")' in self_test_block
    assert '8: ("trim_mode_norm", "RUDDER")' in self_test_block
    assert '9: ("trim_mode_ign_start", "AILERON")' in self_test_block
    checks += 3

    select_role_block = _between(
        source, "def _muslimsim_select_winctrl_trim_role", "def _muslimsim_winctrl_throttle_lab_status",
    )
    assert '"trim_mode_crank": "STAB"' in select_role_block
    assert '"trim_mode_norm": "RUDDER"' in select_role_block
    assert '"trim_mode_ign_start": "AILERON"' in select_role_block
    assert (
        'display_key = "stab_trim_display" if selected == "STAB" else "rudder_trim_display"'
        in select_role_block
    ), "CRANK/STAB must push through the unsigned stabilizer-units channel, not the signed rudder one"
    checks += 4

    live_reset_block = _between(
        source, "if pressed and button_no == 25:", "cmd_id = winctrl_command_ids.get(center_command)",
    )
    assert '"RUDDER": "rudder_center"' in live_reset_block
    assert '"AILERON": "aileron_center"' in live_reset_block
    assert '"STAB":' not in live_reset_block, (
        "there is no real centre command for electric pitch trim, so STAB "
        "must not appear as a dict key in the live RESET dispatch table"
    )
    assert "no reset command for" in live_reset_block
    checks += 4

    assert source.count('if role == "STAB":') == 1, (
        "expected exactly one practice-mode guard making RESET a no-op for the pitch role"
    )
    checks += 1

    print(f"  [ok] bridge/final.py's three trim-role maps and its RESET dispatch agree ({checks} checks)")
    return checks


def main() -> int:
    print("WinCtrl/TCA/AB6 smooth-axis and trim-role remap guard:")
    total = 0
    total += _check_axis_easing()
    total += _check_axis_easing_wiring()
    total += _check_trim_role_remap()
    total += _check_reset_and_clamp_behaviour()
    total += _check_display_channel_readback()
    total += _check_selector_caption_labels()
    total += _check_bridge_trim_role_wiring()
    print(f"WinCtrl/TCA/AB6 smooth-axis and trim-role remap guard passed: {total} checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
