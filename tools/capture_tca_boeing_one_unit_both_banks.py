"""Capture which physical TCA Boeing lever is which SDL axis, once, on the rig.

The Studio already draws the Thrustmaster TCA Boeing quadrant and animates it,
but every one of its controls is declared `status="unknown"` in
`muslimsim/hardware/catalog.py`, and `_input()` sets
`remappable = (status == "implemented")`.  So none of them can be bound to a
simulator function, and the quadrant sends nothing to X-Plane.  The catalogue
refuses to invent the map -- "the lab must never turn a product name into a
made-up HID map" -- so the identities have to come from the hardware itself.

That is what this does.  It asks for one control at a time, watches every axis
and button, and records whichever one actually moved.  Nothing is guessed.

One physical quadrant carries two enumeration-time USB identities:

    selector 1&2 -> "TCA Quadrant Boeing 1&2" -> VID 044F / PID 040A
    selector 3&4 -> "TCA Quadrant Boeing 3&4" -> VID 044F / PID 040B

Moving the selector emits no live event, so the bank is fixed at connect time.
Capture the bank you are plugged in as, then move the selector, replug the USB,
and run this again for the other bank.  Both files are merged by key.

It only reads.  It writes nothing to the aircraft and sends no USB output.

MuslimSim Studio, launch.py, and bridge/final.py must be CLOSED: the project
rule is that no second SDL reader may compete with the live controller reader.
This refuses to start while one is running.

Usage:
    python tools/capture_tca_boeing_one_unit_both_banks.py --list
    python tools/capture_tca_boeing_one_unit_both_banks.py --survey
    python tools/capture_tca_boeing_one_unit_both_banks.py
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

# Movement on an axis has to clear this much of full travel to count as "the
# user moved that one", so a resting lever's jitter never wins a prompt.
AXIS_MOVE_THRESHOLD = 0.25
# A lever that only creeps this far is reported as a warning, not a capture.
AXIS_NOISE_FLOOR = 0.02
PROMPT_TIMEOUT = 25.0
SETTLE_SECONDS = 0.6

# The controls named the way the owner describes the unit.  A prompt captures
# whatever physically moves -- axis, button, or hat -- so nothing here presumes
# that a given control is analogue.
# Established by the 2026-08-31 capture of this unit, twice, on bank 1&2:
# the three phantom axes (0, 1, 2) never leave their rest value, and the three
# levers sit on 3, 4, 5 left to right.  Prompts name the lever, never the index.
AXIS_LABELS = {
    3: "LEFT slide lever  (nearest the Captain)",
    4: "MIDDLE slide lever",
    5: "RIGHT slide lever (nearest the First Officer)",
}

# The owner's own inventory of the unit: three slides, a button on two of them,
# a reverse lever on two of them, two knobs with a button, and five side
# buttons.  Each is provoked on its own so no contact has to be guessed at.
BUTTON_PROMPTS = (
    ("reverse_lever_a", "Pull the REVERSE lever on one of the slides, fully."),
    ("reverse_lever_b", "Pull the REVERSE lever on the OTHER slide, fully."),
    ("slide_button_a", "Press the BUTTON on one of the slides."),
    ("slide_button_b", "Press the BUTTON on the OTHER slide."),
    ("knob_button", "Press the BUTTON on the knobs."),
    ("side_button_1", "Press SIDE button 1 (start at one end)."),
    ("side_button_2", "Press SIDE button 2."),
    ("side_button_3", "Press SIDE button 3."),
    ("side_button_4", "Press SIDE button 4."),
    ("side_button_5", "Press SIDE button 5 (the last one)."),
)

CONTROL_PROMPTS = (
    ("left_slide", "the LEFT slide lever (nearest the Captain) -- full travel, end to end"),
    ("middle_slide", "the MIDDLE slide lever -- full travel, end to end"),
    ("right_slide", "the RIGHT slide lever (nearest the First Officer) -- full travel, end to end"),
    ("reverser_lever", "the REVERSE lever in the middle -- lift/pull it fully, then release"),
    ("select_knob", "the SELECT knob (the detented one) -- turn it two positions"),
    ("encoder_knob", "the TOP knob (the one that spins forever) -- several steps either way"),
)


def running_muslimsim(root: Path):
    """Return the MuslimSim processes that would fight us for the controller."""

    if os.name != "nt":
        return []
    r = str(root).replace("'", "''")
    ps = (
        "$r='" + r + "'; Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match '^(python|pythonw|py|pyw)([0-9.]*)\\.exe$' -and $_.CommandLine -and ("
        "$_.CommandLine -like ('*'+$r+'*MuslimSim Studio.pyw*') -or "
        "$_.CommandLine -like ('*'+$r+'*launch.py*') -or "
        "$_.CommandLine -like ('*'+$r+'*bridge\\final.py*')) } | "
        "ForEach-Object { '{0} {1}' -f $_.ProcessId,$_.Name }"
    )
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        return []
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]


def open_sdl():
    """Initialise SDL exactly the way bridge/final.py does."""

    import pygame

    # SDL freezes button state when its helper window loses focus unless this
    # hint is set before pygame.init().
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    pygame.init()
    try:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "-10000,-10000")
        pygame.display.init()
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
    except Exception as exc:
        print("NOTE: off-screen SDL window unavailable (%s); continuing." % exc)
    pygame.joystick.init()
    return pygame


def bank_from_name(name):
    """Return the logical bank from the SDL product name, or None."""

    text = " ".join(str(name or "").upper().split())
    if "TCA" not in text or "BOEING" not in text:
        return None
    if "1&2" in text or "1 & 2" in text:
        return "1&2"
    if "3&4" in text or "3 & 4" in text:
        return "3&4"
    return None


def list_sticks(pygame):
    sticks = []
    for index in range(pygame.joystick.get_count()):
        joy = pygame.joystick.Joystick(index)
        try:
            joy.init()
        except Exception:
            pass
        sticks.append(joy)
    return sticks


def snapshot(pygame, joy):
    pygame.event.pump()
    axes = tuple(joy.get_axis(i) for i in range(joy.get_numaxes()))
    buttons = tuple(bool(joy.get_button(i)) for i in range(joy.get_numbuttons()))
    hats = tuple(joy.get_hat(i) for i in range(joy.get_numhats()))
    return axes, buttons, hats


def survey(pygame, joy, seconds=20.0):
    """Print live values so the physical shape of the unit is visible."""

    print("")
    print("Live survey for %.0f seconds -- move everything you want to see." % seconds)
    print("Ctrl-C to stop early.")
    print("")
    end = time.monotonic() + seconds
    last = None
    try:
        while time.monotonic() < end:
            axes, buttons, hats = snapshot(pygame, joy)
            line = "axes " + " ".join("%d:%+.3f" % (i, v) for i, v in enumerate(axes))
            down = [str(i) for i, b in enumerate(buttons) if b]
            line += "  buttons[" + (",".join(down) if down else "-") + "]"
            if hats:
                line += "  hats " + " ".join(str(h) for h in hats)
            if line != last:
                print("  " + line)
                last = line
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("  (survey stopped)")
    print("")


def discover(pygame, joy, seconds=25.0):
    """Find which axes and buttons are physically real before naming anything.

    The unit enumerates six axes but does not necessarily carry six levers, so
    an axis that never leaves its rest value is reported as idle rather than
    silently offered as a capture target.
    """

    print("")
    print("=" * 74)
    print("  STEP 1 of 2 -- DISCOVERY")
    print("=" * 74)
    print("  Move EVERY lever, trigger and knob on the quadrant, through full")
    print("  travel, for the next %.0f seconds. Order does not matter." % seconds)
    print("")
    base_axes, base_buttons, _hats = snapshot(pygame, joy)
    print("  resting axes: "
          + "  ".join("%d:%+.3f" % (i, v) for i, v in enumerate(base_axes)))
    print("")
    try:
        input("  Enter to start moving > ")
    except EOFError:
        pass

    lo = list(base_axes)
    hi = list(base_axes)
    pressed = set()
    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            axes, buttons, _h = snapshot(pygame, joy)
            for i, v in enumerate(axes):
                if v < lo[i]:
                    lo[i] = v
                if v > hi[i]:
                    hi[i] = v
            for i, b in enumerate(buttons):
                if b:
                    pressed.add(i)
            remaining = end - time.monotonic()
            live = sum(1 for i in range(len(axes)) if hi[i] - lo[i] > AXIS_MOVE_THRESHOLD)
            print("\r  %4.1fs left   live axes: %d   buttons seen: %2d   "
                  % (remaining, live, len(pressed)), end="", flush=True)
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    print("")
    print("")

    live_axes = []
    print("  AXIS TRAVEL")
    for i in range(len(base_axes)):
        span = hi[i] - lo[i]
        if span > AXIS_MOVE_THRESHOLD:
            live_axes.append(i)
            verdict = "LIVE"
        elif span > AXIS_NOISE_FLOOR:
            verdict = "barely moved"
        else:
            verdict = "idle -- no lever"
        print("    axis %d   rest %+.3f   %+.3f .. %+.3f   span %.3f   %s"
              % (i, base_axes[i], lo[i], hi[i], span, verdict))
    print("")
    print("  BUTTONS SEEN: %s"
          % (", ".join(str(b) for b in sorted(pressed)) if pressed else "none"))
    print("")
    return {
        "live_axes": live_axes,
        "axis_rest": [round(v, 4) for v in base_axes],
        "axis_min": [round(v, 4) for v in lo],
        "axis_max": [round(v, 4) for v in hi],
        "buttons_seen": sorted(pressed),
    }


def _countdown(pygame, joy, seconds, on_sample, label):
    """Sample until the clock runs out, feeding every reading to on_sample."""

    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            axes, buttons, _h = snapshot(pygame, joy)
            on_sample(axes, buttons)
            print("\r  %4.1fs left   %s" % (end - time.monotonic(), label),
                  end="", flush=True)
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    print("")


def capture_buttons(pygame, joy, live_axes, seconds=20.0):
    """Separate real controls from lever detent contacts.

    Discovery sees almost every button because moving a lever closes its
    detent switches.  Counting cannot tell those apart from the reverser
    triggers or the knob, so each is provoked on its own and the axis position
    at the moment of closure is recorded with it.  A contact that only ever
    closes at one end of one lever's travel is that lever's detent, and its
    gate value is exactly what the thrust mapping needs.
    """

    report = {
        "detents": {},
        "select_knob": {},
        "encoder_cw": {},
        "encoder_ccw": {},
        "named_buttons": {},
    }

    print("")
    print("=" * 74)
    print("  BUTTON PASS -- telling detents apart from real controls")
    print("=" * 74)

    # ---- Phase A: which contacts belong to which lever, and where ----
    for axis in live_axes:
        label = AXIS_LABELS.get(axis, "the lever on axis %d" % axis)
        print("")
        print("-" * 74)
        print("  Move ONLY the %s" % label)
        print("  Slowly, end to end and back. Every detent you can feel.")
        print("  Touch nothing else.")
        print("-" * 74)
        try:
            input("  Enter to start > ")
        except EOFError:
            pass
        base_axes, base_buttons, _h = snapshot(pygame, joy)
        events = {}
        state = dict(enumerate(base_buttons))

        def sample(axes, buttons, _axis=axis, _events=events, _state=state):
            for i, b in enumerate(buttons):
                if b and not _state.get(i):
                    _events.setdefault(i, []).append(round(axes[_axis], 3))
                _state[i] = b

        _countdown(pygame, joy, seconds, sample, "move the %s" % label.split("(")[0].strip())

        if events:
            print("  contacts that closed while this lever moved:")
            for index in sorted(events):
                at = events[index]
                print("     button %-2d  closed at lever position %s"
                      % (index, ", ".join("%+.2f" % v for v in at[:6])))
            report["detents"][str(axis)] = {
                str(k): v for k, v in sorted(events.items())
            }
        else:
            print("  no contacts closed -- this lever has no detent switches.")

    # ---- Phase B: two knobs, captured apart ----
    # A detented SELECT knob reports one button per position and holds it.  A
    # continuous encoder has no end stops and pulses a button per step, with a
    # different button for each direction.  Conflating them is what made an
    # earlier single-knob prompt answer 15 once and 13 the next time.
    def _watch(prompt, hint, key):
        print("")
        print("-" * 74)
        print("  %s" % prompt)
        print("  %s" % hint)
        print("-" * 74)
        try:
            input("  Enter to start > ")
        except EOFError:
            pass
        _a, base, _h = snapshot(pygame, joy)
        order = []
        counts = {}
        state = dict(enumerate(base))

        def sample(_axes, buttons, _o=order, _c=counts, _s=state):
            for i, b in enumerate(buttons):
                if b and not _s.get(i):
                    _c[i] = _c.get(i, 0) + 1
                    if not _o or _o[-1] != i:
                        _o.append(i)
                _s[i] = b

        _countdown(pygame, joy, seconds, sample, key)
        report[key] = {"order": order, "counts": counts}
        if not order:
            print("  nothing closed.")
            return
        distinct = sorted(counts)
        print("  order seen : %s" % " -> ".join(str(i) for i in order[:24]))
        print("  buttons    : %s"
              % ", ".join("%d x%d" % (i, counts[i]) for i in distinct))
        return distinct

    select = _watch(
        "Turn the SELECT knob through EVERY position, pausing at each.",
        "The detented one. Stop on each position for a moment.",
        "select_knob",
    )
    if select:
        if len(select) > 1:
            print("  => rotary switch: one button per position, %d positions seen."
                  % len(select))
        else:
            print("  => single contact only.")

    cw = _watch(
        "Turn the TOP knob CLOCKWISE only, many steps.",
        "The one that spins forever. Clockwise the whole time.",
        "encoder_cw",
    )
    ccw = _watch(
        "Now turn the TOP knob COUNTER-CLOCKWISE only, many steps.",
        "Same knob, the other way, the whole time.",
        "encoder_ccw",
    )
    if cw and ccw:
        if set(cw) == set(ccw):
            print("")
            print("  => encoder reports the SAME button both ways (%s):"
                  % ", ".join(str(i) for i in cw))
            print("     direction is not distinguishable from buttons alone.")
        else:
            print("")
            print("  => encoder is direction-coded:  CW %s   CCW %s"
                  % (", ".join(str(i) for i in cw),
                     ", ".join(str(i) for i in ccw)))

    # ---- Phase C: every discrete control, one at a time ----
    # These auto-advance the moment a contact closes, so ten prompts stay quick.
    print("")
    print("=" * 74)
    print("  DISCRETE CONTROLS -- one press each, it advances by itself")
    print("=" * 74)
    named = {}
    for key, description in BUTTON_PROMPTS:
        outcome = capture_press(pygame, joy, description)
        if outcome:
            named[key] = outcome
    report["named_buttons"] = named
    return report


def capture_press(pygame, joy, description, seconds=12.0):
    """Wait for one discrete control and return every contact it closed."""

    print("")
    print("  %s" % description)
    print("    (do nothing for %.0fs to skip)" % seconds)
    time.sleep(0.25)
    _a, base, _h = snapshot(pygame, joy)
    seen = []
    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            _axes, buttons, _h = snapshot(pygame, joy)
            for i, b in enumerate(buttons):
                if b and not base[i] and i not in seen:
                    seen.append(i)
            if seen:
                # A trigger can close two contacts a few ms apart; let it settle.
                settle = time.monotonic() + 0.45
                while time.monotonic() < settle:
                    _axes, buttons, _h = snapshot(pygame, joy)
                    for i, b in enumerate(buttons):
                        if b and not base[i] and i not in seen:
                            seen.append(i)
                    time.sleep(0.02)
                break
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass

    if not seen:
        print("    -> skipped")
        return None
    print("    -> button %s" % ", ".join(str(i) for i in seen))
    return {"buttons": seen}


def capture_control(pygame, joy, name, description):
    """Watch every input and return whichever one the user actually moved."""

    print("")
    print("-" * 74)
    print("  MOVE: %s" % description)
    print("  (s = skip this control, q = stop capturing)")
    print("-" * 74)

    # Let the previous control come to rest before baselining.
    time.sleep(SETTLE_SECONDS)
    base_axes, base_buttons, base_hats = snapshot(pygame, joy)

    lo = list(base_axes)
    hi = list(base_axes)
    seen_buttons = set()
    seen_hats = set()
    deadline = time.monotonic() + PROMPT_TIMEOUT
    result = None

    while time.monotonic() < deadline:
        axes, buttons, hats = snapshot(pygame, joy)

        for i, v in enumerate(axes):
            if v < lo[i]:
                lo[i] = v
            if v > hi[i]:
                hi[i] = v
        for i, b in enumerate(buttons):
            if b and not base_buttons[i]:
                seen_buttons.add(i)
        for i, h in enumerate(hats):
            if h != base_hats[i] and h != (0, 0):
                seen_hats.add((i, h))

        travel = [hi[i] - lo[i] for i in range(len(axes))]
        best = max(range(len(travel)), key=lambda i: travel[i]) if travel else None

        # An axis that has swung far enough wins outright.
        if best is not None and travel[best] >= AXIS_MOVE_THRESHOLD:
            # Keep sampling briefly so the far end of the travel is recorded.
            settle = time.monotonic() + 1.2
            while time.monotonic() < settle:
                axes, buttons, _hats = snapshot(pygame, joy)
                for i, v in enumerate(axes):
                    if v < lo[i]:
                        lo[i] = v
                    if v > hi[i]:
                        hi[i] = v
                for i, b in enumerate(buttons):
                    if b and not base_buttons[i]:
                        seen_buttons.add(i)
                time.sleep(0.02)
            result = {
                "kind": "axis",
                "index": best,
                "rest": round(base_axes[best], 4),
                "min": round(lo[best], 4),
                "max": round(hi[best], 4),
                "travel": round(hi[best] - lo[best], 4),
                "buttons_seen": sorted(seen_buttons),
            }
            break

        if seen_buttons:
            # No axis moved, but a contact closed -- that is the control.
            time.sleep(0.35)
            _a, buttons, _h = snapshot(pygame, joy)
            for i, b in enumerate(buttons):
                if b and not base_buttons[i]:
                    seen_buttons.add(i)
            result = {
                "kind": "button",
                "index": sorted(seen_buttons)[0],
                "all_indices": sorted(seen_buttons),
            }
            break

        if seen_hats:
            index, value = sorted(seen_hats)[0]
            result = {"kind": "hat", "index": index, "value": list(value)}
            break

        time.sleep(0.02)

    if result is None:
        moved = max(hi[i] - lo[i] for i in range(len(hi))) if hi else 0.0
        if moved > AXIS_NOISE_FLOOR:
            print("  nothing cleared the threshold (largest travel %.3f)." % moved)
        else:
            print("  nothing moved.")
        return None

    if result["kind"] == "axis":
        print(
            "  -> AXIS %d   rest %+.3f   travel %+.3f .. %+.3f  (span %.3f)"
            % (result["index"], result["rest"], result["min"],
               result["max"], result["travel"])
        )
        if result["buttons_seen"]:
            print(
                "     buttons that closed during the move: %s"
                % ", ".join(str(b) for b in result["buttons_seen"])
            )
    elif result["kind"] == "button":
        print("  -> BUTTON %s" % ", ".join(str(b) for b in result["all_indices"]))
    else:
        print("  -> HAT %d value %s" % (result["index"], result["value"]))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="list SDL controllers and exit")
    ap.add_argument("--survey", action="store_true", help="live value view, no capture")
    ap.add_argument("--survey-seconds", type=float, default=20.0)
    ap.add_argument("--discover-seconds", type=float, default=25.0)
    ap.add_argument(
        "--buttons", action="store_true",
        help="button pass only: tell lever detents apart from real controls",
    )
    ap.add_argument("--button-seconds", type=float, default=20.0)
    ap.add_argument("--out", default=None, help="output JSON path")
    ap.add_argument(
        "--force", action="store_true",
        help="capture even if a MuslimSim process is running (not advised)",
    )
    a = ap.parse_args()

    procs = running_muslimsim(PROJECT)
    if procs and not a.force:
        print("MuslimSim is running:", file=sys.stderr)
        for p in procs:
            print("   " + p, file=sys.stderr)
        print(
            "\nClose MuslimSim Studio and launch.py first. Two SDL readers must not\n"
            "compete for the same controller. Re-run when they are closed.",
            file=sys.stderr,
        )
        return 1

    try:
        pygame = open_sdl()
    except Exception as exc:
        print("SDL could not start: %s" % exc, file=sys.stderr)
        return 1

    try:
        sticks = list_sticks(pygame)
        if not sticks:
            print("No SDL controllers found.", file=sys.stderr)
            return 1

        if a.list:
            print("")
            for i, joy in enumerate(sticks):
                print(
                    "  [%d] %-40s axes=%d buttons=%d hats=%d  bank=%s"
                    % (i, joy.get_name(), joy.get_numaxes(),
                       joy.get_numbuttons(), joy.get_numhats(),
                       bank_from_name(joy.get_name()) or "-")
                )
            print("")
            return 0

        tca = None
        for joy in sticks:
            if bank_from_name(joy.get_name()):
                tca = joy
                break
        if tca is None:
            print("No TCA Boeing quadrant among the connected controllers:", file=sys.stderr)
            for i, joy in enumerate(sticks):
                print("   [%d] %s" % (i, joy.get_name()), file=sys.stderr)
            return 1

        bank = bank_from_name(tca.get_name())
        print("")
        print("=" * 74)
        print("  TCA BOEING CAPTURE -- read only")
        print("=" * 74)
        print("  device : %s" % tca.get_name())
        print("  bank   : %s   (fixed at USB enumeration)" % bank)
        print("  axes   : %d      buttons: %d      hats: %d"
              % (tca.get_numaxes(), tca.get_numbuttons(), tca.get_numhats()))
        print("")

        if a.survey:
            survey(pygame, tca, a.survey_seconds)
            return 0

        if a.buttons:
            # The three live levers are already established by capture; if this
            # runs standalone, fall back to every axis the device declares.
            live = [3, 4, 5] if tca.get_numaxes() >= 6 else list(
                range(tca.get_numaxes())
            )
            report = capture_buttons(pygame, tca, live, a.button_seconds)
            stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            out = Path(a.out) if a.out else (
                PROJECT / "logs" / ("tca_boeing_buttons_%s_%s.json"
                                    % (bank.replace("&", "-"), stamp))
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({
                "captured_at": _dt.datetime.now().isoformat(timespec="seconds"),
                "device_name": tca.get_name(),
                "bank": bank,
                "axes_examined": live,
                "report": report,
            }, indent=2), encoding="utf-8")
            print("")
            print("  written: %s" % out)
            return 0

        found = discover(pygame, tca, a.discover_seconds)

        print("=" * 74)
        print("  STEP 2 of 2 -- NAMING")
        print("=" * 74)
        print("  Now move ONLY the control named in each prompt, full travel.")
        print("  Leave everything else still.")
        try:
            input("  Enter to begin > ")
        except EOFError:
            pass

        captured = {}
        for name, description in CONTROL_PROMPTS:
            outcome = capture_control(pygame, tca, name, description)
            if outcome is not None:
                captured[name] = outcome

        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = Path(a.out) if a.out else (
            PROJECT / "logs" / ("tca_boeing_capture_%s_%s.json"
                                % (bank.replace("&", "-"), stamp))
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "captured_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "device_name": tca.get_name(),
            "bank": bank,
            "axis_count": tca.get_numaxes(),
            "button_count": tca.get_numbuttons(),
            "hat_count": tca.get_numhats(),
            "discovery": found,
            "controls": captured,
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        print("")
        print("=" * 74)
        print("  CAPTURED %d of %d controls for bank %s"
              % (len(captured), len(CONTROL_PROMPTS), bank))
        for name, entry in captured.items():
            if entry["kind"] == "axis":
                print("    %-16s axis %d   span %.3f"
                      % (name, entry["index"], entry["travel"]))
            elif entry["kind"] == "button":
                print("    %-16s button %s"
                      % (name, ",".join(str(b) for b in entry["all_indices"])))
            else:
                print("    %-16s hat %d" % (name, entry["index"]))
        print("")
        print("  written: %s" % out)
        print("=" * 74)
        return 0
    finally:
        try:
            pygame.joystick.quit()
            pygame.quit()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
