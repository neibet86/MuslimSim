"""BUG-42/53: requested WHEEL details, BLEED topology and native APU state."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from muslimsim.devices import toliss_ecam_synoptics as art
from muslimsim.devices import toliss_ecam_telemetry as telemetry
from muslimsim.devices import systems_renderer_toliss as systems
from muslimsim.devices.pfp_renderer import _OpRecorder
from test_toliss_ecam_reference import Capture
from watch_toliss_bleed_valves import classify, NAMES


def check_details():
    degree = Capture()
    art.text(degree, 100, 100, "°C", art.CYAN)
    assert degree.labels == [("C", art.CYAN)], "Never send Unicode to ASCII LCD text"
    import render_pfp_frame_png as degree_emulator
    glyph = degree_emulator.PfpFrame()
    art.text(glyph, 100, 100, "°C", art.CYAN)
    assert glyph.image.getpixel((104,101))[:3] == art.CYAN
    assert glyph.image.getpixel((103,103))[:3] == art.CYAN
    assert glyph.image.getpixel((105,103))[:3] != art.CYAN, "Degree ring must be hollow"
    ground={"hyd_press":[0,0,0],"hyd_altn_brake":1,"hyd_brake_accu":1,
            "wheel_antiskid":1,"wheel_nws_avail":0}
    values=telemetry.values("wheel",ground) | {"wheel_nws_avail":0,
        "wheel_gear_n":2,"wheel_gear_l":2,"wheel_gear_r":2}
    frame=Capture()
    systems.draw_toliss_system_frame(frame,"wheel",values)
    assert {"WHEEL_CAPITAL_W","WHEEL_DOWN_TRIANGLE_N","WHEEL_DOWN_TRIANGLE_L",
            "WHEEL_DOWN_TRIANGLE_R","WHEEL_NWS_LEGEND","WHEEL_BRAKING_LEGENDS",
            "WHEEL_ACCU_ONLY","WHEEL_AUTO_BRK"} <= frame.features
    for label in ("N/W STEERING","ANTI SKID","NORM BRK","ALTN BRK","AUTO BRK"):
        assert (label,art.AMBER) in frame.labels,label
    assert ("ACCU ONLY",art.GREEN) in frame.labels
    normal=telemetry.values("wheel",ground | {"hyd_press":[3000,3000,3000],"hyd_altn_brake":0})
    normal.update(wheel_nws_avail=1,wheel_gear_n=0,wheel_gear_l=0,wheel_gear_r=0)
    ready=Capture()
    systems.draw_toliss_system_frame(ready,"wheel",normal)
    assert "WHEEL_ACCU_ONLY" not in ready.features and "WHEEL_NWS_LEGEND" not in ready.features
    assert not any(f.startswith("WHEEL_DOWN_TRIANGLE") for f in ready.features)
    closed={"bleed_ind_1":0,"bleed_ind_2":0,"bleed_hp_1":0,"bleed_hp_2":0,
            "bleed_apu_ind":0,"bleed_xbleed_ind":0,
            "bleed_pack_pointer_1":.5,"bleed_pack_pointer_2":.5,
            "bleed_pack_flow_1":.5,"bleed_pack_flow_2":.5,
            "bleed_pack_switch_1":0,"bleed_pack_switch_2":0}
    off,on=Capture(),Capture()
    systems.draw_toliss_system_frame(off,"bleed",closed)
    systems.draw_toliss_system_frame(on,"bleed",closed | {"bleed_ind_1":1})
    assert {"BLEED_FOUR_PACK_ARCS","BLEED_CROSS_MANIFOLD",
            "BLEED_GND_MARKER","BLEED_XBLEED_VERTICAL"} <= off.features
    assert not any(f.startswith("BLEED_IP_HP_CONNECTED") for f in off.features)
    assert "BLEED_IP_HP_CONNECTED_1" in on.features
    assert "BLEED_IP_HP_CONNECTED_2" not in on.features
    # Isolated valve rotates from the actual indication, not a switch request.
    a,b=_OpRecorder(),_OpRecorder()
    systems.draw_toliss_system_frame(a,"bleed",closed)
    systems.draw_toliss_system_frame(b,"bleed",closed | {"bleed_xbleed_ind":1})
    assert a.ops != b.ops
    from PIL import ImageChops
    import render_pfp_frame_png as emulator
    ground_frame=emulator.PfpFrame()
    systems.draw_toliss_system_frame(ground_frame,"bleed",closed | {
        "bleed_press_l":0,"bleed_press_r":0,
    })
    assert ground_frame.image.getpixel((250,54))[:3] == art.GREEN
    assert ground_frame.image.getpixel((250,223))[:3] == art.BLACK
    assert ground_frame.image.getpixel((156,230))[:3] == art.AMBER

    # Native A321 APU-only state: APU supplies both sides through an open
    # horizontal X BLEED valve, while both stopped-engine branches remain
    # amber, horizontal at IP, vertical at HP and physically disconnected.
    apu_only=closed | {
        "bleed_apu_ind":1,"bleed_xbleed_ind":1,
        "bleed_pack_switch_1":1,"bleed_pack_switch_2":1,
        "bleed_pack_temp_1":5,"bleed_pack_temp_2":5,
        "bleed_pack_outlet_1":210,"bleed_pack_outlet_2":210,
        "bleed_pack_pointer_1":.45,"bleed_pack_pointer_2":.45,
        "bleed_pack_flow_1":1,"bleed_pack_flow_2":1,
        "bleed_press_l":37,"bleed_press_r":36,
        "bleed_temp_1":190,"bleed_temp_2":190,
    }
    apu_capture=Capture()
    systems.draw_toliss_system_frame(apu_capture,"bleed",apu_only)
    assert {"BLEED_CROSS_MANIFOLD","BLEED_GND_MARKER","BLEED_APU_BRANCH",
            "BLEED_APU_VALVE_VERTICAL","BLEED_XBLEED_HORIZONTAL",
            "BLEED_IP_HORIZONTAL_1","BLEED_IP_HORIZONTAL_2",
            "BLEED_HP_VERTICAL_1","BLEED_HP_VERTICAL_2"} <= apu_capture.features
    assert not any(f.startswith("BLEED_IP_HP_CONNECTED") for f in apu_capture.features)
    assert ("APU",art.WHITE) in apu_capture.labels
    assert ("1",art.AMBER) in apu_capture.labels and ("2",art.AMBER) in apu_capture.labels
    assert ("37",art.GREEN) in apu_capture.labels and ("36",art.GREEN) in apu_capture.labels
    apu_frame=emulator.PfpFrame()
    systems.draw_toliss_system_frame(apu_frame,"bleed",apu_only)
    assert apu_frame.image.getpixel((250,223))[:3] == art.GREEN
    assert apu_frame.image.getpixel((430,223))[:3] == art.GREEN
    assert apu_frame.image.getpixel((320,240))[:3] == art.GREEN
    assert apu_frame.image.getpixel((156,315))[:3] == art.GREEN
    assert apu_frame.image.getpixel((156,370))[:3] == art.AMBER

    # With both engines supplying and X BLEED closed, each engine lower branch
    # is green independently and the APU branch disappears.
    engines_only=apu_only | {
        "bleed_apu_ind":0,"bleed_xbleed_ind":0,
        "bleed_ind_1":1,"bleed_ind_2":1,
        "bleed_press_l":51,"bleed_press_r":51,
    }
    engines_capture=Capture()
    systems.draw_toliss_system_frame(engines_capture,"bleed",engines_only)
    assert "BLEED_APU_BRANCH" not in engines_capture.features
    assert {"BLEED_XBLEED_VERTICAL","BLEED_IP_VERTICAL_1","BLEED_IP_VERTICAL_2",
            "BLEED_IP_HP_CONNECTED_1","BLEED_IP_HP_CONNECTED_2"} <= engines_capture.features
    assert ("1",art.GREEN) in engines_capture.labels and ("2",art.GREEN) in engines_capture.labels
    asymmetric=emulator.PfpFrame()
    systems.draw_toliss_system_frame(asymmetric,"bleed",engines_only | {"bleed_ind_2":0})
    # X BLEED shut: the native page omits the cross-manifold, while each
    # vertical source branch retains its own operative/closed colour.
    assert asymmetric.image.getpixel((250,223))[:3] == art.BLACK
    assert asymmetric.image.getpixel((430,223))[:3] == art.BLACK
    assert asymmetric.image.getpixel((156,315))[:3] == art.GREEN
    assert asymmetric.image.getpixel((483,315))[:3] == art.AMBER
    failed=Capture()
    systems.draw_toliss_system_frame(failed,"bleed",engines_only | {
        "bleed_ind_1":2,"bleed_ind_2":3,"bleed_hp_1":2,"bleed_hp_2":3,
    })
    assert not any(f.startswith("BLEED_IP_HP_CONNECTED") for f in failed.features)
    assert {"BLEED_IP_HORIZONTAL_1","BLEED_IP_HORIZONTAL_2",
            "BLEED_HP_VERTICAL_1","BLEED_HP_VERTICAL_2"} <= failed.features
    assert ("1",art.AMBER) in failed.labels and ("2",art.AMBER) in failed.labels
    failed_frame=emulator.PfpFrame()
    systems.draw_toliss_system_frame(failed_frame,"bleed",engines_only | {
        "bleed_ind_1":2,"bleed_ind_2":3,"bleed_hp_1":2,"bleed_hp_2":3,
    })
    assert failed_frame.image.getpixel((156,340))[:3] == art.AMBER
    assert failed_frame.image.getpixel((214,360))[:3] == art.AMBER

    fuel=emulator.PfpFrame()
    systems.draw_toliss_system_frame(fuel,"fuel",{"fuel_pump_code_5":3})
    # BUG-45: current A321 code 3 is a running full-wing pump, not stale LO.
    for point in ((476,207),(505,207),(476,236),(505,236)):
        assert fuel.image.getpixel(point)[:3] == art.GREEN,point
    assert fuel.image.getpixel((491,222))[:3] == art.GREEN
    for page,initial,changed in (("wheel",values,normal),("bleed",apu_only,engines_only)):
        delta,full=emulator.PfpFrame(),emulator.PfpFrame()
        systems.draw_live_toliss_system_page(delta,page,initial)
        systems.draw_live_toliss_system_page(delta,page,changed)
        systems.draw_live_toliss_system_page(full,page,changed)
        assert ImageChops.difference(delta.image,full.image).getbbox() is None,page
        assert not systems.draw_live_toliss_system_page(delta,page,changed)
    # Nine ASCII-independent degree rings add 54 operations (731 -> 785).
    assert apu_frame.primitives <= 800, (
        f"BLEED full-frame primitive budget regressed to {apu_frame.primitives}"
    )
    previous={name:0 for name in NAMES}
    changed=previous | {"AirbusFBW/XBleedInd":1}
    event=classify(previous,changed)
    assert event["isolated_candidate"] == "AirbusFBW/XBleedInd" and not event["mapping_verified"]
    assert classify(previous,changed | {"AirbusFBW/APUBleedInd":1})["isolated_candidate"] is None
    assert classify(previous,previous | {"AirbusFBW/XBleedSwitch":1})["isolated_candidate"] is None


if __name__=="__main__":
    check_details()
    print("BUG-42/53: WHEEL details plus exact APU/crossbleed/engine BLEED topology, failure colours and delta pixels passed.")
