"""MuslimSim Studio integration for HOWALT D201/D203 direct serial panels.

This file is intentionally simulator-agnostic.  It connects the physical panel
owners to MuslimSim's existing HardwareLab/control-server surface.  Simulator
routing remains owned by the normal Studio profile/bridge machinery.
"""
from __future__ import annotations

import atexit
from typing import Any, Callable, Dict, Mapping, Optional

from .muslimrtp_d201 import D201_SPEC, MuslimSimRTPRouter
from .muslimatc_d203 import D203_SPEC, MuslimSimATCRouter


D201_INPUT_KEYS: Dict[str, str] = {
    "VHF1": "vhf1", "VHF2": "vhf2", "VHF3": "vhf3",
    "HF1": "hf1", "HF2": "hf2", "AM": "am",
    "TFR1": "tfr1", "TFR2": "tfr2",
    "TEST1": "test1", "TEST2": "test2", "OFF": "off",
    "BMQ1": "bmq1", "BMQ2-1": "bmq2_1", "BMQ2-2": "bmq2_2",
    "BMQ3-1": "bmq3_1", "BMQ3-2": "bmq3_2",
}

D203_INPUT_KEYS: Dict[str, str] = {
    "STBY": "stby", "RPTGOFF": "rptgoff", "XPNDR": "xpndr",
    "ONLY": "only", "ATCTEST": "atc_test", "TA-RA": "ta_ra",
    "XPN1-2": "xpn_1_2", "ALT1-2": "alt_1_2", "IDENT": "ident",
    "BMQ1-1": "bmq1_1", "BMQ1-2": "bmq1_2",
    "BMQ2-2": "bmq2_2", "BMQ2-1": "bmq2_1",
}

D201_OUTPUT_KEYS: Dict[str, str] = {
    "vhf1_led": "VHF1-L", "vhf2_led": "VHF2-L", "vhf3_led": "VHF3-L",
    "hf1_led": "HF1-L", "hf2_led": "HF2-L", "am_led": "AM-L",
    "backlight": "Back light",
    "smg_1": "SMG-1", "smg_2": "SMG-2", "smg_3": "SMG-3", "smg_4": "SMG-4",
    "smg_1_brightness": "SMG-1 brightness",
    "smg_2_brightness": "SMG-2 brightness",
    "smg_3_brightness": "SMG-3 brightness",
    "smg_4_brightness": "SMG-4 brightness",
}

D203_OUTPUT_KEYS: Dict[str, str] = {
    "backlight": "Back light", "fail_led": "FAIL-LED",
    "xpndr2_led": "2-LED", "xpndr1_led": "1-LED", "atc_led": "ATC-LED",
    "squawk": "SMG", "display": "SMG", "display_brightness": "SMG brightness",
}


def _phase_value(phase: str) -> float:
    phase = str(phase)
    if phase == "press":
        return 1.0
    if phase == "release":
        return 0.0
    if phase == "left":
        return -1.0
    if phase == "left-fast":
        return -2.0
    if phase == "right":
        return 1.0
    if phase == "right-fast":
        return 2.0
    return 0.0


class HowaltStudioBundle:
    """Own both HOWALT panels and bind them to one HardwareLab instance."""

    def __init__(
        self,
        *,
        hardware_lab: Any,
        control_server: Any = None,
        device_registration_cls: Any = None,
        diagnose: bool = False,
        rtp_port: Optional[str] = None,
        atc_port: Optional[str] = None,
    ) -> None:
        if hardware_lab is None:
            raise ValueError("HardwareLab is required for HOWALT Studio integration")
        self.hardware_lab = hardware_lab
        self.control_server = control_server
        self.device_registration_cls = device_registration_cls
        self.diagnose = bool(diagnose)
        self._stopped = False

        self.rtp = MuslimSimRTPRouter(
            port=rtp_port,
            input_router=self._make_input_router(
                D201_SPEC.key, D201_SPEC.input_indices, D201_INPUT_KEYS
            ),
            diagnose=self.diagnose,
        )
        self.atc = MuslimSimATCRouter(
            port=atc_port,
            input_router=self._make_input_router(
                D203_SPEC.key, D203_SPEC.input_indices, D203_INPUT_KEYS
            ),
            diagnose=self.diagnose,
        )

    def _make_input_router(
        self,
        device_key: str,
        raw_indices: Mapping[str, int],
        semantic_keys: Mapping[str, str],
    ) -> Callable[[int, str], bool]:
        index_to_raw = {int(index): name for name, index in raw_indices.items()}

        def route(index: int, phase: str) -> bool:
            raw_name = index_to_raw.get(int(index))
            if raw_name is None:
                return False
            control_key = semantic_keys.get(raw_name)
            if control_key is None:
                return False
            value = _phase_value(phase)
            try:
                outcome = self.hardware_lab.input(
                    device_key,
                    control_key,
                    value,
                    phase=str(phase),
                    source="physical",
                )
                if isinstance(outcome, Mapping):
                    return bool(outcome.get("routed"))
                return False
            except Exception as exc:
                try:
                    self.hardware_lab.record_diagnostic(
                        device_key,
                        "howalt-direct-input-error",
                        f"{control_key}: {type(exc).__name__}: {exc}",
                    )
                except Exception:
                    pass
                return False

        return route

    @staticmethod
    def _apply_output(router: Any, mapping: Mapping[str, str], control: str, value: Any) -> None:
        key = str(control).strip()
        target = mapping.get(key, key)
        router.set_lab_output(target, value)

    def start(self) -> None:
        self._stopped = False
        self.rtp.start()
        self.atc.start()
        self._register_control_server()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self.rtp.stop()
        self.atc.stop()

    def _register_control_server(self) -> None:
        if self.control_server is None or self.device_registration_cls is None:
            return
        registration = self.device_registration_cls

        self.control_server.register(registration(
            D201_SPEC.key,
            start=self.rtp.start,
            stop=self.rtp.stop,
            status=self.rtp.service_snapshot,
            output=lambda control, value: self._apply_output(
                self.rtp, D201_OUTPUT_KEYS, control, value
            ),
            diagnostics=self.rtp.studio_snapshot,
        ))
        self.control_server.register(registration(
            D203_SPEC.key,
            start=self.atc.start,
            stop=self.atc.stop,
            status=self.atc.service_snapshot,
            output=lambda control, value: self._apply_output(
                self.atc, D203_OUTPUT_KEYS, control, value
            ),
            diagnostics=self.atc.studio_snapshot,
        ))

    def snapshot(self) -> Dict[str, Any]:
        return {
            D201_SPEC.key: self.rtp.studio_snapshot(),
            D203_SPEC.key: self.atc.studio_snapshot(),
        }


def install_howalt_direct(
    *,
    hardware_lab: Any,
    control_server: Any = None,
    device_registration_cls: Any = None,
    diagnose: bool = False,
    rtp_port: Optional[str] = None,
    atc_port: Optional[str] = None,
) -> HowaltStudioBundle:
    """Create/start both direct services and arrange deterministic shutdown."""
    bundle = HowaltStudioBundle(
        hardware_lab=hardware_lab,
        control_server=control_server,
        device_registration_cls=device_registration_cls,
        diagnose=diagnose,
        rtp_port=rtp_port,
        atc_port=atc_port,
    )
    bundle.start()
    atexit.register(bundle.stop)
    return bundle
