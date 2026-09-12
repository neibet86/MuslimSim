"""X-Plane aircraft-function libraries for the Studio mapper.

Zibo, LevelUp, ToLiss, and the AirfoilLabs C172 NG Digital are deliberately
separate X-Plane workspaces.  The Boeing/Airbus catalogue is imported from the
owner's supplied workbook and is never mixed with MSFS 2024 entries.  The C172
library is read from X-Plane's own installed ``Commands.txt`` and replaced by
the live Web-API inventory while that aircraft is loaded.  Only command rows
are offered for button/selector assignment; dataref rows remain source
metadata until write support is verified, matching the existing safe-axis
policy.
"""

from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .zibo_library import (
    SAFE_AXIS_FUNCTIONS,
    command_category,
    command_label,
    live_command_functions,
)


AIRCRAFT_ZIBO = "zibo"
AIRCRAFT_LEVELUP = "levelup"
AIRCRAFT_TOLISS = "toliss"
AIRCRAFT_C172_NG = "c172ng"
_AIRCRAFT = frozenset({
    AIRCRAFT_ZIBO,
    AIRCRAFT_LEVELUP,
    AIRCRAFT_TOLISS,
    AIRCRAFT_C172_NG,
})
_CATALOGUE_PATH = Path(__file__).with_name("xplane_command_catalog.json")

# These are the systems present in the AirfoilLabs digital C172 and its G1000.
# X-Plane's command inventory contains unrelated weapons, developer, replay,
# CDU, and multi-airliner commands too; keeping those out makes the C172
# browser useful without inventing any AirfoilLabs-only command spelling.
_C172_COMMAND_GROUPS = frozenset({
    "annunciator", "audio_panel", "autopilot", "electrical", "engines",
    "flight_controls", "fuel", "general", "gps", "ground_ops", "ice",
    "instruments", "lights", "magnetos", "map", "radios", "starters",
    "systems", "transponder",
})
_COMMAND_COLUMNS = re.compile(r"\s{2,}")

# A useful simulator-down minimum if an X-Plane installation is temporarily
# unavailable.  On the owner's machine this is extended to roughly two
# thousand real commands from Resources/plugins/Commands.txt.
_C172_FALLBACK_COMMANDS: tuple[tuple[str, str], ...] = (
    ("sim/electrical/battery_1_on", "Battery 1 on."),
    ("sim/electrical/battery_1_off", "Battery 1 off."),
    ("sim/electrical/generator_1_on", "Generator 1 on."),
    ("sim/electrical/generator_1_off", "Generator 1 off."),
    ("sim/systems/avionics_on", "Avionics on."),
    ("sim/systems/avionics_off", "Avionics off."),
    ("sim/magnetos/magnetos_off", "Magnetos off."),
    ("sim/magnetos/magnetos_both", "Magnetos both."),
    ("sim/magnetos/magnetos_up_1", "Magnetos up one position."),
    ("sim/magnetos/magnetos_down_1", "Magnetos down one position."),
    ("sim/starters/engage_starter_1", "Engage starter 1."),
    ("sim/engines/mixture_max", "Mixture full rich."),
    ("sim/engines/mixture_min", "Mixture cutoff."),
    ("sim/engines/throttle_up", "Throttle up."),
    ("sim/engines/throttle_down", "Throttle down."),
    ("sim/fuel/fuel_selector_all", "Fuel selector both/all."),
    ("sim/fuel/fuel_selector_lft", "Fuel selector left."),
    ("sim/fuel/fuel_selector_rgt", "Fuel selector right."),
    ("sim/fuel/fuel_selector_none", "Fuel selector off."),
    ("sim/flight_controls/flaps_up", "Flaps up one detent."),
    ("sim/flight_controls/flaps_down", "Flaps down one detent."),
    ("sim/flight_controls/park_brake_toggle", "Toggle parking brake."),
    ("sim/lights/landing_lights_toggle", "Toggle landing lights."),
    ("sim/lights/taxi_lights_toggle", "Toggle taxi lights."),
    ("sim/lights/nav_lights_toggle", "Toggle navigation lights."),
    ("sim/lights/beacon_lights_toggle", "Toggle beacon light."),
    ("sim/lights/strobe_lights_toggle", "Toggle strobe lights."),
    ("sim/ice/pitot_heat0_tog", "Toggle pitot heat."),
    ("sim/autopilot/fdir_servos_toggle", "Toggle autopilot servos."),
    ("sim/autopilot/heading", "Autopilot heading select."),
    ("sim/autopilot/altitude_hold", "Autopilot altitude hold."),
    ("sim/autopilot/vertical_speed", "Autopilot vertical speed."),
    ("sim/GPS/g1000n1_ap", "G1000 pilot autopilot."),
    ("sim/GPS/g1000n1_hdg", "G1000 pilot HDG."),
    ("sim/GPS/g1000n1_alt", "G1000 pilot ALT."),
    ("sim/GPS/g1000n1_nav", "G1000 pilot NAV."),
    ("sim/GPS/g1000n1_apr", "G1000 pilot approach."),
    ("sim/GPS/g1000n1_direct", "G1000 pilot direct-to."),
    ("sim/GPS/g1000n1_fpl", "G1000 pilot flight plan."),
    ("sim/GPS/g1000n1_proc", "G1000 pilot procedures."),
    ("sim/GPS/g1000n1_range_up", "G1000 pilot range up."),
    ("sim/GPS/g1000n1_range_down", "G1000 pilot range down."),
)


