"""Additive MuslimSim integration for MUSLIMRTP/MUSLIMATC V4.

The serial owners are simulator-agnostic.  This module attaches them to the
existing HardwareLab and (optionally) reads a few standard X-Plane radio
DataRefs through the bridge's own read helpers so the physical displays work
in Live mode without creating a second simulator process/connection layer.
"""
from __future__ import annotations

import atexit
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from .muslimrtp_v4 import D201_SPEC, MuslimRTPV4
from .muslimatc_v4 import D203_SPEC, MuslimATCV4


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
    "BMQ2-1": "bmq2_1", "BMQ2-2": "bmq2_2",
}
D201_OUTPUT_KEYS: Dict[str, str] = {
    "vhf1_led": "VHF1-L", "vhf2_led": "VHF2-L", "vhf3_led": "VHF3-L",
    "hf1_led": "HF1-L", "hf2_led": "HF2-L", "am_led": "AM-L",
    "backlight": "Back light",
    "smg_1": "SMG-1", "smg_2": "SMG-2",
    "smg_3": "SMG-3", "smg_4": "SMG-4",
    "smg_1_brightness": "SMG-1 brightness",
    "smg_2_brightness": "SMG-2 brightness",
    "smg_3_brightness": "SMG-3 brightness",
    "smg_4_brightness": "SMG-4 brightness",
}
D203_OUTPUT_KEYS: Dict[str, str] = {
    "backlight": "Back light", "fail_led": "FAIL-LED",
    "xpndr2_led": "2-LED", "xpndr1_led": "1-LED", "atc_led": "ATC-LED",
    "squawk": "SMG", "display": "SMG",
    "display_brightness": "SMG brightness",
}

# Conservative standard X-Plane output candidates.  These are read-only here.
# The newer 8.33kHz COM values are preferred; old cockpit/radios aliases are
# fallbacks for aircraft/X-Plane builds that expose only the legacy names.
LIVE_DATAREF_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "com_active": (
        "sim/cockpit2/radios/actuators/com1_frequency_hz_833",
        "sim/cockpit/radios/com1_freq_hz",
    ),
    "com_standby": (
        "sim/cockpit2/radios/actuators/com1_standby_frequency_hz_833",
        "sim/cockpit/radios/com1_stdby_freq_hz",
    ),
    "com2_active": (
        "sim/cockpit2/radios/actuators/com2_frequency_hz_833",
        "sim/cockpit/radios/com2_freq_hz",
    ),
    "com2_standby": (
        "sim/cockpit2/radios/actuators/com2_standby_frequency_hz_833",
        "sim/cockpit/radios/com2_stdby_freq_hz",
    ),
    "zibo_transponder_mode": (
        "laminar/B738/knob/transponder_pos",
    ),
    "nav_active": (
        "sim/cockpit2/radios/actuators/nav1_frequency_hz",
        "sim/cockpit/radios/nav1_freq_hz",
    ),
    "nav_standby": (
        "sim/cockpit2/radios/actuators/nav1_standby_frequency_hz",
        "sim/cockpit/radios/nav1_stdby_freq_hz",
    ),
    "transponder": (
        "sim/cockpit2/radios/actuators/transponder_code",
        "sim/cockpit/radios/transponder_code",
    ),
    # Zibo publishes VHF3 as separate MHz and kHz parts plus a flag that
    # replaces the number with DATA, which is what the aircraft's own RTP
    # shows.  All six are read-only, so VHF3 is display-only on the D201.
    "com3_active_mhz": ("laminar/B738/comm/com3/act_freq_MHz",),
    "com3_active_khz": ("laminar/B738/comm/com3/act_freq_kHz",),
    "com3_active_data": ("laminar/B738/comm/com3/act_freq_data",),
    "com3_standby_mhz": ("laminar/B738/comm/com3/stdby_freq_MHz",),
    "com3_standby_khz": ("laminar/B738/comm/com3/stdby_freq_kHz",),
    "com3_standby_data": ("laminar/B738/comm/com3/stdby_freq_data",),
    # The D203 source switches. Zibo reports position read-only and moves the
    # switch through a toggle command, so both halves are needed.
    "xpndr_atc_pos": ("laminar/B738/switch/xpndr_atc_pos",),
    "xpndr_alt_pos": ("laminar/B738/switch/xpndr_alt_pos",),
    # Rule 0.1's power source, in the same order bridge/final.py resolves it
    # for the PU and the throttle.  Rule 0.1 is one rule about the aeroplane,
    # not a per-device opinion, so every device reads the same value.
    "aircraft_power": (
        "laminar/B738/electric/dc_stdbus_status",
        "sim/cockpit2/electrical/battery_on",
        "sim/cockpit/electrical/avionics_on",
    ),
}

AIRCRAFT_POWER_THRESHOLD = 0.5

# Which aircraft radio each D201 selector position reads.  A position that is
# absent here has no verified aircraft source, so its two windows are blanked
# rather than left showing the previously selected radio's frequency.  VHF3 is
# absent deliberately: Zibo publishes it in parts, so it has its own reader.
LIVE_RTP_RADIO_SOURCES: Dict[str, Tuple[str, str]] = {
    "vhf1": ("com_active", "com_standby"),
    "vhf2": ("com2_active", "com2_standby"),
}

