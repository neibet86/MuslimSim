#!/usr/bin/env python3
"""Prove one aircraft's mappings and simulator traffic never reach another.

The owner's requirement, in three parts:

1. Every aircraft has its own controlling profile. A button mapped for one
   airframe is remembered for that airframe only.
2. Mappings may be reused only where the function provably exists on the other
   aircraft - never guessed across unrelated aircraft.
3. While an aircraft is loaded, nothing may command or request telemetry for a
   different aircraft.

Offline: no hardware, no simulator, no bridge process.  Part 3 is checked at
source level, because the guards it protects are inside the running bridge's
dispatch path and deleting them would otherwise be silent.
"""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui.supervisor import (
    SIMULATOR_MSFS24, SIMULATOR_XPLANE, default_profile_path,
)
from muslimsim.hardware.catalog import ALL_HARDWARE
from muslimsim.hardware.mapping_transfer import (
    copy_msfs24_bindings, seed_msfs24_profile,
)
from muslimsim.hardware.msfs24_aircraft import MSFS24_AIRCRAFT, msfs24_family
from muslimsim.hardware.msfs24_library import all_msfs24_functions
from muslimsim.hardware.profiles import HardwareProfileStore, MappingBinding

_XPLANE_AIRCRAFT = ("zibo", "levelup", "toliss", "c172ng")


def _remappable_control():
    """A real catalogued control a command may be bound to."""

    for device in ALL_HARDWARE:
        for control in device.controls:
            if (
                control.is_input
                and getattr(control, "remappable", False)
                and control.kind in {"button", "toggle", "selector"}
            ):
                return device.key, control.key
    raise AssertionError("No remappable button/toggle control in the catalogue")


def _family_target(family):
    """One real (kind, target) from a family. Fenix ships LVARs, PMDG commands."""

    for entry in all_msfs24_functions():
        if str(entry.get("aircraft") or "") != family:
            continue
        kind = str(entry.get("kind") or "")
        target = str(entry.get("target") or "").strip()
        if target and kind in {"command", "dataref"}:
            return kind, target
    raise AssertionError("No usable target for family %r" % family)


def _store(path):
    store = HardwareProfileStore(Path(path))
    store.load()
    return store


def check_every_aircraft_has_its_own_profile():
    """No two aircraft, in either simulator, may share a mapping file."""

    seen = {}
    for aircraft in _XPLANE_AIRCRAFT:
        path = default_profile_path(SIMULATOR_XPLANE, aircraft)
        assert path.name not in seen, (
            "X-Plane %s and %s share %s" % (aircraft, seen.get(path.name), path.name)
        )
        seen[path.name] = "xplane:" + aircraft
    for item in MSFS24_AIRCRAFT:
        path = default_profile_path(SIMULATOR_MSFS24, "zibo", item.key)
        assert path.name not in seen, (
            "MSFS %s collides with %s on %s" % (item.key, seen.get(path.name), path.name)
        )
        seen[path.name] = "msfs24:" + item.key
    print("  [ok] %d aircraft, every one with its own mapping profile" % len(seen))


def check_a_mapping_stays_on_its_own_aircraft():
    """Saving a binding for one airframe must not appear in another."""

    device_key, control_key = _remappable_control()
    with TemporaryDirectory(prefix="muslimsim-isolation-") as temporary:
        root = Path(temporary)
        fenix = root / "fenix.json"
        pmdg = root / "pmdg.json"

        source = _store(fenix)
        kind, target = _family_target(msfs24_family("fenix_a320"))
        source.set_binding(device_key, control_key, MappingBinding(
            kind=kind, target=target, simulator="msfs24",
        ))
        source.save()

        other = _store(pmdg)
        assert not other.has_binding(device_key, control_key), (
            "A mapping saved for the Fenix appeared in a different aircraft's profile."
        )
    print("  [ok] a mapping saved for one aircraft is absent from another")