def normalise_aircraft(value: str) -> str:
    key = str(value or "").strip().casefold()
    if key not in _AIRCRAFT:
        raise ValueError("X-Plane aircraft must be zibo, levelup, toliss, or c172ng")
    return key


def _xplane_install_roots() -> tuple[Path, ...]:
    """Return configured/common X-Plane roots without scanning whole drives."""

    candidates: list[Path] = []
    for variable in ("XPLANE_PATH", "XPLANE12_PATH"):
        configured = os.environ.get(variable, "").strip()
        if configured:
            candidates.append(Path(configured))
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        install_list = Path(local_app_data) / "x-plane_install_12.txt"
        try:
            candidates.extend(
                Path(line.strip())
                for line in install_list.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip()
            )
        except OSError:
            pass
    for drive in ("C", "D", "E", "F"):
        base = Path(f"{drive}:/")
        candidates.extend((
            base / "SteamLibrary" / "steamapps" / "common" / "X-Plane 12",
            base / "steamGame" / "steamapps" / "common" / "X-Plane 12",
            base / "X-Plane 12",
        ))
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        identity = str(candidate).replace("\\", "/").rstrip("/").casefold()
        if identity and identity not in seen:
            seen.add(identity)
            unique.append(candidate)
    return tuple(unique)


def _c172_command_entry(target: str, description: str, source: str) -> dict[str, Any]:
    category = command_category(target).replace("X-Plane •", "C172 NG Digital •", 1)
    return {
        "id": f"c172ng:{target}",
        "kind": "command",
        "target": target,
        "label": command_label(target, description),
        "aircraft": AIRCRAFT_C172_NG,
        "category": category,
        "description": description or target,
        "source": source,
    }


@lru_cache(maxsize=1)
def installed_c172_ng_functions() -> list[dict[str, Any]]:
    """Read real C172/G1000-compatible commands from the installed X-Plane."""

    commands: dict[str, str] = {}
    for root in _xplane_install_roots():
        command_file = root / "Resources" / "plugins" / "Commands.txt"
        try:
            lines = command_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            columns = _COMMAND_COLUMNS.split(raw_line.strip(), maxsplit=1)
            target = columns[0].strip() if columns else ""
            parts = target.split("/")
            if (
                len(parts) < 2
                or parts[0].casefold() != "sim"
                or parts[1].casefold() not in _C172_COMMAND_GROUPS
            ):
                continue
            commands[target] = columns[1].strip() if len(columns) > 1 else ""
        if commands:
            break
    if commands:
        return [
            _c172_command_entry(target, description, "installed-xplane-c172ng")
            for target, description in sorted(commands.items(), key=lambda item: item[0].casefold())
        ]
    return [
        _c172_command_entry(target, description, "built-in-c172ng")
        for target, description in _C172_FALLBACK_COMMANDS
    ]


