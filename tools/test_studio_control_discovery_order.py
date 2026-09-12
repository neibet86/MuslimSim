#!/usr/bin/env python3
"""Static regression guard for prompt Studio <-> bridge control discovery."""
from __future__ import annotations

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge" / "final.py"


def main() -> None:
    source = BRIDGE.read_text(encoding="utf-8")
    ast.parse(source, filename=str(BRIDGE))

    start_matches = list(re.finditer(
        r"(?m)^[ \t]*active_control_port = control_server\.start\(\)[ \t]*$",
        source,
    ))
    if len(start_matches) != 1:
        raise AssertionError(
            f"Expected one control_server.start() assignment, found {len(start_matches)}"
        )

    port_matches = list(re.finditer(
        r'(?m)^[ \t]*print\(f"CONTROL CHANNEL PORT \{active_control_port\}", flush=True\)[ \t]*$',
        source,
    ))
    if len(port_matches) != 1:
        raise AssertionError(
            f"Expected one flushed CONTROL CHANNEL PORT announcement, found {len(port_matches)}"
        )

    token_matches = list(re.finditer(
        r'(?m)^[ \t]*print\(f"CONTROL CHANNEL TOKEN \{control_server\.token\}", flush=True\)[ \t]*$',
        source,
    ))
    profile_matches = list(re.finditer(
        r'(?m)^[ \t]*print\(f"HARDWARE LAB PROFILE \{lab_profile_path\}", flush=True\)[ \t]*$',
        source,
    ))
    if len(token_matches) != 1 or len(profile_matches) != 1:
        raise AssertionError("Control-channel token/profile announcements are not uniquely flushed")

    start = start_matches[0].start()
    port = port_matches[0].start()
    input_sink = source.find("hardware_lab.set_practice_input_sink(_muslimsim_practice_input)", start)
    startup_output = source.find('source="bridge-startup"', start)
    if startup_output < 0:
        raise AssertionError("Could not find the guarded bridge-startup hardware-output marker")
    if input_sink < 0:
        raise AssertionError("Could not find the in-memory practice-input sink wiring")
    if not (start < input_sink < port < startup_output):
        raise AssertionError(
            "Control port must be announced after in-memory lab wiring and before bridge-startup hardware I/O"
        )

    print("PASS  Studio control-channel discovery is flushed after lab wiring and before hardware startup I/O")


if __name__ == "__main__":
    main()
