"""Native-glyph review from a recorded telemetry snapshot, or explicit samples.

No-argument runs cannot silently generate picture-derived demonstration data.
--samples is ONLY an artwork fixture, never a live simulator verification.
"""
from pathlib import Path
import sys
import argparse
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
import render_pfp_frame_png as emulator
from render_toliss_display_previews import _system_values
from muslimsim.devices import systems_renderer_toliss as systems
from muslimsim.devices import toliss_ecam_synoptics as artwork


def sample_values():
    v = _system_values()
    v.update(ecam_tat=-21, ecam_sat=-48, ecam_isa=7, ecam_gw=75800,
             ecam_utc=51*60, press_delta_p=7.9, press_ldg_elev=2180,
             press_cabin_alt=7430, press_cabin_vs=0, press_outflow=.12,
             press_mode=0, status_normal=True, cond_cockpit_temp=22,
             cond_hot_air=1, cond_cargo_hot_air=1, bleed_ram=0,
             fuel_flow_kg_min_0=19.5, fuel_flow_kg_min_1=19.5,
             fuel_qty_ctr=0, fuel_fob=6480, fuel_qty_l=3180, fuel_qty_r=3300,
             fuel_crossfeed=0, fuel_temp_l=3, fuel_temp_r=3,
             fctl_pitch_trim_deg=-.3, fctl_aileron_l=0, fctl_aileron_r=0,
             fctl_elevator_l=-.4, fctl_elevator_r=-.4, fctl_rudder=0,
             door_oxy_psi_1=1850, door_oxy_psi_2=1850,
             apu_n_pct=None, apu_egt=None, apu_bleed_ind=1,
             apu_bleed_press=36.5,
             bleed_xbleed_ind=1, bleed_intercon=3,
             bleed_ground_hp=0, bleed_ground_lp=0,
             bleed_pack_switch_1=1, bleed_pack_switch_2=1,
             bleed_pack_pointer_1=.285, bleed_pack_pointer_2=.285,
             bleed_pack_flow_1=1, bleed_pack_flow_2=1,
             bleed_ind_1=0, bleed_ind_2=0, bleed_hp_1=0, bleed_hp_2=0)
    for i in (0,1):
        v.update({f"eng_used_{i}":2120-40*i, f"eng_oil_qt_{i}":14-.5*i,
                  f"eng_oilpress_{i}":50, f"eng_oiltemp_{i}":90,
                  f"eng_vib_{i}":.3+.1*i, f"eng_vib_n2_{i}":.6+.1*i,
                  f"elec_bat_v_{i}":27, f"elec_bat_a_{i}":1-i})
    for i in (1,2):
        for key,value in {"pack_temp":5,"pack_outlet":210,"temp":190}.items():
            v[f"bleed_{key}_{i}"]=value
        for key,value in {"tr_v":29,"tr_a":81 if i==1 else 44,"gen_load":39 if i==1 else 16,"gen_v":115,"gen_hz":400,"idg_temp":106}.items():
            v[f"elec_{key}_{i}"]=value
    v.update(bleed_press_l=37,bleed_press_r=36)
    for key in ("dc_bat","dc_ess","ac_ess"):
        v["elec_"+key]=1
    for name in ("ckpt","fwd","aft"):
        v["cond_duct_"+name]=21 if name=="ckpt" else 13
    for key in tuple(v):
        if key.startswith("door_") and "psi" not in key:
            v[key]=0
    for key in ("exit_l","exit_r","aft_l","aft_r"):
        v["door_"+key]=0
    for i in range(1,11):
        v[f"fctl_spoiler_{i}"]=0
        v[f"wheel_spoiler_{i}"]=0
    for i in range(6):
        v[f"wheel_tire_{i}"]=170 if i<2 else 210
    for key in ("lo","li","ri","ro"):
        v[f"wheel_brake_temp_{key}"]=60 if key.startswith("l") else 50
    return v


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--snapshot",type=Path)
    choice.add_argument("--samples",action="store_true")
    args=parser.parse_args()
    page_values={}
    if args.snapshot:
        from test_toliss_displays import _load_bridge
        from muslimsim.devices.mcdu_bb36_toliss_paths import TOLISS_MCDU_SECONDARY_DATAREFS
        bridge=_load_bridge()
        captured=json.loads(args.snapshot.read_text(encoding="utf-8"))
        raw={key:captured["values"][ref]["value"]
             for group in TOLISS_MCDU_SECONDARY_DATAREFS.values() for key,ref in group.items()
             if ref in captured["values"] and "value" in captured["values"][ref]}
        for page in artwork.PAGE_TITLES:
            page_values[page]={**bridge._toliss_ecam_common_values(raw),
                               **bridge._toliss_ecam_system_values(page,raw),
                               **artwork.reference_values(page,raw,bridge._toliss_secondary_element)}
        label="RECORDED TELEMETRY " + captured["captured_utc"][:19]
        out=ROOT/"PNG"/"toliss-ecam-telemetry"/args.snapshot.stem
    else:
        page_values={page:sample_values() for page in artwork.PAGE_TITLES}
        label="OFFLINE SAMPLE — NOT TELEMETRY"
        out=ROOT/"PNG"/"toliss-ecam-reference"
    out.mkdir(parents=True,exist_ok=True)
    sheet=Image.new("RGB",(1280,4*505),(18,20,24))
    # Three sheets at full LCD resolution avoid reducing the review glyphs.
    for index,page in enumerate(artwork.PAGE_TITLES):
        frame=emulator.PfpFrame()
        systems.draw_toliss_system_frame(frame,page,page_values[page])
        frame.image.save(out/f"{page}.png")
        x,y=(index%2)*640,((index//2)%2)*505
        if index%4==0:
            sheet=Image.new("RGB",(1280,1010),(18,20,24))
        sheet.paste(frame.image,(x,y+25))
        ImageDraw.Draw(sheet).text((x+20,y+5),f"{page.upper()} — {label}",fill="white")
        if index%4==3:
            sheet.save(out/f"review-{index//4+1}.png")
        print(page,frame.primitives)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
