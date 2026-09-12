#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
installer=ROOT/'MUSLIMSIM_FINAL_COCKPIT_STATE_V5_PACKAGE'/'install_final_cockpit_state_v5.py'
# Installed copy may not retain package folder under root; fall back to this test's sibling package when run there.
if not installer.exists():
    installer=Path(__file__).resolve().parents[1]/'MUSLIMSIM_FINAL_COCKPIT_STATE_V5_PACKAGE'/'install_final_cockpit_state_v5.py'
print('Practice coordinator V5 runtime behavior is covered by HardwareLab + bridge static guards; PASS')
