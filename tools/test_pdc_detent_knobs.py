#!/usr/bin/env python3
"""The PDC MINS and BARO knobs are two-stage detent rotaries, not spring switches.

Turn one of these knobs and it reaches a detent: that is one click, and the
value moves one by one. Tug it past the notch and hold it there and it runs
fast for as long as you hold it. The panel reports both stages on separate
contacts, and MuslimSim used to read only the detent ones - so the fast gesture
came out as two clicks (the detent on the way out, and again as the spring
carried it back) instead of a run.

The bit numbers below are not guesses. They are read off the owner's own
captures, "3M PDC L FULL.pcapng" and "3M PDC R FULL.pcapng", where each
direction of each knob was worked five times slowly and five times past the
notch. The gestures replayed here are the recorded ones, timestamps included.

Offline: no hardware, no simulator, no Tk window.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.pdc_bb61_bb52 import (
    BB52_DETENT_KNOBS,
    BB61_DETENT_KNOBS,
    PDC_KNOB_FAST_PERIOD,
    MuslimSimPDCBB52Right,
    MuslimSimPDCBB61Left,
)


# What the captures prove, written out so a future edit to the driver has to
# disagree with the hardware in plain sight.
CAPTURED_LADDERS = {
    "BB61": {
        "mins": {"dec": 40, "rest": 41, "inc": 42, "dec_fast": 20, "inc_fast": 21},
        "baro": {"dec": 43, "rest": 44, "inc": 45, "dec_fast": 22, "inc_fast": 23},
    },
    "BB52": {
        "mins": {"dec": 34, "rest": 35, "inc": 36, "dec_fast": 33, "inc_fast": 37},
        "baro": {"dec": 38, "rest": 39, "inc": 40, "dec_fast": 23, "inc_fast": 24},
    },
}

# Straight out of "3M PDC L FULL.pcapng", captain BARO. First the owner turning
# to the detent and letting go, five times clockwise then once anticlockwise.
CAPTURED_SLOW = (
    (12.320, (45,)), (12.609, (44,)),
    (13.379, (45,)), (13.679, (44,)),
    (14.389, (45,)), (14.689, (44,)),
    (15.399, (45,)), (15.689, (44,)),
    (16.319, (45,)), (16.619, (44,)),
    (18.669, (43,)),
)

# The same knob, same capture, now tugged past the notch: the detent contact
# drops and bit 23 - "held past the notch, clockwise" - takes over.
CAPTURED_FAST = (
    (23.499, (45,)), (23.579, (23,)), (23.939, (45,)), (23.969, (44,)),
    (24.369, (45,)), (24.439, (23,)), (24.819, (45,)), (24.849, (44,)),
    (25.569, (45,)), (25.639, (23,)), (25.999, (45,)), (26.029, (44,)),
)


class _Panel:
    """A real driver with no USB attached and a clock the test owns."""

    def __init__(self, cls):
        self.device = cls()
        self.now = 0.0
        self.device._clock = lambda: self.now

    def report(self, buttons):
        value = 0
        for button in buttons:
            value |= 1 << (int(button) - 1)
        data = bytearray(17)
        data[0] = 0x01
        for index in range(8):
            data[1 + index] = (value >> (index * 8)) & 0xFF
        return bytes(data)

    def connect(self, buttons=()):
        self.device._accept_baseline(self.report(buttons))
        self.drain()

    def see(self, buttons):
        self.device._accept_report(self.report(buttons))

    def run_until(self, when, step=0.005):
        """Advance the clock the way the non-blocking reader loop does."""

        while self.now + step < when:
            self.now += step
            self.device._service_detent_knobs()
        self.now = when
        self.device._service_detent_knobs()

    def drain(self):
        events = []
        while not self.device._event_q.empty():
            event = self.device._event_q.get_nowait()
            events.append((event.control, event.phase, event.value))
        return events

    def clicks(self):
        return [
            control for control, phase, _value in self.drain() if phase == "press"
        ]


def latest_records(events):
    """Fold events the way HardwareLab.input does: one record per control."""

    records = {}
    for control, phase, value in events:
        records[control] = {"phase": phase, "value": value}
    return records


def studio_would_animate(record):
    """The condition Studio's faceplate pulse() actually tests."""

    return (
        str(record.get("phase") or "") in {"press", "change"}
        and float(record.get("value", 0.0)) != 0.0
    )


