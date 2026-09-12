#!/usr/bin/env python3
"""ToLiss Airbus dispatcher for the WINCTRL FCU-32 / EFIS-32L / EFIS-32R
(VID 4098 / PID BA01) - the real device this hardware already models
(FCU/EFIS is native Airbus terminology; unlike the AGP/throttle, the panel's
own button semantics - AP1/AP2, A/THR, EXPED, LOC, APPR, TRK/FPA, SPD/MACH,
per-side ND mode/range selectors - already match a real A320 FCU + EFIS
control panel directly, with no Boeing reinterpretation needed).

Sibling to fcu_efis_ba01.py's MuslimSimFCUEFISZiboDispatcher - imports from
that module (FcuRawInputEvent, FCU_EFIS_CONTROL_DEFINITIONS) but never edits
it, so the proven Zibo dispatch stays untouched.

Commands/datarefs are verified against
muslimsim/hardware/xplane_command_catalog.json (aircraft == "toliss") or,
for the four bearing selectors absent from that static list, the loaded
aircraft's own writable X-Plane API entries and knobs.obj bindings.  No
selector enum is inferred from a similarly named Boeing control.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, Optional

from .fcu_efis_ba01 import FcuRawInputEvent

# Simple one-shot commands (activate on press). Real, catalogued ToLiss names.
FCU_EFIS_TOLISS_COMMANDS: Dict[str, str] = {
    "ap1": "toliss_airbus/ap1_push",
    "ap2": "toliss_airbus/ap2_push",
    "athr": "AirbusFBW/ATHRbutton",
    "loc": "AirbusFBW/LOCbutton",
    "appr": "AirbusFBW/APPRbutton",
    "exped": "AirbusFBW/EXPEDbutton",
    "trk": "toliss_airbus/hdgtrk_button_push",
    "mach": "toliss_airbus/ias_mach_button_push",
    "metric": "toliss_airbus/metric_alt_button_push",
    "speed_push": "AirbusFBW/PushSPDSel",
    "speed_pull": "AirbusFBW/PullSPDSel",
    "heading_push": "AirbusFBW/PushHDGSel",
    "heading_pull": "AirbusFBW/PullHDGSel",
    "altitude_push": "AirbusFBW/PushAltitude",
    "altitude_pull": "AirbusFBW/PullAltitude",
    "vs_push": "AirbusFBW/PushVSSel",
    "vs_pull": "AirbusFBW/PullVSSel",
    "left_fd": "toliss_airbus/fd1_push",
    "right_fd": "toliss_airbus/fd2_push",
    "left_std_push": "toliss_airbus/capt_baro_push",
    "left_std_pull": "toliss_airbus/capt_baro_pull",
    "right_std_push": "toliss_airbus/copilot_baro_push",
    "right_std_pull": "toliss_airbus/copilot_baro_pull",
    "left_ls": "toliss_airbus/dispcommands/CaptLSButtonPush",
    "right_ls": "toliss_airbus/dispcommands/CoLSButtonPush",
}

# Booleans with no dedicated toggle command - real ToLiss datarefs, written
# directly (read current, write the opposite), the same pattern
# _run_toliss_agp_profile's own apply_default() already uses for
# "terr_on_nd" (AirbusFBW/TerrainSelectedND1).
FCU_EFIS_TOLISS_TOGGLE_DATAREFS: Dict[str, str] = {
    "left_cstr": "AirbusFBW/NDShowCSTRCapt", "right_cstr": "AirbusFBW/NDShowCSTRFO",
    "left_wpt": "AirbusFBW/NDShowWPTCapt", "right_wpt": "AirbusFBW/NDShowWPTFO",
    "left_vord": "AirbusFBW/NDShowVORDCapt", "right_vord": "AirbusFBW/NDShowVORDFO",
    "left_ndb": "AirbusFBW/NDShowNDBCapt", "right_ndb": "AirbusFBW/NDShowNDBFO",
    "left_arpt": "AirbusFBW/NDShowARPTCapt", "right_arpt": "AirbusFBW/NDShowARPTFO",
}

# Two-position selectors (baro unit) - a captured value written per key,
# never a toggle (matching the AGP's own utc_gps/utc_int/utc_set pattern).
FCU_EFIS_TOLISS_BARO_UNIT: Dict[str, tuple] = {
    "left_inhg": ("AirbusFBW/BaroUnitCapt", 0), "left_hpa": ("AirbusFBW/BaroUnitCapt", 1),
    "right_inhg": ("AirbusFBW/BaroUnitFO", 0), "right_hpa": ("AirbusFBW/BaroUnitFO", 1),
}

# ND mode/range rotary positions - real datarefs (AirbusFBW/NDmodeCapt/FO,
# NDrangeCapt/FO), but the catalog carries no enum-order metadata. Ordering
# below follows the physical rotary's own printed sequence (LS-VOR-NAV-ARC-
# PLAN, 10-20-40-80-160-320nm) - JUDGMENT CALL, confirm against a live
# session and correct the index map if the wrong page/range comes up.
FCU_EFIS_TOLISS_ND_MODE: Dict[str, tuple] = {
    "left_mode_ls": ("AirbusFBW/NDmodeCapt", 0), "left_mode_vor": ("AirbusFBW/NDmodeCapt", 1),
    "left_mode_nav": ("AirbusFBW/NDmodeCapt", 2), "left_mode_arc": ("AirbusFBW/NDmodeCapt", 3),
    "left_mode_plan": ("AirbusFBW/NDmodeCapt", 4),
    "right_mode_ls": ("AirbusFBW/NDmodeFO", 0), "right_mode_vor": ("AirbusFBW/NDmodeFO", 1),
    "right_mode_nav": ("AirbusFBW/NDmodeFO", 2), "right_mode_arc": ("AirbusFBW/NDmodeFO", 3),
    "right_mode_plan": ("AirbusFBW/NDmodeFO", 4),
}
FCU_EFIS_TOLISS_ND_RANGE: Dict[str, tuple] = {
    "left_range_10": ("AirbusFBW/NDrangeCapt", 0), "left_range_20": ("AirbusFBW/NDrangeCapt", 1),
    "left_range_40": ("AirbusFBW/NDrangeCapt", 2), "left_range_80": ("AirbusFBW/NDrangeCapt", 3),
    "left_range_160": ("AirbusFBW/NDrangeCapt", 4), "left_range_320": ("AirbusFBW/NDrangeCapt", 5),
    "right_range_10": ("AirbusFBW/NDrangeFO", 0), "right_range_20": ("AirbusFBW/NDrangeFO", 1),
    "right_range_40": ("AirbusFBW/NDrangeFO", 2), "right_range_80": ("AirbusFBW/NDrangeFO", 3),
    "right_range_160": ("AirbusFBW/NDrangeFO", 4), "right_range_320": ("AirbusFBW/NDrangeFO", 5),
}

# Rotary encoders use the four writable ToLiss FCU knob-position datarefs
# referenced by the aircraft's own VR manipulators (AXIS_KNOB -10..29, step
# 1). A controlled live test moved each position by +1 and observed exactly
# one native FCU increment: SPD/HDG +1, ALT +100 at the current 100 setting,
# and V/S +100. Restoring each position restored the selected target. These
# are control inputs; the read-only PFD output values remain display sources.
FCU_EFIS_TOLISS_ROTARY_DATAREFS: Dict[str, tuple] = {
    "speed_inc": ("AirbusFBW/FCUSpeedKnobRotation", 1),
    "speed_dec": ("AirbusFBW/FCUSpeedKnobRotation", -1),
    "heading_inc": ("AirbusFBW/FCUHeadingKnobRotation", 1),
    "heading_dec": ("AirbusFBW/FCUHeadingKnobRotation", -1),
    "altitude_inc": ("AirbusFBW/FCUAltKnobRotation", 1),
    "altitude_dec": ("AirbusFBW/FCUAltKnobRotation", -1),
    "vs_inc": ("AirbusFBW/FCUVSKnobRotation", 1),
    "vs_dec": ("AirbusFBW/FCUVSKnobRotation", -1),
}
FCU_EFIS_TOLISS_ALTITUDE_STEP_DATAREF = "AirbusFBW/ALT100_1000"

# Kept as an empty compatibility export for callers that imported the former
# diagnostic marker. The rotaries are no longer blocked.
FCU_EFIS_TOLISS_BLOCKED_ROTARY = frozenset()

# The loaded ToLiss aircraft publishes the four EFIS source-selector animation
# datarefs as writable integer controls.  Its own knobs.obj binds the physical
# ADF/OFF/VOR sequence to positions 0/1/2.  Keep every captured BA01 position
# explicit so a selector is an absolute three-position write, never a toggle.
FCU_EFIS_TOLISS_NAV_SOURCE: Dict[str, tuple] = {
    "left_nav1_adf": ("ckpt/fcu/adf1Left/anim", 0),
    "left_nav1_off": ("ckpt/fcu/adf1Left/anim", 1),
    "left_nav1_vor": ("ckpt/fcu/adf1Left/anim", 2),
    "left_nav2_adf": ("ckpt/fcu/adf2Left/anim", 0),
    "left_nav2_off": ("ckpt/fcu/adf2Left/anim", 1),
    "left_nav2_vor": ("ckpt/fcu/adf2Left/anim", 2),
    "right_nav1_adf": ("ckpt/fcu/adf1Right/anim", 0),
    "right_nav1_off": ("ckpt/fcu/adf1Right/anim", 1),
    "right_nav1_vor": ("ckpt/fcu/adf1Right/anim", 2),
    "right_nav2_adf": ("ckpt/fcu/adf2Right/anim", 0),
    "right_nav2_off": ("ckpt/fcu/adf2Right/anim", 1),
    "right_nav2_vor": ("ckpt/fcu/adf2Right/anim", 2),
}

# Compatibility export retained for diagnostics.  Every captured FCU/EFIS
# control now has a proven ToLiss action.
FCU_EFIS_TOLISS_UNDRIVEN = frozenset()


class MuslimSimFCUEFISTolissDispatcher:
    """Apply the source-verified BA01 ToLiss profile through bridge callbacks.

    Same __call__(event) shape as MuslimSimFCUEFISZiboDispatcher so it can be
    used as a drop-in alternate fallback dispatcher, chosen by the live
    aircraft_profile at event time.
    """

    def __init__(self, *, api_version: str, resolve_dataref_id: Callable[[str, str], int],
                 read_dataref: Callable[[str, int], float], set_dataref: Callable[[str, int, float], None],
                 resolve_command_id: Callable[[str, str], int], activate_command: Callable[[str, int, float], None],
                 diagnose: bool = False) -> None:
        self.api_version = str(api_version)
        self._resolve_dataref_id, self._read_dataref, self._set_dataref = resolve_dataref_id, read_dataref, set_dataref
        self._resolve_command_id, self._activate_command = resolve_command_id, activate_command
        self.diagnose = bool(diagnose)
        self._dataref_ids: Dict[str, int] = {}
        self._command_ids: Dict[str, int] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _is_stale_id(error: Exception) -> bool:
        return getattr(error, "code", None) == 404

    def _command_id(self, command: str, *, refresh: bool = False) -> int:
        if refresh or command not in self._command_ids:
            self._command_ids[command] = self._resolve_command_id(self.api_version, command)
        return self._command_ids[command]

    def _dataref_id(self, dataref: str, *, refresh: bool = False) -> int:
        if refresh or dataref not in self._dataref_ids:
            self._dataref_ids[dataref] = self._resolve_dataref_id(self.api_version, dataref)
        return self._dataref_ids[dataref]

    def _activate(self, command: str) -> None:
        try:
            self._activate_command(self.api_version, self._command_id(command), 0.0)
        except Exception as exc:
            if not self._is_stale_id(exc):
                raise
            self._activate_command(self.api_version, self._command_id(command, refresh=True), 0.0)

    def _set(self, dataref: str, value: float) -> None:
        try:
            self._set_dataref(self.api_version, self._dataref_id(dataref), float(value))
        except Exception as exc:
            if not self._is_stale_id(exc):
                raise
            self._set_dataref(self.api_version, self._dataref_id(dataref, refresh=True), float(value))

    def _read(self, dataref: str, fallback: float = 0.0) -> float:
        try:
            return float(self._read_dataref(self.api_version, self._dataref_id(dataref)))
        except Exception:
            try:
                return float(self._read_dataref(self.api_version, self._dataref_id(dataref, refresh=True)))
            except Exception:
                return fallback

    def _rotate(self, dataref: str, delta: int) -> None:
        """Move one native ToLiss AXIS_KNOB detent, wrapping -10..29."""

        current = int(round(self._read(dataref)))
        target = ((current + int(delta) + 10) % 40) - 10
        self._set(dataref, target)

    def __call__(self, event: FcuRawInputEvent) -> None:
        if event.phase != "press":
            return
        key = event.control
        try:
            with self._lock:
                if key in FCU_EFIS_TOLISS_UNDRIVEN:
                    return
                if key == "altitude_step_100": self._set(FCU_EFIS_TOLISS_ALTITUDE_STEP_DATAREF, 0)
                elif key == "altitude_step_1000": self._set(FCU_EFIS_TOLISS_ALTITUDE_STEP_DATAREF, 1)
                elif key in FCU_EFIS_TOLISS_ROTARY_DATAREFS:
                    dataref, delta = FCU_EFIS_TOLISS_ROTARY_DATAREFS[key]
                    self._rotate(dataref, delta)
                elif key == "left_baro_inc": self._set("AirbusFBW/BaroKnobRotationCapt", self._read("AirbusFBW/BaroKnobRotationCapt") + 1)
                elif key == "left_baro_dec": self._set("AirbusFBW/BaroKnobRotationCapt", self._read("AirbusFBW/BaroKnobRotationCapt") - 1)
                elif key == "right_baro_inc": self._set("AirbusFBW/BaroKnobRotationFO", self._read("AirbusFBW/BaroKnobRotationFO") + 1)
                elif key == "right_baro_dec": self._set("AirbusFBW/BaroKnobRotationFO", self._read("AirbusFBW/BaroKnobRotationFO") - 1)
                elif key in FCU_EFIS_TOLISS_BARO_UNIT:
                    dataref, value = FCU_EFIS_TOLISS_BARO_UNIT[key]; self._set(dataref, value)
                elif key in FCU_EFIS_TOLISS_ND_MODE:
                    dataref, value = FCU_EFIS_TOLISS_ND_MODE[key]; self._set(dataref, value)
                elif key in FCU_EFIS_TOLISS_ND_RANGE:
                    dataref, value = FCU_EFIS_TOLISS_ND_RANGE[key]; self._set(dataref, value)
                elif key in FCU_EFIS_TOLISS_NAV_SOURCE:
                    dataref, value = FCU_EFIS_TOLISS_NAV_SOURCE[key]; self._set(dataref, value)
                elif key in FCU_EFIS_TOLISS_TOGGLE_DATAREFS:
                    dataref = FCU_EFIS_TOLISS_TOGGLE_DATAREFS[key]
                    self._set(dataref, 0.0 if self._read(dataref) >= 0.5 else 1.0)
                elif key in FCU_EFIS_TOLISS_COMMANDS: self._activate(FCU_EFIS_TOLISS_COMMANDS[key])
                else: return
        except Exception as exc:
            # Printed unconditionally (not gated by self.diagnose) - the
            # bridge's own outer event handler only records this to a
            # Studio diagnostic log, easy to miss, so a real failure here
            # must be visible in the console on its own.
            print(f"FCU/EFIS BA01 {key} -> ToLiss FAILED: {type(exc).__name__}: {exc}")
            return
        if self.diagnose:
            print(f"FCU/EFIS BA01 {key} -> ToLiss")


__all__ = (
    "FCU_EFIS_TOLISS_COMMANDS", "FCU_EFIS_TOLISS_TOGGLE_DATAREFS", "FCU_EFIS_TOLISS_BARO_UNIT",
    "FCU_EFIS_TOLISS_ND_MODE", "FCU_EFIS_TOLISS_ND_RANGE", "FCU_EFIS_TOLISS_ROTARY_DATAREFS",
    "FCU_EFIS_TOLISS_NAV_SOURCE",
    "FCU_EFIS_TOLISS_ALTITUDE_STEP_DATAREF", "FCU_EFIS_TOLISS_BLOCKED_ROTARY",
    "FCU_EFIS_TOLISS_UNDRIVEN", "MuslimSimFCUEFISTolissDispatcher",
)