@lru_cache(maxsize=1)
def _all_entries() -> tuple[dict[str, Any], ...]:
    try:
        raw = json.loads(_CATALOGUE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    entries = raw.get("functions") if isinstance(raw, Mapping) else ()
    return tuple(dict(item) for item in list(entries or ()) if isinstance(item, Mapping))


def offline_xplane_functions(aircraft: str, *, include_axes: bool = True) -> list[dict[str, Any]]:
    """Return one selected aircraft's verified command choices.

    LevelUp is a B738-family selection. Its list is visibly marked as a
    compatibility reference sourced from the Zibo command sheet because the
    supplied workbook has no independent LevelUp SDK sheet. The bridge still
    detects LevelUp separately and applies its captured overrides at runtime.
    """

    key = normalise_aircraft(aircraft)
    if key == AIRCRAFT_C172_NG:
        entries = list(installed_c172_ng_functions())
        if include_axes:
            for axis in SAFE_AXIS_FUNCTIONS:
                target = str(axis.get("target") or "")
                if target.startswith("laminar/B738/"):
                    continue
                entry = {**axis, "source": "verified X-Plane axis"}
                entry["category"] = str(entry.get("category") or "").replace(
                    "X-Plane", "C172 NG / X-Plane",
                )
                entries.append(entry)
        return entries
    source_aircraft = AIRCRAFT_ZIBO if key == AIRCRAFT_LEVELUP else key
    entries: list[dict[str, Any]] = []
    for item in _all_entries():
        if str(item.get("aircraft") or "") != source_aircraft:
            continue
        if str(item.get("kind") or "") != "command":
            continue
        choice = dict(item)
        if key == AIRCRAFT_LEVELUP:
            choice["aircraft"] = "LevelUp 737NG"
            choice["category"] = str(choice.get("category") or "").replace("Zibo 737", "LevelUp 737")
            choice["description"] = (
                f"B738 compatibility reference: {choice.get('description') or choice.get('target')}. "
                "Verify this command against the installed LevelUp variant."
            )
            choice["source"] = "Zibo worksheet / LevelUp compatibility reference"
        entries.append(choice)
    if include_axes:
        for axis in SAFE_AXIS_FUNCTIONS:
            # The captured direct throttle/reverse/speedbrake axes belong to
            # the Zibo B738 protocol.  Do not present them as a ToLiss
            # capability just because they share an X-Plane installation.
            if key == AIRCRAFT_TOLISS and str(axis.get("target") or "").startswith("laminar/B738/"):
                continue
            entry = {**axis, "source": "verified X-Plane axis"}
            if key == AIRCRAFT_TOLISS:
                entry["category"] = str(entry["category"]).replace("X-Plane", "ToLiss / X-Plane")
            elif key == AIRCRAFT_LEVELUP:
                entry["category"] = str(entry["category"]).replace("X-Plane", "LevelUp / X-Plane")
            entries.append(entry)
    return entries


def live_xplane_functions(
    aircraft: str,
    commands: Iterable[Mapping[str, Any]],
    *,
    include_axes: bool = True,
) -> list[dict[str, Any]]:
    """Convert the loaded command inventory without leaking B738-only axes."""

    key = normalise_aircraft(aircraft)
    entries = live_command_functions(commands, include_axes=include_axes)
    if key in {AIRCRAFT_TOLISS, AIRCRAFT_C172_NG}:
        entries = [
            item for item in entries
            if not str(item.get("target") or "").startswith("laminar/B738/")
        ]
    if key == AIRCRAFT_C172_NG:
        for item in entries:
            if str(item.get("category") or "").startswith("X-Plane •"):
                item["category"] = str(item["category"]).replace(
                    "X-Plane •", "C172 NG Digital •", 1,
                )
    return entries


def search_xplane_functions(
    functions: Iterable[Mapping[str, Any]], query: str = "", *, limit: int = 1000,
) -> list[dict[str, Any]]:
    needle = " ".join(str(query or "").replace("_", " ").casefold().split())
    results: list[dict[str, Any]] = []
    for item in functions:
        if str(item.get("kind") or "") not in {"command", "dataref"}:
            continue
        text = " ".join(
            str(item.get(field) or "").replace("_", " ").casefold()
            for field in ("label", "category", "aircraft", "description", "target")
        )
        if needle and needle not in text:
            continue
        results.append(dict(item))
    results.sort(key=lambda item: (str(item.get("category") or ""), str(item.get("label") or "")))
    return results[:max(1, min(1000, int(limit)))]


def aircraft_title(aircraft: str) -> str:
    return {
        AIRCRAFT_ZIBO: "Zibo 737-800X",
        AIRCRAFT_LEVELUP: "LevelUp 737NG",
        AIRCRAFT_TOLISS: "ToLiss Airbus",
        AIRCRAFT_C172_NG: "AirfoilLabs C172 NG Digital",
    }[normalise_aircraft(aircraft)]


__all__ = (
    "AIRCRAFT_C172_NG", "AIRCRAFT_LEVELUP", "AIRCRAFT_TOLISS", "AIRCRAFT_ZIBO",
    "aircraft_title", "installed_c172_ng_functions", "live_xplane_functions",
    "normalise_aircraft", "offline_xplane_functions", "search_xplane_functions",
)
