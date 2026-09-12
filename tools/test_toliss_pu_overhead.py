#!/usr/bin/env python3
"""Offline guard for the ToLiss-only PU overhead and APU gauge profile.

No simulator write, serial port, SDL reader, or HID device is opened.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from bridge import final


def _p4_for(temperature: float) -> int:
    packet = final.build_packet(
        p1=0,
        apu_temp=temperature,
        land_alt=None,
        flt_alt=None,
        light_mask=0,
        egt_scale=1.0,
        egt_offset=0.0,
        egt_zero_threshold=5.0,
        egt_zero_raw=170,
        egt_mid_temp=50.0,
        egt_mid_raw=100,
        egt_peak_temp=100.0,
        egt_peak_raw=20,
        brightness_raw=0,
    )
    return int(packet.strip().split(",")[4])


def main() -> None:
    checks = 0

    assert [final._toliss_pu_selector_value(v) for v in range(4)] == [0, 1, 1, 2]
    assert [final._toliss_pu_wiper_value(v) for v in range(4)] == [0, 1, 1, 2]
    assert final.TOLISS_PU_IR_INDICES == {
        "irs_left": (0,),
        "irs_right": (2, 1),
    }
    checks += 3

    # Installed A321 array slots: L1/L2/CL/CR/R1/R2 and G/B/Y hydraulic
    # controls. These positions must not be reordered from visual guesses.
    assert final.TOLISS_PU_FUEL_INDICES == {
        11: 0, 12: 1, 9: 2, 10: 3, 14: 4, 13: 5,
    }
    assert final.TOLISS_PU_HYD_INDICES == {42: 0, 40: 1, 39: 3, 41: 4}
    assert final.TOLISS_PU_FAC_INDICES == (5, 6)
    checks += 3

    # Charged battery terminals are not proof that their contactors have
    # energized the aircraft. Only the native DC-bus array may wake outputs.
    buses_powered = final._toliss_pu_buses_powered
    assert buses_powered([]) is False
    assert buses_powered([0.0] * final.TOLISS_PU_DC_BUS_COUNT) is False
    assert buses_powered([float("nan"), "bad", 0.0]) is False
    assert buses_powered([0.0, 27.5, 0.0]) is True
    assert final.TOLISS_WINCTRL_DATAREFS["aircraft_powered"] == (
        "AirbusFBW/DCBusVoltages"
    )
    assert "AirbusFBW/BatVolts" not in (
        *final.TOLISS_PU_TELEMETRY_DATAREFS.values(),
        final.TOLISS_WINCTRL_DATAREFS["aircraft_powered"],
    )
    checks += 6

    # The PU's GRD PWR AVAIL lamp is P7 bit 12. The installed ToLiss GPU car
    # owns EnableExternalPower, which represents hookup rather than selection.
    assert final.TOLISS_PU_GROUND_POWER_LIGHT_BIT == 12
    assert final._toliss_pu_ground_power_light_mask(1) == 0x00001000
    assert final._toliss_pu_ground_power_light_mask(0) == 0
    assert final._toliss_pu_ground_power_light_mask(float("nan")) == 0
    assert final._toliss_pu_ground_power_light_mask("bad") == 0
    effective = final._pu_effective_light_mask
    assert effective("live", 0xFFFFFFFF, 0) == 0xFFFFFFFF
    assert effective("test", 0x00001000, 0) == 0x00001000
    assert effective("aircraft-unpowered", 0, 0xFFFFFFFF) == 0x00001000
    assert effective("simulator-offline", 0xFFFFFFFF, 0xFFFFFFFF) == 0
    assert effective("forced-dark", 0xFFFFFFFF, 0xFFFFFFFF) == 0
    checks += 10

    # Cold/off is physical zero. Starting follows real EGT/redline, while
    # AVAIL is exactly the calibrated mark-4 midpoint regardless of hot-day
    # settled EGT variation.
    gauge = final._toliss_pu_apu_gauge_temperature
    assert gauge(False, 100, 580, 675, 1) == 0.0
    assert gauge(True, 0, 40, 1090, 0) == 0.0
    assert gauge(True, 50, 817.5, 1090, 0) == 75.0
    assert gauge(True, 100, 430, 675, 1) == 50.0
    assert gauge(True, 100, 590, 675, 1) == 50.0
    assert _p4_for(0.0) == 170
    assert _p4_for(50.0) == 100
    assert _p4_for(100.0) == 20
    checks += 8

    assert final.TOLISS_PU_DATAREFS["pu_adiru"] == "AirbusFBW/ADIRUSwitchArray"
    expected_commands = {
        "apu_master_on": "toliss_airbus/apucommands/MasterOn",
        "apu_starter_on": "toliss_airbus/apucommands/StarterOn",
        "external_power_on": "toliss_airbus/eleccommands/ExtPowOn",
        "generator_1_on": "sim/electrical/generator_1_on",
        "apu_generator_on": "sim/electrical/APU_generator_on",
        "right_landing_light_up": "toliss_airbus/lightcommands/RLandLightUp",
    }
    for key, name in expected_commands.items():
        assert final.TOLISS_PU_COMMANDS[key] == name
        checks += 1
    assert final.TOLISS_PU_TELEMETRY_DATAREFS == {
        "dc_buses": "AirbusFBW/DCBusVoltages",
        "brightness": "AirbusFBW/OHPBrightnessLevel",
        "external_power_present": "AirbusFBW/EnableExternalPower",
        "apu_n": "AirbusFBW/APUN",
        "apu_egt": "AirbusFBW/APUEGT",
        "apu_egt_limit": "AirbusFBW/APUEGTLimit",
        "apu_avail": "AirbusFBW/APUAvail",
    }
    assert not any(
        "laminar/B738" in name
        for name in (
            *final.TOLISS_PU_DATAREFS.values(),
            *final.TOLISS_PU_COMMANDS.values(),
            *final.TOLISS_PU_TELEMETRY_DATAREFS.values(),
        )
    )
    checks += 3

    # A transient running flag is not enough to release a physical starter.
    # Require the complete captured ToLiss idle signature and a real dwell.
    assert final.TOLISS_PU_ENGINE_DATAREFS == {
        "pu_engine_fadec": "AirbusFBW/FADECStateArray",
        "pu_engine_n1": "sim/cockpit2/engine/indicators/N1_percent",
        "pu_engine_n2": "AirbusFBW/ENGN2Speed",
    }
    assert (
        final.TOLISS_PU_ENGINE_READY_N1_PERCENT,
        final.TOLISS_PU_ENGINE_READY_N2_PERCENT,
    ) == (18.0, 55.0)
    assert final.TOLISS_PU_ENGINE_READY_DWELL_SECONDS >= 1.0
    ready = final._toliss_pu_engine_fully_on
    assert ready(1, 1, 18.0, 55.0) is True
    assert all(
        ready(*sample) is False
        for sample in (
            (0, 1, 20.0, 68.0),
            (1, 0, 20.0, 68.0),
            (1, 1, 17.9, 68.0),
            (1, 1, 20.0, 54.9),
            (1, 1, float("nan"), 68.0),
            (1, 1, "bad", 68.0),
        )
    )
    dwell = final._toliss_pu_engine_ready_after_dwell
    since, is_ready = dwell(True, None, 10.0)
    assert (since, is_ready) == (10.0, False)
    assert dwell(True, since, 10.999)[1] is False
    assert dwell(True, since, 11.0)[1] is True
    assert dwell(False, since, 12.0) == (None, False)
    checks += 9

    source = (PROJECT / "bridge" / "final.py").read_text(encoding="utf-8")
    start = source.index("def _run_toliss_agp_profile(")
    end = source.index("def _run_pfp_pfd_self_test", start)
    profile = source[start:end]
    startup = profile.index('winctrl_evt[0] == "startup_hardware_snapshot"')
    authority = profile.index('winctrl_evt[0] == "startup_pu_authority_baseline"')
    dispatch = profile.index("if _toliss_dispatch_pu_event(winctrl_evt):")
    assert startup < authority < dispatch
    assert '_toliss_seed_pu_baseline(snapshot.get("pu_values", {}))' in profile
    assert 'phase="baseline", source="physical", route=False' in profile
    assert 'for index in TOLISS_PU_IR_INDICES[kind]:' in profile
    assert 'write_ref_indexed("pu_adiru", index, target)' in profile
    assert 'press_command("apu_starter_on")' in profile
    apu_start = profile.index('if kind == "stage5_apu":')
    apu_end = profile.index('if kind == "pu_engine_start":', apu_start)
    assert 'press_command("apu_starter_off")' not in profile[apu_start:apu_end]
    assert 'write_ref_indexed("pu_fcc", index, target)' in profile
    assert 'write_ref("pu_probe_heat", target)' in profile
    assert 'write_ref("pu_x_bleed"' in profile
    assert "route=not args.no_direct_switches" in profile
    assert "nav_target = 1 if (logo or position != 0) else 0" in profile
    light_start = profile.index('if kind == "stage3_light":')
    light_end = profile.index('if kind == "position_light":', light_start)
    light_dispatch = profile[light_start:light_end]
    assert light_dispatch.count("_toliss_pu_press_repeated(") >= 3
    assert '"landing_light_down" if on else "landing_light_up", 2,' in light_dispatch
    assert '_toliss_pu_press_repeated("nose_light_down", 2)' in light_dispatch
    assert 'press_command("nose_light_up")' in light_dispatch
    assert "if args.no_winctrl or args.no_agp_display" not in profile
    assert "if not args.no_agp_display:" in profile
    assert "AGP display unavailable; PU overhead" in profile
    assert "other resolved WinCtrl controls remain active." in profile
    assert "profile is incomplete; no A320 control writes" not in profile
    assert '_toliss_pu_buses_powered([' in profile
    assert 'range(TOLISS_PU_DC_BUS_COUNT)' in profile
    checks += 24

    # Startup baseline is observation-only; only a later GRD edge owns the
    # shared ENG MODE. Boeing fuel/master lever semantics remain separate.
    assert "**TOLISS_PU_ENGINE_DATAREFS" in profile
    assert "pu_starter_retract_request" in profile
    assert '"lease": False' in profile
    engine_start = profile.index('if kind == "pu_engine_start":', apu_end)
    engine_end = profile.index("# The separate Boeing L/BOTH/R", engine_start)
    engine_dispatch = profile[engine_start:engine_end]
    assert 'press_command("engine_mode_start")' in engine_dispatch
    assert 'press_command("engine_1_on")' not in engine_dispatch
    assert 'press_command("engine_2_on")' not in engine_dispatch
    assert 'press_command("engine_1_off")' not in engine_dispatch
    assert 'press_command("engine_2_off")' not in engine_dispatch
    service_start = profile.index("def _toliss_service_pu_engine_starts")
    service_end = profile.index("def _toliss_rearm_throttle_pickup", service_start)
    service = profile[service_start:service_end]
    assert "_toliss_pu_engine_fully_on(" in service
    assert "_toliss_pu_engine_ready_after_dwell(" in service
    assert 'if not all(bool(toliss_pu_engine_cycles[n]["ready"])' in service
    assert "STARTER_RETRACT_MAX_ATTEMPTS" in service
    assert 'pu_starter_retract_request(' in service
    assert 'press_command("engine_mode_norm")' in service
    assert "serial.Serial" not in service and ".write(" not in service
    assert "if _toliss_pu_owns_engine_mode():" in profile
    assert "_toliss_service_pu_engine_starts(now)" in profile
    assert "toliss-stable-idle" in profile
    assert "toliss_mcdu_router_ref,\n                _request_pu_starter_retract," in source
    checks += 20

    telemetry_start = source.index("def _toliss_pu_telemetry_worker(")
    telemetry_end = source.index("def _serial_output_worker(", telemetry_start)
    telemetry = source[telemetry_start:telemetry_end]
    assert "TOLISS_PU_TELEMETRY_DATAREFS.items()" in telemetry
    assert 'ids["dc_buses"]' in telemetry
    assert "range(TOLISS_PU_DC_BUS_COUNT)" in telemetry
    assert "_toliss_pu_buses_powered(bus_volts)" in telemetry
    assert "_toliss_pu_apu_gauge_temperature(" in telemetry
    assert 'ids["external_power_present"]' in telemetry
    assert "_toliss_pu_ground_power_light_mask(" in telemetry
    assert '"light_mask": light_mask' in telemetry
    assert '"power_available_light_mask": light_mask' in telemetry
    assert 'shared_state.update({' in telemetry
    assert ".write(" not in telemetry
    assert "serial.Serial" not in telemetry
    assert 'hardware_lab.mode == "test"' in telemetry
    failure_start = telemetry.index("except Exception as exc:")
    failure = telemetry[failure_start:]
    assert failure.index('"aircraft_powered": False') < failure.index("if failures >= 2:")
    assert source.count('name="PU-ToLiss-Telemetry"') == 1
    checks += 15

    serial_start = source.index("def _serial_output_worker(")
    serial_end = source.index("def main()", serial_start)
    serial_worker = source[serial_start:serial_end]
    assert 'shared_state.get("power_available_light_mask", 0)' in serial_worker
    assert "_pu_effective_light_mask(" in serial_worker
    helper_start = source.index("def _pu_effective_light_mask(")
    helper_end = source.index("def _resolve_pu_power_dataref", helper_start)
    helper = source[helper_start:helper_end]
    assert 'if mode == "aircraft-unpowered":' in helper
    assert "& (1 << TOLISS_PU_GROUND_POWER_LIGHT_BIT)" in helper
    assert '"power_available_light_mask": 0' in source[
        source.index("def _reset_pu_state_for_simulator_offline"):telemetry_start
    ]
    checks += 5

    # COM5 writes are bounded, and ToLiss shutdown never writes or closes the
    # port behind a serial worker that failed to stop.
    assert source.count("write_timeout=PU_SERIAL_WRITE_TIMEOUT_SECONDS") == 2
    assert final.PU_SERIAL_WRITE_TIMEOUT_SECONDS > 0.0
    toliss_main = source.index("if aircraft_profile == AIRCRAFT_PROFILE_TOLISS:")
    toliss_end = source.index("if (\n        fcu_efis_lab_manager", toliss_main)
    toliss_cleanup = source[toliss_main:toliss_end]
    assert "serial_worker_stopped = not serial_thread.is_alive()" in toliss_cleanup
    assert "if serial_worker_stopped:" in toliss_cleanup
    checks += 4

    print(
        f"ToLiss PU overhead guard passed: {checks} checks; IRS 1 + IRS 2/3, "
        "Airbus switch arrays, startup no-write, native APU sequencing, "
        "real EGT/N/AVAIL gauge telemetry, GPU lamp, stable-idle starter "
        "release and sole COM5 ownership pinned."
    )


if __name__ == "__main__":
    main()
