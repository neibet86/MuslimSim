#!/usr/bin/env python3
"""Lock the Studio live-feedback contract so no later change can remove it.

Studio showing physical movement - a yoke, a throttle, a switch, a knob, a
rotary - is a feature of MuslimSim, not an implementation detail of one device.

It broke once, silently.  A single slow device ``status`` callback pushed the
whole status reply past the control client's timeout, so every poll failed,
``self._lab`` was never refreshed, and the UI stopped showing physical input
while the device list stayed on screen.  Nothing raised and nothing was logged
as an error, which is exactly why this file exists.

Three contracts are enforced:

1. A physical input recorded by the bridge reaches the Studio mirror.
2. *Every* catalogued device that has an implemented input posts live feedback.
   This reads the catalogue instead of a hand-written list, so a device adopted
   in the future inherits the requirement the day it is added.
3. A status reply stays inside the poll budget even when a device driver is
   slow, and the control client keeps a margin over it.

Offline: no hardware, no simulator, no socket, and a temporary profile and
database so the owner's real hardware profile and platform data are untouched.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from time import perf_counter, sleep


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.platform.bootstrap import install_bridge_hooks
from muslimsim.platform.studio_hooks import _merge_inputs

install_bridge_hooks()

from muslimsim.control.server import ControlServer, DeviceRegistration
from muslimsim.gui.live_feedback import compose_live_mirror
from muslimsim.hardware.catalog import ALL_HARDWARE
from muslimsim.hardware.lab import HardwareLab
from muslimsim.hardware.profiles import HardwareProfileStore


# A driver this slow must never be able to delay a status reply again.
SLOW_CALLBACK_SECONDS = 1.5
# A warm status reply has to be far quicker than Studio's 0.10 s poll interval.
WARM_STATUS_BUDGET_SECONDS = 0.25
# The control client must keep real headroom over a status reply.
MINIMUM_CLIENT_TIMEOUT_SECONDS = 5.0


def _new_lab(root):
    """A lab on a throwaway profile, so the owner's real profile is untouched."""

    store = HardwareProfileStore(root / "hardware_profiles.json")
    store.load()
    return HardwareLab(store)


def _close(lab):
    """Release the platform runtime so Windows can delete the temporary database."""

    try:
        from muslimsim.platform.bootstrap import runtime_for

        runtime = runtime_for(lab, create=False)
        if runtime is not None:
            runtime.close()
    except Exception:
        pass


def _first_implemented_input(device):
    for control in device.controls:
        if control.is_input and control.status == "implemented":
            return control
    return None


def contract_physical_input_reaches_the_studio_mirror():
    """The whole path, end to end, for one device."""

    with TemporaryDirectory(prefix="muslimsim-live-feedback-", ignore_cleanup_errors=True) as temporary:
        lab = _new_lab(Path(temporary))

        device = next(d for d in ALL_HARDWARE if _first_implemented_input(d))
        control = _first_implemented_input(device)
        lab.input(device.key, control.key, 1, phase="press", source="physical")

        snapshot = lab.snapshot()

        recorded = (snapshot.get("inputs") or {}).get(device.key) or {}
        assert control.key in recorded, (
            "%s.%s: a physical input was not recorded in lab.snapshot()['inputs']. "
            "Studio draws movement from this." % (device.key, control.key)
        )
        assert str(recorded[control.key].get("source")) == "physical", (
            "The recorded sample lost its physical source marking."
        )

        platform = snapshot.get("platform")
        assert isinstance(platform, dict), (
            "lab.snapshot() no longer carries the 'platform' block. The Studio "
            "hook merges live telemetry from it; without it the merge is skipped."
        )
        latest = ((platform.get("telemetry") or {}).get("latest") or {}).get(device.key) or {}
        assert control.key in latest, (
            "%s.%s is missing from platform telemetry 'latest'." % (device.key, control.key)
        )

        # The Studio consumer half.
        response = {"lab": dict(snapshot), "platform": platform}
        _merge_inputs(response, platform)
        merged = ((response.get("lab") or {}).get("inputs") or {}).get(device.key) or {}
        assert control.key in merged, "The Studio telemetry merge dropped the sample."

        mirror = compose_live_mirror(device.key, {}, response["lab"])
        values = mirror.get("input_values") or {}
        assert control.key in values, (
            "compose_live_mirror() produced no input_values entry for %s.%s; "
            "the faceplate would render nothing." % (device.key, control.key)
        )
        _close(lab)

    print("  [ok] a physical input reaches the Studio mirror end to end")


def contract_every_input_device_posts_live():
    """Every catalogued input device - including ones adopted later - must post."""

    with TemporaryDirectory(prefix="muslimsim-live-feedback-all-", ignore_cleanup_errors=True) as temporary:
        lab = _new_lab(Path(temporary))

        covered = []
        missing = []
        for device in ALL_HARDWARE:
            control = _first_implemented_input(device)
            if control is None:
                # No implemented input yet: nothing to post, and this test must
                # not invent a mapping for an uncaptured device.
                continue
            try:
                lab.input(device.key, control.key, 1, phase="press", source="physical")
            except Exception as exc:  # a new device must not break the contract
                missing.append(
                    "%s.%s: lab.input raised %r" % (device.key, control.key, exc)
                )
                continue
            snapshot = lab.snapshot()
            mirror = compose_live_mirror(device.key, {}, snapshot)
            if control.key not in (mirror.get("input_values") or {}):
                missing.append(
                    "%s.%s: recorded but absent from compose_live_mirror()"
                    "['input_values']" % (device.key, control.key)
                )
                continue
            covered.append(device.key)

        assert covered, "No catalogued device has an implemented input control."
        assert not missing, (
            "These devices do not post live feedback to Studio:\n    "
            + "\n    ".join(missing)
            + "\n\nEvery device adopted into MuslimSim Studio must post live "
            "physical feedback. Route its input through HardwareLab.input with "
            "source='physical' rather than a private path."
        )
        _close(lab)

    print("  [ok] all %d catalogued input devices post live feedback" % len(covered))


