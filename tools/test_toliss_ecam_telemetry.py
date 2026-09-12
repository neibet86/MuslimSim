"""BUG-41/53: typed telemetry, native BLEED values, real DU startup; no hardware."""
from pathlib import Path
import base64
import math
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from muslimsim.devices import toliss_ecam_telemetry as telemetry
from muslimsim.devices import toliss_ecam_synoptics as art
from muslimsim.devices.mcdu_bb36_toliss_paths import (
    TOLISS_MCDU_SECONDARY_DATAREFS as REFS, _toliss_decode_text,
)


def check_telemetry_contract():
    # SD colour layers preserve empty cells before and between readings.
    row = b"\x00" * 4 + b"  5" + b"\x00" * 19 + b"  6" + b"\x00" * 7
    for wire in (row, list(row), base64.b64encode(row).decode("ascii")):
        decoded = _toliss_decode_text(wire, fixed_columns=True)
        assert telemetry._sd_number({"ref_status_2_g": decoded}, 2, 4, 7) == 5
        assert telemetry._sd_number({"ref_status_2_g": decoded}, 2, 26, 29) == 6
    assert _toliss_decode_text(b"ABC\x00DEF") == "ABC", "CDU decoding stays unchanged"
    assert not _toliss_decode_text(base64.b64encode(bytes(36)).decode(), fixed_columns=True).strip()
    mapped={name for group in REFS.values() for name in group.values()}
    assert not {"AirbusFBW/SDFUEL","AirbusFBW/SDELEC","AirbusFBW/SDELECDC"} & mapped
    assert REFS["ecam_reference"]["ref_cockpit_temp"] == "AirbusFBW/CockpitTemperature_degC"
    cond=telemetry.values("cond",{"ref_cockpit_temp":39.6,"ref_cabin_fwd":40.2,
                                  "ref_cabin_aft":39.7,"cond_fwd_cabin_temp":22})
    assert cond["cond_cockpit_temp"] == 39.6 and cond["cond_fwd_cabin_temp"] == 40.2
    fuel=telemetry.values("fuel",{"ref_aircraft_path":"Aircraft/ToLissA321_V1p8/a321.acf",
        "ref_fuel_mass":[20,5312,5404],"ref_fuel_flow_kg_sec":[.31,.47],"ref_fuel_used":[101,203]})
    assert (fuel["fuel_qty_l"],fuel["fuel_qty_ctr"],fuel["fuel_qty_r"]) == (5312,20,5404)
    assert fuel["fuel_flow_kg_min_0"] == .31*60 and fuel["eng_used_1"] == 203
    assert math.isnan(telemetry.values("fuel",{"ref_fuel_mass":[1,2,3]})["fuel_qty_l"])
    assert math.isnan(telemetry.array({"x":1},"x",0)), "A scalar page flag is not a one-element array"
    # BUG-44: the page adapter no longer erases the live common TAT/SAT/GW
    # values built upstream. They are absent from overrides by design.
    for page in art.PAGE_TITLES:
        unknown=telemetry.values(page,{"ecam_tat":39,"ecam_sat":39,"ecam_gw":72000})
        assert not {"ecam_tat","ecam_sat","ecam_gw"} & unknown.keys()
        if page != "door":
            assert "door_oxy_psi_1" not in unknown
    for fadec in (0,None):
        eng=telemetry.values("eng",{"eng_fadec":[fadec,0],"eng_gen_oiltemp":[40,40]})
        assert math.isnan(eng["eng_oiltemp_0"]) and math.isnan(eng["eng_oilpress_1"])
    assert "eng_oiltemp_0" not in telemetry.values("eng",{"eng_fadec":[1,1]})
    assert math.isnan(telemetry.values("apu",{"apu_master":0,"apu_n_pct":0})["apu_n_pct"])
    assert "apu_n_pct" not in telemetry.values("apu",{"apu_master":1})
    ambient=14*telemetry.PA_PER_PSI
    apu=telemetry.values("apu",{"apu_master":1,"apu_bleed_ind":1,
                                 "bleed_ambient_pressure_pa":ambient,
                                 "bleed_press_l":62,"bleed_press_r":64})
    assert apu["apu_bleed_press"] == 49
    assert math.isnan(telemetry.values("apu",{"apu_master":1,"apu_bleed_ind":1,
                                              "bleed_press_l":62})["apu_bleed_press"])

    expected_bleed_refs={
        "bleed_ambient_pressure_pa":"sim/weather/aircraft/barometer_current_pas",
        "bleed_engine_running":"sim/flightmodel/engine/ENGN_running",
        "bleed_intercon":"AirbusFBW/BleedIntercon",
        "bleed_ground_hp":"AirbusFBW/GroundHPAir",
        "bleed_ground_lp":"AirbusFBW/GroundLPAir",
    }
    for key,path in expected_bleed_refs.items():
        assert REFS["bleed"][key] == path
    for key in ("eng_gen_n2","ref_status_2_g","ref_status_2_a",
                "ref_status_5_g","ref_status_5_a","ref_status_13_g","ref_status_13_a"):
        assert key in telemetry.PAGE_EXTRA_KEYS["bleed"]

    def sd_row(left,right,left_at,right_at):
        chars=[" "]*36
        chars[left_at:left_at+3]=f"{left:>3}" if left is not None else "   "
        chars[right_at:right_at+3]=f"{right:>3}" if right is not None else "   "
        return "".join(chars)

    common_bleed={
        "bleed_ambient_pressure_pa":ambient,
        "bleed_switch_1":1,"bleed_switch_2":1,
        "ref_pack_fcv_1":1,"ref_pack_fcv_2":1,
        "bleed_pack1_temp":.25,"bleed_pack2_temp":.75,
        "bleed_pack1_flow":1.2,"bleed_pack2_flow":.8,
        "ref_status_2_g":sd_row(5,5,4,26),
        "ref_status_5_g":sd_row(210,210,4,26),
        "ref_status_13_g":sd_row(190,190,5,27),
        "ref_status_2_a":" "*36,"ref_status_5_a":" "*36,"ref_status_13_a":" "*36,
        # These unrelated values must never leak into BLEED temperatures.
        "ref_cabin_fwd":31,"ref_cabin_aft":32,"ecam_tat":39,
    }
    encoded=base64.b64encode((common_bleed["ref_status_5_g"]+"\x00").encode()).decode()
    assert _toliss_decode_text(encoded) == common_bleed["ref_status_5_g"]
    apu_only=telemetry.values("bleed",common_bleed | {
        "bleed_press_l":51,"bleed_press_r":50,
        "bleed_ind_1":0,"bleed_ind_2":0,
        "bleed_engine_running":[0,0],"eng_gen_n2":[0,0],
        "bleed_apu_ind":1,"bleed_intercon":3,
        "bleed_ground_hp":0,"bleed_ground_lp":0,
    })
    assert (apu_only["bleed_pack_temp_1"],apu_only["bleed_pack_temp_2"]) == (5,5)
    assert (apu_only["bleed_pack_outlet_1"],apu_only["bleed_pack_outlet_2"]) == (210,210)
    assert (apu_only["bleed_press_l"],apu_only["bleed_press_r"]) == (37,36)
    assert (apu_only["bleed_temp_1"],apu_only["bleed_temp_2"]) == (190,190)
    assert (apu_only["bleed_ind_1"],apu_only["bleed_ind_2"]) == (0,0)
    assert (apu_only["bleed_pack_pointer_1"],apu_only["bleed_pack_pointer_2"]) == (.25,.75)
    assert math.isclose(apu_only["bleed_pack_flow_1"],1) and apu_only["bleed_pack_flow_2"] == 0
    midpoint=telemetry.values("bleed",{"bleed_pack1_flow":1.0,"bleed_pack1_temp":1.8})
    assert math.isclose(midpoint["bleed_pack_flow_1"],.5) and midpoint["bleed_pack_pointer_1"] == 1
    assert (apu_only["bleed_intercon"],apu_only["bleed_ground_hp"],apu_only["bleed_ground_lp"]) == (3,0,0)

    external=telemetry.values("bleed",common_bleed | {
        "bleed_press_l":14,"bleed_press_r":14,
        "bleed_ind_1":0,"bleed_ind_2":0,
        "bleed_engine_running":[0,0],"eng_gen_n2":[0,0],"bleed_apu_ind":0,
        "ref_status_2_g":" "*36,"ref_status_5_g":" "*36,"ref_status_13_g":" "*36,
        "ref_status_2_a":sd_row("XX","XX",4,26),
        "ref_status_5_a":sd_row("XX","XX",4,26),
        "ref_status_13_a":sd_row("XX","XX",5,27),
    })
    assert (external["bleed_press_l"],external["bleed_press_r"]) == (0,0)
    assert (external["bleed_ind_1"],external["bleed_ind_2"]) == (0,0)
    assert all(math.isnan(external[key]) for key in (
        "bleed_pack_temp_1","bleed_pack_outlet_1","bleed_temp_1",
        "bleed_pack_temp_2","bleed_pack_outlet_2","bleed_temp_2"))

    engines=telemetry.values("bleed",common_bleed | {
        "bleed_press_l":65,"bleed_press_r":65,
        "bleed_ind_1":0,"bleed_ind_2":0,
        "bleed_engine_running":[1,1],"eng_gen_n2":[72,73],"bleed_apu_ind":0,
    })
    assert (engines["bleed_press_l"],engines["bleed_press_r"]) == (51,51)
    assert (engines["bleed_ind_1"],engines["bleed_ind_2"]) == (1,1)
    failures=telemetry.values("bleed",common_bleed | {
        "bleed_press_l":65,"bleed_press_r":65,
        "bleed_ind_1":2,"bleed_ind_2":3,
        "bleed_engine_running":[1,1],"eng_gen_n2":[72,73],"bleed_apu_ind":0,
    })
    assert (failures["bleed_ind_1"],failures["bleed_ind_2"]) == (2,3)
    missing_bleed=telemetry.values("bleed",{})
    assert all(math.isnan(missing_bleed[key]) for key in (
        "bleed_press_l","bleed_press_r","bleed_ind_1","bleed_ind_2",
        "bleed_intercon","bleed_ground_hp","bleed_ground_lp"))
    elec=telemetry.values("elec",{
        "elec_bat_volts":[26.8,27.2],"ref_ac_buses":[115,115,115,115,115],
        "ref_dc_buses":[28.7,29.3,28.7,28.7],
        "ref_battery_amps":[4.1,4.2],"ref_generator_amps":[90,120],
        "ref_bus_load_amps":[0,0,11,12],
        "eng_gen_oiltemp":[44,45],
        "ref_elec_connect_left":14,"ref_elec_connect_right":11,
        "elec_ac_cross":3,
    })
    assert (elec["elec_bat_v_0"],elec["elec_bat_v_1"]) == (26.8,27.2)
    assert all(elec[key] == 1 for key in ("elec_ac_bus_1","elec_ac_bus_2",
        "elec_ac_ess","elec_dc_bus_1","elec_dc_bus_2","elec_dc_bat","elec_dc_ess"))
    assert elec["elec_gen_1"] == 0 and elec["elec_gen_2"] == 1
    assert elec["elec_tr_v_1"] == 28.7 and elec["elec_gen_v_1"] == 0
    assert elec["elec_gen_v_2"] == 115
    assert elec["elec_bat_a_0"] == 4.1 and elec["elec_gen_load_2"] == 40
    assert elec["elec_gen_hz_2"] == 400 and elec["elec_tr_a_2"] == 12
    assert elec["elec_idg_temp_1"] == 44 and elec["elec_idg_temp_2"] == 45
    assert elec["elec_apu_gen"] == 1 and elec["elec_ext_pow"] == 0 and elec["elec_ac_tie"] == 1
    missing=telemetry.values("elec",{})
    assert all(math.isnan(missing[key]) for key in ("elec_bat_v_0","elec_ac_bus_1",
        "elec_dc_bus_1","elec_gen_1","elec_apu_gen"))
    valves=telemetry.values("fuel",{"fuel_lp_valve":[1,3],"ref_fuel_crossfeed":[1],
        "ref_fuel_pumps":[1,3,0,0,2,1],"ref_fuel_auto_pumps":[0,0,1,2,0,0]})
    assert valves["fuel_lp_code_0"] == 1 and valves["fuel_crossfeed_code"] == 1
    assert [valves[f"fuel_pump_code_{i}"] for i in range(6)] == [1,3,1,2,2,1]
    eng=telemetry.values("eng",{"eng_fadec":[1,1],"ref_oil_quantity":[.85,.8],
                                  "eng_gen_n1":[21,35],"eng_gen_n2":[69,92]})
    assert eng["eng_oil_qt_0"] == .85*16.5
    assert eng["eng_vib_0"] == .3 and eng["eng_vib_n2_0"] == .6
    hyd=telemetry.values("hyd",{"ref_hyd_pumps":[1,1,1],"hyd_press":[3000,3000,3000]})
    assert hyd["hyd_fire_valve_g"] == 1 and hyd["hyd_fire_valve_y"] == 1
    calls=[]
    original=art.valve
    try:
        art.valve=lambda c,x,y,value,**kw: calls.append((value,kw["force_colour"],kw["vertical"]))
        for code in (1,2,3):
            art.fuel_valve(None,0,0,code,engine=True)
        art.fuel_valve(None,0,0,1)
    finally:
        art.valve=original
    assert calls == [(0,art.AMBER,True),(1,art.AMBER,True),(1,art.GREEN,True),(0,art.GREEN,False)]
    door=telemetry.values("door",{"ref_aircraft_path":"ToLissA321", "door_pax":[1,1,0,0,1,1,1,1],
                                  "ref_slides_armed":[0]*8,"ref_cockpit_windows":[0,.7],
                                  "ref_oxygen_psi":1888})
    assert door["door_exit_l"] == 1 and door["door_aft_r"] == 1 and door["door_window_1"] == .7
    assert door["door_oxy_psi_1"] == 1888 and door["door_oxy_psi_2"] == 1888
    fctl=telemetry.values("fctl",{"ref_ail_l_avail":[0,0,0],"ref_ail_r_avail":[0,1,0],
                                  "fctl_spoiler_3":.65,"fctl_spoilers":[2]*16})
    assert fctl["fctl_aileron_l_available"] == 0 and fctl["fctl_aileron_r_available"] == 1
    assert fctl["fctl_spoiler_3"] == .65 and fctl["fctl_spoiler_status_3"] == 2
    wheel=telemetry.values("wheel",{"ref_tire_pressure":[231,232,233,234,235,236]})
    assert [wheel[f"wheel_tire_{i}"] for i in range(6)] == [231,232,233,234,235,236]
    status=telemetry.values("status",{"ref_status_1_g":"NORMAL CONFIG"})
    assert status["status_rows"] == ((1,(("g","NORMAL CONFIG"),)),)
    assert status["status_normal"] is False
    assert telemetry.values("status",{})["status_normal"] is True
    press=telemetry.values("press",{"press_mode_lights":1})
    assert press["press_active_system"] == 2
    from test_toliss_ecam_reference import Capture
    canvas=Capture()
    art.self_test(canvas)
    assert canvas.labels == [("SELF TEST IN PROGRESS",art.GREEN),("(MAX 40 SECONDS)",art.GREEN)]
    canvas=Capture()
    art.door(canvas,door | {"door_pax_0":1,"door_cargo_0":1})
    assert ("CABIN",art.AMBER) in canvas.labels and ("CARGO",art.AMBER) in canvas.labels
    assert not any(t=="SLIDE" for t,_ in canvas.labels)


