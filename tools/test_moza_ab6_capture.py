"""The MOZA AB6 capture, and the safety limits it must keep.

The AB6 used to be a preset-derived guess: no VID/PID, three axes marked
``unknown``, and ``status: unimplemented``. `tools/capture_moza_ab6.py` read
its real identity and HID report descriptor off the connected base, and this
locks in what that capture established - plus the one thing it deliberately
did not establish, which is any way to command the motor.

No hardware, simulator or HID handle is opened by this test.
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from muslimsim.devices.moza_a210 import (
    MOZA_A210_AXIS_KEYS,
    MOZA_A210_REPORT_LENGTH,
    decode_moza_a210_report,
)
from muslimsim.hardware import usb
from muslimsim.hardware.catalog import device_by_key
from muslimsim.hardware.product_registry import (
    PRODUCTS,
    product_for_runtime_text,
    product_for_usb,
)

MOZA_AB6_VID = 0x346E
MOZA_AB6_PID = 0x1002

# Read from the connected base on 2026-09-02 by tools/capture_moza_ab6.py.
# Report 01, 34 bytes, at rest: stick near centre, hat null, contact 3 closed.
CAPTURED_RESTING_FRAME = bytes.fromhex(
    "015b80c681ff7f000000000000000005034800000000000000000000000000000000"
)

CHECKS = 0


def check(condition: bool, description: str) -> None:
    global CHECKS
    if not condition:
        raise AssertionError(description)
    CHECKS += 1


def test_identity_is_captured_not_guessed() -> None:
    spec = device_by_key("moza_ab6")
    check(spec is not None, "the AB6 must still be catalogued")
    check(
        spec.identity == "VID 346E / PID 1002",
        f"the AB6 must carry its captured USB identity, got {spec.identity!r}",
    )
    check(
        spec.transport == "USB HID",
        "the AB6 is a USB HID device, not an SDL-name-only controller",
    )
    check(
        spec.status == "implemented",
        "the AB6 input surface is captured and must no longer read as pending",
    )


def test_input_collection_matches_the_captured_descriptor() -> None:
    """8 axes, a hat and 128 contacts - what the descriptor actually declares."""

    spec = device_by_key("moza_ab6")

    for key in MOZA_A210_AXIS_KEYS:
        control = spec.control(key)
        check(control is not None, f"the AB6 must expose {key}")
        check(
            control.status == "implemented",
            f"{key} is proven by the report descriptor and must not read unknown",
        )
        check(
            "AB6 report 01" in control.raw,
            f"{key} must cite the AB6's own report, not the A210's",
        )

    hat = spec.control("hat")
    check(hat is not None and hat.status == "implemented", "the AB6 hat is proven")

    contacts = [
        control for control in spec.controls
        if control.key.startswith("button_") and control.is_input
    ]
    check(
        len(contacts) == 128,
        f"the descriptor declares 128 HID contacts, catalogue has {len(contacts)}",
    )
    check(
        all(control.remappable for control in contacts),
        "every captured AB6 contact must be remappable",
    )
    check(
        all("has not been guessed" in (control.notes or "") for control in contacts),
        "a generic contact number must not claim to know its printed legend",
    )


def test_axis_motion_observation_is_recorded() -> None:
    """A 30 s full-travel exercise separated the live axes from the idle ones."""

    spec = device_by_key("moza_ab6")

    for key in ("axis_x", "axis_y", "axis_slider", "axis_dial"):
        control = spec.control(key)
        check(
            "no motion" not in (control.notes or ""),
            f"{key} swept its full range and must not be marked idle",
        )

    for key in ("axis_z", "axis_rx", "axis_ry", "axis_rz"):
        control = spec.control(key)
        check(
            "no motion" in (control.notes or ""),
            f"{key} stayed pinned through a full-travel exercise and must say so",
        )
        check(
            control.status == "implemented",
            f"{key} still decodes, so it is recorded as idle rather than deleted",
        )


def test_no_force_feedback_output_was_invented() -> None:
    """The capture found an input protocol. It found no way to drive the motor."""

    spec = device_by_key("moza_ab6")
    ffb = spec.control("force_feedback_profile")
    check(ffb is not None, "the AB6 force-feedback profile must remain catalogued")
    check(
        ffb.status == "unimplemented",
        "no Moza output protocol was captured; it must stay unimplemented",
    )
    check(
        not ffb.testable,
        "an untestable output is what stops Studio sending a motor command",
    )

    outputs = [control for control in spec.controls if control.is_output]
    check(
        len(outputs) == 1,
        f"the AB6 must expose exactly one, non-driveable output, got {len(outputs)}",
    )

    # Practice drives only implemented+testable lamps and LEDs, so the AB6
    # must contribute nothing to it.
    from muslimsim.hardware import practice_echo

    check(
        not practice_echo.indicator_controls("moza_ab6"),
        "Practice must never drive anything on a force-feedback base",
    )


def test_product_registry_resolves_one_ab6() -> None:
    entries = [spec for spec in PRODUCTS if spec.key == "moza_ab6"]
    check(
        len(entries) == 1,
        f"two AB6 product specs make the product ambiguous, found {len(entries)}",
    )

    by_usb = product_for_usb(MOZA_AB6_VID, MOZA_AB6_PID)
    check(
        by_usb is not None and by_usb.key == "moza_ab6",
        "346E:1002 must resolve to the AB6 by its captured USB identity",
    )

    by_name = product_for_runtime_text(
        "MOZA AB6", transports=("sdl", "usb-gaming"),
    )
    check(
        by_name is not None and by_name.key == "moza_ab6",
        "the AB6 must still resolve from its SDL controller name alone",
    )

    sibling = product_for_usb(MOZA_AB6_VID, 0x1001)
    check(
        sibling is not None and sibling.key == "moza_a210",
        "the A210 and AB6 share a vendor id and must stay distinct products",
    )


def test_power_cycle_identity_is_registered() -> None:
    check(
        usb._USB_IDENTITIES.get("moza_ab6") == "VID_346E&PID_1002",
        "the AB6 now has a real USB parent and can be restarted like the others",
    )
    check(
        usb._USB_IDENTITIES.get("moza_a210")
        != usb._USB_IDENTITIES.get("moza_ab6"),
        "restarting one Moza base must never restart the other",
    )


def test_captured_frame_decodes() -> None:
    """The recorded resting frame, decoded by the shared A210 decoder."""

    check(
        len(CAPTURED_RESTING_FRAME) == MOZA_A210_REPORT_LENGTH,
        "the captured AB6 frame must be the proven 34-byte report",
    )

    decoded = decode_moza_a210_report(CAPTURED_RESTING_FRAME)
    check(
        decoded is not None,
        "the AB6 frame must decode under the shared capture-proven layout",
    )
    check(
        decoded["axes"]["axis_x"] == 32859
        and decoded["axes"]["axis_y"] == 33222
        and decoded["axes"]["axis_z"] == 32767,
        "the recorded resting stick position must decode as captured",
    )
    check(
        decoded["hat"] == 8,
        "hat 8 is the descriptor's null state and is what a released hat reads",
    )
    check(
        [i + 1 for i, state in enumerate(decoded["buttons"]) if state] == [3],
        "the recorded frame has exactly contact 3 closed at rest",
    )


def test_capture_tool_is_read_only() -> None:
    """It opens a force-feedback base. It must never be able to drive it."""

    import ast

    path = Path(__file__).resolve().parents[1] / "tools" / "capture_moza_ab6.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    # Match real call sites, not the prose in the module docstring that
    # promises the tool does not make them.
    forbidden = {
        "write",
        "send_feature_report",
        "send_output_report",
        "Moza_DeviceParameterSetValue",
        "Moza_DeviceParameterSetValueSync",
        "Moza_DeviceCommandSend",
        "Moza_DeviceCommandSendSync",
    }
    called = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = (
            target.attr if isinstance(target, ast.Attribute)
            else target.id if isinstance(target, ast.Name)
            else ""
        )
        if name in forbidden:
            called.add(name)

    check(
        not called,
        "the AB6 capture tool opens a force-feedback base and must never call "
        f"{sorted(called)}",
    )

    # It must, however, actually read - otherwise it captures nothing.
    reads = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    check(
        "read" in reads and "get_report_descriptor" in reads,
        "the capture tool must still read reports and the report descriptor",
    )


def test_studio_ab6_page_reads_the_ab6() -> None:
    """The AB6 page must read the AB6, not its sibling.

    Studio's AB6 surface was authored when the AB6 had no captured report, so
    it read the A210's inputs, hard-disabled its contacts, and labelled itself
    REFERENCE / PRACTICE. With a real reader behind it, all three made the page
    show nothing however hard the physical base was moved.
    """

    source = (
        Path(__file__).resolve().parents[1]
        / "muslimsim" / "gui" / "studio.py"
    ).read_text(encoding="utf-8")

    check(
        'axes, live_axes = self._moza_live_axes(device)' in source,
        "the Moza page must read the axes of whichever base is selected",
    )
    check(
        'if live_axes and not is_ab6' not in source,
        "the AB6 must no longer be hard-excluded from showing LIVE HID",
    )
    check(
        'width=31, height=29, device="moza_ab6",' in source,
        "the AB6 console contacts must read the AB6's own HID pool",
    )
    check(
        'width=31, height=29, enabled=False' not in source,
        "the AB6 contacts are captured and must no longer be drawn disabled",
    )
    check(
        'device="moza_ab6")' in source,
        "the MAX3 grip is mounted on the AB6 and must read that base",
    )

    # The A210 keeps its own behaviour: every helper defaults to it.
    for default in (
        'def _moza_pressed(self, key: str, device: str = "moza_a210")',
        'def _draw_moza_hat(self, canvas: tk.Canvas, x: float, y: float, device: str = "moza_a210")',
    ):
        check(
            default in source,
            f"existing A210 callers must be preserved by default: {default}",
        )
    check(
        'return self._moza_live_axes("moza_a210")' in source,
        "the original _moza_a210_live_axes entry point must still resolve to the A210",
    )


def test_partial_axis_seed_cannot_blank_the_panel() -> None:
    """The bug that left the page blank: a seed with fewer axes than the reader.

    The AB6's stored practice pose carried only X/Y/Z, left from its
    preset-derived days. The reader publishes all eight axes on its very first
    report, so the draw raised KeyError, the tick swallowed it as
    "Panel update recovered: KeyError", and the whole faceplate rendered empty.
    """

    from muslimsim.gui.studio import MOZA_AXIS_KEYS, MuslimSimStudio

    check(
        len(MOZA_AXIS_KEYS) == 8,
        "both Moza bases declare eight axes and one list must describe them",
    )

    class _Stub:
        pass

    stub = _Stub()
    # Reproduce the pre-fix condition exactly: three seeded axes...
    stub._moza_practice_axes = {
        "moza_ab6": {"axis_x": .5, "axis_y": .5, "axis_z": .5},
    }
    stub._selected_device = "moza_ab6"
    # ...against a reader publishing all eight.
    stub._lab = {
        "inputs": {
            "moza_ab6": {key: {"value": 0.75} for key in MOZA_AXIS_KEYS}
        }
    }
    stub._axis_fraction = MuslimSimStudio._axis_fraction
    stub._number = MuslimSimStudio._number

    axes, live = MuslimSimStudio._moza_live_axes(stub, "moza_ab6")

    check(live is True, "a base publishing every axis must read as live")
    check(
        len(axes) == 8,
        f"a short seed must be filled in, not trusted; got {len(axes)} axes",
    )
    for key in MOZA_AXIS_KEYS:
        check(
            key in axes,
            f"{key} must be present even when the stored pose omitted it",
        )
    check(
        abs(axes["axis_slider"] - 0.75) < 1e-6
        and abs(axes["axis_dial"] - 0.75) < 1e-6,
        "the axes the old seed lacked must still take their live values",
    )

    # A device with no stored pose at all must also be safe.
    stub._moza_practice_axes = {}
    axes, _live = MuslimSimStudio._moza_live_axes(stub, "moza_ab6")
    check(
        len(axes) == 8,
        "a device with no stored pose must still get a complete axis set",
    )


def test_every_captured_control_can_be_assigned() -> None:
    """Studio must offer all 137 captured controls, not three practice poses.

    ``_visual_controls`` returned three hard-coded "visual practice pose" axes
    for the AB6, and ``_learned_source`` returned "" on the grounds that a
    preset is not a verified HID identity. Both were true before the capture
    and false after it, and together they meant nothing on the base could be
    selected on the faceplate or bound to a function.
    """

    from muslimsim.gui.studio import MuslimSimStudio
    from muslimsim.hardware.catalog import catalogue_snapshot

    catalog = {
        entry["key"]: entry for entry in catalogue_snapshot()["devices"]
    }

    class _Stub:
        pass

    stub = _Stub()
    stub._catalog = catalog

    counts = {}
    for device in ("moza_a210", "moza_ab6"):
        stub._selected_device = device
        controls = MuslimSimStudio._visual_controls(stub)
        counts[device] = len(controls)

        for key in ("axis_x", "axis_slider", "axis_dial", "hat", "button_050"):
            check(
                key in controls,
                f"{device}.{key} is captured and must be selectable in Studio",
            )

        stub._visual_controls = lambda _s=stub: MuslimSimStudio._visual_controls(_s)
        for key in ("button_001", "button_050", "axis_slider"):
            check(
                MuslimSimStudio._learned_source(stub, key) == key,
                f"{device}.{key} must be a valid mapping source",
            )

    check(
        counts["moza_ab6"] == counts["moza_a210"],
        "both bases share one captured report and must offer the same "
        f"controls; got AB6 {counts['moza_ab6']} vs A210 {counts['moza_a210']}",
    )
    check(
        counts["moza_ab6"] == 137,
        f"the AB6 must offer all 137 captured inputs, got {counts['moza_ab6']}",
    )

    source = (
        Path(__file__).resolve().parents[1]
        / "muslimsim" / "gui" / "studio.py"
    ).read_text(encoding="utf-8")
    check(
        '"axis_x": {"label": "X axis visual practice pose"' not in source,
        "the AB6's three placeholder practice-pose controls must be gone",
    )
    check(
        'elif self._selected_device == "moza_a210" and selected in' not in source,
        "an AB6 selection must get the same capture-proven description",
    )
    check(
        "An AB6 preset provides settings, not a verified HID identity"
        not in source,
        "the AB6 has a verified HID identity now and must not claim otherwise",
    )


def test_panel_faults_name_their_location() -> None:
    """A swallowed panel fault must be actionable, not just a class name."""

    from muslimsim.gui.studio import MuslimSimStudio

    try:
        {"axis_x": 1}["axis_rx"]
    except KeyError as exc:
        described = MuslimSimStudio._panel_fault_location(exc)

    check(
        "KeyError" in described and "axis_rx" in described,
        f"the fault must name its type and value, got {described!r}",
    )
    check(
        ":" in described and "[" in described,
        f"the fault must name a file and line, got {described!r}",
    )


def test_connection_banner_is_retired_when_the_poll_recovers() -> None:
    """A transient banner must not outlive the failure that raised it.

    Three failed status polls during bridge startup - 0.3 s at ten polls a
    second - raised "Hardware is still connected; waiting for its live
    update". `_receive_status` reset the failure counter but never the footer
    text, so that line stayed on screen for the rest of the session however
    healthy the bridge became.
    """

    import re
    from muslimsim.gui import studio as studio_module
    from muslimsim.gui.studio import MuslimSimStudio

    class _Var:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    class _Stub:
        pass

    # Every banner the UI can raise must be one the UI can also clear.
    for banner in (
        studio_module.BANNER_WAITING_UPDATE,
        studio_module.BANNER_STILL_CONNECTED,
        studio_module.BANNER_SERVICE_STOPPED,
    ):
        check(
            banner in studio_module.CONNECTION_BANNERS,
            f"{banner!r} can be raised but not cleared",
        )
        stub = _Stub()
        stub.footer = _Var(banner)
        MuslimSimStudio._clear_connection_banner(stub)
        check(
            stub.footer.get() == studio_module.CONNECTION_RECOVERED_FOOTER,
            f"a recovered poll must retire {banner!r}",
        )

    # A message the owner still needs must survive an unrelated recovery.
    for keep in (
        "Throttle output test sent through the bridge.",
        "Panel update recovered: KeyError: 'axis_rx'  [studio.py:4269 in x]",
    ):
        stub = _Stub()
        stub.footer = _Var(keep)
        MuslimSimStudio._clear_connection_banner(stub)
        check(
            stub.footer.get() == keep,
            f"clearing a banner must not discard {keep!r}",
        )

    # The text lives in one place, so it cannot drift out of that tuple.
    source = (
        Path(__file__).resolve().parents[1]
        / "muslimsim" / "gui" / "studio.py"
    ).read_text(encoding="utf-8")
    stragglers = re.findall(
        r'self\.footer\.set\("(?:Waiting for the latest|Hardware is still|'
        r'Hardware service stopped)[^"]*"\)',
        source,
    )
    check(
        not stragglers,
        f"banner text must come from the named constants, found {stragglers}",
    )
    check(
        "if self._control_failures:" in source
        and "self._clear_connection_banner()" in source,
        "a successful status poll must clear the banner, not just the counter",
    )


def main() -> None:
    test_identity_is_captured_not_guessed()
    test_input_collection_matches_the_captured_descriptor()
    test_axis_motion_observation_is_recorded()
    test_no_force_feedback_output_was_invented()
    test_product_registry_resolves_one_ab6()
    test_power_cycle_identity_is_registered()
    test_captured_frame_decodes()
    test_capture_tool_is_read_only()
    test_studio_ab6_page_reads_the_ab6()
    test_partial_axis_seed_cannot_blank_the_panel()
    test_every_captured_control_can_be_assigned()
    test_panel_faults_name_their_location()
    test_connection_banner_is_retired_when_the_poll_recovers()
    print(
        f"MOZA AB6 capture self-test passed: {CHECKS} checks. "
        "Identity 346E:1002 and the 34-byte report-01 input collection are "
        "captured from the base itself, the physical legends stay honestly "
        "numbered, and no force-feedback output was invented. "
        "No hardware or simulator touched."
    )


if __name__ == "__main__":
    main()
