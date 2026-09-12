"""Checks for the control panel that need no hardware and no simulator.

The panel is the piece most likely to drift: it is generated from the device
catalogue, and a catalogue entry with a flag the launcher rewrites, or a
dependency naming a device that does not exist, fails silently -- the button
is simply there and does nothing.  These assertions catch that at the desk
rather than in the cockpit.

Run with:
    python muslimsim_panel.py --check
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Callable, List, Tuple

from ..hardware import catalog, usb
from ..hardware.catalog import GLOBAL_OPTIONS, Option
from .settings import Settings, apply_starter_profiles

Check = Tuple[str, Callable[[], None]]


class CheckFailed(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------


def check_catalogue_is_consistent() -> None:
    keys = [device.key for device in catalog.DEVICES]
    _require(len(keys) == len(set(keys)), f"duplicate device keys: {keys}")

    usb_ids: dict = {}

    for device in catalog.DEVICES:
        if not device.detectable():
            continue

        pair = (device.vid, device.pid)
        _require(
            pair not in usb_ids,
            f"{device.key} and {usb_ids.get(pair)} share {device.usb_id}",
        )
        usb_ids[pair] = device.key

    for device in catalog.DEVICES:
        for parent in device.requires:
            _require(
                parent in catalog.DEVICES_BY_KEY,
                f"{device.key} requires unknown device {parent!r}",
            )
            _require(
                parent != device.key,
                f"{device.key} requires itself",
            )


def check_options_are_well_formed() -> None:
    valid = {"bool", "float", "int", "choice", "text"}

    def inspect(option: Option, owner: str) -> None:
        _require(
            option.kind in valid,
            f"{owner}: option {option.flag} has unknown kind {option.kind!r}",
        )
        _require(
            option.flag.startswith("--"),
            f"{owner}: option {option.flag} is not a long flag",
        )

        if option.kind == "choice":
            _require(
                bool(option.choices),
                f"{owner}: choice option {option.flag} lists no choices",
            )
            _require(
                option.default in option.choices,
                f"{owner}: {option.flag} default {option.default!r} "
                "is not among its choices",
            )

        if option.kind in ("float", "int") and option.minimum is not None:
            _require(
                option.maximum is not None and option.maximum > option.minimum,
                f"{owner}: {option.flag} has an empty range",
            )

            if option.default is not None:
                _require(
                    option.minimum <= float(option.default) <= option.maximum,
                    f"{owner}: {option.flag} default {option.default} "
                    "is outside its own range",
                )

    for device in catalog.DEVICES:
        seen = set()

        for option in device.options:
            _require(
                option.flag not in seen,
                f"{device.key}: option {option.flag} is listed twice",
            )
            seen.add(option.flag)
            inspect(option, device.key)

    for option in GLOBAL_OPTIONS:
        inspect(option, "globals")


def check_clamping_holds() -> None:
    for device in catalog.DEVICES:
        for option in device.options:
            if option.kind not in ("float", "int") or option.minimum is None:
                continue

            low = option.clamp(option.minimum - 1000)
            high = option.clamp(option.maximum + 1000)

            _require(
                low >= option.minimum,
                f"{device.key}: {option.flag} clamped below its minimum",
            )
            _require(
                high <= option.maximum,
                f"{device.key}: {option.flag} clamped above its maximum",
            )
            _require(
                option.clamp("not a number") == option.default,
                f"{device.key}: {option.flag} did not fall back on bad input",
            )


# --------------------------------------------------------------------------
# Settings and the command line
# --------------------------------------------------------------------------


def check_settings_round_trip() -> None:
    settings = Settings.defaults()
    settings.enabled["pfp"] = True
    settings.extra_arguments = "--diagnose-controls"

    for device in catalog.implemented():
        for option in device.options:
            if option.kind == "float" and option.minimum is not None:
                settings.set_option(device.key, option, option.minimum)

    restored = Settings.from_dict(settings.to_dict())

    _require(restored.enabled == settings.enabled, "enabled flags did not survive")
    _require(
        restored.extra_arguments == settings.extra_arguments,
        "extra arguments did not survive",
    )
    _require(restored.options == settings.options, "options did not survive")


def check_dependencies_are_enforced() -> None:
    settings = Settings.defaults()
    settings.enabled["winctrl"] = False
    settings.enabled["pfp"] = True

    _require(
        not settings.is_enabled("pfp"),
        "a device stayed enabled while its parent was off",
    )
    _require(
        "winctrl" in settings.blocked_by("pfp"),
        "blocked_by did not name the disabled parent",
    )


def check_arguments_survive_the_launcher() -> None:
    """The launcher rewrites some flags; make sure ours come out intact.

    `muslimsim/devices/pfp.py` strips a bare `--pfp-pfd` unless the launcher's
    own `--with-pfd` was given, so a catalogue that emitted the engine flag
    would be silently discarded.  This is that bug, made permanent.
    """
    from ..app import _build_engine_args, _build_parser, _selection_from_args

    settings = Settings.defaults()
    settings.enabled["pfp"] = True

    arguments = settings.build_arguments()
    parsed, forwarded = _build_parser().parse_known_args(arguments)
    selection = _selection_from_args(parsed)
    engine = _build_engine_args(selection, forwarded)

    _require(
        "--pfp-pfd" in engine,
        "enabling the PFP did not reach the engine as --pfp-pfd; "
        f"got {engine}",
    )

    settings.enabled["pfp"] = False
    arguments = settings.build_arguments()
    parsed, forwarded = _build_parser().parse_known_args(arguments)
    engine = _build_engine_args(_selection_from_args(parsed), forwarded)

    _require(
        "--pfp-pfd" not in engine,
        f"disabling the PFP still produced --pfp-pfd: {engine}",
    )


def check_disable_flags_are_understood() -> None:
    """Every flag the panel can emit must be one the bridge or launcher takes.

    The launcher's flags are read from its own argparse parser rather than
    from its source text, because a built executable has no .py files on
    disk -- scanning source worked from a checkout and failed in the exe,
    which is the wrong way round for a check meant to catch shipping bugs.

    The engine's parser is built inside its `main()`, so its flags still come
    from the file; it is bundled as data precisely because it is loaded by
    path at runtime.
    """
    import re

    from ..app import _build_parser
    from .paths import bridge_path

    known: set[str] = set()

    # The launcher, from the parser itself.
    for action in _build_parser()._actions:
        known.update(action.option_strings)

    # The engine, from its source: its parser is not reachable without
    # running main().
    try:
        engine_text = bridge_path().read_text(encoding="utf-8", errors="replace")
        known |= set(re.findall(r'"(--[a-z0-9\-]+)"', engine_text))
    except OSError as exc:
        raise CheckFailed(
            f"the bridge could not be read at {bridge_path()}: {exc}.  "
            "In a built exe this means it was not bundled."
        )

    emitted: List[str] = []

    for device in catalog.implemented():
        for flag in (device.enable_flag, device.disable_flag,
                     device.diagnose_flag):
            if flag:
                emitted.append(flag)

        emitted.extend(option.flag for option in device.options)

    emitted.extend(option.flag for option in GLOBAL_OPTIONS)

    unknown = sorted({flag for flag in emitted if flag not in known})

    _require(
        not unknown,
        "the panel can emit flags nothing accepts: " + ", ".join(unknown),
    )


def check_profiles_seed_and_load() -> None:
    settings = Settings.defaults()
    apply_starter_profiles(settings)

    _require(settings.profiles, "no starter profiles were seeded")

    for name in list(settings.profiles):
        _require(settings.load_profile(name), f"profile {name!r} would not load")
        settings.build_arguments()


# --------------------------------------------------------------------------
# Control channel and supervisor
# --------------------------------------------------------------------------


def check_control_channel_round_trip() -> None:
    from ..control.client import ControlClient
    from ..control.protocol import new_token
    from ..control.server import ControlServer

    events: List[str] = []

    class Fake:
        def __init__(self) -> None:
            self.alive = True

        def start(self) -> None:
            events.append("start")
            self.alive = True

        def stop(self) -> None:
            events.append("stop")
            self.alive = False

        @property
        def status(self) -> str:
            return "running" if self.alive else "stopped"

    fake = Fake()
    token = new_token()
    server = ControlServer(token, port=0)
    server.register("mcdu", start=fake.start, stop=fake.stop,
                    status=lambda: fake.status)

    port = server.start()

    try:
        client = ControlClient(token, port=port)
        _require(client.ping(), "the control channel did not answer a ping")

        ok, _detail = client.restart_device("mcdu")
        _require(ok, "restart was refused")
        _require(events == ["stop", "start"],
                 f"restart did not stop then start: {events}")

        ok, _detail = client.restart_device("nonexistent")
        _require(not ok, "an unknown device was accepted")

        intruder = ControlClient("wrong", port=port)
        _require(not intruder.ping(), "a bad token was accepted")

        ok, _detail = intruder.restart_device("mcdu")
        _require(not ok, "a bad token could restart a device")
        _require(events == ["stop", "start"],
                 "a rejected caller still reached the device")
    finally:
        server.stop()


def check_supervisor_builds_a_command() -> None:
    from .supervisor import BridgeSupervisor

    from .paths import RUN_BRIDGE_FLAG, is_frozen, resources

    supervisor = BridgeSupervisor(resources())
    command = supervisor.build_command(["--with-pfd"], "token123")

    if is_frozen():
        # A built exe has no interpreter to call, so it re-runs itself.
        _require(
            RUN_BRIDGE_FLAG in command,
            f"the frozen build does not start the bridge with "
            f"{RUN_BRIDGE_FLAG}: {command}",
        )
    else:
        _require("launch.py" in " ".join(command), "the launcher is not invoked")

    _require("--with-pfd" in command, "the caller's arguments were dropped")
    _require(
        any(part.startswith("--control-port=") for part in command),
        "the control port is not passed in `=` form, which argparse needs "
        "for a negative value",
    )
    _require(
        "--control-token=token123" in command,
        "the control token is not passed",
    )


def check_usb_layer_is_safe_without_hardware() -> None:
    """Nothing in the USB layer may raise when a device is absent."""
    _require(usb.present(0x0000, 0x0000) is False,
             "presence of a nonexistent device was not False")

    result = usb.reset_device(None, None)
    _require(not result.ok, "resetting a non-USB device claimed success")

    for device in catalog.DEVICES:
        if device.detectable():
            usb.present(device.vid, device.pid)


def check_reset_never_claims_a_success_it_cannot_have() -> None:
    """A power cycle must not report success it did not achieve.

    Measured on Windows: `pnputil /restart-device` exits 0 without elevation
    and does nothing -- the device never leaves the bus.  Trusting that exit
    code would tell the user a display had been power-cycled when it had not.
    Unelevated, the answer must be a refusal that asks for Administrator.
    """
    if not usb.is_windows() or usb.is_admin():
        return

    for device in catalog.DEVICES:
        if not device.detectable() or not usb.present(device.vid, device.pid):
            continue

        result = usb.reset_device(device.vid, device.pid)

        _require(
            not result.ok,
            f"{device.key}: an unelevated power cycle claimed success",
        )
        _require(
            result.needs_admin,
            f"{device.key}: the refusal did not ask for Administrator",
        )
        return


def check_disable_switches_are_real() -> None:
    """A device the panel lets you switch off must have a flag that does it.

    Without this the checkbox is a lie: the card draws "disabled" while the
    bridge's own output shows the device starting up.
    """
    settings = Settings.defaults()

    for device in catalog.implemented():
        if device.can_disable:
            continue

        settings.enabled[device.key] = False
        arguments = settings.build_arguments()
        settings.enabled[device.key] = True

        _require(
            device.enable_flag is None and device.disable_flag is None,
            f"{device.key}: can_disable disagrees with its own flags",
        )
        _require(
            not any(
                flag in arguments
                for flag in (device.enable_flag, device.disable_flag)
                if flag
            ),
            f"{device.key}: emitted a toggle flag it does not have",
        )


def check_bundled_files_are_present() -> None:
    """The files loaded by path must exist wherever we are running.

    `bridge/final.py` and the display renderer's frame emulator are opened by
    filename, not imported, so PyInstaller's dependency analysis cannot see
    them.  If they are missing from a build, the bridge will not start and
    the display mirror will stay blank -- with no obvious cause.
    """
    from .paths import bridge_path, resources

    required = [
        bridge_path(),
        resources() / "tools" / "render_pfp_frame_png.py",
    ]

    missing = [str(path) for path in required if not path.is_file()]

    _require(
        not missing,
        "files loaded by path are missing from this build: "
        + ", ".join(missing),
    )


def check_throttle_split_is_safe() -> None:
    """The below-idle split must never command thrust the pilot did not ask for.

    This is the one calibration on the machine that can move the aeroplane by
    itself.  Three properties matter, and all three were breakable:

      * at the measured IDLE detent, forward thrust is exactly zero -- the
        hard-coded values gave 1.85% here on this hardware;
      * below IDLE, forward thrust stays zero, whatever the reverse handle
        is doing;
      * reverse is inert until the matching reverse handle is raised.
    """
    from ..hardware.throttle import LeverCalibration, mapping_error, outputs

    if mapping_error():
        raise CheckFailed(
            f"the bridge's throttle mapping could not be loaded: {mapping_error()}"
        )

    lever = LeverCalibration(idle_raw=20165, rev_idle_raw=14115)

    forward, reverse = outputs(lever.idle_raw, lever, reverse_active=False)
    _require(
        forward == 0.0,
        f"at the IDLE detent the lever commanded {forward:.4%} thrust",
    )
    _require(reverse == 0.0, "at the IDLE detent the lever commanded reverse")

    for raw in (lever.idle_raw - 1, lever.rev_idle_raw, 0):
        for handle in (False, True):
            forward, _reverse = outputs(raw, lever, reverse_active=handle)
            _require(
                forward == 0.0,
                f"below IDLE (raw {raw}, handle {'up' if handle else 'down'}) "
                f"the lever commanded {forward:.4%} thrust",
            )

    for raw in (lever.idle_raw - 1, lever.rev_idle_raw, 0):
        _, reverse = outputs(raw, lever, reverse_active=False)
        _require(
            reverse == 0.0,
            f"raw {raw} produced reverse {reverse} with the handle down",
        )

    _, gate = outputs(lever.rev_idle_raw, lever, reverse_active=True)
    _, full = outputs(0, lever, reverse_active=True)
    _require(0.0 < gate < full, "the reverse band does not increase to full")
    _require(
        abs(full - 1.0) < 1e-6,
        f"full reverse reached only {full}",
    )

    top, _ = outputs(lever.max_raw, lever, reverse_active=False)
    _require(abs(top - 1.0) < 1e-6, f"TOGA reached only {top:.4%} thrust")


def check_bad_throttle_calibration_is_not_emitted() -> None:
    """An impossible calibration must never reach the bridge."""
    from ..hardware.throttle import LeverCalibration

    settings = Settings.defaults()
    settings.enabled["winctrl"] = True

    # REV IDLE above IDLE: the bands would be inside out.
    settings.throttle.left = LeverCalibration(idle_raw=14000, rev_idle_raw=20000)
    settings.throttle.right = LeverCalibration(idle_raw=20165, rev_idle_raw=14115)
    settings.throttle.calibrated = True

    ok, _why = settings.throttle.valid()
    _require(not ok, "an inside-out calibration was accepted as valid")

    arguments = settings.build_arguments()
    _require(
        not any(a.startswith("--throttle-") for a in arguments),
        f"an invalid throttle calibration was passed to the bridge: {arguments}",
    )

    settings.throttle.left = LeverCalibration(idle_raw=20165, rev_idle_raw=14115)
    arguments = settings.build_arguments()
    _require(
        "--throttle-left-idle" in arguments and "20165" in arguments,
        f"a valid calibration was not passed to the bridge: {arguments}",
    )


CHECKS: List[Check] = [
    ("catalogue is consistent", check_catalogue_is_consistent),
    ("disable switches are real", check_disable_switches_are_real),
    ("options are well formed", check_options_are_well_formed),
    ("option clamping holds", check_clamping_holds),
    ("settings round-trip", check_settings_round_trip),
    ("dependencies are enforced", check_dependencies_are_enforced),
    ("arguments survive the launcher", check_arguments_survive_the_launcher),
    ("every emitted flag is understood", check_disable_flags_are_understood),
    ("profiles seed and load", check_profiles_seed_and_load),
    ("control channel round-trip", check_control_channel_round_trip),
    ("supervisor builds a command", check_supervisor_builds_a_command),
    ("files loaded by path are bundled", check_bundled_files_are_present),
    ("usb layer is safe without hardware", check_usb_layer_is_safe_without_hardware),
    ("reset never claims a false success", check_reset_never_claims_a_success_it_cannot_have),
    ("throttle split is safe", check_throttle_split_is_safe),
    ("bad throttle calibration is not emitted", check_bad_throttle_calibration_is_not_emitted),
]


def run(verbose: bool = True) -> int:
    failures = 0

    for name, check in CHECKS:
        try:
            check()
        except Exception as exc:
            failures += 1
            print(f"  FAIL  {name}")
            print(f"        {exc}")
        else:
            if verbose:
                print(f"  ok    {name}")

    print()

    if failures:
        print(f"{failures} of {len(CHECKS)} control-panel checks failed.")
        return 1

    print(
        f"Control panel self-test passed: {len(CHECKS)} checks, "
        "no hardware or simulator touched."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
