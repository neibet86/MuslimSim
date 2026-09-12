#!/usr/bin/env python3
"""Prove that the real bridge serves the lab before X-Plane is available."""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui.supervisor import BridgeSupervisor


def main() -> None:
    with TemporaryDirectory(prefix="muslimsim-hardware-lab-") as temporary:
        supervisor = BridgeSupervisor(profile_path=Path(temporary) / "profiles.json")
        supervisor.start()
        try:
            deadline = monotonic() + 12.0
            client = None
            while monotonic() < deadline:
                client = supervisor.client
                if client is not None:
                    break
                sleep(0.05)
            if client is None:
                raise AssertionError("Bridge did not expose a loopback control port")

            ping = client.request("ping")
            assert ping["ok"] is True
            assert "fcu_32_efis" in ping["devices"]
            state = client.request("lab_mode", mode="test")
            assert state["mode"] == "test"
            status = client.request("status")
            assert status["lab"]["simulator_connected"] is False
        finally:
            supervisor.stop()

    print("Bridge simulator-down control-channel end-to-end test passed.")


if __name__ == "__main__":
    main()
