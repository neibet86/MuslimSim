#!/usr/bin/env python3
"""Run MuslimSim's simulator-independent hardware-lab self-tests."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.hardware.selftest import run_self_tests


if __name__ == "__main__":
    run_self_tests()
    print("Hardware laboratory self-test passed: catalogue, persistence, test mode, and loopback token checks are valid.")