LIVE_COMMAND_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    # X-Plane radio commands. The 8.33 COM fine/coarse forms match the live
    # display's preferred 8.33 datarefs.
    "com1_flip": ("sim/radios/com1_standy_flip",),
    "com2_flip": ("sim/radios/com2_standy_flip",),
    "com1_coarse_up": ("sim/radios/stby_com1_coarse_up_833", "sim/radios/stby_com1_coarse_up"),
    "com1_coarse_down": ("sim/radios/stby_com1_coarse_down_833", "sim/radios/stby_com1_coarse_down"),
    "com1_fine_up": ("sim/radios/stby_com1_fine_up_833", "sim/radios/stby_com1_fine_up"),
    "com1_fine_down": ("sim/radios/stby_com1_fine_down_833", "sim/radios/stby_com1_fine_down"),
    "com2_coarse_up": ("sim/radios/stby_com2_coarse_up_833", "sim/radios/stby_com2_coarse_up"),
    "com2_coarse_down": ("sim/radios/stby_com2_coarse_down_833", "sim/radios/stby_com2_coarse_down"),
    "com2_fine_up": ("sim/radios/stby_com2_fine_up_833", "sim/radios/stby_com2_fine_up"),
    "com2_fine_down": ("sim/radios/stby_com2_fine_down_833", "sim/radios/stby_com2_fine_down"),
    "nav1_flip": ("sim/radios/nav1_standy_flip",),
    "nav1_coarse_up": ("sim/radios/stby_nav1_coarse_up",),
    "nav1_coarse_down": ("sim/radios/stby_nav1_coarse_down",),
    "nav1_fine_up": ("sim/radios/stby_nav1_fine_up",),
    "nav1_fine_down": ("sim/radios/stby_nav1_fine_down",),
    "xpdr_ident": ("sim/transponder/transponder_ident",),
    "xpdr_test": ("sim/transponder/transponder_test",),
    "xpdr_stby": ("sim/transponder/transponder_standby",),
    "xpdr_on": ("sim/transponder/transponder_on",),
    "xpdr_alt": ("sim/transponder/transponder_alt",),
    "zibo_xpdr_up": ("laminar/B738/knob/transponder_mode_up",),
    "zibo_xpdr_down": ("laminar/B738/knob/transponder_mode_dn",),
    "xpndr_atc_toggle": ("laminar/B738/toggle_switch/xpndr_atc",),
    "xpndr_alt_toggle": ("laminar/B738/toggle_switch/xpndr_alt",),
    # If an aircraft exposes X-TCAS, these improve generic TA-only/TA-RA.
    "tcas_stby": ("X-TCAS/mode_stby",),
    "tcas_taonly": ("X-TCAS/mode_taonly",),
    "tcas_tara": ("X-TCAS/mode_tara",),
}


def _phase_value(phase: str) -> float:
    return {
        "press": 1.0, "release": 0.0,
        "left": -1.0, "left-fast": -2.0,
        "right": 1.0, "right-fast": 2.0,
    }.get(str(phase), 0.0)


def _format_com(value: Any) -> str:
    try:
        number = abs(int(round(float(value))))
    except Exception:
        return ""
    # New actuator channel values are normally six-digit kHz-like channel
    # numbers (120900 -> 120.900); the legacy radio value is usually five
    # digits (12090 -> 120.90).
    if number >= 100000:
        return f"{number / 1000.0:07.3f}"
    if number >= 10000:
        return f"{number / 100.0:06.2f}"
    return ""


def _format_nav(value: Any) -> str:
    try:
        number = abs(int(round(float(value))))
    except Exception:
        return ""
    if number >= 100000:
        text = f"{number / 1000.0:.3f}"
        if text.endswith("0"):
            text = text[:-1]
        return text
    if number >= 10000:
        return f"{number / 100.0:.2f}"
    return ""


def _format_squawk(value: Any) -> str:
    try:
        number = max(0, int(round(float(value))))
    except Exception:
        return ""
    # Do not clamp octal validity here: some simulator/add-on paths use a
    # temporary decimal integer while the pilot is rotating a digit. The
    # physical panel should mirror what the bridge read.
    return f"{number:04d}"[-4:]