def check_display_modes():
    powered={"ref_ac_buses":[115]*5,"ref_du_brightness":[.8]*8,"ref_du_selftest":[0]*8}
    assert telemetry.display_mode({"elec_bat_volts":[27,27]},"fctl") == "off"
    assert telemetry.display_mode(powered,"fctl") == "ready"
    for page,index in (("pfd",0),("nd",1),("fctl",5),("cdu",6)):
        for time,expected in ((40,"selftest"),(.1,"selftest"),(0,"ready"),(-1,"off"),(math.nan,"off")):
            timer=[0]*8
            timer[index]=time
            assert telemetry.display_mode(powered | {"ref_du_selftest":timer},page) == expected
        bright=[.8]*8
        bright[index]=0
        assert telemetry.display_mode(powered | {"ref_du_brightness":bright},page) == "off"
        assert telemetry.display_mode(powered | {"ref_ac_buses":[0]*5},page) == "off"
    return powered


def check_worker_transitions():
    from test_toliss_displays import _load_bridge
    bridge=_load_bridge()
    powered=check_display_modes()
    for function in (bridge._toliss_bb35_display_output_worker,bridge._toliss_bb36_mirror_output_worker):
        emitted=[]
        stop=threading.Event()
        snapshots=[{}, powered | {"ref_du_selftest":[40]*8},
                   powered | {"ref_du_selftest":[39]*8}, powered,
                   powered | {"ref_ac_buses":[0]*5}, powered]
        class Feed:
            def secondary_snapshot(self):
                if len(snapshots)==1:
                    stop.set()
                return snapshots.pop(0), True
        bridge._toliss_blackout_display=lambda *a: emitted.append("off")
        bridge._toliss_draw_display_selftest=lambda *a: emitted.append("selftest")
        bridge._toliss_draw_mcdu_secondary=lambda *a,**kw: emitted.append("ready")
        bridge._toliss_invalidate_display_canvas=lambda *a: None
        status={}
        function(None,None,Feed(),0,stop,status,threading.Lock(),lambda:"fctl")
        assert emitted == ["off","selftest","ready","off","ready"], (function.__name__,emitted,status)
        assert status["error"] is None


