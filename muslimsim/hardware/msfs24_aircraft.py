"""MSFS 2024 add-on aircraft offered by Studio, grouped by their developer.

One source of truth for the Studio selector, the isolated mapping workspaces
and the function browser, so the three cannot drift apart.

Each entry names the catalogue family it draws functions from.  The imported
``msfs24_command_catalog.json`` is written per *family*, not per variant: every
Fenix variant shares "Fenix A320 family", and PMDG splits only into its 737 and
777 groups.  Variants therefore share a function library but still get their
own mapping workspace, exactly as the X-Plane aircraft do - a saved assignment
for one airframe never leaks into another.

``family=None`` means the imported catalogue has no functions for that aircraft
yet.  It is still offered, because the owner asked for it and its hardware can
be practised, but the mapper says so plainly instead of showing an empty list
with no explanation.  Nothing here invents a command; a family appears only
when the workbook import actually contains it.
"""

from __future__ import annotations

from typing import NamedTuple, Optional


# Catalogue families as spelled in msfs24_command_catalog.json.  These strings
# must match the import exactly or the function browser silently shows nothing.
FAMILY_FENIX = "Fenix A320 family"
FAMILY_FSLABS = "FSLabs A320 family"
FAMILY_PMDG_737 = "PMDG 737 / 777 (737)"
FAMILY_PMDG_777 = "PMDG 737 / 777 (777)"
FAMILY_IFLY_MAX8 = "iFly 737 MAX 8 (MSFS2020/2024)"
# Imported from the owner's Rowsfire MobiFlight, SPAD.neXt and Stream Deck
# sources. Every one of those documents the A32NX; the A380X is a different
# airframe with different LVARs and deliberately keeps no family until its own
# commands are imported.
FAMILY_FBW_A32NX = "FlyByWire A32NX"
FAMILY_INIBUILDS_A350 = "iniBuilds A350"


class Msfs24Aircraft(NamedTuple):
    """One selectable MSFS 2024 airframe."""

    key: str
    brand: str
    label: str
    family: Optional[str]

    @property
    def title(self) -> str:
        return f"{self.brand} {self.label}"

    @property
    def has_functions(self) -> bool:
        return bool(self.family)


BRAND_FENIX = "Fenix"
BRAND_FSLABS = "FSLabs"
BRAND_FLYBYWIRE = "FlyByWire"
BRAND_PMDG = "PMDG"
BRAND_IFLY = "iFly"
BRAND_INIBUILDS = "iniBuilds"


# Order is the order the owner asked for, and the order the selector shows.
MSFS24_AIRCRAFT: tuple[Msfs24Aircraft, ...] = (
    Msfs24Aircraft("fenix_a320", BRAND_FENIX, "A320", FAMILY_FENIX),
    Msfs24Aircraft("fenix_a319", BRAND_FENIX, "A319", FAMILY_FENIX),
    Msfs24Aircraft("fenix_a321", BRAND_FENIX, "A321", FAMILY_FENIX),

    Msfs24Aircraft("fslabs_a321", BRAND_FSLABS, "A321", FAMILY_FSLABS),
    Msfs24Aircraft("fslabs_a321neo", BRAND_FSLABS, "A321neo", FAMILY_FSLABS),
    Msfs24Aircraft("fslabs_a321_sharklets", BRAND_FSLABS, "A321 Sharklets", FAMILY_FSLABS),

    Msfs24Aircraft("fbw_a32nx", BRAND_FLYBYWIRE, "A32NX", FAMILY_FBW_A32NX),
    # The A380X has no imported functions. It is offered without a library
    # rather than borrowing the A32NX's, which would not fit the airframe.
    Msfs24Aircraft("fbw_a380x", BRAND_FLYBYWIRE, "A380X", None),

    Msfs24Aircraft("pmdg_737_600", BRAND_PMDG, "737-600", FAMILY_PMDG_737),
    Msfs24Aircraft("pmdg_737_700", BRAND_PMDG, "737-700", FAMILY_PMDG_737),
    Msfs24Aircraft("pmdg_737_800", BRAND_PMDG, "737-800", FAMILY_PMDG_737),
    Msfs24Aircraft("pmdg_737_900", BRAND_PMDG, "737-900", FAMILY_PMDG_737),
    # The 777-200ER is the PMDG 777 actually installed on the owner's machine
    # (package pmdg-aircraft-77er). It was missing, so loading it detected an
    # aircraft Studio had no workspace to switch to.
    Msfs24Aircraft("pmdg_777_200er", BRAND_PMDG, "777-200ER", FAMILY_PMDG_777),
    Msfs24Aircraft("pmdg_777_300er", BRAND_PMDG, "777-300ER", FAMILY_PMDG_777),
    Msfs24Aircraft("pmdg_777f", BRAND_PMDG, "777F", FAMILY_PMDG_777),

    Msfs24Aircraft("ifly_737_max8", BRAND_IFLY, "737 MAX 8", FAMILY_IFLY_MAX8),
    # Installed alongside the MAX 8 as a separate airframe
    # (ifly-aircraft-737max8200-*). It shares the iFly function library but
    # gets its own mapping workspace, as the Fenix variants do.
    Msfs24Aircraft("ifly_737_max8200", BRAND_IFLY, "737 MAX 8200", FAMILY_IFLY_MAX8),

    # The imported Rowsfire panels document the A350 as one airframe. If the
    # -900 and -1000 are wanted separately they share this family, exactly as
    # the Fenix variants do.
    Msfs24Aircraft("inibuilds_a350", BRAND_INIBUILDS, "A350", FAMILY_INIBUILDS_A350),
)

# The default keeps the original single MSFS profile file exactly where it was,
# the same way Zibo keeps the original X-Plane profile file.
MSFS24_DEFAULT_AIRCRAFT = "fenix_a320"

MSFS24_AIRCRAFT_KEYS = frozenset(item.key for item in MSFS24_AIRCRAFT)

_BY_KEY = {item.key: item for item in MSFS24_AIRCRAFT}


def msfs24_aircraft(key: str) -> Optional[Msfs24Aircraft]:
    """Return one airframe, or ``None`` when the key is not offered."""

    return _BY_KEY.get(str(key or "").strip().casefold())


def msfs24_aircraft_title(key: str) -> str:
    """A readable name for footers and dialog headers."""

    item = msfs24_aircraft(key)
    return item.title if item is not None else "MSFS 2024"


def msfs24_brands() -> tuple[tuple[str, tuple[Msfs24Aircraft, ...]], ...]:
    """Developers in display order, each with its aircraft in display order."""

    order: list[str] = []
    grouped: dict[str, list[Msfs24Aircraft]] = {}
    for item in MSFS24_AIRCRAFT:
        if item.brand not in grouped:
            grouped[item.brand] = []
            order.append(item.brand)
        grouped[item.brand].append(item)
    return tuple((brand, tuple(grouped[brand])) for brand in order)


def msfs24_family(key: str) -> Optional[str]:
    """The catalogue family a selected airframe draws its functions from."""

    item = msfs24_aircraft(key)
    return item.family if item is not None else None


__all__ = (
    "FAMILY_FBW_A32NX", "FAMILY_INIBUILDS_A350", "MSFS24_AIRCRAFT", "MSFS24_AIRCRAFT_KEYS", "MSFS24_DEFAULT_AIRCRAFT",
    "Msfs24Aircraft", "msfs24_aircraft", "msfs24_aircraft_title",
    "msfs24_brands", "msfs24_family",
)
