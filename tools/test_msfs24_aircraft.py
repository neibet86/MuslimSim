#!/usr/bin/env python3
"""Prove the MSFS 2024 aircraft selector matches the imported catalogue.

The selector, the isolated mapping workspaces and the function browser all read
``muslimsim/hardware/msfs24_aircraft.py``.  If a family string there stops
matching ``msfs24_command_catalog.json``, the function browser silently shows an
empty list with no error, which is the failure this test exists to prevent.

Offline: no hardware, no simulator, no bridge process.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui.supervisor import (
    SIMULATOR_MSFS24, SIMULATOR_XPLANE, default_profile_path,
)
from muslimsim.hardware.msfs24_aircraft import (
    MSFS24_AIRCRAFT, MSFS24_DEFAULT_AIRCRAFT, msfs24_aircraft, msfs24_brands,
)
from muslimsim.hardware.msfs24_library import all_msfs24_functions


def check_keys_are_unique():
    keys = [item.key for item in MSFS24_AIRCRAFT]
    assert len(keys) == len(set(keys)), "Duplicate MSFS 2024 aircraft key."
    for item in MSFS24_AIRCRAFT:
        assert msfs24_aircraft(item.key) is item, "Lookup lost %s" % item.key
    print("  [ok] %d aircraft, all keys unique and resolvable" % len(keys))


def check_families_exist_in_the_catalogue():
    """A named family must really be in the import, with functions behind it."""

    catalogue = {}
    for entry in all_msfs24_functions():
        name = str(entry.get("aircraft") or "")
        if name:
            catalogue[name] = catalogue.get(name, 0) + 1

    wrong = []
    for item in MSFS24_AIRCRAFT:
        if item.family is None:
            continue
        if item.family not in catalogue:
            wrong.append(
                "%s: family %r is not in msfs24_command_catalog.json"
                % (item.key, item.family)
            )
        elif catalogue[item.family] <= 0:
            wrong.append("%s: family %r has no functions" % (item.key, item.family))
    assert not wrong, (
        "The selector names catalogue families that do not exist:\n    "
        + "\n    ".join(wrong)
        + "\n\nThe function browser filters on this exact string, so a mismatch "
        "shows an empty list with no error."
    )

    covered = sorted({item.family for item in MSFS24_AIRCRAFT if item.family})
    print("  [ok] every named family exists in the import: %d of %d catalogue families"
          % (len(covered), len(catalogue)))


def check_aircraft_without_functions_are_deliberate():
    """An empty function list must be declared, not an accident."""

    silent = [item.key for item in MSFS24_AIRCRAFT if item.family is None]
    # The A32NX gained a library on 2026-09-04 from the owner's Rowsfire
    # MobiFlight, SPAD.neXt and Stream Deck sources. The A380X is a different
    # airframe and keeps none until its own commands are imported.
    assert silent == ["fbw_a380x"], (
        "Aircraft with no function library changed to %r. Every entry without a "
        "family is reported to the user as 'no functions imported', so this list "
        "must stay deliberate." % (silent,)
    )
    print("  [ok] %d airframe(s) declare no imported functions: %s" % (len(silent), ", ".join(silent)))


def check_workspaces_are_isolated():
    """Each airframe gets its own mapping profile, and the old paths are kept."""

    assert default_profile_path(SIMULATOR_XPLANE, "zibo").name == "hardware_profiles.json", (
        "The Zibo profile path moved; existing X-Plane mappings would be orphaned."
    )
    assert default_profile_path(SIMULATOR_MSFS24).name == "hardware_profiles_msfs24.json", (
        "The default MSFS profile path moved; existing MSFS mappings would be orphaned."
    )

    seen = {}
    for item in MSFS24_AIRCRAFT:
        path = default_profile_path(SIMULATOR_MSFS24, "zibo", item.key)
        assert path.name not in seen, (
            "%s and %s share the mapping profile %s; assignments would leak "
            "between airframes." % (item.key, seen.get(path.name), path.name)
        )
        seen[path.name] = item.key
    print("  [ok] %d isolated MSFS mapping workspaces, legacy paths unchanged" % len(seen))


def check_brand_grouping():
    brands = msfs24_brands()
    names = [brand for brand, _ in brands]
    assert names == ["Fenix", "FSLabs", "FlyByWire", "PMDG", "iFly", "iniBuilds"], (
        "Brand order changed: %r" % (names,)
    )
    counts = {brand: len(items) for brand, items in brands}
    assert counts["Fenix"] == 3, counts
    assert counts["FSLabs"] == 3, counts
    assert counts["FlyByWire"] == 2, counts
    assert counts["PMDG"] >= 3, counts  # 739 and 77er installed; others kept as paths
    # The MAX 8 and the MAX 8200 are both installed as separate airframes, so
    # iFly renders as a drop-down rather than a single button.
    assert counts["iFly"] == 2, counts
    assert counts["iniBuilds"] == 1, counts
    assert msfs24_aircraft(MSFS24_DEFAULT_AIRCRAFT) is not None, (
        "The default MSFS aircraft is not in the list."
    )
    summary = ", ".join("%s %d" % (brand, len(items)) for brand, items in brands)
    print("  [ok] brand grouping: %s" % summary)


def main():
    print("MSFS 2024 aircraft selector:")
    check_keys_are_unique()
    check_families_exist_in_the_catalogue()
    check_aircraft_without_functions_are_deliberate()
    check_workspaces_are_isolated()
    check_brand_grouping()
    print("MSFS 2024 aircraft selector test passed.")


if __name__ == "__main__":
    main()
