"""The MSFS 2024 dispatch path: one seam, several possible transports.

MuslimSim's X-Plane side sends a mapping through X-Plane's own Web API.  MSFS
has no equivalent for what this catalogue holds: nearly every imported function
is an LVAR or RPN calculator code, and **plain SimConnect cannot write an LVAR
or run calculator code**.  Only a WASM module inside the simulator can, because
``execute_calculator_code`` is a gauge API that exists in the sim's own process.

That single fact is why this module exists as an abstraction rather than a
driver.  Which module carries the traffic is a decision that can change - a
third-party one today, MuslimSim's own tomorrow - and the rest of the bridge
must not care.  Everything above this seam speaks ``MsfsTransport``; everything
below it is swappable:

    binding (protocol, target, value)
              |
        dispatch_msfs_binding()      <- aircraft gate, protocol routing
              |
        MsfsTransport                <- the seam
         /        |         \\
    Null      MobiFlight   MuslimSim's own WASM
   (refuses)   / PU_WASM      (needs the MSFS SDK)

The default transport refuses and explains.  Nothing here opens a simulator
connection on its own; a transport is installed deliberately by the bridge once
it has been proven against a running simulator.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

from ..hardware.msfs24_aircraft import msfs24_aircraft_title
from ..hardware.msfs24_detect import detect_msfs24_aircraft


class MsfsTransportError(RuntimeError):
    """A mapping could not be delivered to the simulator."""


class MsfsTransport(Protocol):
    """What any MSFS execution surface has to provide.

    Deliberately small.  Everything MuslimSim needs to send reduces to running
    calculator code or transmitting a SimConnect event, and everything it needs
    to read reduces to an LVAR or a simvar.
    """

    name: str

    def is_connected(self) -> bool:
        ...

    def execute_calculator_code(self, code: str) -> None:
        """Run RPN gauge code, e.g. ``20 (>L:VC_OVHD_ADIRS_1_KNOB, number)``."""

    def send_event(self, event: str, value: int = 0) -> None:
        """Transmit a SimConnect client event, e.g. ``THROTTLE1_AXIS_SET_EX1``."""

    def read_lvar(self, name: str) -> Optional[float]:
        """Latest value of an LVAR, or ``None`` when it is not registered."""


class NullMsfsTransport:
    """The safe default: accepts nothing and says exactly why.

    This is what the bridge runs with until a transport has been proven against
    a running simulator.  It is not a stub that silently drops writes - every
    call raises with the reason, so a mapping can never look delivered when it
    was not.
    """

    name = "none"

    def is_connected(self) -> bool:
        return False

    def _refuse(self, what: str):
        raise MsfsTransportError(
            f"MSFS 2024 has no dispatch transport installed, so {what} was not "
            "sent. The mapping is saved. Executing it needs a WASM module in the "
            "simulator, because SimConnect alone cannot write an LVAR or run "
            "calculator code. Use Practice mode to exercise the panel meanwhile."
        )

    def execute_calculator_code(self, code: str) -> None:
        self._refuse(f"calculator code {code!r}")

    def send_event(self, event: str, value: int = 0) -> None:
        self._refuse(f"event {event!r}")

    def read_lvar(self, name: str) -> Optional[float]:
        return None


# Protocols as they are spelled in msfs24_command_catalog.json.
PROTOCOL_RPN = "rpn"
PROTOCOL_LVAR = "lvar"
PROTOCOL_SIMCONNECT = "simconnect"
PROTOCOL_HEVENT = "hevent"


def build_calculator_code(protocol: str, target: str, value: Any) -> str:
    """Turn one catalogue entry into the gauge code that performs it.

    Nothing is invented: each form below is the shape the source that produced
    the entry already used.
    """

    protocol = str(protocol or "").strip().lower()
    target = str(target or "").strip()
    if not target:
        raise MsfsTransportError("A mapping with no target cannot be executed")

    if protocol == PROTOCOL_RPN:
        # Already executable gauge code, exactly as MobiFlight stored it.
        return target
    if protocol == PROTOCOL_LVAR:
        name = target[2:] if target.upper().startswith("L:") else target
        return f"{_number(value)} (>L:{name}, number)"
    if protocol == PROTOCOL_HEVENT:
        # PMDG's EVT_ names are H: events on the aircraft's own gauge.
        name = target[2:] if target.upper().startswith("H:") else target
        return f"(>H:{name})"
    raise MsfsTransportError(
        f"Protocol {protocol!r} is not calculator code; route it as an event"
    )


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def dispatch_msfs_binding(
    transport: MsfsTransport,
    *,
    protocol: str,
    target: str,
    value: Any = 0,
    phase: str = "change",
    selected_aircraft: str = "",
    loaded_title: str = "",
    loaded_path: str = "",
) -> dict:
    """Send one mapping to MSFS, refusing anything the aircraft gate rejects.

    The gate is the same rule the X-Plane bridge enforces: a mapping belongs to
    one aircraft workspace, and it may only reach the simulator while that
    aircraft is the one loaded.  Without it, a Fenix mapping could fire into a
    PMDG because both workspaces were open in the same session.
    """

    protocol = str(protocol or "").strip().lower()

    if selected_aircraft:
        loaded = detect_msfs24_aircraft(loaded_title, loaded_path)
        if loaded is None:
            raise MsfsTransportError(
                "The loaded MSFS aircraft was not recognised, so a mapping for "
                f"{msfs24_aircraft_title(selected_aircraft)} was not sent. "
                "MuslimSim never guesses which airframe is in the simulator."
            )
        if loaded != selected_aircraft:
            raise MsfsTransportError(
                f"The selected workspace is {msfs24_aircraft_title(selected_aircraft)} "
                f"but {msfs24_aircraft_title(loaded)} is loaded, so the mapping was "
                "not sent. Select the matching aircraft, or use Practice mode."
            )

    # A momentary command fires on the press, never again on the release.
    if protocol in {PROTOCOL_RPN, PROTOCOL_HEVENT} and str(phase) == "release":
        return {"sent": False, "reason": "release of a momentary command"}

    if protocol == PROTOCOL_SIMCONNECT:
        transport.send_event(target, int(_number(value)))
        return {"sent": True, "via": "event", "target": target}

    code = build_calculator_code(protocol, target, value)
    transport.execute_calculator_code(code)
    return {"sent": True, "via": "calculator", "code": code}


__all__ = (
    "MsfsTransport", "MsfsTransportError", "NullMsfsTransport",
    "PROTOCOL_HEVENT", "PROTOCOL_LVAR", "PROTOCOL_RPN", "PROTOCOL_SIMCONNECT",
    "build_calculator_code", "dispatch_msfs_binding",
)
