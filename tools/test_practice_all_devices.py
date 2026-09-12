"""Practice mode must make every device that can respond, respond.

Before this, only five of the seventeen catalogued devices posted anything at
all in Practice: pressing a control on any of the other twelve produced no
physical output, so there was no way to tell a working panel from a dead one
with the simulator off.

These checks run the real HardwareLab and the real
ControlServer.apply_practice_snapshot with apply_lab_output recorded, so they
assert the shipping path rather than a description of it.

No hardware, simulator, HID handle or profile file is opened or written.
"""

from __future__ import annotations

from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from muslimsim.control.server import ControlServer
from muslimsim.hardware.catalog import ALL_HARDWARE, device_by_key
from muslimsim.hardware.lab import HardwareLab, LabError
from muslimsim.hardware import practice_echo

CHECKS = 0


def check(condition: bool, description: str) -> None:
    global CHECKS
    if not condition:
        raise AssertionError(description)
    CHECKS += 1


class _Rig:
    """A lab wired to the real practice snapshot path, with writes recorded."""

    def __init__(self) -> None:
        self.lab = HardwareLab()
        self.written: list[tuple[str, str, object]] = []
        server = ControlServer.__new__(ControlServer)
        server._lock = threading.RLock()
        server._practice_signature = None
        server.apply_lab_output = self._record
        self.lab.set_practice_output_sink(server.apply_practice_snapshot)

    def _record(self, device_key, control_key, value, source="test"):
        self.written.append((str(device_key), str(control_key), value))

    def writes_for(self, device: str) -> dict:
        return {
            control: value
            for dev, control, value in self.written
            if dev == device
        }

    def first_input(self, device: str):
        spec = device_by_key(device)
        for control in spec.controls:
            if control.is_input and control.status == "implemented":
                return control.key
        return None


def test_every_driveable_device_posts() -> None:
    """Any device with a capture-proven indicator must light in Practice."""

    expected = practice_echo.devices_with_echo()

    # These five posted nothing whatsoever before: no practice page existed
    # for them, so their panels stayed dark however hard you pressed them.
    for device in (
        "pu_overhead", "ecam32", "winctrl_throttle",
        "muslimrtp_d201", "muslimatc_d203",
    ):
        check(
            device in expected,
            f"{device} used to post nothing in Practice and must now respond",
        )

    for device in expected:
        rig = _Rig()
        rig.lab.set_mode("test")
        control = rig.first_input(device)

        if control is not None:
            rig.lab.input(
                device, control, 1.0,
                phase="press", source="test", route=False,
            )
        else:
            # ECAM32 has no catalogued input yet; opening its page is the ask.
            rig.lab.practice_wake(device)

        lit = rig.writes_for(device)
        indicators = practice_echo.indicator_controls(device)
        check(
            bool(lit),
            f"{device} must post something when it is practised",
        )
        for indicator in indicators:
            check(
                lit.get(indicator) == practice_echo.PRACTICE_ECHO_ON,
                f"{device}.{indicator} must light when the device is practised",
            )


def test_page_open_wakes_a_device_without_inputs() -> None:
    """ECAM32 has 19 proven LEDs and no catalogued input at all."""

    rig = _Rig()
    rig.lab.set_mode("test")

    spec = device_by_key("ecam32")
    usable_inputs = [
        c for c in spec.controls
        if c.is_input and c.status == "implemented"
    ]
    check(
        not usable_inputs,
        "this check exists because ECAM32 has no catalogued input to press",
    )

    rig.lab.practice_wake("ecam32")
    lit = rig.writes_for("ecam32")
    check(
        len(lit) == 19,
        f"opening the ECAM32 page must light all 19 proven LEDs, got {len(lit)}",
    )
    check(
        all(value == practice_echo.PRACTICE_ECHO_ON for value in lit.values()),
        "every ECAM32 practice LED must be lit, not merely addressed",
    )


def test_devices_sleep_again_when_left_alone() -> None:
    """Rule 0.1: a tested output returns to OFF/BLACK when the test ends."""

    rig = _Rig()
    rig.lab.set_mode("test")
    rig.lab.practice_wake("pu_overhead")
    check(
        rig.writes_for("pu_overhead").get("panel_backlight")
        == practice_echo.PRACTICE_ECHO_ON,
        "the PU must light when its page is opened in Practice",
    )

    preview = rig.lab._practice_preview
    check(
        not preview.expire(now=__import__("time").monotonic()),
        "a device still being practised must not be put to sleep",
    )

    rig.written.clear()
    future = __import__("time").monotonic() + practice_echo.PRACTICE_IDLE_SLEEP_SECONDS + 1.0
    expired = preview.expire(now=future)
    check(
        "pu_overhead" in expired,
        "a device left alone past the idle timeout must be put to sleep",
    )

    rig.lab._darken_practice_devices(expired)
    dark = rig.writes_for("pu_overhead")
    check(bool(dark), "the sleeping device must receive an explicit dark frame")
    check(
        all(value == practice_echo.PRACTICE_ECHO_OFF for value in dark.values()),
        "every practice indicator must be driven to OFF when the device sleeps",
    )


