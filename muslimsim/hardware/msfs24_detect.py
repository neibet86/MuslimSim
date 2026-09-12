"""Identify the loaded MSFS 2024 aircraft without any third-party helper.

This is the MSFS counterpart of the X-Plane bridge's ``.acf`` path detection.
It takes what SimConnect already reports about the loaded aircraft - the
``TITLE`` simvar and the ``aircraft.cfg`` path from the ``AircraftLoaded``
system event - and resolves it to one of Studio's isolated MSFS workspaces.

Nothing here is guessed.  Every rule below was read from the owner's actual
installation under ``D:\\MSFS24\\Community``, and the evidence is recorded with
each rule so a future reader can re-check it rather than trust it.

Two facts from that survey shape the design, and they pull in opposite
directions:

* **Fenix titles discriminate, its package does not.**  ``fnx-aircraft-319-321``
  ships A319 *and* A321 airframes, and also contained a livery titled
  "Fenix A320 - Tunisair TS-IML".  The package name cannot tell those apart;
  the titles ``FenixA319`` / ``FenixA320`` / ``FenixA321`` can.
* **PMDG is the reverse.**  Its titles are generic - ``737-900 PAX BW SC``,
  ``777-200ER GE`` - with no vendor name at all, so a title match would collide
  with any other developer's 737.  Its package names are exact:
  ``pmdg-aircraft-739``, ``pmdg-aircraft-77er``.

So the title is tried first where it is specific, and the package path is used
where it is not.  An aircraft that matches neither returns ``None`` rather than
a guess: Studio then leaves the workspace alone instead of silently mapping
controls onto the wrong airframe.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional


class DetectionRule(NamedTuple):
    """One evidence-backed way to recognise an installed aircraft."""

    aircraft_key: str
    title_pattern: Optional[str]
    package_pattern: Optional[str]
    evidence: str


# Ordered: the first rule that matches wins, so more specific rules come first.
RULES: tuple[DetectionRule, ...] = (
    # --- Fenix: title is authoritative, package is not -------------------
    DetectionRule(
        "fenix_a319", r"\bFenix\s*A?319\b", None,
        "titles 'FenixA319 CFM SL HD' ... in fnx-aircraft-319-321",
    ),
    DetectionRule(
        "fenix_a321", r"\bFenix\s*A?321\b", None,
        "titles 'FenixA321 CFM SL SC' ... in fnx-aircraft-319-321",
    ),
    DetectionRule(
        "fenix_a320", r"\bFenix\s*A?320\b", r"fnx-aircraft-320",
        "titles 'FenixA320 CFM SL' ... in fnx-aircraft-320; a Tunisair A320 "
        "livery also ships inside fnx-aircraft-319-321",
    ),

    # --- FlyByWire: both title and package are clear ---------------------
    DetectionRule(
        "fbw_a380x", r"\bA380", r"flybywire-aircraft-a380",
        "package flybywire-aircraft-a380-842, title 'Pride A380X' (the title is "
        "livery-dependent, so the package carries this one)",
    ),
    DetectionRule(
        "fbw_a32nx", r"FlyByWire|A32NX", r"flybywire-aircraft-a320",
        "package flybywire-aircraft-a320-neo, title 'Airbus A320 Neo FlyByWire'",
    ),

    # --- iFly ------------------------------------------------------------
    DetectionRule(
        "ifly_737_max8200", r"\biFly\s*737-?MAX\s*8200", r"ifly-aircraft-737max8200",
        "titles 'iFly 737-MAX8200' and 'iFly 737-MAX8200 SKYDUBAI A6MAX'; "
        "packages ifly-aircraft-737max8200-*",
    ),
    DetectionRule(
        "ifly_737_max8", r"\biFly\s*737-?MAX\s*8", r"ifly-aircraft-737max8",
        "titles 'iFly 737-MAX8 (166Seats)' and 'iFly 737-MAX8200'; packages "
        "ifly-aircraft-737max8 and ifly-aircraft-737max8200-*",
    ),

    # --- PMDG: package is authoritative, titles carry no vendor name -----
    DetectionRule(
        "pmdg_777_200er", None, r"pmdg-aircraft-77er",
        "package pmdg-aircraft-77er, titles '777-200ER GE/PW/RR'",
    ),
    DetectionRule(
        "pmdg_777_300er", None, r"pmdg-aircraft-77[w3]",
        "PMDG's 777-300ER package naming; not installed on the owner's machine",
    ),
    DetectionRule(
        "pmdg_737_900", None, r"pmdg-aircraft-739",
        "package pmdg-aircraft-739, titles '737-900 PAX BW SC' / '737-900ER ...'",
    ),
    DetectionRule(
        "pmdg_737_800", None, r"pmdg-aircraft-738",
        "PMDG 737-800 package naming; not installed on the owner's machine",
    ),
    DetectionRule(
        "pmdg_737_700", None, r"pmdg-aircraft-737",
        "PMDG 737-700 package naming; not installed on the owner's machine",
    ),
    DetectionRule(
        "pmdg_737_600", None, r"pmdg-aircraft-736",
        "PMDG 737-600 package naming; not installed on the owner's machine",
    ),

    # --- Not installed here; rules kept so detection works when they are --
    # FSLabs is installed as package fsl-a32x, and the airframes present are
    # A321-251N / -251NX / -271N / -271NX: the neo with LEAP (251) and PW
    # (271) engines. The neo rule therefore claims them first; the plain and
    # sharklet rules stay for FSLabs airframes that may be added later.
    DetectionRule(
        "fslabs_a321neo", r"\bFSLabs\b.*\bA321-2[57]1N", r"fsl-a32x",
        "titles 'FSLabs A321-251N - FSL (SN-FSL)' ... in package fsl-a32x, "
        "SimObjects 'FSLabs A321-NEO LEAP' and 'FSLabs A321-NEO PW'",
    ),
    DetectionRule(
        "fslabs_a321_sharklets", r"\bFSLabs\b.*\bA321\b.*\bSharklet", None,
        "FSLabs naming for a sharklet A321; not among the installed airframes",
    ),
    DetectionRule(
        "fslabs_a321", r"\bFSLabs\b.*\bA?321\b", None,
        "any remaining FSLabs A321; the neo rule above claims the installed ones",
    ),
    DetectionRule(
        "inibuilds_a350", r"\biniBuilds\b.*\bA350\b", r"inibuilds-aircraft-a350",
        "iniBuilds naming; only Asobo's passive A350 traffic package is "
        "installed, which is not a flyable add-on",
    ),
)


def detect_msfs24_aircraft(title: str = "", path: str = "") -> Optional[str]:
    """Resolve a loaded MSFS aircraft to a Studio workspace key.

    ``title`` is SimConnect's ``TITLE`` simvar and ``path`` is the
    ``aircraft.cfg`` path reported by the ``AircraftLoaded`` system event.
    Either may be empty.  Returns ``None`` when nothing matches, which the
    caller must treat as "leave the workspace alone" rather than a default.
    """

    text_title = " ".join(str(title or "").split())
    text_path = str(path or "").replace("\\", "/")

    for rule in RULES:
        if rule.title_pattern and text_title:
            if re.search(rule.title_pattern, text_title, re.I):
                return rule.aircraft_key
        if rule.package_pattern and text_path:
            if re.search(rule.package_pattern, text_path, re.I):
                return rule.aircraft_key
    return None


def describe_detection(title: str = "", path: str = "") -> dict:
    """The match plus the evidence behind it, for diagnostics."""

    key = detect_msfs24_aircraft(title, path)
    rule = next((r for r in RULES if r.aircraft_key == key), None)
    return {
        "aircraft": key,
        "title": title,
        "path": path,
        "evidence": rule.evidence if rule else "no rule matched",
    }


__all__ = ("RULES", "DetectionRule", "describe_detection", "detect_msfs24_aircraft")