def check_family_inheritance_then_independence():
    """Siblings inherit once, then diverge without touching each other."""

    device_key, control_key = _remappable_control()
    kind, target = _family_target(msfs24_family("fenix_a320"))
    with TemporaryDirectory(prefix="muslimsim-isolation-family-") as temporary:
        root = Path(temporary)
        a320 = root / "msfs24_fenix_a320.json"
        a321 = root / "msfs24_fenix_a321.json"

        source = _store(a320)
        source.set_binding(device_key, control_key, MappingBinding(
            kind=kind, target=target, simulator="msfs24",
        ))
        source.save()

        siblings = {item.key: root / ("msfs24_" + item.key + ".json") for item in MSFS24_AIRCRAFT}
        report = seed_msfs24_profile(a321, "fenix_a321", siblings)
        assert report is not None and report.get("copied"), (
            "A new Fenix A321 workspace did not inherit its A320 sibling's mappings."
        )
        assert _store(a321).has_binding(device_key, control_key), "Inheritance wrote nothing."

        # Seeding must never run twice, or it would overwrite real work.
        assert seed_msfs24_profile(a321, "fenix_a321", siblings) is None, (
            "Inheritance ran again on an existing workspace; it must run only once."
        )

        # Independence: change the A321, the A320 must not move.
        changed = _store(a321)
        changed.set_binding(device_key, control_key, MappingBinding())
        changed.save()
        assert _store(a320).binding(device_key, control_key).target == target, (
            "Editing the A321 changed the A320. Workspaces must stay independent "
            "after inheritance."
        )
    print("  [ok] family siblings inherit once, then stay independent")


def check_unrelated_aircraft_never_guess():
    """A function absent from the destination library must not transfer."""

    device_key, control_key = _remappable_control()
    fenix_kind, fenix_target = _family_target(msfs24_family("fenix_a320"))
    with TemporaryDirectory(prefix="muslimsim-isolation-cross-") as temporary:
        root = Path(temporary)
        source_path = root / "fenix.json"
        target_path = root / "pmdg.json"

        source = _store(source_path)
        source.set_binding(device_key, control_key, MappingBinding(
            kind=fenix_kind, target=fenix_target, simulator="msfs24",
        ))
        source.save()

        report = copy_msfs24_bindings(
            source_path, target_path,
            source_key="fenix_a320", target_key="pmdg_737_800",
        )
        assert not report["copied"], (
            "A Fenix command was copied onto a PMDG 737. Unrelated aircraft must "
            "never inherit a function that does not exist in their own library."
        )
        assert report["skipped"], "The refusal was not reported to the user."
        assert not report["same_family"], "Fenix and PMDG must not count as one family."

        # A destination with no imported library at all takes nothing.
        empty = copy_msfs24_bindings(
            source_path, root / "fbw.json",
            source_key="fenix_a320", target_key="fbw_a32nx",
        )
        assert not empty["copied"], (
            "Mappings were copied onto FlyByWire, which has no imported functions."
        )
    print("  [ok] unrelated aircraft never inherit a function they do not have")


def check_bridge_refuses_the_wrong_loaded_aircraft():
    """The dispatch guards must still exist in the bridge."""

    source = (PROJECT / "bridge" / "final.py").read_text(encoding="utf-8", errors="replace")

    assert "selection_matches_loaded_aircraft" in source, (
        "The bridge lost its loaded-aircraft dispatch gate. Without it a mapping "
        "for one aircraft can be sent while a different aircraft is loaded."
    )
    assert "does not match the aircraft currently loaded" in source, (
        "The loaded-aircraft mismatch refusal message is gone."
    )
    assert "belongs to the MSFS 2024 workspace, not the X-Plane bridge" in source, (
        "The bridge lost the guard that stops an MSFS mapping reaching the "
        "X-Plane API."
    )
    gates = source.count("aircraft_profile ==") + source.count("aircraft_profile in ")
    assert gates >= 10, (
        "Only %d aircraft-scoped startup gates remain in the bridge. Telemetry "
        "workers are started per detected aircraft; losing these would make the "
        "bridge request datarefs for aircraft that are not loaded." % gates
    )
    print("  [ok] bridge keeps its dispatch gate and %d aircraft-scoped worker gates" % gates)


def main():
    print("Aircraft isolation contract:")
    check_every_aircraft_has_its_own_profile()
    check_a_mapping_stays_on_its_own_aircraft()
    check_family_inheritance_then_independence()
    check_unrelated_aircraft_never_guess()
    check_bridge_refuses_the_wrong_loaded_aircraft()
    print("Aircraft isolation contract test passed.")


if __name__ == "__main__":
    main()