def contract_status_stays_inside_the_poll_budget():
    """A slow driver must not be able to delay the status reply again."""

    with TemporaryDirectory(prefix="muslimsim-live-feedback-status-", ignore_cleanup_errors=True) as temporary:
        lab = _new_lab(Path(temporary))
        server = ControlServer(lab, token="live-feedback-contract")

        device = next(d for d in ALL_HARDWARE if _first_implemented_input(d))

        def slow_status():
            sleep(SLOW_CALLBACK_SECONDS)
            return {"state": "running", "detail": "deliberately slow driver"}

        server.register(DeviceRegistration(key=device.key, status=slow_status))
        request = {"cmd": "status", "token": server.token}

        server.handle(request)  # the first reply may collect synchronously

        started = perf_counter()
        response = server.handle(request)
        warm = perf_counter() - started

        assert response.get("ok") is True, "A warm status reply was not ok."
        assert device.key in (response.get("devices") or {}), (
            "Caching device status must not drop the device from the reply."
        )
        assert warm < WARM_STATUS_BUDGET_SECONDS, (
            "A warm status reply took %.3fs with one %.1fs driver, over the %.2fs "
            "budget. Device status must be collected off the request path, or "
            "every Studio poll times out and live feedback silently stops."
            % (warm, SLOW_CALLBACK_SECONDS, WARM_STATUS_BUDGET_SECONDS)
        )
        _close(lab)

    print("  [ok] a %.1fs driver leaves status warm at %.3fs" % (SLOW_CALLBACK_SECONDS, warm))


def contract_control_client_keeps_timeout_margin():
    """Studio's client must keep headroom over a status reply."""

    source = (PROJECT / "muslimsim" / "gui" / "supervisor.py").read_text(encoding="utf-8")
    found = re.search(r"ControlClient\([^)]*timeout=([0-9.]+)", source)
    assert found, "supervisor.py no longer builds its ControlClient with a timeout."
    timeout = float(found.group(1))
    assert timeout >= MINIMUM_CLIENT_TIMEOUT_SECONDS, (
        "The Studio control client timeout is %ss, under the %ss minimum. It was "
        "3.0s once while a status reply took 3.05s, so every poll failed and live "
        "feedback died with no error shown."
        % (timeout, MINIMUM_CLIENT_TIMEOUT_SECONDS)
    )

    print("  [ok] Studio control client keeps a %ss timeout" % timeout)


def contract_studio_consumes_the_bridge_lab():
    """Studio must still read the bridge lab and the V7 telemetry hook."""

    from muslimsim.gui.studio import MuslimSimStudio

    assert callable(getattr(MuslimSimStudio, "_receive_status", None)), (
        "Studio lost _receive_status; nothing would assign self._lab."
    )
    assert callable(getattr(MuslimSimStudio, "_device_mirror", None)), (
        "Studio lost _device_mirror; faceplates would have no values to draw."
    )
    assert getattr(MuslimSimStudio, "_muslimsim_platform_v7", False) is True, (
        "The Platform V7 Studio hook is not installed on MuslimSimStudio. It is "
        "wrapped in a bare except that stores the error and continues, so a "
        "failure here is invisible at runtime."
    )

    print("  [ok] Studio still consumes the bridge lab and the V7 telemetry hook")


def contract_a_failed_hook_is_not_silent():
    """A hook that fails to install must say so, not just store the error."""

    studio = (PROJECT / "muslimsim" / "gui" / "studio.py").read_text(encoding="utf-8")

    assert "_MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR" in studio, (
        "The Platform V7 Studio hook no longer records why it failed."
    )
    # The error must be read somewhere, not only assigned. It is installed
    # inside a bare except that continues on failure, so without a reader the
    # telemetry merge can vanish and nothing tells the owner.
    reported = re.search(
        r"if\s+_MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR\s+is not None\s*:",
        studio,
    )
    assert reported, (
        "Nothing reads _MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR. The V7 hook merges "
        "the bridge telemetry that drives live physical feedback; if it fails to "
        "install, the error is stored and execution continues, so the panel "
        "silently stops animating with no message anywhere."
    )

    bridge = (PROJECT / "bridge" / "final.py").read_text(encoding="utf-8", errors="replace")
    for name, why in (
        ("MuslimSim Platform V7 bootstrap unavailable",
         "the bridge would publish no platform telemetry block"),
        ("MuslimSim device lifecycle unavailable",
         "USB plug/unplug tracking would be inert"),
    ):
        assert name in bridge, (
            "bridge/final.py no longer warns when a startup import fails, so %s "
            "with nothing shown to the owner." % why
        )

    print("  [ok] a failed telemetry hook or lifecycle import is reported, not swallowed")


def main():
    print("Live-feedback contract:")
    contract_physical_input_reaches_the_studio_mirror()
    contract_every_input_device_posts_live()
    contract_status_stays_inside_the_poll_budget()
    contract_control_client_keeps_timeout_margin()
    contract_studio_consumes_the_bridge_lab()
    contract_a_failed_hook_is_not_silent()
    print("Studio live-feedback contract test passed.")


if __name__ == "__main__":
    main()