class HowaltV4Bundle:
    def __init__(
        self,
        *,
        hardware_lab: Any,
        control_server: Any = None,
        device_registration_cls: Any = None,
        diagnose: bool = False,
        rtp_port: Optional[str] = None,
        atc_port: Optional[str] = None,
        shutdown_event: Optional[threading.Event] = None,
        simulator_context: Optional[Mapping[str, Any]] = None,
        resolve_dataref_id: Optional[Callable[[str, str], int]] = None,
        read_dataref: Optional[Callable[..., float]] = None,
        set_dataref: Optional[Callable[[str, int, float], None]] = None,
        resolve_command_id: Optional[Callable[[str, str], int]] = None,
        activate_command: Optional[Callable[..., None]] = None,
    ) -> None:
        if hardware_lab is None:
            raise ValueError("HardwareLab is required")
        self.hardware_lab = hardware_lab
        self.control_server = control_server
        self.device_registration_cls = device_registration_cls
        self.diagnose = bool(diagnose)
        self.shutdown_event = shutdown_event
        self.simulator_context = simulator_context
        self.resolve_dataref_id = resolve_dataref_id
        self.read_dataref = read_dataref

        # The installed bridge block predates live HOWALT defaults and passes
        # only read helpers. Reuse the exact helper functions already defined
        # by bridge/final.py from this same process instead of opening another
        # simulator connection or modifying final.py again.
        try:
            import __main__ as _bridge_main
        except Exception:
            _bridge_main = None
        self.set_dataref = (
            set_dataref
            if callable(set_dataref)
            else getattr(_bridge_main, "set_dataref", None)
        )
        self.resolve_command_id = (
            resolve_command_id
            if callable(resolve_command_id)
            else getattr(_bridge_main, "resolve_command_id", None)
        )
        self.activate_command = (
            activate_command
            if callable(activate_command)
            else getattr(_bridge_main, "activate_command", None)
        )

        self.stop_evt = threading.Event()
        self.monitor_thread: Optional[threading.Thread] = None
        self._last_mode = ""
        self._resolved_version = ""
        self._resolved: Dict[str, int] = {}
        self._resolve_retry_at = 0.0
        self._last_live_values: Dict[str, str] = {}
        self._output_powered: Optional[bool] = None
        self._live_command_ids: Dict[str, int] = {}
        self._live_write_refs: Dict[str, int] = {}
        self._rtp_live_radio = "vhf1"
        self._manual_outputs: Dict[str, set[str]] = {
            D201_SPEC.key: set(), D203_SPEC.key: set(),
        }
        self._practice_lock = threading.RLock()
        self._previous_practice_input_sink = getattr(
            hardware_lab, "_practice_input_sink", None
        )
        self._practice_wrapper: Optional[Callable[[str, str, float, str], None]] = None
        self._rtp_practice = {
            "smg_1": 120.900, "smg_2": 129.875,
            "smg_3": 114.85, "smg_4": 115.40,
        }
        self._atc_practice = "5716"
        self._test_generation = 0

        self.rtp = MuslimRTPV4(
            port=rtp_port,
            input_router=self._make_input_router(
                D201_SPEC.key, D201_SPEC.input_indices, D201_INPUT_KEYS
            ),
            event_sink=self._on_rtp_raw_event,
            diagnose=self.diagnose,
        )
        self.atc = MuslimATCV4(
            port=atc_port,
            input_router=self._make_input_router(
                D203_SPEC.key, D203_SPEC.input_indices, D203_INPUT_KEYS
            ),
            diagnose=self.diagnose,
        )

    def _make_input_router(
        self, device_key: str, raw_indices: Mapping[str, int],
        semantic_keys: Mapping[str, str],
    ) -> Callable[[int, str], bool]:
        index_to_raw = {int(index): name for name, index in raw_indices.items()}

        def route(index: int, phase: str) -> bool:
            raw_name = index_to_raw.get(int(index))
            control_key = semantic_keys.get(raw_name or "")
            if control_key is None:
                return False
            try:
                outcome = self.hardware_lab.input(
                    device_key, control_key, _phase_value(phase),
                    phase=str(phase), source="physical",
                )
                routed = (
                    bool(outcome.get("routed"))
                    if isinstance(outcome, Mapping) else False
                )
                if routed or self._mode() == "test":
                    return routed
                if self._has_saved_binding(device_key, control_key):
                    return False
                return self._dispatch_live_default(
                    device_key, control_key, str(phase)
                )
            except Exception as exc:
                try:
                    self.hardware_lab.record_diagnostic(
                        device_key, "howalt-v4-input-error",
                        {"control": control_key, "error": f"{type(exc).__name__}: {exc}"},
                    )
                except Exception:
                    pass
                return False
        return route

    def _has_saved_binding(self, device_key: str, control_key: str) -> bool:
        """Respect an explicit Studio mapping/disable before any native default."""
        candidates = [
            self.hardware_lab,
            getattr(self.hardware_lab, "profiles", None),
            getattr(self.hardware_lab, "profile_store", None),
            getattr(self.hardware_lab, "store", None),
            getattr(self.hardware_lab, "_profiles", None),
            getattr(self.hardware_lab, "_store", None),
        ]
        for candidate in candidates:
            if candidate is None:
                continue
            checker = getattr(candidate, "has_binding", None)
            if callable(checker):
                try:
                    return bool(checker(device_key, control_key))
                except Exception:
                    continue
        return False

    def _on_rtp_raw_event(self, event: Mapping[str, Any]) -> None:
        """Separate the HF SENS push contact from BMQ1 rotation if emitted.

        HFSENSE.pcapng contains only encoder command-6 BMQ1 frames, not a
        distinct command-7 button frame. The physical knob is known to be a
        pushable control, so V4.7 is type-aware and ready for a firmware
        button frame named BMQ1 / HFSENS / HF SENS without inventing one.
        """
        if str(event.get("kind") or "") != "button":
            return
        raw = str(event.get("control") or "").strip()
        normalized = re.sub(r"[^a-z0-9]+", "", raw.lower())
        if normalized not in {"bmq1", "hfsens", "hfsense"}:
            return
        phase = str(event.get("phase") or "")
        try:
            outcome = self.hardware_lab.input(
                D201_SPEC.key, "hf_sens_push",
                1.0 if phase != "release" else 0.0,
                phase=phase, source="physical",
            )
            if (
                isinstance(outcome, Mapping)
                and outcome.get("routed")
            ) or self._mode() == "test":
                return
            if self._has_saved_binding(D201_SPEC.key, "hf_sens_push"):
                return
            # No native Zibo/X-Plane HF sensitivity action is assumed.
        except Exception:
            return

    def _active_version(self) -> str:
        return self._api_version()

    def _command_once(self, key: str) -> bool:
        version = self._active_version()
        if (
            not version
            or not callable(self.resolve_command_id)
            or not callable(self.activate_command)
        ):
            return False
        command_id = self._live_command_ids.get(key)
        if command_id is None:
            for name in LIVE_COMMAND_CANDIDATES.get(key, ()):
                try:
                    command_id = int(self.resolve_command_id(version, name))
                    self._live_command_ids[key] = command_id
                    break
                except Exception:
                    continue
        if command_id is None:
            return False
        try:
            self.activate_command(version, command_id, 0.0)
            return True
        except Exception:
            self._live_command_ids.pop(key, None)
            return False

    def _resolve_write_ref(self, key: str) -> Optional[int]:
        version = self._active_version()
        if not version or not callable(self.resolve_dataref_id):
            return None
        if key in self._live_write_refs:
            return self._live_write_refs[key]
        for name in LIVE_DATAREF_CANDIDATES.get(key, ()):
            try:
                ref = int(self.resolve_dataref_id(version, name))
                self._live_write_refs[key] = ref
                return ref
            except Exception:
                continue
        return None

    def _write_ref(self, key: str, value: float) -> bool:
        version = self._active_version()
        ref = self._resolve_write_ref(key)
        if (
            not version or ref is None
            or not callable(self.set_dataref)
        ):
            return False
        try:
            self.set_dataref(version, ref, float(value))
            return True
        except Exception:
            self._live_write_refs.pop(key, None)
            return False

    def _set_rtp_live_radio(self, control_key: str) -> None:
        self._rtp_live_radio = control_key
        led_for = {
            "vhf1": "VHF1-L", "vhf2": "VHF2-L", "vhf3": "VHF3-L",
            "hf1": "HF1-L", "hf2": "HF2-L", "am": "AM-L",
        }
        selected = led_for.get(control_key)
        for led in led_for.values():
            self.rtp.set_output(led, 255 if led == selected else 0)
        self._last_live_values.pop("smg_1", None)
        self._last_live_values.pop("smg_2", None)

    def _dispatch_rtp_live(self, control_key: str, phase: str) -> bool:
        if phase == "release":
            return False

        if control_key in {"vhf1", "vhf2", "vhf3", "hf1", "hf2", "am"}:
            self._set_rtp_live_radio(control_key)
            return True
        if control_key == "off":
            self._set_rtp_live_radio("")
            return True

        bank = 2 if self._rtp_live_radio == "vhf2" else 1
        # VHF3/HF1/HF2/AM remain remappable but are not silently redirected
        # into another aircraft radio when X-Plane exposes no matching radio.
        supported_vhf = self._rtp_live_radio in {"vhf1", "vhf2"}

        if control_key == "tfr1":
            return (
                self._command_once(f"com{bank}_flip")
                if supported_vhf else False
            )
        if control_key == "tfr2":
            return self._command_once("nav1_flip")

        direction = -1 if phase.startswith("left") else 1
        fast = phase.endswith("fast")
        repeat = 2 if fast else 1

        command_key = None
        if control_key == "bmq2_1" and supported_vhf:
            command_key = f"com{bank}_coarse_{'up' if direction > 0 else 'down'}"
        elif control_key == "bmq2_2" and supported_vhf:
            command_key = f"com{bank}_fine_{'up' if direction > 0 else 'down'}"
        elif control_key == "bmq3_1":
            command_key = f"nav1_coarse_{'up' if direction > 0 else 'down'}"
        elif control_key == "bmq3_2":
            command_key = f"nav1_fine_{'up' if direction > 0 else 'down'}"
        elif control_key in {"bmq1", "test1", "test2", "hf_sens_push"}:
            # HF SENS/TEST are real remappable controls, but no Zibo/X-Plane
            # default is invented for them.
            return False

        if command_key is None:
            return False
        ok = False
        for _ in range(repeat):
            ok = self._command_once(command_key) or ok
        return ok

    def _current_squawk(self) -> int:
        version = self._active_version()
        if version:
            value = self._read(version, "transponder")
            if value is not None:
                try:
                    return max(0, int(round(float(value))))
                except Exception:
                    pass
        try:
            return int(self._atc_practice)
        except Exception:
            return 1200

    def _adjust_live_squawk_digit(
        self, control_key: str, phase: str
    ) -> bool:
        index = {
            "bmq1_1": 0, "bmq1_2": 1,
            "bmq2_1": 2, "bmq2_2": 3,
        }.get(control_key)
        if index is None:
            return False
        step = -1 if phase.startswith("left") else 1
        code = f"{self._current_squawk():04d}"[-4:]
        chars = list(code)
        try:
            current = int(chars[index])
        except Exception:
            current = 0
        # Transponder digits are octal 0..7.
        chars[index] = str((current + step) % 8)
        new_code = int("".join(chars))
        if not self._write_ref("transponder", new_code):
            return False
        self._atc_practice = f"{new_code:04d}"
        self.atc.set_squawk(self._atc_practice)
        return True

    def _set_atc_mode(self, control_key: str) -> bool:
        # Zibo exposes the ATC/TCAS knob position as a sequential 1..5 value
        # and, more importantly, publishes native mode-up/mode-down commands.
        # Use those commands rather than assuming the position DataRef accepts
        # direct writes. STBY=1 and TA/RA=5 are independently documented; the
        # physical intermediate detents occupy the sequential 2/3/4 positions.
        target = {
            "stby": 1, "rptgoff": 2, "xpndr": 3,
            "only": 4, "ta_ra": 5,
        }.get(control_key)
        version = self._active_version()
        if target is not None and version:
            current_raw = self._read(version, "zibo_transponder_mode")
            try:
                current = max(1, min(5, int(round(float(current_raw)))))
            except Exception:
                current = 0

            if current:
                command_key = (
                    "zibo_xpdr_up" if target > current
                    else "zibo_xpdr_down"
                )
                if target == current:
                    return True
                ok = True
                for _ in range(abs(target - current)):
                    if not self._command_once(command_key):
                        ok = False
                        break
                if ok:
                    return True

        # Generic X-Plane fallback. TA-only/TA-RA are attempted only when
        # an X-TCAS-compatible command exists.
        fallback = {
            "stby": "xpdr_stby",
            "rptgoff": "xpdr_on",
            "xpndr": "xpdr_alt",
            "only": "tcas_taonly",
            "ta_ra": "tcas_tara",
        }.get(control_key)
        return self._command_once(fallback) if fallback else False

    def _set_atc_source(self, control_key: str, phase: str) -> bool:
        """Move a Zibo source switch to match the physical one.

        The D203 switch is absolute - it is either in position 1 or position 2
        - while the aircraft offers only "flip it" plus a read-only position.
        So read the aircraft's position, compare, and fire the toggle only when
        the two disagree.  That keeps a repeated event from flapping the
        switch, and lets the panel re-assert its position after the aircraft
        was changed from the cockpit.
        """
        if phase not in ("press", "release"):
            return False
        which = "atc" if control_key == "xpn_1_2" else "alt"
        version = self._active_version()
        if not version:
            return False
        current = self._read(version, f"xpndr_{which}_pos")
        if current is None:
            return False
        desired = (
            ATC_SOURCE_PRESSED_POSITION if phase == "press"
            else 1 - ATC_SOURCE_PRESSED_POSITION
        )
        if int(round(current)) == desired:
            return True
        return self._command_once(f"xpndr_{which}_toggle")

    def _dispatch_atc_live(self, control_key: str, phase: str) -> bool:
        # A two-position source switch reports both edges: moving it to
        # position 2 is a release, not "nothing happened".  This has to be
        # decided before the release guard below.
        if control_key in {"xpn_1_2", "alt_1_2"}:
            return self._set_atc_source(control_key, phase)
        if phase == "release":
            return False
        if control_key in {"stby", "rptgoff", "xpndr", "only", "ta_ra"}:
            return self._set_atc_mode(control_key)
        if control_key == "ident":
            return self._command_once("xpdr_ident")
        if control_key == "atc_test":
            return self._command_once("xpdr_test")
        if control_key in {"bmq1_1", "bmq1_2", "bmq2_1", "bmq2_2"}:
            return self._adjust_live_squawk_digit(control_key, phase)
        # XPNDR source 1/2 and ALT source 1/2 stay fully remappable; no
        # aircraft-specific source-selection dataref is guessed.
        return False

    def _dispatch_live_default(
        self, device_key: str, control_key: str, phase: str
    ) -> bool:
        if self._mode() != "live" or not self._active_version():
            return False
        if device_key == D201_SPEC.key:
            return self._dispatch_rtp_live(control_key, phase)
        if device_key == D203_SPEC.key:
            return self._dispatch_atc_live(control_key, phase)
        return False

    def _apply_output(
        self, device_key: str, router: Any, mapping: Mapping[str, str],
        control: str, value: Any,
    ) -> None:
        semantic = str(control).strip()
        self._manual_outputs.setdefault(device_key, set()).add(semantic)
        target = mapping.get(semantic, semantic)
        router.set_lab_output(target, value)

    def _register(self) -> None:
        if self.control_server is None or self.device_registration_cls is None:
            return
        R = self.device_registration_cls
        self.control_server.register(R(
            D201_SPEC.key, start=self.rtp.start, stop=self.rtp.stop,
            status=self.rtp.service_snapshot,
            output=lambda control, value: self._apply_output(
                D201_SPEC.key, self.rtp, D201_OUTPUT_KEYS, control, value
            ),
            diagnostics=self.rtp.studio_snapshot,
        ))
        self.control_server.register(R(
            D203_SPEC.key, start=self.atc.start, stop=self.atc.stop,
            status=self.atc.service_snapshot,
            output=lambda control, value: self._apply_output(
                D203_SPEC.key, self.atc, D203_OUTPUT_KEYS, control, value
            ),
            diagnostics=self.atc.studio_snapshot,
        ))

    def start(self) -> None:
        self.stop_evt.clear()
        self._install_practice_input_wrapper()
        self.rtp.start()
        self.atc.start()
        self._register()
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(
                target=self._monitor, name="MuslimSim-HOWALT-V4", daemon=True
            )
            self.monitor_thread.start()

    def stop(self) -> None:
        self.stop_evt.set()
        # Rule 0.1: MuslimSim does not leave a panel lit behind it.  Darken
        # while these routers are still the owners, before the ports close.
        self._all_panels_dark()
        self.rtp.stop()
        self.atc.stop()
        self._restore_practice_input_sink()
        if self.monitor_thread is not None and self.monitor_thread is not threading.current_thread():
            self.monitor_thread.join(timeout=2.0)
        self.monitor_thread = None

    def _install_practice_input_wrapper(self) -> None:
        if self._practice_wrapper is not None:
            return

        previous = self._previous_practice_input_sink

        def wrapped(device_key: str, control_key: str, value: float, phase: str) -> None:
            if device_key in {D201_SPEC.key, D203_SPEC.key}:
                self._handle_howalt_practice_input(
                    str(device_key), str(control_key), float(value), str(phase)
                )
                return
            if callable(previous):
                previous(device_key, control_key, value, phase)

        self._practice_wrapper = wrapped
        setter = getattr(self.hardware_lab, "set_practice_input_sink", None)
        if callable(setter):
            setter(wrapped)
        else:
            setattr(self.hardware_lab, "_practice_input_sink", wrapped)

    def _restore_practice_input_sink(self) -> None:
        wrapper = self._practice_wrapper
        if wrapper is None:
            return
        current = getattr(self.hardware_lab, "_practice_input_sink", None)
        if current is wrapper:
            setter = getattr(self.hardware_lab, "set_practice_input_sink", None)
            if callable(setter):
                setter(self._previous_practice_input_sink)
            else:
                setattr(
                    self.hardware_lab, "_practice_input_sink",
                    self._previous_practice_input_sink,
                )
        self._practice_wrapper = None

    @staticmethod
    def _direction(phase: str) -> int:
        phase = str(phase).lower()
        if phase in {"left", "left-fast"}:
            return -5 if phase == "left-fast" else -1
        if phase in {"right", "right-fast"}:
            return 5 if phase == "right-fast" else 1
        # A Studio left-click on a rotary is a virtual one-step clockwise turn.
        if phase == "press":
            return 1
        return 0

    def _rtp_refresh_practice(self) -> None:
        self.rtp.set_display("SMG-1", f"{self._rtp_practice['smg_1']:.3f}", mask=0x3F)
        self.rtp.set_display("SMG-2", f"{self._rtp_practice['smg_2']:.3f}", mask=0x3F)
        self.rtp.set_display("SMG-3", f"{self._rtp_practice['smg_3']:.2f}", mask=0x1F)
        self.rtp.set_display("SMG-4", f"{self._rtp_practice['smg_4']:.2f}", mask=0x1F)

    def _atc_refresh_practice(self) -> None:
        self.atc.set_squawk(self._atc_practice)

    def _restore_after_test(self, generation: int, device_key: str) -> None:
        if self.stop_evt.wait(0.65):
            return
        with self._practice_lock:
            if generation != self._test_generation or self._mode() != "test":
                return
            if device_key == D201_SPEC.key:
                self._rtp_refresh_practice()
                self.rtp.set_output("VHF1-L", 0)
                self.rtp.set_output("VHF2-L", 255)
                self.rtp.set_output("VHF3-L", 0)
                self.rtp.set_output("HF1-L", 0)
                self.rtp.set_output("HF2-L", 0)
                self.rtp.set_output("AM-L", 0)
            else:
                self._atc_refresh_practice()
                self.atc.set_output("FAIL-LED", 0)
                self.atc.set_output("1-LED", 255)
                self.atc.set_output("2-LED", 0)
                self.atc.set_output("ATC-LED", 255)

    def _brief_test(self, device_key: str) -> None:
        self._test_generation += 1
        generation = self._test_generation
        if device_key == D201_SPEC.key:
            self.rtp.set_display("SMG-1", "888.888", mask=0x3F)
            self.rtp.set_display("SMG-2", "888.888", mask=0x3F)
            for led in ("VHF1-L", "VHF2-L", "VHF3-L", "HF1-L", "HF2-L", "AM-L"):
                self.rtp.set_output(led, 255)
        else:
            self.atc.set_display("SMG", "8888", mask=0x0F)
            for led in ("FAIL-LED", "1-LED", "2-LED", "ATC-LED"):
                self.atc.set_output(led, 255)
        threading.Thread(
            target=self._restore_after_test,
            args=(generation, device_key),
            name=f"HOWALT-Test-{device_key}",
            daemon=True,
        ).start()

    def _select_rtp_radio(self, control_key: str) -> None:
        led_for = {
            "vhf1": "VHF1-L", "vhf2": "VHF2-L", "vhf3": "VHF3-L",
            "hf1": "HF1-L", "hf2": "HF2-L", "am": "AM-L",
        }
        selected = led_for.get(control_key)
        for led in led_for.values():
            self.rtp.set_output(led, 255 if led == selected else 0)

    def _adjust_atc_digit(self, control_key: str, direction: int) -> None:
        if not direction:
            return
        digit_index = {
            "bmq1_1": 0, "bmq1_2": 1,
            "bmq2_1": 2, "bmq2_2": 3,
        }.get(control_key)
        if digit_index is None:
            return
        chars = list(str(self._atc_practice).zfill(4)[-4:])
        current = int(chars[digit_index])
        step = 1 if direction > 0 else -1
        # Squawk digits are octal 0..7.
        chars[digit_index] = str((current + step) % 8)
        self._atc_practice = "".join(chars)
        self._atc_refresh_practice()

    def _handle_howalt_practice_input(
        self, device_key: str, control_key: str, value: float, phase: str
    ) -> None:
        """Give HOWALT physical/Studio controls real simulator-down behavior."""
        if self._mode() != "test":
            return

        with self._practice_lock:
            if device_key == D201_SPEC.key:
                if control_key == "hf_sens_push":
                    # Separate front-panel push target. The provided HFSENSE
                    # capture has rotation only, so Practice records the push
                    # without fabricating a firmware input name.
                    return
                raw_by_semantic = {v: k for k, v in D201_INPUT_KEYS.items()}
                raw = raw_by_semantic.get(control_key, control_key)
                self.rtp.mirror_practice_input(raw, phase)

                if control_key in {"vhf1", "vhf2", "vhf3", "hf1", "hf2", "am"}:
                    if phase != "release":
                        self._select_rtp_radio(control_key)
                    return
                if control_key == "off" and phase != "release":
                    self._select_rtp_radio("")
                    return
                if control_key == "tfr1" and phase != "release":
                    self._rtp_practice["smg_1"], self._rtp_practice["smg_2"] = (
                        self._rtp_practice["smg_2"], self._rtp_practice["smg_1"]
                    )
                    self._rtp_refresh_practice()
                    return
                if control_key == "tfr2" and phase != "release":
                    self._rtp_practice["smg_3"], self._rtp_practice["smg_4"] = (
                        self._rtp_practice["smg_4"], self._rtp_practice["smg_3"]
                    )
                    self._rtp_refresh_practice()
                    return
                if control_key in {"test1", "test2"} and phase != "release":
                    self._brief_test(D201_SPEC.key)
                    return

                direction = self._direction(phase)
                if control_key == "bmq2_1" and direction:
                    self._rtp_practice["smg_2"] = max(
                        118.000, min(136.975,
                            self._rtp_practice["smg_2"] + (1.0 if direction > 0 else -1.0)
                        )
                    )
                    self._rtp_refresh_practice()
                elif control_key == "bmq2_2" and direction:
                    self._rtp_practice["smg_2"] = max(
                        118.000, min(136.975,
                            round(self._rtp_practice["smg_2"] + (0.025 if direction > 0 else -0.025), 3)
                        )
                    )
                    self._rtp_refresh_practice()
                elif control_key == "bmq3_1" and direction:
                    self._rtp_practice["smg_4"] = max(
                        108.00, min(117.95,
                            self._rtp_practice["smg_4"] + (1.0 if direction > 0 else -1.0)
                        )
                    )
                    self._rtp_refresh_practice()
                elif control_key == "bmq3_2" and direction:
                    self._rtp_practice["smg_4"] = max(
                        108.00, min(117.95,
                            round(self._rtp_practice["smg_4"] + (0.05 if direction > 0 else -0.05), 2)
                        )
                    )
                    self._rtp_refresh_practice()
                return

            if device_key == D203_SPEC.key:
                raw_by_semantic = {v: k for k, v in D203_INPUT_KEYS.items()}
                raw = raw_by_semantic.get(control_key, control_key)
                self.atc.mirror_practice_input(raw, phase)

                if control_key == "xpn_1_2":
                    # The contact closes in position 1, the same polarity the
                    # faceplate selector uses; a release is position 2.
                    is_two = phase == "release"
                    self.atc.set_output("1-LED", 0 if is_two else 255)
                    self.atc.set_output("2-LED", 255 if is_two else 0)
                    return
                if control_key == "ident" and phase != "release":
                    self.atc.set_output("ATC-LED", 255)
                    return
                if control_key == "atc_test" and phase != "release":
                    self._brief_test(D203_SPEC.key)
                    return
                direction = self._direction(phase)
                if control_key in {"bmq1_1", "bmq1_2", "bmq2_1", "bmq2_2"}:
                    self._adjust_atc_digit(control_key, direction)
                return

    def snapshot(self) -> Dict[str, Any]:
        return {
            D201_SPEC.key: self.rtp.studio_snapshot(),
            D203_SPEC.key: self.atc.studio_snapshot(),
        }

    def _mode(self) -> str:
        try:
            return str(self.hardware_lab.mode or "live").lower()
        except Exception:
            return "live"

    def _external_stop(self) -> bool:
        return bool(self.shutdown_event is not None and self.shutdown_event.is_set())

    def _monitor(self) -> None:
        while not self.stop_evt.is_set() and not self._external_stop():
            mode = self._mode()
            if mode != self._last_mode:
                if mode == "test":
                    self._enter_practice()
                elif self._last_mode == "test":
                    self._leave_practice()
                self._last_mode = mode
            if mode == "live":
                self._sync_live_displays()
            self.stop_evt.wait(0.20)
        # Reached when the bridge's shutdown event fires without stop() being
        # called; the same rule applies to this exit.
        self._all_panels_dark()
        self.rtp.stop()
        self.atc.stop()

    def _enter_practice(self) -> None:
        # Simulator-down panel operation: both physical controls and Studio
        # clicks manipulate these verified output surfaces.
        with self._practice_lock:
            self._rtp_practice = {
                "smg_1": 120.900, "smg_2": 129.875,
                "smg_3": 114.85, "smg_4": 115.40,
            }
            self._atc_practice = "5716"
            self.rtp.apply_practice_defaults()
            self.atc.apply_practice_defaults()
            self._rtp_refresh_practice()
            self._atc_refresh_practice()

    def _leave_practice(self) -> None:
        # Remove fake practice data before Live mode. User/manual output
        # requests are remembered separately and will take precedence later.
        self.rtp.set_output("VHF2-L", 0)
        self.atc.set_output("ATC-LED", 0)
        for name in D201_SPEC.displays:
            self.rtp.clear_display(name)
        self.atc.clear_display("SMG")
        self._last_live_values.clear()

    def _api_version(self) -> str:
        ctx = self.simulator_context
        if not isinstance(ctx, Mapping):
            return ""
        return str(ctx.get("api_version") or "")

    def _resolve_live_refs(self, version: str) -> None:
        if not version or self.resolve_dataref_id is None:
            return
        now = time.monotonic()
        if version == self._resolved_version and self._resolved:
            return
        if now < self._resolve_retry_at:
            return
        self._resolved_version = version
        self._resolved.clear()
        for key, candidates in LIVE_DATAREF_CANDIDATES.items():
            for name in candidates:
                try:
                    self._resolved[key] = int(self.resolve_dataref_id(version, name))
                    break
                except Exception:
                    continue
        self._resolve_retry_at = now + (1.0 if self._resolved else 4.0)

    def _read(self, version: str, key: str) -> Optional[float]:
        ref = self._resolved.get(key)
        if ref is None or self.read_dataref is None:
            return None
        try:
            try:
                return float(self.read_dataref(version, ref, timeout=0.35))
            except TypeError:
                return float(self.read_dataref(version, ref))
        except Exception:
            return None

    def _all_panels_dark(self) -> None:
        """Rule 0.1: both HOWALT panels off, through each device's own off.

        `all_off` writes `set_output(name, 0)` for every declared output and
        blanks every display through the same masked writer normal output
        already uses, so no vendor packet is invented to force this dark.
        """
        for router in (self.rtp, self.atc):
            try:
                router.all_off()
            except Exception:
                pass
        self._last_live_values.clear()

    def _aircraft_powered(self, version: str) -> bool:
        """Judge output power, telling the two kinds of "no reading" apart.

        No power DataRef resolved at all means the loaded aircraft simply does
        not publish one.  There is nothing to judge, so preserve the behaviour
        that was working rather than blacking out a panel on an assumption -
        the same call `_agp_aircraft_output_powered` makes in bridge/final.py.

        A ref that resolved and cannot be read now is the opposite case: live
        data lost while Studio is still in Live mode, which rule 0.1 says must
        go dark rather than hold a stale indication.
        """
        if "aircraft_power" not in self._resolved:
            return True
        value = self._read(version, "aircraft_power")
        if value is None:
            return False
        return value >= AIRCRAFT_POWER_THRESHOLD

    def _zibo_com3_window(self, version: str, which: str) -> str:
        """One VHF3 window: a frequency, or DATA when it is the data link.

        Returns "" when the aircraft publishes no third COM, which leaves the
        caller to blank the window rather than show another radio.
        """
        flag = self._read(version, f"com3_{which}_data")
        if flag is None:
            return ""
        if flag >= 0.5:
            return "DATA"
        mhz = self._read(version, f"com3_{which}_mhz")
        khz = self._read(version, f"com3_{which}_khz")
        if mhz is None or khz is None:
            return ""
        try:
            return f"{int(round(mhz))}.{int(round(khz)):03d}"
        except Exception:
            return ""

    def _sync_live_displays(self) -> None:
        version = self._api_version()
        if not version:
            return
        self._resolve_live_refs(version)
        if not self._resolved:
            return

        # Rule 0.1: nothing lights while the aeroplane is unpowered.  Test
        # mode stays user-owned, exactly as the AGP and throttle authorities
        # in bridge/final.py already treat it.
        if self._mode() != "test":
            if not self._aircraft_powered(version):
                if self._output_powered is not False:
                    self._all_panels_dark()
                    self._output_powered = False
                return
            if self._output_powered is not True:
                # Coming back from dark, every dirty-only value must compare
                # against an empty cache or a value identical to the one held
                # before the blackout would never be written back.
                self._last_live_values.clear()
                self._output_powered = True

        radio_sources = LIVE_RTP_RADIO_SOURCES.get(self._rtp_live_radio)

        values = {
            "smg_1": "",
            "smg_2": "",
            "smg_3": _format_nav(self._read(version, "nav_active")),
            "smg_4": _format_nav(self._read(version, "nav_standby")),
            "squawk": _format_squawk(self._read(version, "transponder")),
        }
        if radio_sources is not None:
            values["smg_1"] = _format_com(self._read(version, radio_sources[0]))
            values["smg_2"] = _format_com(self._read(version, radio_sources[1]))
        elif self._rtp_live_radio == "vhf3":
            values["smg_1"] = self._zibo_com3_window(version, "active")
            values["smg_2"] = self._zibo_com3_window(version, "standby")
        for semantic, display_name in (
            ("smg_1", "SMG-1"), ("smg_2", "SMG-2"),
            ("smg_3", "SMG-3"), ("smg_4", "SMG-4"),
        ):
            if semantic in self._manual_outputs[D201_SPEC.key]:
                continue
            value = values[semantic]
            if not value:
                # VHF3/HF1/HF2/AM have no verified aircraft radio.  Blank the
                # two COM windows instead of leaving VHF1's frequency showing
                # under a different selector position.
                if radio_sources is None and semantic in ("smg_1", "smg_2"):
                    signature = f"rtp:{semantic}:blank"
                    if self._last_live_values.get(semantic) != signature:
                        self.rtp.clear_display(display_name)
                        self._last_live_values[semantic] = signature
                continue
            signature = f"rtp:{semantic}:{value}"
            if self._last_live_values.get(semantic) == signature:
                continue
            self.rtp.set_display(
                display_name, value, mask=D201_SPEC.display_masks[display_name]
            )
            self._last_live_values[semantic] = signature
        if (
            values["squawk"]
            and "squawk" not in self._manual_outputs[D203_SPEC.key]
            and "display" not in self._manual_outputs[D203_SPEC.key]
        ):
            signature = f"atc:{values['squawk']}"
            if self._last_live_values.get("squawk") != signature:
                self.atc.set_squawk(values["squawk"])
                self._last_live_values["squawk"] = signature

        # The "1" and "2" lamps beside the XPNDR legend report which ATC
        # source is selected.  They were only ever driven in practice mode, so
        # in Live they sat wherever they were last left - and once the
        # aircraft-power blackout started clearing them, nothing lit them
        # again.  Drive them from the aircraft's own source position, which is
        # the thing they are reporting in the first place.
        atc_pos = self._read(version, "xpndr_atc_pos")
        if atc_pos is not None:
            is_two = int(round(atc_pos)) != ATC_SOURCE_PRESSED_POSITION
            signature = f"atc:source:{is_two}"
            if self._last_live_values.get("atc_source") != signature:
                if "xpndr1_led" not in self._manual_outputs[D203_SPEC.key]:
                    self.atc.set_output("1-LED", 0 if is_two else 255)
                if "xpndr2_led" not in self._manual_outputs[D203_SPEC.key]:
                    self.atc.set_output("2-LED", 255 if is_two else 0)
                self._last_live_values["atc_source"] = signature

        # Illuminate only the neutral panel backlight.  Functional annunciators
        # are never guessed from a radio value.
        if "backlight" not in self._manual_outputs[D201_SPEC.key]:
            self.rtp.set_output("Back light", 180)
        if "backlight" not in self._manual_outputs[D203_SPEC.key]:
            self.atc.set_output("Back light", 180)


