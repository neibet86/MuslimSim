#!/usr/bin/env python3
from __future__ import annotations
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
bridge=(ROOT/'bridge/final.py').read_text(encoding='utf-8-sig')
studio=(ROOT/'muslimsim/gui/studio.py').read_text(encoding='utf-8-sig')
ast.parse(bridge); ast.parse(studio)
required=(
 'MUSLIMSIM_FINAL_COCKPIT_STATE_V5',
 'practice_outputs_active',
 '_muslimsim_set_practice_output_group',
 '_muslimsim_cockpit_output_ready',
 'panel_wake', 'panel_backlight',
 'throttle_backlight', 'flaps_airbrake_backlight', 'trim_display_backlight',
 'source="baseline"', 'left_toe_brake', 'right_toe_brake',
)
for marker in required:
    assert marker in bridge, marker
assert 'self._request(\n            "practice_wake"' not in studio
assert 'MUSLIMSIM_FINAL_COCKPIT_STATE_V5' in studio
# Practice gate must remain fail-closed.
assert 'return hardware_lab.mode == "test"' in bridge
assert 'MUSLIMSIM_STARTUP_PRACTICE_AUTHORITY_V32' in bridge
print('Final cockpit state V5 static contract: PASS')
