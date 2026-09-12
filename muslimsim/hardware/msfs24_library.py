"""MSFS 2024 simulator-function catalogue for the visual mapper.

This module is intentionally independent from :mod:`zibo_library`.  It reads
the curated aircraft entries imported from the owner's command workbook and
returns choices only; it never opens a simulator connection, a HID device, or
an FSUIPC/SimConnect client.  The future MSFS bridge is therefore the only
place allowed to dispatch an MSFS mapping.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


_CATALOGUE_PATH = Path(__file__).with_name("msfs24_command_catalog.json")

# Precomputed lowercase search text, added once when the catalogue is loaded.
_SEARCH_KEY = "_search"


@lru_cache(maxsize=1)
def all_msfs24_functions() -> tuple[dict[str, Any], ...]:
    """Return every imported MSFS 2024 command/LVAR choice.

    The JSON is generated from the supplied workbook, then shipped with
    Studio so the function browser works before MSFS starts.  An unreadable
    optional file produces an empty library rather than blocking Studio.
    """

    try:
        raw = json.loads(_CATALOGUE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    entries = raw.get("functions") if isinstance(raw, Mapping) else ()
    items = [dict(item) for item in list(entries or ()) if isinstance(item, Mapping)]
    # The browser filters as the owner types, and the search text used to be
    # rebuilt for every entry on every keystroke.  That is fine at 2,355
    # entries and visibly slow at ten times that, so it is built once here -
    # this function is cached, so the cost is paid on the first search only.
    for item in items:
        item[_SEARCH_KEY] = " ".join(
            str(item.get(field) or "").replace("_", " ").casefold()
            for field in ("label", "category", "aircraft", "description", "target", "protocol")
        )
    return tuple(items)


def search_msfs24_functions(
    functions: Iterable[Mapping[str, Any]],
    query: str = "",
    *,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Search the imported library without mixing it with X-Plane choices."""

    needle = " ".join(str(query or "").casefold().replace("_", " ").split())
    matches: list[dict[str, Any]] = []
    for item in functions:
        if str(item.get("kind") or "") not in {"command", "dataref"}:
            continue
        text = item.get(_SEARCH_KEY)
        if text is None:
            text = " ".join(
                str(item.get(field) or "").replace("_", " ").casefold()
                for field in ("label", "category", "aircraft", "description", "target", "protocol")
            )
        if needle and needle not in text:
            continue
        entry = dict(item)
        entry.pop(_SEARCH_KEY, None)
        matches.append(entry)
    matches.sort(key=lambda item: (
        str(item.get("aircraft") or ""),
        str(item.get("category") or ""),
        str(item.get("label") or ""),
    ))
    return matches[:max(1, min(1000, int(limit)))]


def offline_msfs24_functions(*, include_axes: bool = True) -> list[dict[str, Any]]:
    """Expose workbook-proven MSFS choices for the matching control type.

    ``include_axes`` is retained for the same mapper API as X-Plane.  The
    workbook's writable LVARs are represented as dataref-style targets and
    include axis-capable Fenix entries; no generic SimConnect axis event is
    invented where the supplied catalogue did not document one.
    """

    entries = list(all_msfs24_functions())
    if include_axes:
        return entries
    return [item for item in entries if str(item.get("kind") or "") == "command"]


def catalogue_summary() -> dict[str, Any]:
    """Small status payload for the MSFS bridge and Studio header."""

    items = all_msfs24_functions()
    aircraft = sorted({str(item.get("aircraft") or "") for item in items if item.get("aircraft")})
    return {
        "simulator": "msfs24",
        "total": len(items),
        "aircraft": aircraft,
        "source": "FlightSim_Command_Catalog.xlsx",
    }


__all__ = (
    "all_msfs24_functions", "catalogue_summary", "offline_msfs24_functions",
    "search_msfs24_functions",
)
