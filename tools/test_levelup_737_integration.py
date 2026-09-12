"""Offline regression guard for BUG-18 LevelUp display and trim parity.

This test reads source only.  It never imports the bridge, opens X-Plane, or
touches a hardware handle.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINAL_PATH = ROOT / "bridge" / "final.py"


def _literal_assignment(tree: ast.AST, name: str) -> dict[str, str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict):
                raise AssertionError(f"{name} must remain a literal dictionary")
            return value
    raise AssertionError(f"missing assignment: {name}")


def _between(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


def main() -> None:
    source = FINAL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(FINAL_PATH))
    checks = 0

    levelup = _literal_assignment(tree, "LEVELUP_WINCTRL_COMMAND_OVERRIDES")
    assert levelup["pitch_trim_up"] == "sim/flight_controls/pitch_trim_up"
    assert levelup["pitch_trim_down"] == "sim/flight_controls/pitch_trim_down"
    checks += 2

    zibo = _literal_assignment(tree, "WINCTRL_COMMANDS")
    assert zibo["pitch_trim_up"] == "laminar/B738/flight_controls/pitch_trim_up"
    assert zibo["pitch_trim_down"] == "laminar/B738/flight_controls/pitch_trim_down"
    checks += 2

    pfd_gate = _between(
        source,
        "# The PFP page is deliberately independent",
        'print("Resolving captain PFD values for BB35/BB36 display paths...")',
    )
    assert "AIRCRAFT_PROFILE_LEVELUP" in pfd_gate
    checks += 1

    bb35_gate = _between(
        source,
        "use_bb35_path_router = (",
        "if args.pfp_pfd and not args.no_winctrl",
    )
    assert "AIRCRAFT_PROFILE_LEVELUP" in bb35_gate
    checks += 1

    bb36_gate = _between(
        source,
        "# BB36 uses one fixed display mode",
        "if MuslimSimBB36PathRouter is None:",
    )
    assert "AIRCRAFT_PROFILE_LEVELUP" in bb36_gate
    checks += 1

    assert "BB36 FMC/PFD router skipped for LevelUp profile" not in source
    checks += 1

    print(
        f"LevelUp 737 integration guard passed: {checks} checks; "
        "BB35/BB36 routes enabled, LevelUp trim overridden, Zibo trim preserved."
    )


if __name__ == "__main__":
    main()
