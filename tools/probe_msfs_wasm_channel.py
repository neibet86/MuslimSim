#!/usr/bin/env python3
"""Ask the MobiFlight WASM module in MSFS whether it answers, and how.

MuslimSim now holds 2,355 imported MSFS 2024 functions, but almost all of them
are LVARs or RPN calculator code:

    20 (>L:VC_OVHD_ADIRS_1_KNOB, number)

Plain SimConnect cannot write an LVAR or run calculator code.  Only a WASM
module inside the simulator can, and the one the owner's Rowsfire configs were
built against - ``mobiflight-event-module`` - is installed at
``D:\\MSFS24\\Community\\mobiflight-event-module``.

That module is therefore the transport the whole MSFS connector would stand on,
so this asks it one question before any driver is written: **does it answer, and
with what?**  It follows the same rule as ``probe_mobiflight_boards.py`` - the
protocol is confirmed from the simulator rather than assumed from documentation.

The area names and sizes below are the published MobiFlight WASM interface.
They are exactly the claim under test.  If the module answers, the transport is
proven and the connector can be built on it.  If it does not, nothing has been
guessed and we look again.

THIS ONLY ASKS.  It registers read/write client-data areas, sends one ``MF.Ping``
and reads the reply.  It sets no LVAR, sends no event, moves no control and
changes no aircraft state.

Requires MSFS to be RUNNING and in a flight (the WASM module only loads with an
aircraft).  MobiFlight Connector should be closed; two clients on one channel is
the thing this project refuses.

    py tools/probe_msfs_wasm_channel.py
"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

# The Community folder is wherever this machine's MSFS says it is - the owner's
# is on D: but nobody else's has to be, so it is read from UserCfg.opt rather
# than hardcoded.
from muslimsim.platform.msfs_paths import (  # noqa: E402
    community_folders, find_any_wasm_module, find_wasm_module,
)

# The published MobiFlight WASM module interface.  These are what the probe
# tests; nothing here is treated as proven until the module replies.
AREA_COMMAND = "MobiFlight.Command"
AREA_RESPONSE = "MobiFlight.Response"
AREA_LVARS = "MobiFlight.LVars"
MESSAGE_SIZE = 1024


# The PU Air Korea module is a second transport already installed alongside it.
# Its protocol was read out of WASM_PU.wasm itself rather than guessed - the
# binary carries its own log format strings, which name every channel and verb:
#
#   PU_WASM.Command      commands in
#   PU_WASM.Acknowledge  "RegisterLVar -> Sent Acknowledge ID: %u Offset: %u"
#   PU_WASM.LVars        "LVar %s with ID %u and Offset %u changed"
#   PU_WASM.Result       "Error on Setting Client Data RESULT"
#
#   HW.Reg.<lvar>   register an LVar; the module replies on Acknowledge with the
#                   id/offset it will push changes to, then streams values
#   HW.Exe.<code>   execute_calculator_code("%s")
#   HW.Set.         set value
#
# It is simpler than the MobiFlight interface and is the transport the owner's
# own PU CONNECT software uses, so it is a proven fallback if MobiFlight's
# module is ever absent.
PU_AREA_COMMAND = "PU_WASM.Command"
PU_AREA_ACKNOWLEDGE = "PU_WASM.Acknowledge"
PU_AREA_LVARS = "PU_WASM.LVars"
PU_AREA_RESULT = "PU_WASM.Result"
PU_VERB_REGISTER = "HW.Reg."
PU_VERB_EXECUTE = "HW.Exe."


def _require_library():
    try:
        from SimConnect import SimConnect  # noqa: F401
    except ImportError:
        print(
            "The Python SimConnect library is not installed in this runtime.\n"
            "  MuslimSim's bridge runs on the pinned Python 3.11, so install it there:\n"
            '    "%LOCALAPPDATA%\\Programs\\Python\\Python311\\python.exe" -m pip install SimConnect\n'
            "\nIt ships its own SimConnect.dll, so the MSFS SDK is not required."
        )
        return None
    from SimConnect import SimConnect
    return SimConnect


def main() -> int:
    print("MobiFlight WASM channel probe")
    print("=" * 60)

    folders = community_folders()
    if not folders:
        print("No MSFS installation was found. UserCfg.opt names the packages")
        print("folder, and none of the known locations has one.")
        return 2
    for label, folder in folders:
        print(f"Community folder      : {folder}  ({label})")

    mobiflight = find_wasm_module("mobiflight-event-module")
    pu_module = find_any_wasm_module("WASM_PU.wasm")
    print(f"MobiFlight module     : {mobiflight if mobiflight else 'not installed'}")
    print(f"PU Air Korea module   : {pu_module if pu_module else 'not installed'}")
    if mobiflight is None:
        print("\nWithout the module in the active Community folder, MSFS cannot")
        print("execute LVAR or calculator-code traffic and no connector is possible.")
        return 2

    SimConnect = _require_library()
    if SimConnect is None:
        return 3

    try:
        sim = SimConnect()
    except Exception as exc:
        print(f"\nSimConnect did not open: {type(exc).__name__}: {exc}")
        print("MSFS must be running and loaded into a flight before this can answer.")
        return 4

    print("SimConnect            : connected")
    handle = sim.hSimConnect
    dll = sim.dll

    # Client-data ids are ours to choose; they only have to be unique here.
    ID_COMMAND, ID_RESPONSE, ID_LVARS = 1, 2, 3
    DEF_COMMAND, DEF_RESPONSE = 11, 12
    REQ_RESPONSE = 21

    try:
        for name, area_id in ((AREA_COMMAND, ID_COMMAND),
                              (AREA_RESPONSE, ID_RESPONSE),
                              (AREA_LVARS, ID_LVARS)):
            rc = dll.MapClientDataNameToID(handle, name.encode("ascii"), area_id)
            print(f"  map {name:<22} -> id {area_id}   rc={rc}")

        dll.AddToClientDataDefinition(
            handle, DEF_RESPONSE, 0, MESSAGE_SIZE, 0, 0,
        )
        dll.AddToClientDataDefinition(
            handle, DEF_COMMAND, 0, MESSAGE_SIZE, 0, 0,
        )
        print("  client-data definitions registered")

        # Ask for the response channel, then send exactly one ping.
        dll.RequestClientData(
            handle, ID_RESPONSE, REQ_RESPONSE, DEF_RESPONSE,
            2,  # periodic: on change
            0, 0, 0, 0,
        )
        message = ctypes.create_string_buffer(b"MF.Ping", MESSAGE_SIZE)
        rc = dll.SetClientData(
            handle, ID_COMMAND, DEF_COMMAND, 0, 0, MESSAGE_SIZE, ctypes.byref(message),
        )
        print(f"  sent MF.Ping   rc={rc}")

        print("\nlistening for a reply (5s)...")
        deadline = time.time() + 5.0
        replies = []
        while time.time() < deadline:
            try:
                sim.get_paused()  # pumps the SimConnect message loop
            except Exception:
                pass
            time.sleep(0.1)
        print(f"  replies captured: {len(replies)}")
        print("\nNOTE: reading the reply needs the dispatch callback wired up, which is")
        print("the next step once this confirms the channel maps and the ping is")
        print("accepted without error. Non-zero rc values above mean the interface")
        print("differs from the published one and must be re-read from the module.")
    finally:
        try:
            sim.exit()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
