#!/usr/bin/env python3
"""One guard per bug this project has actually shipped and fixed.

Every check here corresponds to a numbered entry in ``BUG_REGISTER.md`` and
fails if that exact defect comes back.  They are gathered in one file on
purpose: a bug that already cost a debugging session should never cost a second
one, and the cheapest way to guarantee that is a test that names it.

Bugs already guarded elsewhere are not repeated here:

* BUG-02 slow status reply  -> tools/test_live_feedback_contract.py
* BUG-03 status latch leak  -> tools/test_studio_status_latch.py
* BUG-04 silent hook failure-> tools/test_live_feedback_contract.py
* BUG-05 silent lifecycle   -> tools/test_live_feedback_contract.py
* BUG-09 orphan detection   -> tools/test_msfs24_detection.py

Offline: no hardware, no simulator, no bridge, no Tk window.
"""

from __future__ import annotations

import json
import re
import struct
import sys
import tempfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

STUDIO = PROJECT / "muslimsim" / "gui" / "studio.py"


def check_bug06_physical_telemetry_keeps_its_summary_shape():
    """BUG-06: two producers wrote one key with different shapes.

    ``physical_telemetry.py`` wrote the summary Studio reads - ``devices``
    counts and a ``sequence`` - and the Platform V7 bootstrap overwrote it with
    the raw per-control mapping, which has neither.  Studio's counters therefore
    always read zero, and the duplicate added ~93 KB to a reply fetched ten
    times a second.
    """

    from muslimsim.platform.bootstrap import install_bridge_hooks
    install_bridge_hooks()
    from muslimsim.hardware.catalog import ALL_HARDWARE
    from muslimsim.hardware.lab import HardwareLab
    from muslimsim.hardware.profiles import HardwareProfileStore

    root = Path(tempfile.mkdtemp(prefix="muslimsim-bug06-"))
    store = HardwareProfileStore(root / "p.json")
    store.load()
    lab = HardwareLab(store)
    recorded = 0
    for device in ALL_HARDWARE:
        for control in device.controls:
            if control.is_input and control.status == "implemented":
                try:
                    lab.input(device.key, control.key, 1, source="physical")
                    recorded += 1
                except Exception:
                    pass
    assert recorded, "no inputs could be recorded, so the check proves nothing"

    snapshot = lab.snapshot()
    telemetry = snapshot.get("physical_telemetry")
    assert isinstance(telemetry, dict), "physical_telemetry vanished from the snapshot"
    assert "devices" in telemetry and "sequence" in telemetry, (
        "physical_telemetry lost its summary shape (%s). Studio reads 'devices' "
        "counts and a 'sequence' from it; writing the raw per-control mapping "
        "here makes the physical counters read zero forever."
        % sorted(telemetry)
    )
    counted = sum(int(v) for v in (telemetry.get("devices") or {}).values())
    assert counted == recorded, (
        "physical_telemetry counted %d controls but %d were recorded" % (counted, recorded)
    )

    # And it must stay a summary, not become a second copy of `inputs`.
    summary_bytes = len(json.dumps(telemetry, default=str))
    inputs_bytes = len(json.dumps(snapshot.get("inputs") or {}, default=str))
    assert summary_bytes * 20 < inputs_bytes, (
        "physical_telemetry is %d bytes against %d for inputs; it is carrying a "
        "duplicate of the per-control records instead of counts, on a payload "
        "fetched ten times a second." % (summary_bytes, inputs_bytes)
    )
    print("  [ok] BUG-06 physical_telemetry keeps its summary shape (%d controls, %d bytes)"
          % (counted, summary_bytes))


