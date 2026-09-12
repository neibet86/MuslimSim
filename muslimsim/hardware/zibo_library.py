"""Human-friendly simulator-function library used by the visual mapper.

This module deliberately contains no HID information and never sends a
simulator command.  It turns the command inventory supplied by the currently
loaded X-Plane aircraft into choices a pilot can search and assign from the
Studio.  The bridge adds the live Zibo command inventory when available; this
small built-in set keeps the same visual workflow useful while the simulator
is off.
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


# Axis mappings are intentionally a compact, verified list.  X-Plane's command
# inventory cannot report whether an arbitrary dataref is writable, so Studio
# must never present every read-only dataref as an axis target.
SAFE_AXIS_FUNCTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "axis-zibo-throttle-1", "kind": "dataref",
        "target": "laminar/B738/axis/throttle1", "label": "Throttle 1 axis",
        "category": "Zibo 737 • Engine", "description": "Direct Zibo throttle 1 input.",
    },
    {
        "id": "axis-zibo-throttle-2", "kind": "dataref",
        "target": "laminar/B738/axis/throttle2", "label": "Throttle 2 axis",
        "category": "Zibo 737 • Engine", "description": "Direct Zibo throttle 2 input.",
    },
    {
        "id": "axis-zibo-reverse-1", "kind": "dataref",
        "target": "laminar/B738/flt_ctrls/reverse_lever1", "label": "Reverse thrust 1 axis",
        "category": "Zibo 737 • Engine", "description": "Direct Zibo reverse-lever 1 input.",
    },
    {
        "id": "axis-zibo-reverse-2", "kind": "dataref",
        "target": "laminar/B738/flt_ctrls/reverse_lever2", "label": "Reverse thrust 2 axis",
        "category": "Zibo 737 • Engine", "description": "Direct Zibo reverse-lever 2 input.",
    },
    {
        "id": "axis-zibo-speedbrake", "kind": "dataref",
        "target": "laminar/B738/flt_ctrls/speedbrake_lever", "label": "Speedbrake axis",
        "category": "Zibo 737 • Flight controls", "description": "Direct Zibo speedbrake-lever input.",
    },
    {
        "id": "axis-rudder", "kind": "dataref",
        "target": "sim/joystick/yoke_heading_ratio", "label": "Rudder axis",
        "category": "X-Plane • Flight controls", "description": "Standard X-Plane joystick rudder input.",
    },
    {
        "id": "axis-left-brake", "kind": "dataref",
        "target": "sim/cockpit2/controls/left_brake_ratio", "label": "Left toe-brake axis",
        "category": "X-Plane • Brakes", "description": "Standard X-Plane left toe-brake input.",
    },
    {
        "id": "axis-right-brake", "kind": "dataref",
        "target": "sim/cockpit2/controls/right_brake_ratio", "label": "Right toe-brake axis",
        "category": "X-Plane • Brakes", "description": "Standard X-Plane right toe-brake input.",
    },
    # Added for the TCA Boeing quadrant's out-of-the-box rules.  Both were
    # confirmed writable against a running Zibo before being offered here.
    {
        "id": "axis-zibo-flap-lever", "kind": "dataref",
        "target": "laminar/B738/flt_ctrls/flap_lever", "label": "Flap lever axis",
        "category": "Zibo 737 • Flight controls",
        "description": "Direct Zibo flap-lever input.",
    },
    {
        "id": "axis-throttle-all-engines", "kind": "dataref",
        "target": "sim/cockpit2/engine/actuators/throttle_ratio_all",
        "label": "Thrust - all engines",
        "category": "X-Plane • Engine",
        "description": (
            "One lever drives every engine the loaded aircraft has. Engine-count "
            "agnostic, so the same binding is correct on a twin and on a four."
        ),
    },
)


# A short offline library.  The live command browser replaces/extends this
# list with every command currently registered by the loaded Zibo aircraft.
OFFLINE_COMMANDS: tuple[tuple[str, str, str, str], ...] = (
    ("Battery ON", "Zibo 737 • Electrical", "laminar/B738/switch/battery_dn", "Set the Boeing battery switch on."),
    ("Battery OFF", "Zibo 737 • Electrical", "laminar/B738/push_button/batt_full_off", "Set the Boeing battery switch off."),
    ("Ground power ON", "Zibo 737 • Electrical", "laminar/B738/toggle_switch/gpu_dn", "Set ground power on."),
    ("Ground power OFF", "Zibo 737 • Electrical", "laminar/B738/toggle_switch/gpu_up", "Set ground power off."),
    ("APU START", "Zibo 737 • APU", "laminar/B738/spring_toggle_switch/APU_start_pos_dn", "Move the APU selector to START."),
    ("APU ON", "Zibo 737 • APU", "laminar/B738/spring_toggle_switch/APU_start_pos_up", "Move the APU selector to ON."),
    ("Engine 1 starter GRD", "Zibo 737 • Engine start", "laminar/B738/rotary/eng1_start_grd", "Engage engine 1 ground start."),
    ("Engine 2 starter GRD", "Zibo 737 • Engine start", "laminar/B738/rotary/eng2_start_grd", "Engage engine 2 ground start."),
    ("Engine 1 fuel lever IDLE", "Zibo 737 • Engine", "laminar/B738/engine/mixture1_idle", "Set engine 1 fuel lever to IDLE."),
    ("Engine 1 fuel lever CUTOFF", "Zibo 737 • Engine", "laminar/B738/engine/mixture1_cutoff", "Set engine 1 fuel lever to CUTOFF."),
    ("Engine 2 fuel lever IDLE", "Zibo 737 • Engine", "laminar/B738/engine/mixture2_idle", "Set engine 2 fuel lever to IDLE."),
    ("Engine 2 fuel lever CUTOFF", "Zibo 737 • Engine", "laminar/B738/engine/mixture2_cutoff", "Set engine 2 fuel lever to CUTOFF."),
    ("Autothrottle disconnect", "Zibo 737 • Autoflight", "laminar/B738/autopilot/left_at_dis_press", "Press the left autothrottle disconnect."),
    ("Parking brake", "Zibo 737 • Brakes", "laminar/B738/push_button/park_brake_on_off", "Toggle the parking brake."),
    ("Flaps 0", "Zibo 737 • Flight controls", "laminar/B738/push_button/flaps_0", "Select flaps 0."),
    ("Flaps 5", "Zibo 737 • Flight controls", "laminar/B738/push_button/flaps_5", "Select flaps 5."),
    ("Flaps 15", "Zibo 737 • Flight controls", "laminar/B738/push_button/flaps_15", "Select flaps 15."),
    ("Flaps 25", "Zibo 737 • Flight controls", "laminar/B738/push_button/flaps_25", "Select flaps 25."),
    ("Flaps 30", "Zibo 737 • Flight controls", "laminar/B738/push_button/flaps_30", "Select flaps 30."),
    ("Landing lights ON", "Zibo 737 • Lights", "laminar/B738/switch/land_lights_left_on", "Set the left landing light on."),
    ("Landing lights OFF", "Zibo 737 • Lights", "laminar/B738/switch/land_lights_left_off", "Set the left landing light off."),
    ("Taxi light ON", "Zibo 737 • Lights", "laminar/B738/toggle_switch/taxi_light_brightness_on", "Set the taxi light on."),
    ("Taxi light OFF", "Zibo 737 • Lights", "laminar/B738/toggle_switch/taxi_light_brightness_off", "Set the taxi light off."),
    ("Yaw damper", "Zibo 737 • Flight controls", "laminar/B738/toggle_switch/yaw_dumper", "Toggle the yaw damper."),
    ("Autopilot disconnect", "X-Plane • Autoflight", "sim/autopilot/fdir_servos_toggle", "Toggle the flight-director servos."),
    ("Starter 1", "X-Plane • Engine start", "sim/engines/engage_starter_1", "Engage standard X-Plane starter 1."),
    ("Starter 2", "X-Plane • Engine start", "sim/engines/engage_starter_2", "Engage standard X-Plane starter 2."),
)


# A Zibo installation includes its own Lua command references.  Reading those
# files gives Studio a real, useful simulator-down catalogue instead of a tiny
# hand-written sample.  This is intentionally read-only and bounded to the
# known xLua script directory; Studio never writes into X-Plane or tries to
# guess commands which are not present in the installed aircraft.
_ZIBO_COMMAND_CALL = re.compile(
    r"(?:find_command|create_command)\s*\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)


def _local_zibo_roots() -> tuple[Path, ...]:
    """Return common Zibo aircraft locations without a wide disk scan."""

    candidates: list[Path] = []
    for variable in ("MUSLIMSIM_ZIBO_AIRCRAFT", "XPLANE_PATH", "XPLANE12_PATH"):
        configured = os.environ.get(variable, "").strip()
        if configured:
            root = Path(configured)
            candidates.extend((root, root / "Aircraft" / "B737-800X"))
    for drive in ("C", "D", "E", "F"):
        base = Path(f"{drive}:/")
        candidates.extend((
            base / "SteamLibrary" / "steamapps" / "common" / "X-Plane 12" / "Aircraft" / "B737-800X",
            base / "SteamLibrary" / "steamapps" / "common" / "X-Plane 11" / "Aircraft" / "B737-800X",
            base / "X-Plane 12" / "Aircraft" / "B737-800X",
            base / "X-Plane 11" / "Aircraft" / "B737-800X",
        ))
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            identity = str(candidate.resolve()).casefold()
        except OSError:
            identity = str(candidate).casefold()
        if identity not in seen:
            seen.add(identity)
            unique.append(candidate)
    return tuple(unique)


@lru_cache(maxsize=1)
def installed_zibo_functions() -> list[dict[str, Any]]:
    """Load the local Zibo package's command references, if it is installed.

    The current user installation exposes several hundred command references,
    including the full FMC keypad, MCP/EFIS, overhead, doors, EFB and cabin
    functions.  They remain separately tagged so the UI can state exactly
    whether choices came from an installed package or a live X-Plane session.
    """

    commands: set[str] = set()
    for aircraft_root in _local_zibo_roots():
        scripts = aircraft_root / "plugins" / "xlua" / "scripts"
        if not scripts.is_dir():
            continue
        try:
            files = tuple(scripts.rglob("*.lua"))
        except OSError:
            continue
        for script in files:
            try:
                text = script.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in _ZIBO_COMMAND_CALL.finditer(text):
                command = match.group(1).strip()
                if command.casefold().startswith("laminar/b738/"):
                    commands.add(command)
        if commands:
            break
    return [
        {
            "id": f"installed-zibo:{name}", "kind": "command", "target": name,
            "label": command_label(name), "category": command_category(name),
            "description": "Command referenced by the installed Zibo 737 package.",
            "source": "installed-zibo",
        }
        for name in sorted(commands, key=str.casefold)
    ]


def _normalise(text: Any) -> str:
    return " ".join(str(text or "").replace("_", " ").replace("/", " ").split()).strip()


def command_category(name: str) -> str:
    """Group one active simulator command without making up its function."""

    parts = [part for part in str(name).split("/") if part]
    if len(parts) >= 3 and parts[0].lower() == "laminar" and parts[1].upper() == "B738":
        return f"Zibo 737 • {_normalise(parts[2]).title()}"
    if parts and parts[0].lower() == "sim":
        return f"X-Plane • {_normalise(parts[1] if len(parts) > 1 else 'Commands').title()}"
    return "Aircraft / plugin • Commands"


def command_label(name: str, description: str = "") -> str:
    description = str(description or "").strip()
    if description:
        return description
    leaf = str(name).rsplit("/", 1)[-1]
    return _normalise(leaf).title() or str(name)


def offline_functions(*, include_axes: bool, include_installed: bool = True) -> list[dict[str, Any]]:
    """Return a simulator-down command library plus safe mapped axes.

    The local Zibo package wins over the small cross-aircraft starter set.
    This means the owner can map from the actual installed Zibo function set
    before launching X-Plane; normal live inventory still takes precedence
    once the simulator is running.
    """

    starter = [
        {
            "id": f"offline:{index}", "kind": "command", "target": target,
            "label": label, "category": category, "description": description,
            "source": "built-in",
        }
        for index, (label, category, target, description) in enumerate(OFFLINE_COMMANDS)
    ]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    installed = installed_zibo_functions() if include_installed else ()
    for item in [*installed, *starter]:
        target = str(item.get("target") or "")
        if not target or target in seen:
            continue
        seen.add(target)
        items.append(item)
    if include_axes:
        for item in SAFE_AXIS_FUNCTIONS:
            target = str(item.get("target") or "")
            if target not in seen:
                seen.add(target)
                items.append({**item, "source": "built-in"})
    return items


def live_command_functions(
    commands: Iterable[Mapping[str, Any]],
    *,
    include_axes: bool,
) -> list[dict[str, Any]]:
    """Convert X-Plane's live command inventory into visual mapper entries."""

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for command in commands:
        name = str(command.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        description = str(command.get("description") or "").strip()
        items.append({
            "id": f"command:{name}", "kind": "command", "target": name,
            "label": command_label(name, description),
            "category": command_category(name),
            "description": description or name,
            "source": "live-x-plane",
        })
    if include_axes:
        items.extend({**item, "source": "built-in"} for item in SAFE_AXIS_FUNCTIONS)
    return items


def search_functions(
    functions: Iterable[Mapping[str, Any]],
    query: str = "",
    *,
    limit: int = 700,
) -> list[dict[str, Any]]:
    """Return a bounded, predictable list for the Tk function browser."""

    needle = _normalise(query).casefold()
    results: list[dict[str, Any]] = []
    for item in functions:
        if str(item.get("kind")) not in {"command", "dataref"}:
            continue
        haystack = " ".join(
            _normalise(item.get(key)).casefold()
            for key in ("label", "category", "description", "target")
        )
        if needle and needle not in haystack:
            continue
        results.append(dict(item))
    results.sort(key=lambda item: (
        0 if str(item.get("category", "")).startswith("Zibo 737") else 1,
        str(item.get("category", "")), str(item.get("label", "")),
    ))
    return results[:max(1, int(limit))]


__all__ = (
    "SAFE_AXIS_FUNCTIONS", "command_category", "command_label", "offline_functions",
    "installed_zibo_functions", "live_command_functions", "search_functions",
)
