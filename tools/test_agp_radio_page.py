"""Offline regression checks for AGP RADIO/NAV V2.

No hardware and no simulator are opened. The bridge module is imported only to
exercise pure formatting/stepping helpers and inspect the source wiring.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import time
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

failures: list[str] = []
checks = 0


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(message)


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "_agp_radio_nav_bridge", PROJECT / "bridge" / "final.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORIGINAL_DIGITS = {
    "0": 0x3F, "1": 0x06, "2": 0x5B, "3": 0x4F, "4": 0x66,
    "5": 0x6D, "6": 0x7D, "7": 0x07, "8": 0x7F, "9": 0x6F,
    "-": 0x40, " ": 0x00,
}


def main() -> int:
    bridge = load_bridge()

    # Existing seven-segment numeric font is protected.
    for char, mask in ORIGINAL_DIGITS.items():
        check(
            bridge.AGP_SEGMENT_MASKS.get(char) == mask,
            f"AGP numeric segment mask changed for {char!r}",
        )

    # Only two factory modes remain and TERR toggles between them forever.
    check(
        bridge.AGP_PAGE_ORDER == ("radio", "navigation"),
        f"unexpected AGP factory modes: {bridge.AGP_PAGE_ORDER!r}",
    )
    check(
        bridge._agp_next_display_page("radio") == "navigation",
        "TERR must move RADIO -> NAV",
    )
    check(
        bridge._agp_next_display_page("navigation") == "radio",
        "TERR must move NAV -> RADIO",
    )
    check(
        not hasattr(bridge, "AGP_UTC_SWITCH_PAGES"),
        "old GPS/INT/SET display-page switching must be removed",
    )

    # RADIO normally shows squawk steadily. D# appears only while explicit
    # ATC edit is active.
    state = {
        "vhf": 2,
        "editing": False,
        "active_khz": 121500,
        "standby_khz": 118250,
        "squawk": "2567",
        "squawk_digit": 0,
        "squawk_editing": False,
    }
    check(
        bridge._agp_radio_page_text(state) == ("U2", "121500", "2567"),
        f"RADIO active text wrong: {bridge._agp_radio_page_text(state)!r}",
    )
    frequency_editing = dict(state, editing=True)
    check(
        bridge._agp_radio_page_text(frequency_editing) == ("S2", "118250", "2567"),
        f"RADIO standby text wrong: {bridge._agp_radio_page_text(frequency_editing)!r}",
    )
    atc_editing = dict(
        state,
        squawk_editing=True,
        squawk_digit=2,
        squawk_blink_on=True,
    )
    check(
        bridge._agp_radio_page_text(atc_editing) == ("U2d3", "121500", "2567"),
        f"ATC digit-selection text wrong: {bridge._agp_radio_page_text(atc_editing)!r}",
    )

    # Restore the pre-RADIO/NAV transponder-mode confirmation, then return to
    # squawk automatically when the timer expires.
    mode_overlay = dict(
        state,
        xpdr_mode="tara",
        mode_shown_until=time.monotonic() + 1.0,
    )
    check(
        bridge._agp_radio_page_text(mode_overlay)[2] == "tArA",
        "TA/RA transient mode confirmation was not restored",
    )
    expired_overlay = dict(
        mode_overlay,
        mode_shown_until=time.monotonic() - 1.0,
    )
    check(
        bridge._agp_radio_page_text(expired_overlay)[2] == "2567",
        "mode confirmation did not return to squawk after timeout",
    )

    # Squawk digit edit is octal and wraps in an open loop.
    check(bridge._agp_step_squawk("1200", 0, 1) == "2200", "digit 1 + failed")
    check(bridge._agp_step_squawk("7200", 0, 1) == "0200", "7 -> 0 wrap failed")
    check(bridge._agp_step_squawk("0200", 0, -1) == "7200", "0 -> 7 wrap failed")
    check(bridge._agp_step_squawk("1207", 3, 1) == "1200", "last digit wrap failed")

    # Physical SET gesture contract:
    # first long press enters D1 edit, later long presses advance, short tap exits.
    gesture_state = {
        "squawk_digit": 0,
        "squawk_editing": False,
    }
    check(
        bridge._agp_set_long_press(gesture_state) == 0
        and gesture_state["squawk_editing"],
        "first SET long press must enter edit on current digit",
    )
    check(
        bridge._agp_set_long_press(gesture_state) == 1
        and gesture_state["squawk_editing"],
        "second SET long press must advance to next flashing digit",
    )
    check(
        bridge._agp_set_long_press(gesture_state) == 2,
        "later SET long presses must continue the open digit loop",
    )
    bridge._agp_set_short_tap(gesture_state)
    check(
        not gesture_state["squawk_editing"],
        "short SET tap must stop flashing/exit ATC edit",
    )

    # Existing COM stepping remains bounded and deterministic.
    step = bridge._agp_radio_step_frequency
    check(step(120900, 1, coarse=True) == 121900, "COM coarse +1 MHz failed")
    check(step(120900, -1, coarse=True) == 119900, "COM coarse -1 MHz failed")
    check(step(120900, 1, coarse=False) == 120925, "COM fine +25 kHz failed")
    check(step(120900, -1, coarse=False) == 120875, "COM fine -25 kHz failed")
    for bad in (None, "", "junk", float("nan"), -1):
        value = step(bad, 1, coarse=False)
        check(
            bridge.AGP_RADIO_COM_MIN_KHZ <= value <= bridge.AGP_RADIO_COM_MAX_KHZ,
            f"bad COM input escaped band: {bad!r} -> {value}",
        )

    # NAV shows and controls selected MCP values.
    nav = bridge._agp_navigation_page_text(
        {
            "speed": 250.0,
            "speed_is_mach": 0.0,
            "altitude": 12300.0,
            "heading": 91.0,
        }
    )
    check(nav == (" 250", " 12300", "  91"), f"NAV text wrong: {nav!r}")
    mach = bridge._agp_navigation_page_text(
        {
            "speed": 0.78,
            "speed_is_mach": 1.0,
            "altitude": 10000.0,
            "heading": 359.0,
        }
    )
    check(mach[0].strip() == "78", f"Mach display wrong: {mach!r}")

    src = (PROJECT / "bridge" / "final.py").read_text(encoding="utf-8")
    input_start = src.index("for button_index in sorted(newly_pressed):")
    input_branch = src[input_start: input_start + 18000]

    # TERR is the only native mode switch.
    check(
        "button_index == AGP_MODE_SWITCH_BUTTON" in input_branch
        and "_agp_next_display_page" in input_branch,
        "TERR dedicated mode toggle is not wired",
    )
    for forbidden in (
        'agp_display_page = "flight"',
        'AGP_UTC_SWITCH_PAGES',
    ):
        check(
            forbidden not in input_branch,
            f"old page escape still exists in native input branch: {forbidden}",
        )

    # knobs.pcapng contract: signed counters, not short direction bits, own
    # rotary actions. Fast reports can contain multi-step deltas.
    check(
        bridge._agp_rotary_counter_delta(-102, -98) == 4,
        "RST counter +4 delta failed",
    )
    check(
        bridge._agp_rotary_counter_delta(32767, -32768) == 1,
        "signed 16-bit counter wrap failed",
    )
    check(
        bridge._agp_rotary_counter_delta(-32768, 32767) == -1,
        "reverse signed counter wrap failed",
    )
    check(
        "rotary_counter_deltas" in src
        and "AGP_ROTARY_CONTACT_BITS" in src
        and "native_rotary_deltas" in src,
        "rotary counter dispatch is not installed",
    )
    check(
        "in AGP_ROTARY_CONTACT_BITS" in src,
        "legacy rotary contact bits are not suppressed",
    )

    # RADIO control contract now uses the native Zibo captain RTP, which
    # makes the simulator's own VHF selection/status lights follow too.
    for token in (
        "laminar/B738/rtp_L/vhf_1/sel_switch",
        "laminar/B738/rtp_L/vhf_2/sel_switch",
        "laminar/B738/rtp_L/vhf_3/sel_switch",
        "laminar/B738/rtp_L/freq_txfr/sel_switch",
        "laminar/B738/rtp_L/freq_MHz/sel_dial_up",
        "laminar/B738/rtp_L/freq_MHz/sel_dial_dn",
        "laminar/B738/rtp_L/freq_khz/sel_dial_up",
        "laminar/B738/rtp_L/freq_khz/sel_dial_dn",
        "laminar/B738/comm/rtp_L/vhf_1_status",
        "laminar/B738/comm/rtp_L/vhf_2_status",
        "laminar/B738/comm/rtp_L/vhf_3_status",
    ):
        check(token in src, f"missing native Zibo RTP path: {token}")

    check(
        "AGP_BUTTON_RST_PRESS" in input_branch
        and '"rtp_transfer"' in input_branch,
        "RST push must transfer selected COM",
    )
    check(
        "AGP_BUTTON_CHR_PRESS" in input_branch
        and "radio_handled = False" in input_branch,
        "CHR push must have no factory RADIO/NAV action",
    )
    check(
        "AGP_SET_LONG_PRESS_SECONDS" in src
        and "_agp_set_long_press(agp_radio_state)" in src
        and "_agp_set_short_tap(agp_radio_state)" in src,
        "SET press duration must distinguish long-advance from short-exit",
    )
    check(
        "_agp_step_squawk" in src
        and '"transponder_code"' in src,
        "SET counter rotation must write the selected squawk digit",
    )
    check(
        bridge._agp_step_squawk("1200", 3, 3) == "1203",
        "multi-step squawk counter delta failed",
    )
    check(
        bridge._agp_step_squawk("1207", 3, 2) == "1201",
        "multi-step octal squawk wrap failed",
    )

    # Selected digit flashes by blanking only that digit on alternate phases.
    blink_state = {
        "vhf": 1, "editing": False, "active_khz": 120900,
        "standby_khz": 129875, "squawk": "2567",
        "squawk_digit": 2, "squawk_editing": True,
        "squawk_blink_on": False,
    }
    check(
        bridge._agp_radio_page_text(blink_state)[2] == "25 7",
        "selected squawk digit does not flash/blank independently",
    )
    steady_state = dict(blink_state, squawk_editing=False)
    check(
        bridge._agp_radio_page_text(steady_state)[2] == "2567",
        "squawk must stop flashing after edit mode exits",
    )
    check(
        '"mode_shown_until"' in src
        and '"xpdr_mode_hold_until"' in src
        and "AGP_RADIO_MODE_FLASH_SECONDS" in src,
        "ATC mode selection must be held on screen before squawk returns",
    )

    # Spring selector contract.
    check(
        bridge._agp_next_rst_xpdr_mode("off") == "on"
        and bridge._agp_next_rst_xpdr_mode("on") == "ta"
        and bridge._agp_next_rst_xpdr_mode("ta") == "tara"
        and bridge._agp_next_rst_xpdr_mode("tara") == "on",
        "RST spring ATC mode cycle is incorrect",
    )
    check(
        '"stby": 1' in src and '"off": 2' in src
        and '"on": 3' in src and '"ta": 4' in src and '"tara": 5' in src,
        "Zibo ATC selector positions are incomplete",
    )
    check(
        "agp_xpdr_spring_return_pending" in input_branch,
        "spring return STP suppression is missing",
    )

    # NAV counter contract.
    check(
        "pap3_next_speed_value" in src
        and '"nav_speed_kts"' in src
        and 'native_rotary_deltas.get("rst"' in src,
        "RST counter NAV role must write selected MCP speed",
    )
    check(
        '"nav_altitude_up"' in src
        and '"nav_altitude_down"' in src
        and 'native_rotary_deltas.get("chr"' in src,
        "CHR counter NAV role must drive selected MCP altitude",
    )
    check(
        '"nav_heading_up"' in src
        and '"nav_heading_down"' in src
        and 'native_rotary_deltas.get("date"' in src,
        "SET counter NAV role must drive selected MCP heading",
    )

    # Latency and stale-ID recovery.
    check(
        bridge.AGP_INPUT_INTERVAL <= 0.005,
        f"AGP input poll is still too slow: {bridge.AGP_INPUT_INTERVAL}",
    )
    check(
        bridge.AGP_DISPLAY_INTERVAL <= 0.05,
        f"AGP display refresh is still too slow: {bridge.AGP_DISPLAY_INTERVAL}",
    )
    check(
        "resolve_dataref_id(api_version, name)" in src
        and "resolve_command_id(api_version, name)" in src,
        "AGP live writes must recover stale Web-API IDs",
    )

    # Studio mode request and catalog output are required so software and
    # physical TERR cannot disagree.
    studio_src = (PROJECT / "muslimsim" / "gui" / "studio.py").read_text(
        encoding="utf-8"
    )
    catalog_src = (PROJECT / "muslimsim" / "hardware" / "catalog.py").read_text(
        encoding="utf-8"
    )
    check(
        'visual_key == "terr_on_nd"' in studio_src
        and 'control="display_mode"' in studio_src,
        "Studio TERR must request the bridge-owned display_mode",
    )
    check(
        '"display_mode", "RADIO/NAV mode"' in catalog_src,
        "AGP catalog must expose the bridge-owned display_mode output",
    )
    check(
        "agp_window_mode" not in studio_src,
        "old independent Studio clock/radio control must be removed",
    )

    if failures:
        print("AGP RADIO/NAV V2 check FAILED:", file=sys.stderr)
        for line in failures:
            print("  - " + line, file=sys.stderr)
        return 1

    print(f"AGP RADIO/NAV V2 check passed: {checks} checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