def install_howalt_v4(
    *,
    hardware_lab: Any,
    control_server: Any = None,
    device_registration_cls: Any = None,
    diagnose: bool = False,
    rtp_port: Optional[str] = None,
    atc_port: Optional[str] = None,
    shutdown_event: Optional[threading.Event] = None,
    simulator_context: Optional[Mapping[str, Any]] = None,
    resolve_dataref_id: Optional[Callable[[str, str], int]] = None,
    read_dataref: Optional[Callable[..., float]] = None,
    set_dataref: Optional[Callable[[str, int, float], None]] = None,
    resolve_command_id: Optional[Callable[[str, str], int]] = None,
    activate_command: Optional[Callable[..., None]] = None,
) -> HowaltV4Bundle:
    bundle = HowaltV4Bundle(
        hardware_lab=hardware_lab,
        control_server=control_server,
        device_registration_cls=device_registration_cls,
        diagnose=diagnose,
        rtp_port=rtp_port,
        atc_port=atc_port,
        shutdown_event=shutdown_event,
        simulator_context=simulator_context,
        resolve_dataref_id=resolve_dataref_id,
        read_dataref=read_dataref,
        set_dataref=set_dataref,
        resolve_command_id=resolve_command_id,
        activate_command=activate_command,
    )
    bundle.start()
    atexit.register(bundle.stop)
    return bundle

# The D203 source switches close their contact in position 1, and Zibo counts
# its position DataRef from 0.  Kept as one named constant because it is the
# single thing in this mapping that a live check can prove backwards.
ATC_SOURCE_PRESSED_POSITION = 0

MUSLIMSIM_HOWALT_V45_PRACTICE_REPAIR = True

MUSLIMSIM_HOWALT_V47_LIVE_DEFAULTS = True
