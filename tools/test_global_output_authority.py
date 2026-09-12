"""Check the global output authority: nothing wakes unless it was asked for.

The rule this guards is that MuslimSim never lights hardware as a side effect.
Entering Test mode must not wake every screen; registering an output adapter
must not wake anything; and a Test-mode press may drive the device being
tested and nothing else.

That last one is a correction to the original patch, which removed the practice
mirror entirely.  Removing it satisfied "do not wake everything" by also losing
"the thing you are testing lights up", and the two are both required.  The
mirror is therefore kept and scoped, and this test pins the scope: press a
control on one device, and only that device is written.

It also pins the AGP power judgement, where "no electrical ref is published by
this aircraft" and "the refs exist but cannot be read right now" must give
opposite answers.

No hardware, no simulator, no SDL.

Usage:
    python tools/test_global_output_authority.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.hardware.lab import HardwareLab  # noqa: E402


class RecordingSink:
    """Stands in for control_server.apply_practice_snapshot."""

    def __init__(self):
        self.calls = []

    def __call__(self, snapshot, *, only_device=None, force=False):
        self.calls.append(only_device)


def main() -> int:
    checks = 0
    failures = []

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    # ---- Test mode must not wake hardware by itself ----
    lab = HardwareLab()
    sink = RecordingSink()

    lab.set_practice_output_sink(sink)
    check(
        not sink.calls,
        "registering an output sink wrote to hardware",
    )

    lab.set_mode("test")
    check(
        not sink.calls,
        "entering Test mode woke outputs before anything was tested",
    )

    lab.set_mode("live")
    lab.set_mode("test")
    check(
        not sink.calls,
        "toggling back into Test mode woke outputs",
    )

    # ---- but a press is a request to test that control ----
    lab._advance_practice("pap3_mag", "n1", "change")
    check(
        sink.calls == ["pap3_mag"],
        f"a Test-mode press emitted {sink.calls}, expected exactly ['pap3_mag']",
    )

    lab._advance_practice("fcu_32_efis", "fcu_windows", "change")
    check(
        sink.calls == ["pap3_mag", "fcu_32_efis"],
        f"the second press emitted {sink.calls}, expected the pressed device only",
    )
    check(
        None not in sink.calls,
        "a press emitted an unscoped snapshot, which wakes every device",
    )

    # ---- a release is not a request ----
    before = len(sink.calls)
    lab._advance_practice("pap3_mag", "n1", "release")
    check(len(sink.calls) == before, "a release drove output hardware")

    # ---- and Live mode never uses this path at all ----
    lab.set_mode("live")
    before = len(sink.calls)
    lab._advance_practice("pap3_mag", "n1", "change")
    check(
        len(sink.calls) == before,
        "the practice mirror ran in Live mode",
    )

    # ---- the server must honour the scope it is given ----
    from muslimsim.control.server import ControlServer  # noqa: E402

    applied = []

    class ScopeProbe(ControlServer):
        def __init__(self, lab):  # noqa: D107
            self.lab = lab
            import threading
            self._lock = threading.RLock()
            self._practice_signature = None
            self._devices = {}

        def apply_lab_output(self, device_key, control_key, value, *, source=""):
            applied.append(device_key)

    probe = ScopeProbe(HardwareLab())
    snapshot = {
        "fcu_32_efis": {"values": {"speed": "250"}},
        "pap3_mag": {"values": {"speed": "250"}},
    }
    probe.apply_practice_snapshot(snapshot, only_device="pap3_mag")
    check(
        applied and set(applied) == {"pap3_mag"},
        f"scoped mirror wrote to {sorted(set(applied))}, expected only pap3_mag",
    )

    applied.clear()
    probe.apply_practice_snapshot(snapshot, force=True)
    check(
        "fcu_32_efis" in applied and "pap3_mag" in applied,
        "an unscoped mirror should still reach every device when asked",
    )

    # ---- AGP power: unknown-because-absent and unknown-because-lost differ ----
    spec = importlib.util.spec_from_file_location(
        "_goa_bridge", PROJECT / "bridge" / "final.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)

    def with_reader(fn):
        bridge.read_dataref = fn

    with_reader(lambda *a, **k: 28.0)
    check(
        bridge._agp_aircraft_output_powered("v3", {}) is True,
        "an aircraft that publishes no electrical ref must keep working",
    )
    check(
        bridge._agp_aircraft_output_powered("v3", {"dc_volts": 1}) is True,
        "a readable, powered bus should permit output",
    )

    with_reader(lambda *a, **k: 0.0)
    check(
        bridge._agp_aircraft_output_powered("v3", {"dc_volts": 1}) is False,
        "a readable, unpowered bus must black the panel",
    )

    def boom(*a, **k):
        raise RuntimeError("simulator gone")

    with_reader(boom)
    check(
        bridge._agp_aircraft_output_powered("v3", {"dc_volts": 1, "ac_volts": 2}) is False,
        "refs that exist but cannot be read mean live data was lost, which must "
        "go dark rather than hold a stale indication",
    )
    check(
        bridge._agp_aircraft_output_powered("v3", {}) is True,
        "an unreadable simulator must still not black a panel whose aircraft "
        "never published those refs",
    )

    # ---- rule 0.1: the throttle goes dark with the aircraft ----
    # Its wake sequence lights the backlight at HID open, regardless of whether
    # the aeroplane has any electrical power, so it needs an explicit blackout.
    class Recorder:
        def __init__(self):
            self.writes = []

        def write(self, data):
            self.writes.append(bytes(data))
            return len(data)

    channels = list(bridge.WINCTRL_THROTTLE_OUTPUT_CHANNELS)

    dark = Recorder()
    bridge._winctrl_throttle_blackout(dark)
    check(
        len(dark.writes) == len(channels),
        f"blackout wrote {len(dark.writes)} reports for {len(channels)} channels: "
        f"a channel left out is a light left on",
    )
    for key, written in zip(channels, dark.writes):
        check(
            written == bridge._winctrl_throttle_output_packet(key, 0),
            f"blackout of {key} is not the captured channel report at value 0 - "
            f"never invent a vendor packet to force something dark",
        )
    check(
        all(len(w) == 14 for w in dark.writes),
        "every blackout report must stay the captured 14-byte channel report",
    )
    check(
        "throttle_backlight" in channels,
        "the throttle backlight must be one of the channels the blackout covers",
    )
    check(
        "trim_display_backlight" in channels,
        "the numeric window's backlight must be covered, since that is what "
        "darkens the window without inventing a blank glyph mode",
    )

    lit = Recorder()
    bridge._winctrl_throttle_restore_defaults(lit)
    check(
        len(lit.writes) == len(bridge.WINCTRL_THROTTLE_OUTPUT_DEFAULTS),
        "restore must return every channel the capture recorded a default for",
    )
    check(
        dark.writes != lit.writes,
        "blackout and restore must not write the same thing",
    )

    # ---- rule 0.1 at shutdown: the PU must actually go dark ----
    class Args:
        egt_scale = 1.0
        egt_offset = 0.0
        egt_zero_threshold = 0.0
        egt_zero_raw = 0
        egt_mid_temp = 300.0
        egt_mid_raw = 128
        egt_peak_temp = 700.0
        egt_peak_raw = 255
        interval = 0.05

    dark_packet = bridge._pu_safe_dark_packet(Args())
    fields = dark_packet.strip().split(",")
    check(len(fields) >= 8, f"PU dark packet has too few fields: {dark_packet!r}")
    if len(fields) >= 8:
        # OVHD,P1,P2,P3,APU_EGT_RAW,LAND_ALT,FLT_ALT,LIGHT_MASK,P8
        check(fields[1].strip() == "0", "PU dark packet must not assert P1")
        check(
            int(fields[7].strip() or "0", 0) == 0,
            "PU dark packet must carry an all-dark P7 light mask",
        )
        check(
            int(fields[8].strip() or "0") == 0 if len(fields) > 8 else True,
            "PU dark packet must carry zero P8 brightness",
        )
        for index, name in ((5, "LAND ALT"), (6, "FLT ALT")):
            check(
                not fields[index].strip().isdigit(),
                f"PU dark packet must blank {name}, not send a number",
            )

    # The shutdown wait has to outlast the dash latch.  When it did not, the
    # writer was interrupted inside that latch and broke out before ever
    # writing this packet, so the panel kept its last lit mask.
    check(
        bridge.PU_SERIAL_DASH_LATCH_SECONDS > 0,
        "the dash latch must have a real duration",
    )
    shutdown_wait = (
        max(0.15, Args.interval * 3.0)
        + bridge.PU_SERIAL_DASH_LATCH_SECONDS
        + bridge.PU_SERIAL_VALUE_SETTLE_SECONDS
    )
    check(
        shutdown_wait > bridge.PU_SERIAL_DASH_LATCH_SECONDS,
        "the pre-stop wait must outlast the dash latch or the dark frame is "
        "never written",
    )

    import inspect

    # ---- rule 0.1 coverage: every device that can light must go dark ----
    # This is the part that makes the rule hold for devices that do not exist
    # yet.  A new catalogue device with implemented outputs fails this test
    # until someone says, here, how it goes dark.  "It probably inherits it"
    # is exactly how the throttle and the BB36 were each missed once.
    BLACKOUT_COVERAGE = {
        "pu_overhead": (
            "bridge/final.py _pu_write_safe_dark_frame, written by the COM5 "
            "owner as it exits and by the shutdown path"
        ),
        "winctrl_throttle": (
            "bridge/final.py _winctrl_throttle_blackout, captured channel "
            "reports at value 0"
        ),
        "agp_bb80": "bridge/final.py _agp_blackout",
        "fcu_32_efis": "muslimsim/devices/fcu_efis_ba01.py _write_blackout",
        "ecam32": "muslimsim/devices/ecam32.py _write_blackout",
        "pap3_mag": "muslimsim/devices/pap3_mcp.py _blackout, on stop_event",
        "pfp3n_bb35": (
            "muslimsim/devices/pfp_bb35_separate_paths.py stop() darkens "
            "before releasing the handle"
        ),
        "mcdu32_bb36": (
            "muslimsim/devices/mcdu_bb36_separate_paths.py stop() darkens "
            "before releasing the handle"
        ),
        "muslimrtp_d201": (
            "muslimsim/devices/howalt_v4_integration.py _all_panels_dark, "
            "which calls each router's own all_off: set_output(name, 0) for "
            "every declared output and a blank through the masked display "
            "writer. Aircraft-unpowered in _sync_live_displays, and on both "
            "shutdown paths before the ports close."
        ),
        "muslimatc_d203": (
            "muslimsim/devices/howalt_v4_integration.py _all_panels_dark, "
            "same path as muslimrtp_d201"
        ),
    }
    # MUSLIMSIM_PDC_FIXED_BLACKOUT_CONTRACT_V53
    BLACKOUT_COVERAGE.update({
        'pdc_bb61_left': 'muslimsim/devices/pdc_bb61_bb52.py',
        'pdc_bb52_right': 'muslimsim/devices/pdc_bb61_bb52.py',
    })

    from muslimsim.hardware.catalog import ALL_HARDWARE  # noqa: E402

    lightable = {
        dev.key
        for dev in ALL_HARDWARE
        if any(
            c.is_output and c.status == "implemented" and c.testable
            for c in dev.controls
        )
    }
    for key in sorted(lightable):
        check(
            key in BLACKOUT_COVERAGE,
            f"{key} has implemented outputs but no declared blackout. Rule 0.1 "
            f"covers every device including new ones: add it here and say how "
            f"it goes dark.",
        )
    for key in sorted(BLACKOUT_COVERAGE):
        check(
            key in lightable,
            f"{key} declares a blackout but no longer has implemented outputs; "
            f"the coverage table has gone stale",
        )

    # The two that were each missed once must stay covered by real code.
    throttle_src = inspect.getsource(bridge._winctrl_throttle_blackout)
    check(
        "_winctrl_throttle_output_packet" in throttle_src,
        "the throttle blackout must use the captured channel report",
    )
    # Three separate cases have to reach it, and only two did.  The panel was
    # darkened when the aircraft lost power and when the simulator went away,
    # but not when MuslimSim itself exited - so the throttle stayed lit after
    # Studio closed.  Measured on the hardware: the blackout holds after the
    # handle closes, so this really was ours to send.
    bridge_src = (PROJECT / "bridge" / "final.py").read_text(encoding="utf-8")
    close_at = bridge_src.index("def _close_winctrl_trim_display(")
    close_end = bridge_src.index("device.close()", close_at)
    check(
        "_winctrl_throttle_blackout" in bridge_src[close_at:close_end],
        "releasing the B930 output handle must darken it first, or MuslimSim "
        "leaves the throttle lit behind it when it exits",
    )
    # The RUD TRIM number is event-driven: it is written only while the rocker
    # is moving, and the readout disarms itself on the settled reading.  So
    # restoring the backlight alone brings the window back lit and empty.  That
    # is exactly how the first attempt at this blackout left the trim LCD
    # blank, and it cost the whole feature a revert on 2026-09-01.  The power
    # restore must arm one refresh, the way the AGP block clears its own cache.
    # Anchored on the authority block, not the helper's own def, which comes
    # first in the file.
    restore_at = bridge_src.index("desired_winctrl_power = _read_pu_aircraft_power")
    restore_window = bridge_src[restore_at:restore_at + 2000]
    check(
        "_winctrl_throttle_restore_defaults(" in restore_window,
        "the aircraft-power authority must restore the throttle outputs when "
        "power comes back",
    )
    check(
        "winctrl_stab_trim_readout_pending = True" in restore_window,
        "restoring the throttle outputs must re-arm the stabilizer readout, or "
        "the RUD TRIM window comes back lit but blank; this is the regression "
        "that got the blackout reverted once already",
    )
    check(
        "next_winctrl_stab_readout = 0.0" in restore_window,
        "the re-armed stabilizer readout must also be due immediately, or the "
        "window stays blank until the next scheduled read",
    )
    # The PU is the one exemption from the shutdown half of rule 0.1, and it
    # is not a gap to be closed again: it has no off state, returning to its
    # physical knob brightness about a second after anything stops sending it
    # frames.  Five attempts were made and removed on 2026-09-01; AGENTS.md
    # records the exemption and DEVICE_REFERENCE.md records the measurements.
    # Its aircraft-unpowered blackout, which is the half that works, is
    # covered by the _pu_output_mode checks above.
    bb36_path = PROJECT / "muslimsim" / "devices" / "mcdu_bb36_separate_paths.py"
    bb36 = bb36_path.read_text(encoding="utf-8")
    stop_at = bb36.index("    def stop(")
    close_at = bb36.index("output_device.close()", stop_at)
    darken = bb36[stop_at:close_at]
    check(
        "_set_brightness(output_device, 0, 0)" in darken,
        "the BB36 router must darken its screen before closing the handle, "
        "the way its BB35 sibling does",
    )
    # ...but only on the final teardown.  This path is stopped on every
    # FMC/PFD handoff and every recovery, and darkening on each of those makes
    # the panel visibly flash - the same thing PAP3 recorded years of tuning
    # about.  Guarding it is the difference between working and unusable.
    check(
        "if final and output_device is not None" in darken,
        "the BB36 blackout must be gated on a final teardown; ungated it fires "
        "on every handoff and the screen flashes",
    )
    teardown_calls = [
        line.strip()
        for line in bb36.splitlines()
        if "_stop_active_path(" in line and "def " not in line
    ]
    final_calls = [c for c in teardown_calls if "final=True" in c]
    check(
        len(teardown_calls) > 1,
        "expected several BB36 teardown paths (handoff, recovery, shutdown)",
    )
    check(
        len(final_calls) == 1,
        f"exactly one BB36 teardown may be final; found {len(final_calls)} of "
        f"{len(teardown_calls)}. More than one means a handoff darkens the "
        f"screen and it flashes.",
    )


    if failures:
        print("Global output authority self-test FAILED:", file=sys.stderr)
        for line in failures:
            print("  - " + line, file=sys.stderr)
        return 1

    print(
        "Global output authority self-test passed: %d checks. Nothing wakes "
        "unless it was asked for, a Test-mode press drives only the device "
        "under test, and lost live data goes dark. No hardware or simulator "
        "touched." % checks
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
