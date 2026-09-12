"""MUSLIMATC direct driver for the Hoowalt D203 ATC/transponder panel."""
from __future__ import annotations

from typing import Any, Optional

from .howalt_cmdmessenger import EventSink, HowaltDirectRouter, InputRouter, PanelSpec

D203_SPEC = PanelSpec(
    key="muslimatc_d203",
    software_name="MUSLIMATC",
    title="Hoowalt D203 ATC",
    module_name="Hoowalt D203 ATC",
    expected_serial="SN-4F6-017",
    buttons=("STBY", "RPTGOFF", "XPNDR", "ONLY", "ATCTEST", "TA-RA", "XPN1-2", "ALT1-2", "IDENT"),
    encoders=("BMQ1-1", "BMQ1-2", "BMQ2-2", "BMQ2-1"),
    outputs=("Back light", "FAIL-LED", "2-LED", "1-LED", "ATC-LED"),
    displays=("SMG",),
    default_brightness={"SMG": 15},
    aliases={
        "backlight": "Back light",
        "back light": "Back light",
        "squawk": "SMG",
        "code": "SMG",
        "transponder code": "SMG",
        "fail led": "FAIL-LED",
        "xpndr2 led": "2-LED",
        "xpndr 2 led": "2-LED",
        "2 led": "2-LED",
        "xpndr1 led": "1-LED",
        "xpndr 1 led": "1-LED",
        "1 led": "1-LED",
        "atc led": "ATC-LED",
    },
)


class MuslimSimATCRouter(HowaltDirectRouter):
    def __init__(
        self,
        *,
        port: Optional[str] = None,
        input_router: Optional[InputRouter] = None,
        event_sink: Optional[EventSink] = None,
        diagnose: bool = False,
    ) -> None:
        super().__init__(
            D203_SPEC,
            port=port,
            input_router=input_router,
            event_sink=event_sink,
            diagnose=diagnose,
        )

    def set_squawk(self, code: Any) -> None:
        # Keep leading zeros and use the exact four captured display positions.
        text = str(code).strip()
        text = text[-4:].rjust(4, "0")
        self.set_display("SMG", text, mask=0x0F)


# Requested user-facing software name.
MUSLIMATC = MuslimSimATCRouter
