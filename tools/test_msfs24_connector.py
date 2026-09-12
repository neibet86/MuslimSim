#!/usr/bin/env python3
"""Prove the MSFS dispatch seam routes correctly and refuses safely.

The MSFS connector has no execution surface yet, which makes this the moment to
fix its behaviour: what it sends, how it translates each protocol, and above all
what it refuses.  A mapping that looks delivered but was not is the worst
outcome, so the default transport raises rather than dropping silently.

The aircraft gate is the same rule the X-Plane bridge enforces: a mapping
belongs to one aircraft workspace, and may only reach the simulator while that
aircraft is loaded.  Without it a Fenix mapping could fire into a PMDG.

Offline: no simulator, no hardware, no bridge process.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.platform.msfs_connector import (
    MsfsTransportError, NullMsfsTransport, build_calculator_code,
    dispatch_msfs_binding,
)

COMMUNITY = r"D:\MSFS24\Community"
FENIX = ("FenixA320 CFM SL", rf"{COMMUNITY}\fnx-aircraft-320\x\aircraft.cfg")
PMDG = ("737-900 PAX BW SC", rf"{COMMUNITY}\pmdg-aircraft-739\x\aircraft.cfg")


class _Recorder:
    """A transport that records instead of flying anything."""

    name = "recorder"

    def __init__(self):
        self.codes = []
        self.events = []

    def is_connected(self):
        return True

    def execute_calculator_code(self, code):
        self.codes.append(code)

    def send_event(self, event, value=0):
        self.events.append((event, value))

    def read_lvar(self, name):
        return None


def check_nothing_is_silently_dropped():
    """With no transport, every send must raise and explain."""

    for protocol, target in (
        ("rpn", "20 (>L:VC_OVHD_ADIRS_1_KNOB, number)"),
        ("lvar", "L:A32NX_EFIS_L_OPTION"),
        ("hevent", "EVT_OH_ELEC_BATTERY_SWITCH"),
        ("simconnect", "THROTTLE1_AXIS_SET_EX1"),
    ):
        try:
            dispatch_msfs_binding(
                NullMsfsTransport(), protocol=protocol, target=target, value=1,
            )
        except MsfsTransportError as exc:
            assert "not sent" in str(exc), exc
        else:
            raise AssertionError(
                f"{protocol} was accepted with no transport installed. A mapping "
                "must never look delivered when nothing carried it."
            )
    print("  [ok] with no transport every protocol refuses and says why")


def check_each_protocol_is_translated_correctly():
    """Each catalogue protocol becomes the form its own source used."""

    rpn = "20 (>L:VC_OVHD_ADIRS_1_KNOB, number)"
    assert build_calculator_code("rpn", rpn, 1) == rpn, (
        "RPN targets are already executable gauge code and must pass through "
        "untouched."
    )
    assert build_calculator_code("lvar", "L:A32NX_EFIS_L_OPTION", 2) == (
        "2.0 (>L:A32NX_EFIS_L_OPTION, number)"
    ), build_calculator_code("lvar", "L:A32NX_EFIS_L_OPTION", 2)
    assert build_calculator_code("hevent", "EVT_OH_ELEC_BATTERY_SWITCH", 1) == (
        "(>H:EVT_OH_ELEC_BATTERY_SWITCH)"
    ), build_calculator_code("hevent", "EVT_OH_ELEC_BATTERY_SWITCH", 1)
    try:
        build_calculator_code("simconnect", "THROTTLE1_AXIS_SET_EX1", 0)
    except MsfsTransportError:
        pass
    else:
        raise AssertionError("A SimConnect event must not be sent as calculator code.")
    print("  [ok] rpn, lvar and hevent translate to their documented forms")


def check_events_and_code_take_different_routes():
    recorder = _Recorder()
    dispatch_msfs_binding(
        recorder, protocol="simconnect", target="THROTTLE1_AXIS_SET_EX1", value=16383,
    )
    dispatch_msfs_binding(
        recorder, protocol="rpn", target="1 (>L:X, number)", value=1,
    )
    assert recorder.events == [("THROTTLE1_AXIS_SET_EX1", 16383)], recorder.events
    assert recorder.codes == ["1 (>L:X, number)"], recorder.codes
    print("  [ok] SimConnect events and calculator code take separate routes")


def check_a_release_does_not_refire_a_momentary_command():
    recorder = _Recorder()
    for phase in ("press", "release"):
        dispatch_msfs_binding(
            recorder, protocol="hevent", target="EVT_TEST", value=1, phase=phase,
        )
    assert len(recorder.codes) == 1, (
        "A momentary command fired %d times across press and release; a spring "
        "return must not send it twice." % len(recorder.codes)
    )
    print("  [ok] a momentary command fires on press only")


def check_the_aircraft_gate():
    """A mapping may only reach the simulator on its own aircraft."""

    recorder = _Recorder()

    # Matching aircraft: allowed.
    dispatch_msfs_binding(
        recorder, protocol="rpn", target="1 (>L:X, number)", value=1,
        selected_aircraft="fenix_a320", loaded_title=FENIX[0], loaded_path=FENIX[1],
    )
    assert recorder.codes, "A mapping was blocked on its own aircraft."

    # Wrong aircraft loaded: refused.
    try:
        dispatch_msfs_binding(
            recorder, protocol="rpn", target="1 (>L:X, number)", value=1,
            selected_aircraft="fenix_a320", loaded_title=PMDG[0], loaded_path=PMDG[1],
        )
    except MsfsTransportError as exc:
        assert "loaded" in str(exc), exc
    else:
        raise AssertionError(
            "A Fenix mapping was sent while a PMDG was loaded. The workspace gate "
            "is what stops one aircraft's controls reaching another."
        )

    # Unrecognised aircraft: refused rather than guessed.
    try:
        dispatch_msfs_binding(
            recorder, protocol="rpn", target="1 (>L:X, number)", value=1,
            selected_aircraft="fenix_a320",
            loaded_title="Cessna 172", loaded_path=r"D:\MSFS24\Official2024\c172\aircraft.cfg",
        )
    except MsfsTransportError as exc:
        assert "not recognised" in str(exc), exc
    else:
        raise AssertionError("An unrecognised aircraft must not be treated as a match.")
    print("  [ok] the aircraft gate allows, refuses and never guesses")


def main():
    print("MSFS 2024 connector:")
    check_nothing_is_silently_dropped()
    check_each_protocol_is_translated_correctly()
    check_events_and_code_take_different_routes()
    check_a_release_does_not_refire_a_momentary_command()
    check_the_aircraft_gate()
    print("MSFS 2024 connector test passed.")


if __name__ == "__main__":
    main()
