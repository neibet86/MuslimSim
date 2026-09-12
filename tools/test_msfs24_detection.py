#!/usr/bin/env python3
"""Prove MSFS aircraft detection against the owner's real installation.

Every sample below was read out of an ``aircraft.cfg`` under
``D:\\MSFS24\\Community`` - these are the exact strings SimConnect reports for
the aircraft actually installed on this machine, not invented examples.

The detection has to hold two opposite cases at once, which is why both are
tested here:

* Fenix titles discriminate but its package does not - ``fnx-aircraft-319-321``
  ships A319 and A321 airframes plus an A320 livery.
* PMDG is the reverse - its titles carry no vendor name at all
  (``737-900 PAX BW SC``), so only the package identifies it.

Offline: no simulator, no hardware, no bridge.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.hardware.msfs24_aircraft import MSFS24_AIRCRAFT_KEYS
from muslimsim.hardware.msfs24_detect import RULES, detect_msfs24_aircraft

COMMUNITY = r"D:\MSFS24\Community"

# (title, aircraft.cfg path, expected workspace key) - all harvested from disk.
REAL_SAMPLES = (
    ("FenixA320 CFM SL",
     rf"{COMMUNITY}\fnx-aircraft-320\SimObjects\Airplanes\FNX_320\aircraft.cfg",
     "fenix_a320"),
    ("FenixA319 CFM SL HD",
     rf"{COMMUNITY}\fnx-aircraft-319-321\SimObjects\Airplanes\FNX_319\aircraft.cfg",
     "fenix_a319"),
    ("FenixA321 IAE WF TC",
     rf"{COMMUNITY}\fnx-aircraft-319-321\SimObjects\Airplanes\FNX_321\aircraft.cfg",
     "fenix_a321"),
    # The A320 livery that ships inside the 319-321 package: the title must win.
    ("Fenix A320 - Tunisair TS-IML",
     rf"{COMMUNITY}\fnx-aircraft-319-321\SimObjects\Airplanes\FNX_320_CFM_TARTSIML\aircraft.cfg",
     "fenix_a320"),

    ("Airbus A320 Neo FlyByWire",
     rf"{COMMUNITY}\flybywire-aircraft-a320-neo\SimObjects\Airplanes\FlyByWire_A320_NEO\aircraft.cfg",
     "fbw_a32nx"),
    # The A380 title is livery-dependent, so the package has to carry it.
    ("Pride A380X",
     rf"{COMMUNITY}\flybywire-aircraft-a380-842\SimObjects\Airplanes\FlyByWire_A380_842\aircraft.cfg",
     "fbw_a380x"),

    ("iFly 737-MAX8 (166Seats)",
     rf"{COMMUNITY}\ifly-aircraft-737max8\SimObjects\Airplanes\iFly 737-MAX8\aircraft.cfg",
     "ifly_737_max8"),
    # The 8200 is a separate installed airframe and must not fold into the MAX 8.
    ("iFly 737-MAX8200",
     rf"{COMMUNITY}\ifly-aircraft-737max8\SimObjects\Airplanes\iFly 737-MAX8200\aircraft.cfg",
     "ifly_737_max8200"),
    ("iFly 737-MAX8200 SKYDUBAI A6MAX",
     rf"{COMMUNITY}\ifly-aircraft-737max8200-RYR-EI-HAY\x\aircraft.cfg",
     "ifly_737_max8200"),

    # FSLabs is installed as fsl-a32x, and the airframes are the NEO.
    ("FSLabs A321-251N - FSL (SN-FSL)",
     rf"{COMMUNITY}\fsl-a32x\SimObjects\Airplanes\FSLabs A321-NEO LEAP\aircraft.cfg",
     "fslabs_a321neo"),
    ("FSLabs A321-271NX - FSL (SN-FSL)",
     rf"{COMMUNITY}\fsl-a32x\SimObjects\Airplanes\FSLabs A321-NEO PW\aircraft.cfg",
     "fslabs_a321neo"),
    ("FSLabs A321-253NX - American Airlines (#435 | N435AN)",
     rf"{COMMUNITY}\fsl-a32x-liveries\x\aircraft.cfg",
     "fslabs_a321neo"),

    # PMDG: generic titles, so these must resolve on the package alone.
    ("737-900 PAX BW SC",
     rf"{COMMUNITY}\pmdg-aircraft-739\SimObjects\Airplanes\PMDG 737-900\aircraft.cfg",
     "pmdg_737_900"),
    ("737-900ER PAX BW HD",
     rf"{COMMUNITY}\pmdg-aircraft-739\SimObjects\Airplanes\PMDG 737-900ER\aircraft.cfg",
     "pmdg_737_900"),
    ("777-200ER GE",
     rf"{COMMUNITY}\pmdg-aircraft-77er\SimObjects\Airplanes\PMDG 777-200ER\aircraft.cfg",
     "pmdg_777_200er"),
)


def check_every_rule_targets_a_real_workspace():
    """A rule may not resolve to an aircraft Studio does not offer."""

    orphans = sorted({
        rule.aircraft_key for rule in RULES
        if rule.aircraft_key not in MSFS24_AIRCRAFT_KEYS
    })
    assert not orphans, (
        "These detection rules resolve to aircraft the Studio selector does not "
        "offer: %s.\nDetecting an aircraft with no workspace to switch to is a "
        "dead end - either add the aircraft to msfs24_aircraft.py or remove the "
        "rule." % (orphans,)
    )
    print("  [ok] all %d rules resolve to offered workspaces" % len(RULES))


def check_real_aircraft_are_identified():
    """Every sample taken from the owner's disk must resolve correctly."""

    wrong = []
    for title, path, expected in REAL_SAMPLES:
        got = detect_msfs24_aircraft(title, path)
        if got != expected:
            wrong.append(f"{title!r} -> {got!r}, expected {expected!r}")
    assert not wrong, "Detection failed on real installed aircraft:\n    " + "\n    ".join(wrong)
    print("  [ok] all %d real installed aircraft identified correctly" % len(REAL_SAMPLES))