def test_leaving_practice_darkens_everything() -> None:
    rig = _Rig()
    rig.lab.set_mode("test")
    rig.lab.practice_wake("pu_overhead")
    rig.lab.practice_wake("ecam32")

    rig.written.clear()
    rig.lab.set_mode("live")

    for device in ("pu_overhead", "ecam32"):
        dark = rig.writes_for(device)
        check(
            bool(dark),
            f"leaving Practice must darken {device}, not abandon it lit",
        )
        check(
            all(
                value == practice_echo.PRACTICE_ECHO_OFF
                for value in dark.values()
            ),
            f"{device} must be driven fully OFF when Practice ends",
        )


def test_practice_is_refused_outside_practice_mode() -> None:
    """Live mode must never be lit by the practice path."""

    rig = _Rig()
    check(rig.lab.mode == "live", "the lab must start in live mode")

    result = rig.lab.practice_wake("pu_overhead")
    check(
        result.get("awake") is False,
        "a practice wake must be refused while the lab is live",
    )
    check(
        not rig.writes_for("pu_overhead"),
        "a practice wake in Live mode must write nothing to the hardware",
    )

    control = rig.first_input("pu_overhead")
    rig.lab.input(
        "pu_overhead", control, 1.0,
        phase="press", source="test", route=False,
    )
    check(
        not rig.writes_for("pu_overhead"),
        "a Live-mode input must not drive the practice indicators",
    )


def test_practice_never_reaches_the_saved_profile() -> None:
    """The owner's rule: what you practise never passes to Live.

    Practice is an experiment sandbox.  Assignments are made in Live, and
    nothing exercised in Practice may quietly become a saved binding.
    """

    rig = _Rig()
    rig.lab.set_mode("test")

    check(
        rig.lab.profile_store is None,
        "this rig has no profile store, so any write attempt would raise",
    )

    for device in practice_echo.devices_with_echo():
        control = rig.first_input(device)
        if control is None:
            continue
        rig.lab.input(
            device, control, 1.0,
            phase="press", source="test", route=False,
        )
    rig.lab.practice_wake("ecam32")

    # The practice path records inputs/outputs and diagnostics only.  If it
    # ever learned a binding it would have to go through profile_store, and
    # the assertion above proves there is nothing for it to write into.
    source = Path(practice_echo.__file__).read_text(encoding="utf-8")
    check(
        "profile" not in source.lower().replace("profile_store", ""),
        "the practice echo policy must not reference saved profiles at all",
    )


def test_practice_never_actuates_or_guesses() -> None:
    """Only proven indicators, never motors, solenoids or guessed displays."""

    for item in ALL_HARDWARE:
        for control_key in practice_echo.indicator_controls(item.key):
            control = item.control(control_key)
            check(
                control.kind in practice_echo.PRACTICE_ECHO_KINDS,
                f"{item.key}.{control_key} is a {control.kind}; Practice drives "
                "only lamps and LEDs",
            )
            check(
                control.status == "implemented" and control.testable,
                f"{item.key}.{control_key} must be a capture-proven, testable "
                "output before Practice may drive it",
            )

    # The throttle's vibration motors and the PU's starter solenoid are the
    # cases this policy exists to exclude: Practice lights panels, it does
    # not shake or actuate hardware.
    throttle = practice_echo.indicator_controls("winctrl_throttle")
    check(
        "vibration_motor_1" not in throttle
        and "vibration_motor_2" not in throttle,
        "Practice must never drive the throttle vibration motors",
    )
    check(
        "engine_start_retract" not in practice_echo.indicator_controls("pu_overhead"),
        "Practice must never fire the PU starter retract solenoid",
    )
    check(
        "unmapped_vendor_output" not in practice_echo.indicator_controls("pdc_bb62"),
        "Practice must never drive an output whose protocol is unknown",
    )


def main() -> None:
    test_every_driveable_device_posts()
    test_page_open_wakes_a_device_without_inputs()
    test_devices_sleep_again_when_left_alone()
    test_leaving_practice_darkens_everything()
    test_practice_is_refused_outside_practice_mode()
    test_practice_never_reaches_the_saved_profile()
    test_practice_never_actuates_or_guesses()
    covered = practice_echo.devices_with_echo()
    print(
        f"Practice all-devices self-test passed: {CHECKS} checks. "
        f"{len(covered)} devices now respond to being practised, they sleep "
        "again when left alone, nothing is driven that is not a capture-proven "
        "lamp or LED, and nothing practised reaches the saved profile. "
        "No hardware or simulator touched."
    )


if __name__ == "__main__":
    main()
