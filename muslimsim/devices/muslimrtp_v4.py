"""MUSLIMRTP V4 direct driver for HOWALT/Hoowalt D201 RTP panels."""
from __future__ import annotations

from typing import Any, Optional

from .howalt_v4_protocol import EventSink, HowaltDirectRouter, InputRouter, PanelSpec

D201_SPEC = PanelSpec(
    key="muslimrtp_d201",
    software_name="MUSLIMRTP",
    title="MUSLIMRTP - HOWALT D201 RTP",
    module_name="Hoowalt D201 RTP",
    identity_names=("Howalt D201 RTP", "Hoowalt D201 RTP", "D201 RTP"),
    buttons=(
        "VHF1", "VHF2", "VHF3", "HF1", "HF2", "AM",
        "TFR1", "TFR2", "TEST1", "TEST2", "OFF",
    ),
    encoders=("BMQ1", "BMQ2-1", "BMQ2-2", "BMQ3-1", "BMQ3-2"),
    outputs=("VHF1-L", "VHF2-L", "VHF3-L", "HF1-L", "HF2-L", "AM-L", "Back light"),
    displays=("SMG-1", "SMG-2", "SMG-3", "SMG-4"),
    default_brightness={"SMG-1": 7, "SMG-2": 7, "SMG-3": 7, "SMG-4": 7},
    # D201RTPLCD.pcapng directly proves SMG-1/SMG-2 command mask 63 (0x3F)
    # and point plane 8 for three-decimal VHF values (for example 124.850).
    # The saved D201 board config proves SMG-3/SMG-4 are separate modules; the
    # owner's faceplate photograph shows their NAV windows as five positions,
    # so only those lower masks remain photo-derived at 0x1F. Practice mode
    # writes every module independently so that inference is easy to verify.
    display_masks={"SMG-1": 0x3F, "SMG-2": 0x3F, "SMG-3": 0x1F, "SMG-4": 0x1F},
    aliases={
        "backlight": "Back light", "back light": "Back light",
        "smg1": "SMG-1", "smg 1": "SMG-1",
        "smg2": "SMG-2", "smg 2": "SMG-2",
        "smg3": "SMG-3", "smg 3": "SMG-3",
        "smg4": "SMG-4", "smg 4": "SMG-4",
        "vhf1 led": "VHF1-L", "vhf2 led": "VHF2-L", "vhf3 led": "VHF3-L",
        "hf1 led": "HF1-L", "hf2 led": "HF2-L", "am led": "AM-L",
    },
)


class MuslimRTPV4(HowaltDirectRouter):
    def __init__(
        self,
        *,
        port: Optional[str] = None,
        input_router: Optional[InputRouter] = None,
        event_sink: Optional[EventSink] = None,
        diagnose: bool = False,
    ) -> None:
        super().__init__(
            D201_SPEC, port=port, input_router=input_router,
            event_sink=event_sink, diagnose=diagnose,
        )

    def set_radio_display(self, bank: int, text: Any, *, points: int = 0) -> None:
        if bank not in (1, 2, 3, 4):
            raise ValueError("bank must be 1..4")
        name = f"SMG-{bank}"
        self.set_display(name, text, points=points, mask=D201_SPEC.display_masks[name])

    def apply_practice_defaults(self) -> None:
        """Stage a complete safe display/illumination proof without a simulator."""
        for output in D201_SPEC.outputs:
            self.set_output(output, 0)
        self.set_output("Back light", 200)
        self.set_output("VHF2-L", 255)
        self.set_radio_display(1, "120.900")
        self.set_radio_display(2, "129.875")
        self.set_radio_display(3, "114.85")
        self.set_radio_display(4, "115.40")


MUSLIMRTP = MuslimRTPV4