def check_fenix_package_alone_is_not_trusted():
    """The 319-321 package holds three airframes; only the title separates them."""

    shared = rf"{COMMUNITY}\fnx-aircraft-319-321\SimObjects\Airplanes\X\aircraft.cfg"
    a319 = detect_msfs24_aircraft("FenixA319 CFM SL HD", shared)
    a321 = detect_msfs24_aircraft("FenixA321 IAE WF TC", shared)
    assert a319 == "fenix_a319" and a321 == "fenix_a321", (
        "The same Fenix package resolved to %r and %r. If the package name were "
        "trusted over the title, an A321 would load the A319 workspace and take "
        "its mappings." % (a319, a321)
    )
    print("  [ok] Fenix variants in one package stay separated by title")


def check_an_unknown_aircraft_is_not_guessed():
    """No match must mean no match, not a default."""

    for title, path in (
        ("Cessna 172 Skyhawk", r"D:\MSFS24\Official2024\asobo-aircraft-c172\aircraft.cfg"),
        ("", ""),
        ("Some Unreleased Airliner", r"D:\MSFS24\Community\unknown-aircraft-x\aircraft.cfg"),
    ):
        got = detect_msfs24_aircraft(title, path)
        assert got is None, (
            "Unknown aircraft %r resolved to %r. Guessing here would point the "
            "hardware at the wrong airframe's mappings." % (title, got)
        )
    print("  [ok] an unrecognised aircraft resolves to nothing, not a default")


def main():
    print("MSFS 2024 aircraft detection:")
    check_every_rule_targets_a_real_workspace()
    check_real_aircraft_are_identified()
    check_fenix_package_alone_is_not_trusted()
    check_an_unknown_aircraft_is_not_guessed()
    print("MSFS 2024 aircraft detection test passed.")


if __name__ == "__main__":
    main()
