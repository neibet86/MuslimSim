"""Shared, read-only CDU EXEC annunciator contract for BB35 and BB36.

The light command and channels in this module are not inferred vendor packets.
Both displays already use WinCtrl command 0x49 for brightness/light channels.
The BB36 SimAppPro update capture clears its five top annunciator windows on
channels 12..16; the photographed second window from the right is channel 15.
BB35's Boeing-labelled EXEC window is the rightmost member of the same bank.
"""

from __future__ import annotations

import math
from typing import Any, Tuple


ZIBO_CAPTAIN_EXEC_LIGHT_DATAREFS: Tuple[str, ...] = (
    "laminar/B738/indicators/fms_exec_light_pilot",
    "laminar/B738/indicators/fmc_exec_lights",
)

BB35_EXEC_LIGHT_CHANNEL = 16
BB36_EXEC_DASH_LIGHT_CHANNEL = 15
EXEC_LIGHT_OFF = 0
EXEC_LIGHT_ON = 255


def exec_light_active(value: Any) -> bool:
    """Return the discrete captain EXEC state from REST or WebSocket shapes."""

    if isinstance(value, dict):
        for key in ("value", "data", "values"):
            if key in value:
                return exec_light_active(value[key])
        if len(value) == 1:
            return exec_light_active(next(iter(value.values())))
        return False
    if isinstance(value, (list, tuple)):
        return exec_light_active(value[0]) if value else False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric) and numeric >= 0.5


def exec_light_output_value(
    value: Any,
    *,
    simulator_connected: bool,
    display_powered: bool,
) -> int:
    """Apply Live output authority to the discrete EXEC indication."""

    if (
        bool(simulator_connected)
        and bool(display_powered)
        and exec_light_active(value)
    ):
        return EXEC_LIGHT_ON
    return EXEC_LIGHT_OFF
