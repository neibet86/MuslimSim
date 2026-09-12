"""Additive catalogue definitions for MUSLIMRTP and MUSLIMATC V4.

This module does not import ``muslimsim.hardware.catalog`` and therefore does
not create a catalogue import cycle.  The existing catalogue passes its
DeviceSpec/_input/_output constructors into ``build_device_specs``.
"""
from __future__ import annotations


def build_device_specs(DeviceSpec, _input, _output):
    rtp_controls = (
        _input("vhf1", "VHF 1 select", "button", "D201 serial 7,VHF1,raw"),
        _input("vhf2", "VHF 2 select", "button", "D201 serial 7,VHF2,raw"),
        _input("vhf3", "VHF 3 select", "button", "D201 serial 7,VHF3,raw"),
        _input("hf1", "HF 1 select", "button", "D201 serial 7,HF1,raw"),
        _input("hf2", "HF 2 select", "button", "D201 serial 7,HF2,raw"),
        _input("am", "AM select", "button", "D201 serial 7,AM,raw"),
        _input("tfr1", "Transfer 1", "button", "D201 serial 7,TFR1,raw"),
        _input("tfr2", "Transfer 2", "button", "D201 serial 7,TFR2,raw"),
        _input("test1", "VHF TEST", "button", "D201 serial 7,TEST1,raw"),
        _input("test2", "NAV TEST", "button", "D201 serial 7,TEST2,raw"),
        _input("off", "Panel OFF", "button", "D201 serial 7,OFF,raw"),
        _input("bmq1", "HF SENS rotary", "rotary", "D201 serial 6,BMQ1,event"),
        _input("bmq2_1", "VHF outer rotary", "rotary", "D201 serial 6,BMQ2-1,event"),
        _input("bmq2_2", "VHF inner rotary", "rotary", "D201 serial 6,BMQ2-2,event"),
        _input("bmq3_1", "NAV outer rotary", "rotary", "D201 serial 6,BMQ3-1,event"),
        _input("bmq3_2", "NAV inner rotary", "rotary", "D201 serial 6,BMQ3-2,event"),
        _output("vhf1_led", "VHF 1 annunciator", "led", "D201 output index 0 / VHF1-L"),
        _output("vhf2_led", "VHF 2 annunciator", "led", "D201 output index 1 / VHF2-L"),
        _output("vhf3_led", "VHF 3 annunciator", "led", "D201 output index 2 / VHF3-L"),
        _output("hf1_led", "HF 1 annunciator", "led", "D201 output index 3 / HF1-L"),
        _output("hf2_led", "HF 2 annunciator", "led", "D201 output index 4 / HF2-L"),
        _output("am_led", "AM annunciator", "led", "D201 output index 5 / AM-L"),
        _output("backlight", "Panel backlight", "led", "D201 output index 6 / Back light"),
        _output("smg_1", "VHF ACTIVE display", "display",
                "D201 MAX7219 module 0 / SMG-1 / capture mask 0x3F"),
        _output("smg_2", "VHF STANDBY display", "display",
                "D201 MAX7219 module 1 / SMG-2 / capture mask 0x3F"),
        _output("smg_3", "NAV ACTIVE display", "display",
                "D201 MAX7219 module 2 / SMG-3 / photo-derived mask 0x1F"),
        _output("smg_4", "NAV STANDBY display", "display",
                "D201 MAX7219 module 3 / SMG-4 / photo-derived mask 0x1F"),
        _output("smg_1_brightness", "VHF ACTIVE brightness", "led", "D201 module 0 brightness 0..16"),
        _output("smg_2_brightness", "VHF STANDBY brightness", "led", "D201 module 1 brightness 0..16"),
        _output("smg_3_brightness", "NAV ACTIVE brightness", "led", "D201 module 2 brightness 0..16"),
        _output("smg_4_brightness", "NAV STANDBY brightness", "led", "D201 module 3 brightness 0..16"),
    )

    atc_controls = (
        _input("stby", "ATC mode STBY", "selector", "D203 serial 7,STBY,raw"),
        _input("rptgoff", "ATC mode ALT RPTG/OFF", "selector", "D203 serial 7,RPTGOFF,raw"),
        _input("xpndr", "ATC mode XPNDR", "selector", "D203 serial 7,XPNDR,raw"),
        _input("only", "ATC mode TA ONLY", "selector", "D203 serial 7,ONLY,raw"),
        _input("ta_ra", "ATC mode TA/RA", "selector", "D203 serial 7,TA-RA,raw"),
        _input("atc_test", "ATC TEST", "button", "D203 serial 7,ATCTEST,raw"),
        _input("xpn_1_2", "XPNDR source 1/2", "toggle", "D203 serial 7,XPN1-2,raw"),
        _input("alt_1_2", "ALT source 1/2", "toggle", "D203 serial 7,ALT1-2,raw"),
        _input("ident", "IDENT", "button", "D203 serial 7,IDENT,raw"),
        _input("bmq1_1", "Squawk left outer rotary", "rotary", "D203 serial 6,BMQ1-1,event"),
        _input("bmq1_2", "Squawk left inner rotary", "rotary", "D203 serial 6,BMQ1-2,event"),
        _input("bmq2_1", "Squawk right outer rotary", "rotary", "D203 serial 6,BMQ2-1,event"),
        _input("bmq2_2", "Squawk right inner rotary", "rotary", "D203 serial 6,BMQ2-2,event"),
        _output("backlight", "Panel backlight", "led", "D203 output index 0 / Back light"),
        _output("fail_led", "FAIL annunciator", "led", "D203 output index 1 / FAIL-LED"),
        _output("xpndr2_led", "XPNDR 2 annunciator", "led", "D203 output index 2 / 2-LED"),
        _output("xpndr1_led", "XPNDR 1 annunciator", "led", "D203 output index 3 / 1-LED"),
        _output("atc_led", "ATC annunciator", "led", "D203 output index 4 / ATC-LED"),
        _output("squawk", "ATC code display", "display",
                "D203 MAX7219 module 0 / SMG / focused capture mask 0x0F"),
        _output("display_brightness", "ATC code brightness", "led", "D203 module 0 brightness 0..16"),
    )

    return (
        DeviceSpec(
            "muslimrtp_d201", "MUSLIMRTP - HOWALT D201 RTP", "USB serial",
            "VID 1A86 / PID 7523; model identity HOWALT/Hoowalt D201 RTP",
            "muslimsim.devices.muslimrtp_v4",
            notes=(
                "Native MuslimSim 115200-baud owner. No MobiFlight Connector "
                "runtime dependency. COM port and individual unit serial are "
                "auto-discovered; controls remain Studio-remappable."
            ),
            controls=rtp_controls,
            aliases=("muslimrtp", "d201", "howalt_d201_rtp"),
        ),
        DeviceSpec(
            "muslimatc_d203", "MUSLIMATC - HOWALT D203 ATC", "USB serial",
            "VID 1A86 / PID 7523; model identity HOWALT/Hoowalt D203 ATC",
            "muslimsim.devices.muslimatc_v4",
            notes=(
                "Native MuslimSim 115200-baud owner. No MobiFlight Connector "
                "runtime dependency. D203 code display uses the captured "
                "four active MAX7219 positions."
            ),
            controls=atc_controls,
            aliases=("muslimatc", "d203", "howalt_d203_atc"),
        ),
    )
