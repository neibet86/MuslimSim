"""Low-overhead, simulator-independent cockpit state for Studio practice mode.

This is a panel model, not an aircraft simulator.  It produces the same kinds
of target values and FMC text that the Studio needs to exercise its visual
controls while X-Plane is off.  It never opens USB, talks to X-Plane, or
performs a real aircraft action.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, Mapping, Optional, Tuple

from .practice_echo import (
    PRACTICE_IDLE_SLEEP_SECONDS,
    echo_outputs,
    indicator_controls,
)


def _row(text: str) -> str:
    return str(text)[:24].ljust(24)


class VirtualZiboPreview:
    """A small mutable Zibo-style panel preview used only in practice mode."""

    def __init__(self) -> None:
        self.speed = 250
        self.heading = 90
        self.altitude = 10000
        self.vertical_speed = 0
        self.course_capt = 0
        self.course_fo = 0
        self.left_baro = 29.92
        self.right_baro = 29.92
        # These are deliberately only a Studio practice model.  They hold
        # the selected positions of the two EFIS panels so a real press, a
        # virtual click, and the faceplate all have the same visible result
        # while X-Plane is not running.  They are not claimed to be output
        # telemetry from the BA01 hardware.
        self._efis: Dict[str, Dict[str, Any]] = {
            side: {
                "unit": "inhg", "std": False, "mode": "nav", "range": 40,
                "nav1": "off", "nav2": "off",
                "buttons": {
                    "fd": False, "ls": False, "cstr": False, "wpt": False,
                    "vord": False, "ndb": False, "arpt": False,
                },
            }
            for side in ("left", "right")
        }
        self._pap3_lights: Dict[str, float] = {
            "led_n1": 0.0, "led_speed": 0.0, "led_vnav": 0.0,
            "led_lvl_chg": 0.0, "led_hdg_sel": 0.0, "led_lnav": 0.0,
            "led_vorloc": 0.0, "led_app": 0.0, "led_alt_hld": 0.0,
            "led_vs": 0.0, "led_cmd_a": 0.0, "led_cws_a": 0.0,
            "led_cmd_b": 0.0, "led_cws_b": 0.0, "led_at_arm": 0.0,
            "led_ma_capt": 0.0, "led_ma_fo": 0.0,
        }
        # The AGP practice model mirrors the bridge's two-mode fallback head.
        # TERR ON ND is the only mode switch.
        self.agp_page = "radio"
        self._agp_brake_fan = False
        self._agp_autobrake = "OFF"
        self._agp_anti_skid = True
        self._agp_gear = "DOWN"
        self._agp_vhf = 1
        self._agp_radio_editing = False
        self._agp_active_khz = {1: 120900, 2: 121500, 3: 122800}
        self._agp_standby_khz = {1: 129875, 2: 124850, 3: 126000}
        self._agp_squawk = "1200"
        self._agp_squawk_digit = 0
        self._agp_squawk_editing = False
        self._agp_xpdr_mode = "off"
        self._agp_mode_shown_until = 0.0
        self._agp_elapsed_running = False
        # The AGP's three pressable encoders publish independent signed raw
        # counters. Test mode models the same relative count.
        self._agp_rotary_raw = {"rst": 0, "chr": 0, "date": 0}
        self._scratchpad: Dict[str, str] = {"pfp3n_bb35": "", "mcdu32_bb36": ""}
        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        # Only five devices were ever modelled here, so pressing a control on
        # any of the other twelve produced nothing at all - the panel simply
        # never responded.  Every catalogued device now keeps a wake stamp, and
        # the snapshot carries its capture-proven lamp/LED state, so Practice
        # can show that the device works.  ``None`` means asleep and pending a
        # single dark frame; absent means asleep and already dark.
        self._echo_awake: Dict[str, Optional[float]] = {}
        self._last_update = 0.0
        self._snapshot: Dict[str, Dict[str, Any]] = {}
        self._rebuild(time.monotonic())

    def wake(self, device: str, now: Optional[float] = None) -> None:
        """Mark a device as being practised, so its indicators light."""

        if not indicator_controls(device):
            return
        self._echo_awake[str(device)] = (
            time.monotonic() if now is None else float(now)
        )
        self._rebuild(time.monotonic())

    def expire(self, now: Optional[float] = None) -> Tuple[str, ...]:
        """Put idle devices to sleep; return those needing a dark frame.

        Rule 0.1 requires a tested output to return to OFF/BLACK when the test
        ends.  Practice has no explicit end, so leaving a device alone is the
        end.  A device is reported once, while its snapshot still carries the
        dark state, and is then forgotten.
        """

        moment = time.monotonic() if now is None else float(now)
        expired = []
        for device, stamp in list(self._echo_awake.items()):
            if stamp is None:
                # Its dark frame was published on the previous sweep.
                self._echo_awake.pop(device, None)
                continue
            if moment - stamp >= PRACTICE_IDLE_SLEEP_SECONDS:
                self._echo_awake[device] = None
                expired.append(device)
        if expired:
            self._rebuild(moment)
        return tuple(expired)

    def sleep_all(self) -> Tuple[str, ...]:
        """Darken every practised device, for leaving Practice mode."""

        awake = tuple(
            device for device, stamp in self._echo_awake.items()
            if stamp is not None
        )
        for device in awake:
            self._echo_awake[device] = None
        if awake:
            self._rebuild(time.monotonic())
        return awake

    def _echo_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Capture-proven lamp/LED state for every practised device."""

        return {
            device: {
                "state": "practice",
                "outputs": echo_outputs(device, stamp is not None),
            }
            for device, stamp in self._echo_awake.items()
        }

    def step(self) -> bool:
        """Advance the small visual model at most eight times per second."""

        now = time.monotonic()
        if now - self._last_update < 0.125:
            return False
        self._rebuild(now)
        return True

    def activate(self, device: str, control: str, label: str = "") -> None:
        """Apply a visual/physical input to the practice-only panel model."""

        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        # Exercising any control is what asks that device to respond, whether
        # or not this model happens to carry a detailed page for it.
        self.wake(device)

        if device in {"fcu_32_efis", "pap3_mag"}:
            changes = {
                "speed_dec": ("speed", -1), "speed_inc": ("speed", 1),
                "heading_dec": ("heading", -1), "heading_inc": ("heading", 1),
                "altitude_dec": ("altitude", -100), "altitude_inc": ("altitude", 100),
                "vs_dec": ("vertical_speed", -100), "vs_inc": ("vertical_speed", 100),
                "left_baro_dec": ("left_baro", -0.01), "left_baro_inc": ("left_baro", 0.01),
                "right_baro_dec": ("right_baro", -0.01), "right_baro_inc": ("right_baro", 0.01),
                "course_capt_dec": ("course_capt", -1), "course_capt_inc": ("course_capt", 1),
                "course_fo_dec": ("course_fo", -1), "course_fo_inc": ("course_fo", 1),
            }
            change = changes.get(control)
            if change is not None:
                field, delta = change
                value = (float(getattr(self, field)) if field in {"left_baro", "right_baro"} else int(getattr(self, field))) + delta
                if field in {"heading", "course_capt", "course_fo"}:
                    value %= 360
                elif field == "speed":
                    value = max(100, min(400, value))
                elif field == "altitude":
                    value = max(0, value)
                elif field in {"left_baro", "right_baro"}:
                    value = max(20.00, min(35.00, value))
                setattr(self, field, value)
            if device == "fcu_32_efis":
                side, separator, selector = control.partition("_")
                panel = self._efis.get(side) if separator else None
                if panel is not None:
                    if selector == "inhg":
                        panel["unit"] = "inhg"
                        panel["std"] = False
                    elif selector == "hpa":
                        panel["unit"] = "hpa"
                        panel["std"] = False
                    elif selector == "std_push":
                        panel["std"] = True
                    elif selector == "std_pull":
                        panel["std"] = False
                    elif selector.startswith("mode_"):
                        panel["mode"] = selector.removeprefix("mode_")
                    elif selector.startswith("range_"):
                        try:
                            panel["range"] = int(selector.removeprefix("range_"))
                        except ValueError:
                            pass
                    elif selector.startswith("nav1_"):
                        panel["nav1"] = selector.removeprefix("nav1_")
                    elif selector.startswith("nav2_"):
                        panel["nav2"] = selector.removeprefix("nav2_")
                    elif selector in panel["buttons"]:
                        buttons = panel["buttons"]
                        buttons[selector] = not bool(buttons.get(selector))
            if device == "pap3_mag":
                lamp = {
                    "n1": "led_n1", "speed": "led_speed", "vnav": "led_vnav",
                    "lvl_chg": "led_lvl_chg", "hdg_sel": "led_hdg_sel", "lnav": "led_lnav",
                    "vorloc": "led_vorloc", "app": "led_app", "alt_hld": "led_alt_hld",
                    "vs": "led_vs", "cmd_a": "led_cmd_a", "cws_a": "led_cws_a",
                    "cmd_b": "led_cmd_b", "cws_b": "led_cws_b", "at_arm": "led_at_arm",
                }.get(control)
                if lamp:
                    self._pap3_lights[lamp] = 0.0 if self._pap3_lights.get(lamp, 0.0) else 1.0
        elif device == "agp_bb80":
            if control == "brake_fan_on":
                self._agp_brake_fan = True
            elif control == "brake_fan_off":
                self._agp_brake_fan = False
            elif control in {
                "autobrake_low", "autobrake_med", "autobrake_max"
            }:
                self._agp_autobrake = (
                    control.removeprefix("autobrake_").upper()
                )
            elif control == "anti_skid_on":
                self._agp_anti_skid = True
            elif control == "anti_skid_off":
                self._agp_anti_skid = False
            elif control == "terr_on_nd":
                self.agp_page = (
                    "navigation"
                    if self.agp_page != "navigation"
                    else "radio"
                )
                self._agp_radio_editing = False
            elif control == "gear_up":
                self._agp_gear = "UP"
            elif control == "gear_down":
                self._agp_gear = "DOWN"

            elif control in {
                "rst_ccw", "rst_cw", "chr_left", "chr_right",
                "date_ccw", "date_cw",
            }:
                counter, delta = {
                    "rst_ccw": ("rst", -1),
                    "rst_cw": ("rst", 1),
                    "chr_left": ("chr", -1),
                    "chr_right": ("chr", 1),
                    "date_ccw": ("date", -1),
                    "date_cw": ("date", 1),
                }[control]
                self._agp_rotary_raw[counter] += delta

                if self.agp_page == "radio":
                    if counter in {"rst", "chr"} and self._agp_vhf in (1, 2, 3):
                        current = int(
                            self._agp_standby_khz[self._agp_vhf]
                        )
                        if counter == "chr":
                            # Coarse MHz step.
                            current += delta * 1000
                        else:
                            # Fine 8.33/25 kHz fallback preview step.
                            current += delta * 25
                        current = max(118000, min(136975, current))
                        self._agp_standby_khz[self._agp_vhf] = current
                        self._agp_radio_editing = True
                    elif counter == "date" and self._agp_squawk_editing:
                        digits = list(self._agp_squawk.zfill(4)[-4:])
                        index = self._agp_squawk_digit % 4
                        digits[index] = str(
                            (int(digits[index]) + delta) % 8
                        )
                        self._agp_squawk = "".join(digits)
                else:
                    if counter == "rst":
                        self.speed = max(
                            100, min(400, int(self.speed) + delta)
                        )
                    elif counter == "chr":
                        self.altitude = max(
                            0, int(self.altitude) + delta * 100
                        )
                    elif counter == "date":
                        self.heading = (
                            int(self.heading) + delta
                        ) % 360

            elif self.agp_page == "radio" and control == "rst":
                active = self._agp_active_khz[self._agp_vhf]
                standby = self._agp_standby_khz[self._agp_vhf]
                self._agp_active_khz[self._agp_vhf] = standby
                self._agp_standby_khz[self._agp_vhf] = active
                self._agp_radio_editing = False
            elif self.agp_page == "radio" and control == "chr_press":
                pass
            elif self.agp_page == "radio" and control == "date_press":
                if self._agp_squawk_editing:
                    self._agp_squawk_digit = (
                        self._agp_squawk_digit + 1
                    ) % 4
                else:
                    self._agp_squawk_editing = True
            elif self.agp_page == "radio" and control == "utc_gps":
                self._agp_vhf = 1
                self._agp_radio_editing = False
            elif self.agp_page == "radio" and control == "utc_int":
                self._agp_vhf = 2
                self._agp_radio_editing = False
            elif self.agp_page == "radio" and control == "utc_set":
                self._agp_vhf = 3
                self._agp_radio_editing = False
            elif self.agp_page == "radio" and control == "timer_run":
                self._agp_xpdr_mode = "stby"
                self._agp_mode_shown_until = time.monotonic() + 1.5
            elif self.agp_page == "radio" and control == "timer_stop":
                # A deliberate move to STP is ALT OFF. Spring return after
                # RST is modeled by timer_reset leaving the logical mode set.
                if self._agp_xpdr_mode == "stby":
                    self._agp_xpdr_mode = "off"
                    self._agp_mode_shown_until = time.monotonic() + 1.5
            elif self.agp_page == "radio" and control == "timer_reset":
                cycle = ("on", "ta", "tara")
                if self._agp_xpdr_mode not in cycle:
                    self._agp_xpdr_mode = "on"
                else:
                    index = cycle.index(self._agp_xpdr_mode)
                    self._agp_xpdr_mode = cycle[(index + 1) % len(cycle)]
                self._agp_mode_shown_until = time.monotonic() + 1.5
        elif device in self._scratchpad:
            token = str(label).strip().upper()
            current = self._scratchpad[device]
            if token == "CLR":
                current = current[:-1]
            elif token in {"DEL", "OVERFLY -> DEL"}:
                current = "DELETE"
            elif token in {"EXEC", "EMPTY TOP RIGHT -> EXEC"}:
                current = "EXECUTED"
            elif len(token) == 1 and token in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./":
                current = (current + token)[-22:]
            elif token == "SPACE":
                current = (current + " ")[-22:]
            elif token == "+/-":
                current = (current + "-")[-22:]
            self._scratchpad[device] = current
        self._rebuild(time.monotonic())

    def snapshot(self) -> Mapping[str, Mapping[str, Any]]:
        return {key: dict(value) for key, value in self._snapshot.items()}

    def _fmc_lines(self, device: str, title: str) -> list[str]:
        scratchpad = self._scratchpad.get(device, "")
        return [
            _row(title), _row(""), _row("RTE 1                 ACT"),
            _row("ORIGIN        DEST"), _row("KSEA          KPDX"),
            _row(""), _row("CRZ ALT       CI"), _row(f"{self.altitude:05d}        35"),
            _row(""), _row("<INDEX       RTE DATA>"), _row(""), _row(""),
            _row(scratchpad), _row("MUSLIMSIM  PRACTICE"),
        ]

    def _sync_agp_timers(self, now: float) -> None:
        """Accumulate only the two A320 clock timers that are actually running."""

        if self._agp_chrono_running:
            self._agp_chrono_seconds += max(0.0, now - self._agp_chrono_changed_at)
        self._agp_chrono_changed_at = now
        if self._agp_elapsed_running:
            self._agp_elapsed_seconds += max(0.0, now - self._agp_elapsed_changed_at)
        self._agp_elapsed_changed_at = now

    @staticmethod
    def _clock_minutes_seconds(seconds: float) -> str:
        total = max(0, int(seconds))
        return f"{(total // 60) % 100:02d}{total % 60:02d}"

    @staticmethod
    def _elapsed_hours_minutes(seconds: float) -> str:
        total_minutes = max(0, int(seconds) // 60)
        return f"{(total_minutes // 60) % 100:02d}{total_minutes % 60:02d}"

    def _rebuild(self, now: float) -> None:
        self._last_update = now
        # Small deterministic motion makes a panel visibly alive without a
        # rendering loop, 3D scene, textures, or any simulator dependency.
        phase = now * 0.35
        ias = max(0, self.speed + int(round(math.sin(phase) * 2)))
        if self.agp_page == "navigation":
            agp_values = (
                f"{int(self.speed):>4d}",
                f"{int(self.altitude):>6d}",
                f"{int(self.heading) % 360:>4d}",
            )
        else:
            vhf = int(self._agp_vhf)
            prefix = "S" if self._agp_radio_editing else "U"
            chr_text = f"{prefix}{vhf}d{self._agp_squawk_digit + 1}"
            if self._agp_radio_editing and vhf in (1, 2):
                freq = self._agp_standby_khz[vhf]
            else:
                freq = self._agp_active_khz.get(vhf, 0)
            if now < self._agp_mode_shown_until:
                mode_text = {
                    "stby": "Stby",
                    "off": "ALoF",
                    "on": "ALon",
                    "ta": "  tA",
                    "tara": "tArA",
                }.get(self._agp_xpdr_mode, "ALoF")
                et_text = mode_text
            else:
                squawk_chars = list(self._agp_squawk)
                if (
                    self._agp_squawk_editing
                    and int(now / 0.25) % 2 == 0
                ):
                    squawk_chars[self._agp_squawk_digit % 4] = " "
                et_text = "".join(squawk_chars)
            agp_values = (
                (
                    f"{prefix}{vhf}d{self._agp_squawk_digit + 1}"
                    if self._agp_squawk_editing
                    else f"{prefix}{vhf}"
                ),
                f"{int(freq):06d}" if freq else "------",
                et_text,
            )
        left_efis = self._efis["left"]
        right_efis = self._efis["right"]
        pap_values = {
            "speed": float(self.speed), "speed_is_mach": 0.0,
            "heading": float(self.heading), "altitude": float(self.altitude),
            "vertical_speed": float(self.vertical_speed), "vertical_speed_visible": 1.0,
            "speed_visible": 1.0, "avionics": 1.0, "course_capt": float(self.course_capt),
            "course_fo": float(self.course_fo), "fd_capt": 1.0, "fd_fo": 1.0,
            "at_arm": 1.0, "bank_angle": 2.0,
            "left_baro": float(self.left_baro), "right_baro": float(self.right_baro),
            "display_enabled": 1.0, "backlight": 180.0,
        }
        # Keep FCU-only selector poses out of the PAP3 LCD output mapping.
        # PAP3 accepts a six-window MCP payload; the FCU adapter accepts the
        # BARO-window values plus these visual-position fields.
        fcu_values = dict(pap_values)
        fcu_values.update({
            "left_baro_inhg": 1.0 if left_efis["unit"] == "inhg" else 0.0,
            "right_baro_inhg": 1.0 if right_efis["unit"] == "inhg" else 0.0,
            "left_baro_std": 1.0 if left_efis["std"] else 0.0,
            "right_baro_std": 1.0 if right_efis["std"] else 0.0,
            "left_mode": str(left_efis["mode"]), "right_mode": str(right_efis["mode"]),
            "left_range": float(left_efis["range"]), "right_range": float(right_efis["range"]),
            "left_nav1": str(left_efis["nav1"]), "right_nav1": str(right_efis["nav1"]),
            "left_nav2": str(left_efis["nav2"]), "right_nav2": str(right_efis["nav2"]),
        })
        for side, panel in (("left", left_efis), ("right", right_efis)):
            for button, enabled in dict(panel["buttons"]).items():
                fcu_values[f"{side}_{button}"] = 1.0 if enabled else 0.0
        pap_values.update(self._pap3_lights)
        self._snapshot = {
            "fcu_32_efis": {"state": "practice", "values": fcu_values},
            "pap3_mag": {"state": "practice", "values": pap_values},
            "agp_bb80": {
                "state": "practice",
                "page": self.agp_page,
                "labels": ("CHR", "UTC", "ET"),
                "values": agp_values,
                "rotary_raw": dict(self._agp_rotary_raw),
                "vhf": int(self._agp_vhf),
                "squawk_digit": int(self._agp_squawk_digit),
                "squawk_editing": bool(self._agp_squawk_editing),
                "xpdr_mode": str(self._agp_xpdr_mode),
                "controls": {
                    "brake_fan": self._agp_brake_fan,
                    "autobrake": self._agp_autobrake,
                    "anti_skid": self._agp_anti_skid,
                    "terrain": self.agp_page == "navigation",
                    "gear": self._agp_gear,
                    "elapsed_running": self._agp_elapsed_running,
                    "vhf": int(self._agp_vhf),
                    "xpdr_mode": str(self._agp_xpdr_mode),
                },
            },
            "pfp3n_bb35": {"state": "fmc", "lines": self._fmc_lines("pfp3n_bb35", "MUSLIMSIM PFP FMC")},
            "mcdu32_bb36": {"state": "fmc", "lines": self._fmc_lines("mcdu32_bb36", "MUSLIMSIM MCDU FMC")},
        }
        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        # Merge the lamp/LED practice state in last.  A device that already has
        # an authored page above keeps every one of its existing keys and only
        # gains ``outputs``; the twelve that had no page at all appear here for
        # the first time, which is what lets them respond to being practised.
        for device, echo in self._echo_snapshot().items():
            entry = self._snapshot.setdefault(device, {})
            entry.setdefault("state", echo["state"])
            entry["outputs"] = echo["outputs"]


__all__ = ("VirtualZiboPreview",)

MUSLIMSIM_AGP_RADIO_NAV_V2_PRACTICE = True

MUSLIMSIM_AGP_RADIO_NAV_V2_2_PRACTICE = True

MUSLIMSIM_AGP_RADIO_NAV_V2_3_PRACTICE = True
