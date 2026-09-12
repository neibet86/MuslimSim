"""MuslimSim application launcher.

This file owns project-level choices.  The hardware engine continues to own
the already-proven X-Plane, COM, HID, and rendering work until each device is
migrated and verified independently.
"""

from __future__ import annotations

import argparse
from typing import Iterable, Sequence

from .core.engine import BridgeEngineError, describe_engine, run_engine
from .core.profiles import DeviceSelection
from .devices import agp, pdc, pedals, pfp, pu_overhead, winctrl


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="MuslimSim",
        description=(
            "Modular launcher for the MuslimSim WinCtrl / PU Overhead bridge. "
            "All unrecognised options are passed to the proven final.py engine."
        ),
    )
    parser.add_argument(
        "--with-pfd",
        action="store_true",
        help="Enable the WinCtrl PFP captain PFD page.",
    )
    parser.add_argument(
        "--without-pfp",
        action="store_true",
        help="Keep the PFP in its normal keypad/display mode.",
    )
    parser.add_argument(
        "--without-winctrl",
        action="store_true",
        help=(
            "Disable WinCtrl throttle, AGP, PFP, PAP3, and PDC handling; "
            "pedals stay separate."
        ),
    )
    parser.add_argument(
        "--without-pdc",
        action="store_true",
        help="Disable only the separate WINCTRL PDC / EFIS BB62 manager.",
    )
    parser.add_argument(
        "--without-pedals",
        action="store_true",
        help="Disable WinCtrl rudder-pedal yaw and independent toe-brake input.",
    )
    parser.add_argument(
        "--without-agp",
        action="store_true",
        help="Leave WinCtrl controls active but disable the AGP display worker.",
    )
    parser.add_argument(
        "--without-pu-lights",
        action="store_true",
        help="Keep PU controls active but disable live P7 annunciator polling.",
    )
    parser.add_argument(
        "--show-devices",
        action="store_true",
        help="Print the device modules and then start normally.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the launcher layout without connecting to X-Plane or hardware.",
    )
    parser.add_argument(
        "--bridge-help",
        action="store_true",
        help="Show the full legacy bridge options, including --port and self-tests.",
    )
    return parser


def _selection_from_args(args: argparse.Namespace) -> DeviceSelection:
    return DeviceSelection(
        pu_lights=not args.without_pu_lights,
        winctrl=not args.without_winctrl,
        pedals=not args.without_pedals,
        agp=not args.without_winctrl and not args.without_agp,
        pfp=args.with_pfd and not args.without_pfp and not args.without_winctrl,
        pdc=not args.without_winctrl and not args.without_pdc,
    )


def _dedupe_flags(arguments: Iterable[str]) -> list[str]:
    """Keep user-supplied values in order while avoiding duplicate switches."""
    result: list[str] = []
    seen: set[str] = set()
    for argument in arguments:
        if argument in seen and argument.startswith("--"):
            continue
        result.append(argument)
        if argument.startswith("--"):
            seen.add(argument)
    return result


def _build_engine_args(selection: DeviceSelection, forwarded: Sequence[str]) -> list[str]:
    arguments = list(forwarded)
    arguments = pu_overhead.apply(selection, arguments)
    arguments = winctrl.apply(selection, arguments)
    arguments = pedals.apply(selection, arguments)
    arguments = agp.apply(selection, arguments)
    arguments = pfp.apply(selection, arguments)
    arguments = pdc.apply(selection, arguments)
    return _dedupe_flags(arguments)


def _print_devices(selection: DeviceSelection) -> None:
    print("MuslimSim device modules")
    print("------------------------")
    for module, enabled in (
        (pu_overhead, selection.pu_lights),
        (winctrl, selection.winctrl),
        (pdc, selection.pdc),
        (pedals, selection.pedals),
        (agp, selection.agp),
        (pfp, selection.pfp),
    ):
        state = "enabled" if enabled else "disabled"
        print(f"{state:8s} {module.DESCRIPTOR.title}: {module.DESCRIPTOR.purpose}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    project_args, forwarded = parser.parse_known_args(argv)

    if project_args.bridge_help:
        try:
            return run_engine(["--help"])
        except BridgeEngineError as exc:
            parser.error(str(exc))

    selection = _selection_from_args(project_args)

    if project_args.check:
        try:
            print(describe_engine())
        except BridgeEngineError as exc:
            print(f"CHECK FAILED: {exc}")
            return 2
        _print_devices(selection)
        print("Check passed.  No simulator, serial port, WinCtrl, or PU hardware was opened.")
        return 0

    if project_args.show_devices:
        _print_devices(selection)
        print()

    engine_args = _build_engine_args(selection, forwarded)
    try:
        return run_engine(engine_args)
    except BridgeEngineError as exc:
        print(f"MuslimSim launcher error: {exc}")
        return 2