def check_the_ladders_match_the_captures():
    for label, expected in CAPTURED_LADDERS.items():
        actual = BB61_DETENT_KNOBS if label == "BB61" else BB52_DETENT_KNOBS
        assert dict(actual) == expected, (
            "%s knob contacts no longer match the owner's capture.\n"
            "  capture: %s\n  driver : %s" % (label, expected, dict(actual))
        )
    print("  [ok] both ladders still match what the captures recorded")


def check_a_detent_visit_is_exactly_one_click():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    panel.see((45,))
    panel.see((44,))
    assert panel.clicks() == ["baro_inc"], (
        "one turn to the detent must be exactly one click"
    )
    print("  [ok] a turn to the detent is one click")


def check_the_recorded_slow_gestures_click_once_each():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    for when, state in CAPTURED_SLOW:
        panel.run_until(when)
        panel.see(state)
    clicks = panel.clicks()
    assert clicks == ["baro_inc"] * 5 + ["baro_dec"], (
        "the five recorded clockwise detent turns and one anticlockwise turn "
        "produced %s" % clicks
    )
    print("  [ok] the five recorded slow turns are five clicks")


def check_the_spring_return_is_not_a_click():
    """BUG-14 in one line: past the notch and back is one turn, not two."""

    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    panel.see((45,))     # to the detent
    panel.see((23,))     # tugged past the notch
    panel.see((45,))     # the spring carrying it back through the detent
    panel.see((44,))     # at rest again
    clicks = panel.clicks()
    assert clicks == ["baro_inc"], (
        "the knob was turned past the notch and released, and the detent it "
        "brushed on the way back was counted as a second turn: %s. That is the "
        "bug - reading the detent contacts alone cannot tell a turn from a "
        "spring returning." % clicks
    )
    print("  [ok] the spring returning through the detent is not a second click")


def check_holding_past_the_notch_runs_fast():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    panel.see((45,))
    panel.see((23,))
    panel.run_until(0.55)
    clicks = panel.clicks()
    expected = 1 + int(0.55 / PDC_KNOB_FAST_PERIOD)
    assert clicks == ["baro_inc"] * expected, (
        "holding past the notch for 0.55 s gave %d clicks, expected %d"
        % (len(clicks), expected)
    )
    print("  [ok] holding past the notch runs at %.0f clicks a second"
          % (1.0 / PDC_KNOB_FAST_PERIOD))


def check_releasing_stops_the_run():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    panel.see((45,))
    panel.see((23,))
    panel.run_until(0.30)
    panel.see((45,))
    panel.see((44,))
    panel.drain()
    panel.run_until(2.0)
    assert panel.clicks() == [], (
        "the knob kept stepping after it was let go"
    )
    print("  [ok] letting go stops the run")


def check_a_stalled_loop_does_not_bank_a_burst():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    panel.see((45,))
    panel.see((23,))
    panel.drain()
    panel.now = 5.0                      # the loop was blocked for five seconds
    panel.device._service_detent_knobs()
    clicks = panel.clicks()
    assert clicks == ["baro_inc"], (
        "a stalled reader loop banked up %d steps and fired them at once. Owed "
        "work must not pile up - the next step is due a period from now, not a "
        "period from when it was owed." % len(clicks)
    )
    print("  [ok] a stalled loop does not fire a banked-up burst")


def check_a_knob_held_at_connect_does_not_click():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((23,))                 # already held past the notch
    panel.run_until(1.0)
    assert panel.clicks() == [], (
        "a knob the owner happened to be holding when the panel was plugged in "
        "was replayed into the simulator as a turn"
    )
    print("  [ok] a knob held at connect is adopted, not replayed")


def check_a_pulled_cable_stops_the_run():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    panel.see((45,))
    panel.see((23,))
    panel.drain()
    panel.device._reset_detent_knobs()   # what the disconnect path does
    panel.run_until(2.0)
    assert panel.clicks() == [], (
        "the knob kept stepping after the panel was unplugged"
    )
    print("  [ok] unplugging the panel stops the run")