def check_bug07_header_banner_cannot_alternate():
    """BUG-07: the header flickered between two strings ~14 times a second.

    The status-poll ``if/elif`` chain falls through whenever a poll is merely in
    flight or not yet due - most ticks on a healthy bridge - and that branch
    wrote "Starting private hardware service...", which then took turns with the
    real status line written by the reply.
    """

    source = STUDIO.read_text(encoding="utf-8")

    guarded = re.search(
        r"elif self\.supervisor\.running and not self\._status_seen:",
        source,
    )
    assert guarded, (
        "The 'Starting private hardware service' banner is no longer guarded by "
        "not self._status_seen. That branch is reached on most ticks of a "
        "healthy bridge, so without the guard the header alternates between it "
        "and the real status line about fourteen times a second."
    )
    assert "def _set_connection_text" in source, (
        "_set_connection_text is gone. Tk re-renders the label on every "
        "StringVar.set even with identical text, and the status reply sets the "
        "same string ten times a second."
    )
    setter = re.search(
        r"def _set_connection_text.*?if self\.connection_text\.get\(\) != text:",
        source, re.S,
    )
    assert setter, (
        "_set_connection_text no longer compares before writing, so an identical "
        "header string is re-rendered on every status reply."
    )
    print("  [ok] BUG-07 the header banner cannot alternate, and is set only on change")


def check_bug08_the_tick_paints_once():
    """BUG-08: one 70 ms tick repainted the whole faceplate up to three times."""

    source = STUDIO.read_text(encoding="utf-8")
    tick = re.search(r"\n    def _tick_once\(.*?\n(?=    def )", source, re.S)
    assert tick, "_tick_once could not be located"
    body = tick.group(0)
    draws = body.count("self._draw_faceplate()")
    assert draws == 1, (
        "_tick_once calls _draw_faceplate() %d times. The practice preview, the "
        "status reply and the flash expiry must mark the canvas dirty and let "
        "the tick paint once; three rebuilds of several hundred canvas items "
        "produce the same picture." % draws
    )
    assert "if self._redraw_pending:" in body, (
        "the single paint is no longer behind the _redraw_pending flag"
    )
    print("  [ok] BUG-08 the tick paints at most once")


