"""Which outputs Practice mode may drive, and when they go back to sleep.

Practice exists to verify that a device works, with no simulator running.  A
panel that shows nothing when you press its buttons cannot do that, and until
now only five of the seventeen catalogued devices posted anything at all.

This module decides the policy; it performs no I/O and holds no state.

What Practice drives
--------------------
Only controls the catalogue already marks ``implemented`` **and**
``testable``, and only of kind ``led`` or ``lamp``.  Those two kinds have one
unambiguous practice meaning - lit or dark - and each already owns a
capture-proven driver adapter reachable through the normal lab output path.
Nothing here invents a vendor packet, which rule 0.1 forbids.

What Practice deliberately does not drive
-----------------------------------------
- ``display``  - every display adapter takes its own shape (line lists, window
  dicts, digit strings).  The five devices that already have a modelled
  practice display keep it; a sixth would have to be authored, not guessed.
- ``gauge``    - these are real actuators here, including the throttle's two
  vibration motors.  Practice lights indicators; it does not shake hardware.
- ``solenoid`` - same reason, and the PU's is a timed starter retract.

Sleep
-----
Rule 0.1 requires a tested output to return to OFF/BLACK when the test ends.
Practice has no explicit "end", so leaving a device alone is the end: its
indicators go dark once it has been idle for ``PRACTICE_IDLE_SLEEP_SECONDS``.
Touching it again wakes it.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .catalog import device_by_key

# Kinds whose lit/dark practice meaning is unambiguous.
PRACTICE_ECHO_KINDS = ("led", "lamp")

# How long a device keeps its practice indicators lit after the last input.
# Long enough to look at the panel you just pressed, short enough that walking
# away leaves the cockpit dark.
PRACTICE_IDLE_SLEEP_SECONDS = 20.0

PRACTICE_ECHO_ON = 1.0
PRACTICE_ECHO_OFF = 0.0

_CACHE: Dict[str, Tuple[str, ...]] = {}


def indicator_controls(device_key: str) -> Tuple[str, ...]:
    """Return the lamp/LED controls Practice is allowed to drive on a device."""

    key = str(device_key)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    spec = device_by_key(key)
    if spec is None:
        _CACHE[key] = ()
        return ()

    controls = tuple(
        control.key
        for control in spec.controls
        if control.is_output
        and control.kind in PRACTICE_ECHO_KINDS
        and control.status == "implemented"
        and control.testable
    )
    _CACHE[key] = controls
    return controls


def echo_outputs(device_key: str, lit: bool) -> Dict[str, Any]:
    """Return the practice indicator state for one device."""

    value = PRACTICE_ECHO_ON if lit else PRACTICE_ECHO_OFF
    return {control: value for control in indicator_controls(device_key)}


def devices_with_echo() -> Tuple[str, ...]:
    """Every catalogued device Practice can make visibly respond."""

    from .catalog import ALL_HARDWARE

    return tuple(
        item.key for item in ALL_HARDWARE if indicator_controls(item.key)
    )


__all__ = (
    "PRACTICE_ECHO_KINDS",
    "PRACTICE_ECHO_OFF",
    "PRACTICE_ECHO_ON",
    "PRACTICE_IDLE_SLEEP_SECONDS",
    "devices_with_echo",
    "echo_outputs",
    "indicator_controls",
)