def check_page_scoped_snapshots():
    from muslimsim.devices.mcdu_bb36_toliss_paths import TolissDisplayFeed, _DISPLAY_SNAPSHOT_KEYS
    feed=TolissDisplayFeed("http://unused", "v2")  # Never started.
    feed.secondary_values={key:0 for group in REFS.values() for key in group}
    before={page:feed.page_snapshot(page)[0] for page in _DISPLAY_SNAPSHOT_KEYS}
    feed.secondary_values.update({f"unrelated_aircraft_{i}":i for i in range(10000)})
    for page in _DISPLAY_SNAPSHOT_KEYS:
        assert feed.page_snapshot(page)[0] == before[page]
        assert set(telemetry.POWER_KEYS) <= set(_DISPLAY_SNAPSHOT_KEYS[page])
    from test_toliss_displays import _load_bridge
    bridge=_load_bridge()
    def normal(value):
        if isinstance(value,float) and math.isnan(value):
            return None
        if isinstance(value,dict):
            return {k:normal(v) for k,v in value.items()}
        if isinstance(value,(tuple,list)):
            return tuple(map(normal,value))
        return value
    for page in _DISPLAY_SNAPSHOT_KEYS:
        full=feed.secondary_values
        scoped=feed.page_snapshot(page)[0]
        if page in ("pfd","nd"):
            translate=getattr(bridge,"_toliss_"+page+"_values")
            assert normal(translate(full)) == normal(translate(scoped)),page
        elif page != "cdu":
            def translate(raw):
                return {**bridge._toliss_ecam_common_values(raw),
                        **bridge._toliss_ecam_system_values(page,raw),
                        **telemetry.values(page,raw)}
            assert normal(translate(full)) == normal(translate(scoped)),page
    print("Page-scoped fields:", {p:len(_DISPLAY_SNAPSHOT_KEYS[p]) for p in ("cdu","eng","fuel","fctl")})


