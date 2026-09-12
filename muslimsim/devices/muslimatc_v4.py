"""MUSLIMATC V4 direct driver for HOWALT/Hoowalt D203 ATC panels."""
from __future__ import annotations

from typing import Any, Optional

from .howalt_v4_protocol import EventSink, HowaltDirectRouter, InputRouter, PanelSpec

D203_SPEC = PanelSpec(
    key="muslimatc_d203",
    software_name="MUSLIMATC",
    title="MUSLIMATC - HOWALT D203 ATC",
    module_name="Hoowalt D203 ATC",
    identity_names=(
        "Howalt D203 ATC", "Hoowalt D203 ATC", "D203 ATC",
        "D203 XPNDR", "D203 Transponder",
    ),
    buttons=(
        "STBY", "RPTGOFF", "XPNDR", "ONLY", "ATCTEST",
        "TA-RA", "XPN1-2", "ALT1-2", "IDENT",
    ),
    encoders=("BMQ1-1", "BMQ1-2", "BMQ2-2", "BMQ2-1"),
    outputs=("Back light", "FAIL-LED", "2-LED", "1-LED", "ATC-LED"),
    displays=("SMG",),
    default_brightness={"SMG": 15},
    # Both supplied D203 .mcc profiles explicitly select ledDigits 0,1,2,3.
    display_masks={"SMG": 0x0F},
    aliases={
        "backlight": "Back light", "back light": "Back light",
        "squawk": "SMG", "display": "SMG", "code": "SMG",
        "transponder code": "SMG",
        "fail led": "FAIL-LED",
        "xpndr2 led": "2-LED", "xpndr 2 led": "2-LED", "2 led": "2-LED",
        "xpndr1 led": "1-LED", "xpndr 1 led": "1-LED", "1 led": "1-LED",
        "atc led": "ATC-LED",
    },
)


class MuslimATCV4(HowaltDirectRouter):
    def __init__(
        self,
        *,
        port: Optional[str] = None,
        input_router: Optional[InputRouter] = None,
        event_sink: Optional[EventSink] = None,
        diagnose: bool = False,
    ) -> None:
        super().__init__(
            D203_SPEC, port=port, input_router=input_router,
            event_sink=event_sink, diagnose=diagnose,
        )

    def set_squawk(self, code: Any) -> None:
        text = "".join(ch for ch in str(code).strip() if ch.isdigit())
        text = text[-4:].rjust(4, "0")
        self.set_display("SMG", text, mask=0x0F)

    def apply_practice_defaults(self) -> None:
        for output in D203_SPEC.outputs:
            self.set_output(output, 0)
        self.set_output("Back light", 200)
        self.set_output("ATC-LED", 255)
        self.set_squawk("5716")


MUSLIMATC = MuslimATCV4
