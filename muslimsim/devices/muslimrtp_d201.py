"""MUSLIMRTP direct driver for the Hoowalt D201 RTP radio panel."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from .howalt_cmdmessenger import EventSink, HowaltDirectRouter, InputRouter, PanelSpec

D201_SPEC = PanelSpec(
    key="muslimrtp_d201",
    software_name="MUSLIMRTP",
    title="Hoowalt D201 RTP",
    module_name="Hoowalt D201 RTP",
    expected_serial="SN-1FD-E25",
    buttons=(
        "VHF1", "VHF2", "VHF3", "HF1", "HF2", "AM",
        "TFR1", "TFR2", "TEST1", "TEST2", "OFF",
    ),
    encoders=("BMQ1", "BMQ2-1", "BMQ2-2", "BMQ3-1", "BMQ3-2"),
    outputs=("VHF1-L", "VHF2-L", "VHF3-L", "HF1-L", "HF2-L", "AM-L", "Back light"),
    displays=("SMG-1", "SMG-2", "SMG-3", "SMG-4"),
    default_brightness={"SMG-1": 7, "SMG-2": 7, "SMG-3": 7, "SMG-4": 7},
    aliases={
        "backlight": "Back light",
        "back light": "Back light",
        "smg1": "SMG-1", "smg 1": "SMG-1",
        "smg2": "SMG-2", "smg 2": "SMG-2",
        "smg3": "SMG-3", "smg 3": "SMG-3",
        "smg4": "SMG-4", "smg 4": "SMG-4",
        "vhf1 led": "VHF1-L", "vhf2 led": "VHF2-L", "vhf3 led": "VHF3-L",
        "hf1 led": "HF1-L", "hf2 led": "HF2-L", "am led": "AM-L",
    },
)


class MuslimSimRTPRouter(HowaltDirectRouter):
    def __init__(
        self,
        *,
        port: Optional[str] = None,
        input_router: Optional[InputRouter] = None,
        event_sink: Optional[EventSink] = None,
        diagnose: bool = False,
    ) -> None:
        super().__init__(
            D201_SPEC,
            port=port,
            input_router=input_router,
            event_sink=event_sink,
            diagnose=diagnose,
        )

    def set_radio_display(self, bank: int, text: Any, *, points: int = 0, mask: int = 0xFF) -> None:
        if bank not in (1, 2, 3, 4):
            raise ValueError("bank must be 1..4")
        self.set_display(f"SMG-{bank}", text, points=points, mask=mask)


# Requested user-facing software name.
MUSLIMRTP = MuslimSimRTPRouter