def check_availability_delta_pixels():
    # Synthetic transitions test drawing mechanics, not all-phase acceptance.
    from PIL import ImageChops
    import render_pfp_frame_png as emulator
    from muslimsim.devices import systems_renderer_toliss as systems
    cold={"fctl_aileron_l":-.8,"fctl_aileron_l_available":0,
          "fctl_rudder":.8,"fctl_rudder_available":0,
          "fctl_trim_powered":0,"fctl_pitch_trim_deg":0,
          "fctl_spoiler_1":0,"fctl_spoiler_status_1":2,
          "eng_oilpress_0":math.nan,"eng_oiltemp_0":math.nan,
          "door_pax_0":0,"door_slide_0":0}
    ready=cold | {"fctl_aileron_l":.6,"fctl_aileron_l_available":1,
                  "fctl_rudder":-.7,"fctl_rudder_available":1,
                  "fctl_trim_powered":1,"fctl_pitch_trim_deg":1.2,
                  "fctl_spoiler_1":.7,"fctl_spoiler_status_1":1,
                  "eng_oilpress_0":51,"eng_oiltemp_0":88,
                  "door_pax_0":1,"door_slide_0":1}
    for page in ("fctl","eng","door"):
        delta,full=emulator.PfpFrame(),emulator.PfpFrame()
        systems.draw_live_toliss_system_page(delta,page,cold)
        systems.draw_live_toliss_system_page(delta,page,ready)
        systems.draw_live_toliss_system_page(full,page,ready)
        assert ImageChops.difference(delta.image,full.image).getbbox() is None,page
        assert not systems.draw_live_toliss_system_page(delta,page,ready)


if __name__ == "__main__":
    check_telemetry_contract()
    check_worker_transitions()
    check_page_scoped_snapshots()
    check_availability_delta_pixels()
    print("BUG-41/53: typed fields, exact BLEED conversions, source validity, no sample fallbacks and both DU startup/power paths passed.")