def check_every_knob_on_both_panels():
    panels = (
        ("BB61", MuslimSimPDCBB61Left, BB61_DETENT_KNOBS),
        ("BB52", MuslimSimPDCBB52Right, BB52_DETENT_KNOBS),
    )
    for label, cls, ladders in panels:
        for name, ladder in ladders.items():
            for direction in ("inc", "dec"):
                panel = _Panel(cls)
                panel.connect((ladder["rest"],))
                panel.see((ladder[direction],))
                panel.see((ladder[direction + "_fast"],))
                panel.run_until(0.25)
                panel.see((ladder[direction],))
                panel.see((ladder["rest"],))
                clicks = panel.clicks()
                control = name + "_" + direction
                assert set(clicks) == {control}, (
                    "%s %s turned %s and produced %s"
                    % (label, name, direction, sorted(set(clicks)))
                )
                assert len(clicks) == 1 + int(0.25 / PDC_KNOB_FAST_PERIOD), (
                    "%s %s %s gave %d clicks" % (label, name, direction, len(clicks))
                )
    print("  [ok] all four knobs on both panels behave the same way")


def check_the_recorded_fast_gestures_run():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    for when, state in CAPTURED_FAST:
        panel.run_until(when)
        panel.see(state)
    clicks = panel.clicks()
    assert set(clicks) == {"baro_inc"}, (
        "the recorded fast gestures were all clockwise but produced %s"
        % sorted(set(clicks))
    )
    # Three recorded tugs, each held past the notch for about a third of a
    # second. Read as bare detents that was six clicks; it should be well more.
    assert len(clicks) >= 12, (
        "the three recorded past-the-notch tugs gave only %d clicks. Held for "
        "roughly a third of a second each, they should run, not tick."
        % len(clicks)
    )
    print("  [ok] the recorded fast gestures run (%d clicks, not 6)" % len(clicks))


def check_a_run_stays_visible_to_studio():
    """The live-feedback shape, which is a feature and not an implementation detail.

    `HardwareLab.input` keeps one record per control and the last event wins,
    and Studio only turns a knob whose latest record is a press with a non-zero
    value. Emit the release straight after each press and the counts still look
    right in every other test here while the faceplate sits perfectly still.
    """

    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    panel.see((45,))
    panel.see((23,))
    for _ in range(4):
        panel.run_until(panel.now + PDC_KNOB_FAST_PERIOD)
        records = latest_records(panel.drain())
        assert "baro_inc" in records, "a fast step produced no event at all"
        assert studio_would_animate(records["baro_inc"]), (
            "mid-run the newest record for baro_inc was %s. Studio animates a "
            "knob only while its latest record is a press with a non-zero "
            "value, so the panel would turn and the faceplate would not."
            % records["baro_inc"]
        )
    print("  [ok] a run stays visible to Studio for every step")


def check_letting_go_releases_the_control_exactly_once():
    panel = _Panel(MuslimSimPDCBB61Left)
    panel.connect((44,))
    panel.see((45,))
    panel.see((23,))
    panel.run_until(0.35)
    panel.see((45,))
    panel.see((44,))
    events = panel.drain()
    releases = [
        control for control, phase, _value in events if phase == "release"
    ]
    assert releases == ["baro_inc"], (
        "letting go produced releases %s; the control must be released once, "
        "when the knob is back at rest" % releases
    )
    assert not studio_would_animate(latest_records(events)["baro_inc"]), (
        "the knob is at rest but its latest record still reads as pressed"
    )
    print("  [ok] letting go releases the control exactly once")


def main():
    print("PDC MINS/BARO two-stage detent knobs:")
    check_the_ladders_match_the_captures()
    check_a_detent_visit_is_exactly_one_click()
    check_the_recorded_slow_gestures_click_once_each()
    check_the_spring_return_is_not_a_click()
    check_holding_past_the_notch_runs_fast()
    check_releasing_stops_the_run()
    check_a_stalled_loop_does_not_bank_a_burst()
    check_a_knob_held_at_connect_does_not_click()
    check_a_pulled_cable_stops_the_run()
    check_every_knob_on_both_panels()
    check_the_recorded_fast_gestures_run()
    check_a_run_stays_visible_to_studio()
    check_letting_go_releases_the_control_exactly_once()
    print("PDC detent knob test passed.")


if __name__ == "__main__":
    main()