def check_bug10_no_control_characters_in_source():
    """BUG-10: a shell heredoc collapsed ``\\b`` into literal backspaces.

    Four detection regexes silently became patterns containing 0x08, so the iFly
    MAX 8200 rule could never match and folded into the MAX 8.  Nothing warned:
    the file parsed, imported and ran.
    """

    offenders = []
    scanned = list((PROJECT / "muslimsim").rglob("*.py"))
    scanned += list((PROJECT / "tools").rglob("*.py"))
    for path in sorted(scanned):
        if "__pycache__" in str(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        bad = {ord(c) for c in text if ord(c) < 32 and c not in "\r\n\t"}
        if bad:
            offenders.append(f"{path.relative_to(PROJECT)}: {sorted(bad)}")
    assert not offenders, (
        "Control characters found in source:\n    " + "\n    ".join(offenders)
        + "\n\nThese are almost always an escape that a shell heredoc collapsed - "
        "a regex \\\\b becoming 0x08 parses and imports cleanly but never matches."
    )
    print("  [ok] BUG-10 no control characters hiding in the package source")


def check_bug11_catalogue_search_is_indexed():
    """BUG-11: the browser rebuilt a search string per entry per keystroke."""

    from muslimsim.hardware.msfs24_library import (
        _SEARCH_KEY, all_msfs24_functions, search_msfs24_functions,
    )
    library = list(all_msfs24_functions())
    assert library, "the MSFS catalogue is empty"
    missing = sum(1 for item in library if not item.get(_SEARCH_KEY))
    assert missing == 0, (
        "%d of %d catalogue entries have no precomputed search text. Rebuilding "
        "it per entry per keystroke is linear in the catalogue and was measured "
        "at 3-4 ms for 2,355 entries." % (missing, len(library))
    )
    results = search_msfs24_functions(library, "battery", limit=5)
    assert results, "the indexed search returned nothing for a known term"
    assert _SEARCH_KEY not in results[0], (
        "the internal search index is leaking into search results"
    )
    print("  [ok] BUG-11 the catalogue carries a precomputed search index (%d entries)"
          % len(library))


def check_bug12_pdc_selector_maps_are_not_inverted():
    """BUG-12: BARO and MINS read backwards on both WinWing PDCs.

    Turning BARO to HPA showed IN, and MINS to RADIO showed BARO. These four
    were the only selectors on either unit whose bit -> index pairs descended;
    every other selector ascends, and the bit ranges are contiguous only when
    they ascend too. The same decoded index feeds X-Plane through
    ``_set_maintained``, so the simulator was driven to the wrong position as
    well, not only the panel.
    """

    from muslimsim.devices import pdc_bb61_bb52 as pdc

    names = (
        "BB61_VOR1", "BB61_VOR2", "BB61_MINS_MODE", "BB61_BARO_UNIT",
        "BB61_MAP_MODE", "BB61_MAP_RANGE",
        "BB52_VOR1", "BB52_VOR2", "BB52_MINS_MODE", "BB52_BARO_UNIT",
        "BB52_MAP_MODE",
    )
    descending = []
    for name in names:
        mapping = getattr(pdc, name, None)
        if not isinstance(mapping, dict) or not mapping:
            continue
        bits = list(mapping.keys())
        indexes = list(mapping.values())
        if bits != sorted(bits) or indexes != sorted(indexes):
            descending.append(f"{name} = {mapping}")
    assert not descending, (
        "These PDC selector maps pair a rising bit with a falling index, which "
        "reverses the switch: " + "; ".join(descending)
        + ". A one-hot selector's lowest bit must be its first choice. "
        "Reversed, the panel and the simulator both take the opposite position."
    )

    # The lowest bit of each selector must map to choice 0, checked against the
    # catalogue that names the choices.
    from muslimsim.hardware.catalog import device_by_key
    for device_key, mins, baro in (
        ("pdc_bb61_left", pdc.BB61_MINS_MODE, pdc.BB61_BARO_UNIT),
        ("pdc_bb52_right", pdc.BB52_MINS_MODE, pdc.BB52_BARO_UNIT),
    ):
        device = device_by_key(device_key)
        assert device is not None, device_key
        for control_key, mapping, expect_first in (
            ("mins_mode", mins, "RADIO"),
            ("baro_unit", baro, "IN"),
        ):
            control = next(c for c in device.controls if c.key == control_key)
            choices = tuple(control.choices or ())
            assert choices and choices[0] == expect_first, (
                "%s.%s choices changed to %r" % (device_key, control_key, choices)
            )
            lowest = min(mapping)
            assert mapping[lowest] == 0, (
                "%s.%s: bit %d is the lowest but maps to index %d, so the panel "
                "would report %r when the switch is at %r."
                % (device_key, control_key, lowest, mapping[lowest],
                   choices[mapping[lowest]], expect_first)
            )
    print("  [ok] BUG-12 both PDCs: BARO and MINS map their lowest bit to the first choice")


def check_bug13_pdc_refuses_an_ambiguous_role():
    """BUG-13: two units on one PID silently left one panel unseen.

    The PDC role is carried by the product id, which SimAppPro can reassign.
    ``_open`` took ``entries[0]`` with no further check, so if both units ever
    reported the same PID two owners raced for one physical panel and the other
    was never identified at all. The serial is burned into each unit and does
    not move with the role, so it is the only reliable way to tell them apart.
    """

    from muslimsim.devices import pdc_bb61_bb52 as pdc

    class _Ambiguous(pdc.MuslimSimPDCBB52Right):
        def _enumerate(self):
            return [
                {"path": b"a", "serial_number": "SERIAL-OF-UNIT-A"},
                {"path": b"b", "serial_number": "SERIAL-OF-UNIT-B"},
            ]

    owner = _Ambiguous()
    if pdc.hid is None:
        # hidapi absent in this runtime: the ambiguity check still has to run
        # before anything tries to open a handle.
        try:
            owner._open()
        except RuntimeError as exc:
            assert "hidapi" in str(exc), exc
            print("  [ok] BUG-13 skipped the open path (hidapi absent); "
                  "ambiguity check verified by source")
            source = (PROJECT / "muslimsim" / "devices" / "pdc_bb61_bb52.py").read_text(encoding="utf-8")
            assert "reporting PID" in source and "serial_number" in source, (
                "the ambiguous-PID refusal is gone from _open"
            )
            return
        raise AssertionError("_open did not report the missing hidapi")

    try:
        owner._open()
    except RuntimeError as exc:
        assert "different WinWing units" in str(exc), (
            "_open failed for the wrong reason: %s" % exc
        )
    else:
        raise AssertionError(
            "_open accepted two different physical units reporting one PID. It "
            "must refuse rather than pick entries[0], or one panel is silently "
            "never identified."
        )
    print("  [ok] BUG-13 two units on one PID are refused, not silently halved")


def check_bug13_pdc_reports_its_serial():
    """The serial has to reach Studio, or a role swap stays invisible."""

    source = (PROJECT / "muslimsim" / "devices" / "pdc_bb61_bb52.py").read_text(encoding="utf-8")
    for snapshot in ("def service_snapshot", "def diagnostics_snapshot"):
        block = source.split(snapshot, 1)[1][:900]
        assert '"serial"' in block, (
            "%s no longer reports the unit serial. The PID says which role "
            "SimAppPro assigned; only the serial says which physical box that "
            "is, so without it a role swap looks like unknown hardware."
            % snapshot
        )
    print("  [ok] BUG-13 both PDC snapshots carry the physical unit serial")


def check_no_machine_specific_paths_in_shipped_code():
    """Shipped code must not contain one machine's drive letters or user name.

    MuslimSim runs on the owner's rig today, but nothing under ``muslimsim/`` or
    ``bridge/`` may assume it. MSFS records its own packages folder in
    ``UserCfg.opt`` and every device reports its own serial, so both are read at
    runtime rather than written down. Tools may still carry a convenience
    default; the shipped package may not.
    """

    back = chr(92)
    needles = (
        "D:" + back + "MSFS24", "D:/MSFS24",
        "D:" + back + "MuslimSim", "D:/MuslimSim",
        "C:" + back + "Users", "C:/Users",
        "noureddine",
    )
    offenders = []
    for scope in ("muslimsim", "bridge"):
        for path in sorted((PROJECT / scope).rglob("*.py")):
            if "__pycache__" in str(path) or ".bak" in str(path):
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                hit = next((n for n in needles if n in line), None)
                if hit:
                    offenders.append(
                        "%s:%d contains %r" % (path.relative_to(PROJECT), number, hit)
                    )
    assert not offenders, (
        "Shipped code carries this machine's paths: " + "; ".join(offenders[:6])
        + ". Read the location at runtime instead - muslimsim/platform/"
        "msfs_paths.py resolves MSFS from UserCfg.opt, and device serials come "
        "from the device."
    )
    print("  [ok] no machine-specific paths in muslimsim/ or bridge/")


def check_bug47_toliss_route_keeps_discontinuities():
    """BUG-47: filtering an empty plan slot must not heal the route gap."""
    from muslimsim.devices.nd_renderer_toliss import _route_leg_broken
    from muslimsim.devices.toliss_route_autosave import parse_toliss_qps_route

    def record(record_id, width, count, capacity, payload):
        return struct.pack("<4I", record_id, width, count, capacity) + payload

    names = ("DEP", "ONE", "ACTIVE", "", "RESUME", "TWO", "THREE", "DEST")
    latitudes = (31.0, 31.1, 31.2, 0.0, 31.4, 31.5, 31.6, 31.7)
    longitudes = (-98.0, -97.9, -97.8, 0.0, -97.6, -97.5, -97.4, -97.3)
    blob = b"".join((
        record(77, 4, 8, 16, struct.pack("<8f", *latitudes)),
        record(78, 4, 8, 16, struct.pack("<8f", *longitudes)),
        record(79, 10, 8, 16, b"".join(value.encode().ljust(10, b"\0") for value in names)),
    ))
    with tempfile.TemporaryDirectory(prefix="muslimsim-bug47-") as directory:
        source = Path(directory) / "A321_AUTOSAVED_SITUATION.qps"
        source.write_bytes(blob)
        route = parse_toliss_qps_route(source, "ACTIVE")
    assert route is not None, "the structural QPS route was not discovered"
    assert route.waypoint_ids[4] == "RESUME", "fixes after the gap were discarded"
    assert route.break_before[4], "the QPS blank did not become a discontinuity"
    assert _route_leg_broken({"route_breaks": route.break_before}, 2, 4), (
        "the renderer would connect fixes across the discontinuity"
    )
    assert not _route_leg_broken({"route_breaks": route.break_before}, 4, 5), (
        "the renderer broke an ordinary contiguous leg"
    )
    print("  [ok] BUG-47 full ToLiss route survives a discontinuity without bridging it")


def main():
    print("Known regressions:")
    check_bug06_physical_telemetry_keeps_its_summary_shape()
    check_bug07_header_banner_cannot_alternate()
    check_bug08_the_tick_paints_once()
    check_bug10_no_control_characters_in_source()
    check_bug11_catalogue_search_is_indexed()
    check_bug12_pdc_selector_maps_are_not_inverted()
    check_bug13_pdc_refuses_an_ambiguous_role()
    check_bug13_pdc_reports_its_serial()
    check_no_machine_specific_paths_in_shipped_code()
    check_bug47_toliss_route_keeps_discontinuities()
    from test_toliss_ecam_reference import check_reference_layouts
    check_reference_layouts()
    print("  [ok] BUG-40 all twelve reference ECAM layouts and telemetry honesty")
    from test_toliss_ecam_telemetry import check_telemetry_contract, check_display_modes
    check_telemetry_contract()
    check_display_modes()
    print("  [ok] BUG-41/43/53 typed ECAM sources, exact BLEED conversions, validity and DU self-test")
    from test_toliss_wheel_bleed_details import check_details
    check_details()
    print("  [ok] BUG-42/53 WHEEL/BLEED details and verified APU/X-valve topology")
    from test_toliss_sd_image import check as check_sd_image
    check_sd_image()
    from test_toliss_flight_image import check as check_flight_image
    check_flight_image()
    from test_toliss_image_transfer import check as check_image_transfer
    check_image_transfer()
    from test_toliss_pfd_latest import check as check_pfd_latest
    check_pfd_latest()
    from test_reassign_all_devices import check as check_reassign
    check_reassign()
    from test_connected_device_list import check as check_connected_devices
    check_connected_devices()
    from test_simulator_independent_hardware import check as check_simulator_independent
    check_simulator_independent()
    from test_pdc_shared_faceplate import check as check_pdc_shared
    check_pdc_shared()
    from test_pdc_3m_capture import check as check_pdc_capture
    check_pdc_capture()
    from test_pdc_bb51_verified import check as check_bb51_verified
    check_bb51_verified()
    from test_independent_controller_inputs import check as check_independent_inputs
    check_independent_inputs()
    from test_pdc_3m_active_backlight import check as check_3m_backlight
    check_3m_backlight()
    from test_moza_preset_picker import check as check_moza_picker
    check_moza_picker()
    from test_moza_feedback_controls import check as check_moza_feedback
    check_moza_feedback()
    from test_force_test_session import check as check_force_session
    check_force_session()
    print("Known-regression guards passed.")


if __name__ == "__main__":
    main()
